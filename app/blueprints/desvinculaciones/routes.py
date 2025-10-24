from datetime import datetime
import math
from io import StringIO, BytesIO
import csv
from sqlalchemy import func, desc, text
import pandas as pd
from flask import render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename

from . import bp
from app.extensions import db
from app.models import Desvinculacion, Cuenta, UserRecintoCuenta, UserCuenta  # <-- UserCuenta = user_cuentas
from flask_login import login_required, current_user


# ========================== Utilitarios ==========================
def parse_date(s: str):
    """Acepta dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd; retorna date o None."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _col_distinct(col):
    """Lista ordenada y distinta de una columna (no nulos)."""
    return [
        r[0]
        for r in db.session.query(col)
        .filter(col.isnot(None))
        .distinct()
        .order_by(col.asc())
        .all()
    ]


def _opts_3():
    """Opciones de autocomplete solo para EMPRESA / UNIDAD / CARGO."""
    return (
        _col_distinct(Desvinculacion.EMPRESA),
        _col_distinct(Desvinculacion.UNIDAD_DE_NEGOCIO),
        _col_distinct(Desvinculacion.CARGO),
    )


def _parse_date(s: str | None):
    """Acepta dd-mm-aaaa y yyyy-mm-dd; retorna date o None."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ========================== Permisos ==========================
def _allowed_area_codes_for_user(user) -> set[str]:
    """
    Retorna SIEMPRE un set con los CÓDIGOS de área/cuenta (BAT, BRF, VAS, ...).
    Fuente: user_cuentas (globales). Si no tiene, devuelve set() -> no ve nada.
    """
    rows = (
        db.session.query(Cuenta.code)
        .join(UserCuenta, UserCuenta.cuenta_id == Cuenta.id)
        .filter(UserCuenta.user_id == user.id, UserCuenta.is_active.is_(True))
        .distinct()
        .all()
    )
    codes = {r[0] for r in rows}

    # (Opcional) Si además quieres sumar permisos por recinto-cuenta, descomenta:
    # rc_rows = (
    #     db.session.query(Cuenta.code)
    #     .join(UserRecintoCuenta, UserRecintoCuenta.cuenta_id == Cuenta.id)
    #     .filter(UserRecintoCuenta.user_id == user.id, UserRecintoCuenta.is_active.is_(True))
    #     .distinct()
    #     .all()
    # )
    # codes |= {r[0] for r in rc_rows}

    return codes


# ======================== LISTADO ========================
@bp.get("/")
@login_required
def index():
    per = request.args.get("per", type=int) or 100
    page = max(request.args.get("page", type=int) or 1, 1)
    offset = (page - 1) * per

    # filtros UI
    desde_raw = (request.args.get("desde") or "").strip()
    hasta_raw = (request.args.get("hasta") or "").strip()
    area_raw  = (request.args.get("area")  or "").strip()

    f_desde = _parse_date(desde_raw)
    f_hasta = _parse_date(hasta_raw)

    # === Áreas permitidas para el usuario (códigos tipo BAT/PGC/...) ===
    allowed_areas = _allowed_area_codes_for_user(current_user)
    areas_select = sorted(allowed_areas)  # combo se llena solo con estas

    # Si el usuario no tiene cuentas, devolvemos la página vacía
    if not allowed_areas:
        return render_template(
            "desv/index.html",
            rows=[],
            total=0,
            page=1,
            per=per,
            last_page=1,
            first_item=0,
            last_item=0,
            desde=desde_raw, hasta=hasta_raw, area=area_raw,
            areas=areas_select,
        )

    # base query (solo columnas necesarias para la grilla)
    q = db.session.query(
        Desvinculacion.id.label("id"),
        Desvinculacion.RUT.label("RUT"),
        Desvinculacion.APELLIDOS_NOMBRES.label("APELLIDOS_NOMBRES"),
        Desvinculacion.EMPRESA.label("EMPRESA"),
        Desvinculacion.centro_costo_area.label("UNIDAD_DE_NEGOCIO"),
        Desvinculacion.CARGO.label("CARGO"),
        Desvinculacion.FECHA_CTTO.label("FECHA_CTTO"),
        Desvinculacion.FECHA_TERMINO.label("FECHA_TERMINO"),
        Desvinculacion.CAUSA_EGRESO.label("CAUSA_EGRESO"),
    )

    # alcance por cuentas (SIEMPRE se restringe al set permitido)
    q = q.filter(Desvinculacion.centro_costo_area.in_(allowed_areas))

    # filtros fecha
    if f_desde:
        q = q.filter(Desvinculacion.FECHA_TERMINO >= f_desde)
    if f_hasta:
        q = q.filter(Desvinculacion.FECHA_TERMINO <= f_hasta)

    # filtro de área UI: solo aceptamos si está en su set, si no => 0 filas
    if area_raw:
        if area_raw in allowed_areas:
            q = q.filter(Desvinculacion.centro_costo_area == area_raw)
        else:
            q = q.filter(text("1=0"))

    # total/paginación
    total = db.session.query(func.count()).select_from(q.subquery()).scalar()
    last_page = max(math.ceil(total / per), 1)
    first_item = 0 if total == 0 else offset + 1
    last_item  = min(offset + per, total)

    rows = (
        q.order_by(desc(Desvinculacion.id))
         .offset(offset)
         .limit(per)
         .all()
    )

    return render_template(
        "desv/index.html",
        rows=rows, total=total, page=page, per=per, last_page=last_page,
        first_item=first_item, last_item=last_item,
        desde=desde_raw, hasta=hasta_raw, area=area_raw,
        areas=areas_select,
    )


