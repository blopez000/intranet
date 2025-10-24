# app/blueprints/admin/routes.py
from __future__ import annotations
from functools import wraps

from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import text

from app.extensions import db
from app.models import (
    User, Role, Recinto, Cuenta,
    UserRecinto, RecintoCuenta, SuperAdmin, UserCuenta
)
from . import bp  # blueprint definido en __init__.py


# ----------------------------- utilidades -----------------------------
def superadmin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        is_sa = False
        if current_user and getattr(current_user, "id", None):
            is_sa = db.session.query(SuperAdmin).filter_by(user_id=current_user.id).first() is not None
        if not is_sa:
            abort(403)
        return view(*args, **kwargs)
    return wrapped

def _redirect_manage(uid: int):
    return redirect(url_for("admin.user_manage", uid=uid))

def _roles_from_db():
    return db.session.query(Role).order_by(Role.level.asc(), Role.name.asc()).all()

def _niveles_from_db():
    return [1, 2, 3]

def _recintos_for_user(uid: int):
    return db.session.execute(text("""
        SELECT r.id, r.code, r.name, ur.nivel, ur.desde, ur.hasta, ur.is_active
        FROM user_recintos ur
        JOIN recintos r ON r.id = ur.recinto_id
        WHERE ur.user_id = :uid
        ORDER BY r.name
    """), {"uid": uid}).mappings().all()

def _recintos_catalog_with_cuentas():
    return db.session.execute(text("""
        SELECT r.id, r.code, r.name,
               GROUP_CONCAT(DISTINCT c.code ORDER BY c.code SEPARATOR ', ') AS cuentas_codes
        FROM recintos r
        LEFT JOIN recinto_cuentas rc ON rc.recinto_id = r.id AND rc.is_active = 1
        LEFT JOIN cuentas c         ON c.id = rc.cuenta_id AND c.is_active  = 1
        WHERE r.is_active = 1
        GROUP BY r.id, r.code, r.name
        ORDER BY r.name
    """)).mappings().all()

def _cuentas_universo_por_recinto(rid: int):
    return db.session.execute(text("""
        SELECT c.id, c.code, c.name
        FROM recinto_cuentas rc
        JOIN cuentas c ON c.id = rc.cuenta_id
        WHERE rc.recinto_id = :rid
          AND rc.is_active  = 1
          AND c.is_active   = 1
        ORDER BY c.code
    """), {"rid": rid}).mappings().all()

def _user_cuentas_activas(uid: int) -> set[int]:
    rows = db.session.execute(text("""
        SELECT cuenta_id
        FROM user_cuentas
        WHERE user_id = :uid AND is_active = 1
    """), {"uid": uid}).scalars().all()
    return set(rows)

def _cuentas_marcadas_por_recinto(uid: int) -> dict[int, set[int]]:
    rows = db.session.execute(text("""
        SELECT rc.recinto_id, uc.cuenta_id
        FROM user_cuentas uc
        JOIN recinto_cuentas rc
          ON rc.cuenta_id = uc.cuenta_id AND rc.is_active = 1
        WHERE uc.user_id = :uid AND uc.is_active = 1
        ORDER BY rc.recinto_id, uc.cuenta_id
    """), {"uid": uid}).mappings().all()
    out = {}
    for r in rows:
        out.setdefault(r["recinto_id"], set()).add(r["cuenta_id"])
    return out

def _usuario_tiene_recinto(uid: int, rid: int) -> bool:
    ok = db.session.execute(text("""
        SELECT 1
        FROM user_recintos ur
        WHERE ur.user_id = :uid
          AND ur.recinto_id = :rid
          AND ur.is_active = 1
          AND (ur.desde IS NULL OR ur.desde <= CURRENT_DATE)
          AND (ur.hasta IS NULL OR ur.hasta >= CURRENT_DATE)
        LIMIT 1
    """), {"uid": uid, "rid": rid}).first()
    return bool(ok)

