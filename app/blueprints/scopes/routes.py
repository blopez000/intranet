# app/blueprints/scopes/routes.py  (CORREGIDO A NUEVOS MODELOS)

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.models import User, Recinto, Cuenta, UserRecinto, RecintoCuenta

from . import bp

def _as_bool(val) -> bool:
    return str(val).lower() in ("1","true","on","yes","si","sí")

def _q(s): 
    return f"%{s.strip()}%" if s else None

def _require_nivel1():
    # ajusta esta política a tu app (ej.: is_admin o nivel_acceso==1)
    if getattr(current_user, "is_admin", False):
        return
    if getattr(current_user, "nivel_acceso", 3) != 1:
        abort(403)

@bp.get("/")
@login_required
def index():
    _require_nivel1()
    q_user = request.args.get("q_user")
    q_rec  = request.args.get("q_rec")
    q_cue  = request.args.get("q_cue")
    only_active = request.args.get("only_active", "1") == "1"

    # Construimos una grilla a nivel usuario–recinto–cuenta (cuentas derivadas del recinto)
    query = (db.session.query(
                User.id.label("user_id"),
                User.email.label("user_email"),
                User.name.label("user_name"),
                Recinto.id.label("recinto_id"),
                Recinto.name.label("recinto_name"),
                UserRecinto.nivel.label("nivel"),
                UserRecinto.is_active.label("ur_active"),
                Cuenta.code.label("cuenta_code"),
                Cuenta.name.label("cuenta_name"),
                RecintoCuenta.is_active.label("rc_active"),
            )
            .join(UserRecinto, UserRecinto.user_id == User.id)
            .join(Recinto, Recinto.id == UserRecinto.recinto_id)
            .join(RecintoCuenta, RecintoCuenta.recinto_id == Recinto.id)
            .join(Cuenta, Cuenta.id == RecintoCuenta.cuenta_id))

    # Filtros
    if q_user:
        query = query.filter(or_(User.email.ilike(_q(q_user)), User.name.ilike(_q(q_user))))
    if q_rec:
        if q_rec.isdigit():
            query = query.filter(Recinto.id == int(q_rec))
        else:
            query = query.filter(Recinto.name.ilike(_q(q_rec)))
    if q_cue:
        query = query.filter(or_(Cuenta.code.ilike(_q(q_cue)), Cuenta.name.ilike(_q(q_cue))))
    if only_active:
        # Requiere que el vínculo user↔recinto esté activo y el vínculo recinto↔cuenta también
        query = query.filter(UserRecinto.is_active.is_(True), RecintoCuenta.is_active.is_(True), Cuenta.is_active.is_(True))

    rows = (query
            .order_by(User.email.asc(), Recinto.name.asc(), Cuenta.code.asc())
            .limit(600)
            .all())

    users = db.session.query(User).order_by(User.email).limit(500).all()
    recintos = db.session.query(Recinto).order_by(Recinto.name).all()

    # Nota de template:
    # - antes accedías a recintos por Recinto.nombre -> ahora es Recinto.name
    # - antes 'cuenta_area' -> ahora usa 'cuenta_code'/'cuenta_name'
    return render_template(
        "scopes/index.html", 
        rows=rows, users=users, recintos=recintos,
        q_user=q_user or "", q_rec=q_rec or "", q_cue=q_cue or "", only_active=only_active
    )

@bp.post("/create")
@login_required
def create():
    _require_nivel1()
    user_id = request.form.get("user_id", type=int)
    recinto_id = request.form.get("recinto_id", type=int)
    nivel = request.form.get("nivel", type=int) or 1

    if not user_id or not recinto_id:
        flash("Faltan datos (user_id o recinto_id).", "danger")
        return redirect(url_for("scopes.index"))

    ur = db.session.get(UserRecinto, {"user_id": user_id, "recinto_id": recinto_id})
    if ur:
        if not ur.is_active:
            ur.is_active = True
            ur.nivel = nivel
            db.session.commit()
            flash("Asignación reactivada.", "success")
        else:
            ur.nivel = nivel
            db.session.commit()
            flash("La asignación ya existía; nivel actualizado.", "info")
        return redirect(url_for("scopes.index"))

    db.session.add(UserRecinto(user_id=user_id, recinto_id=recinto_id, nivel=nivel, is_active=True))
    db.session.commit()
    flash("Asignación creada.", "success")
    return redirect(url_for("scopes.index"))

@bp.post("/toggle")
@login_required
def toggle():
    _require_nivel1()
    user_id = request.form.get("user_id", type=int)
    recinto_id = request.form.get("recinto_id", type=int)

    ur = db.session.get(UserRecinto, {"user_id": user_id, "recinto_id": recinto_id})
    if not ur:
        flash("Asignación no encontrada.", "warning")
    else:
        ur.is_active = not bool(ur.is_active)
        db.session.commit()
        flash("Estado actualizado.", "success")
    return redirect(url_for("scopes.index"))

@bp.post("/delete")
@login_required
def delete():
    _require_nivel1()
    user_id = request.form.get("user_id", type=int)
    recinto_id = request.form.get("recinto_id", type=int)

    ur = db.session.get(UserRecinto, {"user_id": user_id, "recinto_id": recinto_id})
    if ur:
        db.session.delete(ur)
        db.session.commit()
        flash("Asignación eliminada.", "success")
    else:
        flash("Asignación no encontrada.", "warning")
    return redirect(url_for("scopes.index"))

@bp.get("/cuentas")
@login_required
def cuentas_suggest():
    _require_nivel1()
    recinto_id = request.args.get("recinto_id", type=int)
    if not recinto_id:
        return jsonify([])

    # Sugerimos las cuentas asociadas AL RECINTO vía RecintoCuenta (solo activas)
    rows = (db.session.query(Cuenta.code)
            .join(RecintoCuenta, RecintoCuenta.cuenta_id == Cuenta.id)
            .filter(RecintoCuenta.recinto_id == recinto_id,
                    RecintoCuenta.is_active.is_(True),
                    Cuenta.is_active.is_(True))
            .order_by(Cuenta.code)
            .limit(200)
            .all())
    return jsonify([code for (code,) in rows])