# ======================== EXPORTACIÓN ========================
@bp.get("/export")
@login_required
def export_excel():
    desde_raw = (request.args.get("desde") or "").strip()
    hasta_raw = (request.args.get("hasta") or "").strip()
    area_raw  = (request.args.get("area")  or "").strip()

    f_desde = _parse_date(desde_raw)
    f_hasta = _parse_date(hasta_raw)

    # Alcance: cuentas permitidas
    allowed_areas = _allowed_area_codes_for_user(current_user)
    if not allowed_areas:
        # Export vacío pero válido
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            pd.DataFrame([]).to_excel(writer, index=False, sheet_name="Desvinculaciones")
        buf.seek(0)
        return send_file(
            buf,
            as_attachment=True,
            download_name="desvinculaciones.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # Query completa (sin límite) con alias pensados para Excel
    q = db.session.query(
        Desvinculacion.id.label("ID"),
        Desvinculacion.RUT.label("RUT"),
        Desvinculacion.APELLIDOS_NOMBRES.label("NOMBRE"),
        Desvinculacion.EMPRESA.label("EMPRESA"),
        Desvinculacion.centro_costo_area.label("AREA"),
        Desvinculacion.CARGO.label("CARGO"),
        Desvinculacion.FECHA_CTTO.label("F_CONTRATO"),
        Desvinculacion.FECHA_TERMINO.label("F_TERMINO"),
        Desvinculacion.CAUSA_EGRESO.label("CAUSA"),
    ).filter(Desvinculacion.centro_costo_area.in_(allowed_areas))

    if f_desde:
        q = q.filter(Desvinculacion.FECHA_TERMINO >= f_desde)
    if f_hasta:
        q = q.filter(Desvinculacion.FECHA_TERMINO <= f_hasta)

    if area_raw:
        # Solo aceptamos áreas permitidas; si no, export vacío
        if area_raw in allowed_areas:
            q = q.filter(Desvinculacion.centro_costo_area == area_raw)
        else:
            q = q.filter(text("1=0"))

    q = q.order_by(desc(Desvinculacion.id))
    data = [dict(row._mapping) for row in q.all()]

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(data).to_excel(writer, index=False, sheet_name="Desvinculaciones")
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name="desvinculaciones.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ========================== CRUD + Carga masiva (igual que tenías) ==========================
@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        f = request.form
        obj = Desvinculacion(
            RUT=f.get("RUT") or None,
            UNIDAD_DE_NEGOCIO=f.get("UNIDAD_DE_NEGOCIO") or None,
            EMPRESA=f.get("EMPRESA") or None,
            APELLIDOS_NOMBRES=f.get("APELLIDOS_NOMBRES") or None,
            CARGO=f.get("CARGO") or None,
            FECHA_CTTO=parse_date(f.get("FECHA_CTTO") or f.get("FECHA_CTTO_txt")),
            CAUSA_EGRESO=f.get("CAUSA_EGRESO") or None,
            FECHA_TERMINO=parse_date(f.get("FECHA_TERMINO") or f.get("FECHA_TERMINO_txt")),
            MOTIVO_SALIDA=f.get("MOTIVO_SALIDA") or None,
            Contrato=f.get("Contrato") or None,
            fecha_contrato=f.get("fecha_contrato") or None,
        )
        if not obj.RUT:
            flash("El RUT es obligatorio.", "warning")
            return redirect(url_for("desvinculaciones.create"))

        try:
            db.session.add(obj)
            db.session.commit()
            flash("✅ Desvinculación creada.", "success")
            return redirect(url_for("desvinculaciones.index"))
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error al guardar: {e}", "danger")
            return redirect(url_for("desvinculaciones.create"))

    empresas_opts, unidades_opts, cargos_opts = _opts_3()
    return render_template(
        "desv/form.html",
        obj=None,
        empresas_opts=empresas_opts,
        unidades_opts=unidades_opts,
        cargos_opts=cargos_opts,
    )


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
def edit(id):
    obj = Desvinculacion.query.get_or_404(id)

    if request.method == "POST":
        f = request.form
        obj.RUT = f.get("RUT") or None
        obj.UNIDAD_DE_NEGOCIO = f.get("UNIDAD_DE_NEGOCIO") or None
        obj.EMPRESA = f.get("EMPRESA") or None
        obj.APELLIDOS_NOMBRES = f.get("APELLIDOS_NOMBRES") or None
        obj.CARGO = f.get("CARGO") or None
        obj.FECHA_CTTO = parse_date(f.get("FECHA_CTTO") or f.get("FECHA_CTTO_txt"))
        obj.CAUSA_EGRESO = f.get("CAUSA_EGRESO") or None
        obj.FECHA_TERMINO = parse_date(f.get("FECHA_TERMINO") or f.get("FECHA_TERMINO_txt"))
        obj.MOTIVO_SALIDA = f.get("MOTIVO_SALIDA") or None
        obj.Contrato = f.get("Contrato") or None
        obj.fecha_contrato = f.get("fecha_contrato") or None

        try:
            db.session.commit()
            flash("✅ Registro actualizado.", "success")
            return redirect(url_for("desvinculaciones.index"))
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error al actualizar: {e}", "danger")
            return redirect(url_for("desvinculaciones.edit", id=id))

    empresas_opts, unidades_opts, cargos_opts = _opts_3()
    return render_template(
        "desv/form.html",
        obj=obj,
        empresas_opts=empresas_opts,
        unidades_opts=unidades_opts,
        cargos_opts=cargos_opts,
    )


@bp.post("/<int:id>/delete")
def delete(id):
    obj = Desvinculacion.query.get_or_404(id)
    try:
        db.session.delete(obj)
        db.session.commit()
        flash("🗑️ Registro eliminado.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ No se pudo eliminar: {e}", "danger")
    return redirect(url_for("desvinculaciones.index"))


@bp.get("/cargar")
def gestionar_desv():
    empresas_opts, unidades_opts, cargos_opts = _opts_3()
    return render_template(
        "desv/gestionar.html",
        empresas_opts=empresas_opts,
        unidades_opts=unidades_opts,
        cargos_opts=cargos_opts,
    )


REQUIRED_HEADERS = [
    "RUT",
    "UNIDAD_DE_NEGOCIO",
    "EMPRESA",
    "APELLIDOS_NOMBRES",
    "CARGO",
    "FECHA_CTTO",
    "CAUSA_EGRESO",
    "FECHA_TERMINO",
    "MOTIVO_SALIDA",
    "Contrato",
    "fecha_contrato",
]


@bp.route("/carga-masiva", methods=["GET", "POST"])
def desv_bulk():
    if request.method == "GET":
        return render_template("desv/bulk_upload.html", result=None, preview=None, errors=None)

    file = request.files.get("file")
    confirm = request.form.get("confirm") == "1"

    if not file or file.filename == "":
        flash("Selecciona un archivo CSV.", "warning")
        return redirect(url_for("desvinculaciones.desv_bulk"))

    filename = secure_filename(file.filename)
    raw = file.read()
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        text = raw.decode("latin1")

    reader = csv.DictReader(StringIO(text))

    headers = [h.strip() for h in (reader.fieldnames or [])]
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing:
        msg = f"Faltan columnas obligatorias: {', '.join(missing)}"
        flash(msg, "danger")
        return render_template("desv/bulk_upload.html", result=None, preview=None, errors=[msg])

    rows_ok, errors = [], []
    rownum = 1
    for row in reader:
        rownum += 1
        rec = {k: (row.get(k, "") or "").strip() for k in REQUIRED_HEADERS}

        if not rec["RUT"]:
            errors.append(f"Fila {rownum}: RUT es obligatorio.")
            continue

        f_ctto = parse_date(rec["FECHA_CTTO"])
        if rec["FECHA_CTTO"] and not f_ctto:
            errors.append(f"Fila {rownum}: FECHA_CTTO inválida '{rec['FECHA_CTTO']}'.")
            continue

        f_term = parse_date(rec["FECHA_TERMINO"])
        if rec["FECHA_TERMINO"] and not f_term:
            errors.append(f"Fila {rownum}: FECHA_TERMINO inválida '{rec['FECHA_TERMINO']}'.")
            continue

        obj = Desvinculacion(
            RUT=rec["RUT"],
            UNIDAD_DE_NEGOCIO=rec["UNIDAD_DE_NEGOCIO"] or None,
            EMPRESA=rec["EMPRESA"] or None,
            APELLIDOS_NOMBRES=rec["APELLIDOS_NOMBRES"] or None,
            CARGO=rec["CARGO"] or None,
            FECHA_CTTO=f_ctto,
            CAUSA_EGRESO=rec["CAUSA_EGRESO"] or None,
            FECHA_TERMINO=f_term,
            MOTIVO_SALIDA=rec["MOTIVO_SALIDA"] or None,
            Contrato=rec["Contrato"] or None,
            fecha_contrato=rec["fecha_contrato"] or None,
        )
        rows_ok.append(obj)

    if confirm:
        if errors:
            flash("No se puede confirmar: hay errores en el archivo.", "danger")
        else:
            try:
                db.session.bulk_save_objects(rows_ok)
                db.session.commit()
                flash(f"Carga completada: {len(rows_ok)} registro(s) insertado(s).", "success")
                return redirect(url_for("desvinculaciones.index"))
            except Exception as e:
                db.session.rollback()
                errors.append(f"Error de base de datos: {e}")
                flash("Fallo la inserción. Revisa los errores.", "danger")

    preview = []
    for o in rows_ok[:25]:
        preview.append(
            {
                "RUT": o.RUT,
                "NOMBRE": o.APELLIDOS_NOMBRES,
                "EMPRESA": o.EMPRESA,
                "AREA": o.UNIDAD_DE_NEGOCIO,
                "CARGO": o.CARGO,
                "FECHA_CTTO": o.FECHA_CTTO.strftime("%d/%m/%Y") if o.FECHA_CTTO else "",
                "FECHA_TERMINO": o.FECHA_TERMINO.strftime("%d/%m/%Y") if o.FECHA_TERMINO else "",
            }
        )

    result = {
        "filename": filename,
        "valid_count": len(rows_ok),
        "error_count": len(errors),
        "warnings": [],
    }
    return render_template("desv/bulk_upload.html", result=result, preview=preview, errors=errors)


@bp.get("/carga-masiva/plantilla")
def desv_bulk_plantilla():
    out = StringIO()
    w = csv.writer(out)
    w.writerow(REQUIRED_HEADERS)
    w.writerow(
        [
            "12.345.678-9",
            "P&G VAS",
            "ID LOGISTICS",
            "Pérez Juan",
            "OPERARIO",
            "01/02/2024",
            "RENUNCIA",
            "30/09/2025",
            "Oferta externa",
            "Indefinido",
            "Texto opcional",
        ]
    )
    mem = BytesIO(out.getvalue().encode("utf-8-sig"))
    mem.seek(0)
    return send_file(
        mem,
        as_attachment=True,
        download_name="plantilla_desvinculaciones.csv",
        mimetype="text/csv",
    )