def _cuentas_universo_global():
    return db.session.execute(text("""
        SELECT id, code, name
        FROM cuentas
        WHERE is_active = 1
        ORDER BY code
    """)).mappings().all()


# ============================== LISTA ==============================
@bp.get("/users")
@login_required
@superadmin_required
def users_list():
    q = request.args.get("q", "", type=str).strip()
    base_sql = """
        SELECT u.id, u.email, u.name, u.is_active, r.name AS role_name
        FROM users u
        JOIN roles r ON r.id = u.role_id
    """
    params = {}
    if q:
        base_sql += " WHERE u.email LIKE :q OR u.name LIKE :q "
        params["q"] = f"%{q}%"
    base_sql += " ORDER BY u.name ASC"
    rows = db.session.execute(text(base_sql), params).mappings().all()
    return render_template("admin/users_list.html", users=rows, q=q)


# ============================== CREAR ==============================
@bp.route("/users/new", methods=["GET", "POST"])
@login_required
@superadmin_required
def users_create():
    if request.method == "POST":
        name     = (request.form.get("name") or "").strip()
        email    = (request.form.get("email") or "").strip().lower()
        role_id  = request.form.get("role_id", type=int)
        is_active = (request.form.get("is_active") == "on")

        if not email or not role_id:
            flash("Email y rol son obligatorios.", "warning")
            return redirect(url_for("admin.users_create"))

        exists = db.session.execute(text("SELECT 1 FROM users WHERE email=:e LIMIT 1"),
                                    {"e": email}).first()
        if exists:
            flash("Ya existe un usuario con ese email.", "warning")
            return redirect(url_for("admin.users_create"))

        u = User(email=email, name=name or email, role_id=role_id, is_active=is_active)
        pwd = (request.form.get("password") or "").strip()
        if pwd and hasattr(u, "set_password"):
            u.set_password(pwd)
        db.session.add(u)
        db.session.commit()
        flash("Usuario creado correctamente.", "success")
        return _redirect_manage(u.id)

    roles = _roles_from_db()
    return render_template("admin/user_create.html", roles=roles)


# ============================== GESTIONAR (ÚNICA) ==============================
@bp.get("/users/<int:uid>/manage")
@login_required
@superadmin_required
def user_manage(uid):
    u = db.session.query(User).get(uid)
    if not u:
        abort(404)

    recintos_asignados = _recintos_for_user(uid)
    universo_cuentas_por_recinto = { r["id"]: _cuentas_universo_por_recinto(r["id"])
                                     for r in recintos_asignados }
    cuentas_aut_por_recinto = _cuentas_marcadas_por_recinto(uid)
    recintos_catalog = _recintos_catalog_with_cuentas()

    cuentas_globales_ids = _user_cuentas_activas(uid)
    universo_global = _cuentas_universo_global()
    roles = _roles_from_db()

    return render_template(
        "admin/user_manage.html",
        user=u,
        roles=roles,
        recintos=recintos_asignados,
        recintos_catalog=recintos_catalog,
        universo_cuentas_por_recinto=universo_cuentas_por_recinto,
        cuentas_aut_por_recinto=cuentas_aut_por_recinto,
        universo_global=universo_global,
        cuentas_globales_ids=cuentas_globales_ids,
    )


# ---------- (LEGADO) cualquier GET /users/<uid> -> gestionar ----------
@bp.get("/users/<int:uid>")
@login_required
@superadmin_required
def users_edit_get(uid):
    return _redirect_manage(uid)


# ===================== POST: guardar “Datos básicos” =====================
@bp.post("/users/<int:uid>/basic")
@login_required
@superadmin_required
def users_basic_save(uid):
    u = db.session.query(User).get(uid)
    if not u:
        abort(404)
    role_id   = request.form.get("role_id", type=int)
    is_active = request.form.get("is_active") == "on"
    if role_id:
        u.role_id = role_id
    u.is_active = is_active
    db.session.commit()
    flash("Datos básicos actualizados.", "success")
    return _redirect_manage(uid)


# ===================== Cuentas GLOBAL (checkboxes) =====================
@bp.post("/users/<int:uid>/cuentas/save")
@login_required
@superadmin_required
def users_cuentas_save(uid):
    universo_ids = set(
        db.session.execute(text("SELECT id FROM cuentas WHERE is_active=1")).scalars().all()
    )
    selected: set[int] = set()
    for raw in request.form.getlist("cuentas[]"):
        try:
            val = int(raw)
            if val in universo_ids:
                selected.add(val)
        except ValueError:
            pass

    actuales = _user_cuentas_activas(uid)
    to_enable  = selected - actuales
    to_disable = (actuales & universo_ids) - selected

    if to_enable:
        values_sql = ", ".join(f"(:uid, {cid}, 1, :admin_id, NOW())" for cid in to_enable)
        db.session.execute(text(f"""
            INSERT IGNORE INTO user_cuentas (user_id, cuenta_id, is_active, granted_by, created_at)
            VALUES {values_sql}
        """), {"uid": uid, "admin_id": getattr(current_user, "id", None)})
        db.session.execute(text("""
            UPDATE user_cuentas SET is_active=1, updated_at=NOW()
            WHERE user_id=:uid AND cuenta_id IN :ids
        """), {"uid": uid, "ids": tuple(to_enable)})

    if to_disable:
        db.session.execute(text("""
            UPDATE user_cuentas SET is_active=0, updated_at=NOW()
            WHERE user_id=:uid AND cuenta_id IN :ids
        """), {"uid": uid, "ids": tuple(to_disable)})

    db.session.commit()
    flash("Cuentas globales actualizadas.", "success")
    return _redirect_manage(uid)


# ===================== Recintos: asignar / quitar =====================
@bp.post("/users/<int:uid>/recintos/add")
@login_required
@superadmin_required
def users_recintos_add(uid):
    recinto_id = request.form.get("recinto_id", type=int)
    nivel      = request.form.get("nivel", type=int) or 1
    if not recinto_id:
        flash("Selecciona un recinto.", "warning")
        return _redirect_manage(uid)

    db.session.execute(text("""
        INSERT INTO user_recintos (user_id, recinto_id, nivel, desde, is_active, granted_by, created_at)
        VALUES (:uid, :rid, :nivel, CURRENT_DATE, 1, :admin_id, NOW())
        ON DUPLICATE KEY UPDATE
            nivel = VALUES(nivel),
            desde = LEAST(COALESCE(user_recintos.desde, VALUES(desde)), VALUES(desde)),
            is_active = 1,
            updated_at = NOW()
    """), {"uid": uid, "rid": recinto_id, "nivel": nivel,
           "admin_id": getattr(current_user, "id", None)})
    db.session.commit()
    flash("Recinto asignado al usuario.", "success")
    return _redirect_manage(uid)

@bp.post("/users/<int:uid>/recintos/<int:rid>/remove")
@login_required
@superadmin_required
def users_recintos_remove(uid, rid):
    db.session.execute(text("""
        UPDATE user_recintos
           SET is_active = 0, hasta = CURRENT_DATE, updated_at = NOW()
         WHERE user_id = :uid AND recinto_id = :rid AND is_active = 1
    """), {"uid": uid, "rid": rid})
    db.session.commit()
    flash("Recinto quitado del usuario.", "info")
    return _redirect_manage(uid)


# ===================== Permisos por recinto (checkboxes) =====================
@bp.post("/users/<int:uid>/perm/recintos/<int:rid>/cuentas")
@login_required
@superadmin_required
def users_perm_recinto_cuentas_save(uid, rid):
    if not _usuario_tiene_recinto(uid, rid):
        flash("Primero asigna el recinto al usuario.", "warning")
        return _redirect_manage(uid)

    universo_ids = {r["id"] for r in _cuentas_universo_por_recinto(rid)}

    selected = set()
    for raw in request.form.getlist("cuentas[]"):
        try:
            cid = int(raw)
            if cid in universo_ids:
                selected.add(cid)
        except ValueError:
            pass

    actuales = _user_cuentas_activas(uid)
    to_enable  = selected - actuales
    to_disable = (actuales & universo_ids) - selected

    if to_enable:
        values_sql = ", ".join(f"(:uid, {cid}, 1, :admin_id, NOW())" for cid in to_enable)
        db.session.execute(text(f"""
            INSERT IGNORE INTO user_cuentas (user_id, cuenta_id, is_active, granted_by, created_at)
            VALUES {values_sql}
        """), {"uid": uid, "admin_id": getattr(current_user, "id", None)})
        db.session.execute(text("""
            UPDATE user_cuentas SET is_active=1, updated_at=NOW()
            WHERE user_id=:uid AND cuenta_id IN :ids
        """), {"uid": uid, "ids": tuple(to_enable)})

    if to_disable:
        db.session.execute(text("""
            UPDATE user_cuentas SET is_active=0, updated_at=NOW()
            WHERE user_id=:uid AND cuenta_id IN :ids
        """), {"uid": uid, "ids": tuple(to_disable)})

    db.session.commit()
    flash("Permisos de cuentas actualizados.", "success")
    return _redirect_manage(uid)

@bp.post("/users/<int:uid>/perm/recintos/<int:rid>/cuentas/all")
@login_required
@superadmin_required
def users_perm_recinto_cuentas_all(uid, rid):
    if not _usuario_tiene_recinto(uid, rid):
        flash("Primero asigna el recinto al usuario.", "warning")
        return _redirect_manage(uid)

    universo_ids = {r["id"] for r in _cuentas_universo_por_recinto(rid)}
    if not universo_ids:
        flash("Este recinto no tiene cuentas activas vinculadas.", "warning")
        return _redirect_manage(uid)

    values_sql = ", ".join(f"(:uid, {cid}, 1, :admin_id, NOW())" for cid in universo_ids)
    db.session.execute(text(f"""
        INSERT IGNORE INTO user_cuentas (user_id, cuenta_id, is_active, granted_by, created_at)
        VALUES {values_sql}
    """), {"uid": uid, "admin_id": getattr(current_user, "id", None)})
    db.session.execute(text("""
        UPDATE user_cuentas SET is_active=1, updated_at=NOW()
        WHERE user_id=:uid AND cuenta_id IN :ids
    """), {"uid": uid, "ids": tuple(universo_ids)})

    db.session.commit()
    flash("Se asignaron todas las cuentas del recinto.", "success")
    return _redirect_manage(uid)

@bp.post("/users/<int:uid>/perm/recintos/<int:rid>/cuentas/none")
@login_required
@superadmin_required
def users_perm_recinto_cuentas_none(uid, rid):
    if not _usuario_tiene_recinto(uid, rid):
        flash("Primero asigna el recinto al usuario.", "warning")
        return _redirect_manage(uid)

    universo_ids = {r["id"] for r in _cuentas_universo_por_recinto(rid)}
    if not universo_ids:
        flash("No hay cuentas vinculadas a este recinto.", "info")
        return _redirect_manage(uid)

    db.session.execute(text("""
        UPDATE user_cuentas SET is_active=0, updated_at=NOW()
        WHERE user_id=:uid AND cuenta_id IN :ids
    """), {"uid": uid, "ids": tuple(universo_ids)})

    db.session.commit()
    flash("Se quitaron todas las cuentas del recinto.", "info")
    return _redirect_manage(uid)


# ===================== API (opcional debug) =====================
@bp.get("/users/<int:uid>/perm/recintos/<int:rid>/cuentas.json")
@login_required
@superadmin_required
def users_perm_recinto_cuentas_json(uid, rid):
    universo = list(_cuentas_universo_por_recinto(rid))
    marcadas = list(_cuentas_marcadas_por_recinto(uid).get(rid, set()))
    return {"ok": True, "universo": universo, "checked": marcadas}
