
from functools import wraps
from flask import abort
from flask_login import current_user
from sqlalchemy import text
from app.extensions import db
from functools import wraps
from flask import abort
from flask_login import current_user
from functools import wraps
from flask import redirect, url_for, flash, request, abort
from flask_login import current_user, login_required as _flask_login_required


def nivel_requerido(min_level=2):
    """
    Permite acceso si:
      - el usuario es admin, o
      - nivel_acceso <= min_level
    Caso contrario: 403.
    """
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            if not current_user.is_authenticated:
                abort(401)
            try:
                lvl = int(getattr(current_user, "nivel_acceso", 99))
            except Exception:
                lvl = 99
            is_admin = bool(getattr(current_user, "is_admin", False))
            if not is_admin and lvl > int(min_level):
                abort(403)
            return fn(*a, **k)
        return wrapper
    return deco




def login_required(view):
    """Atajo por si en otras rutas usas @login_required propio."""
    return _flask_login_required(view)

def _user_has_role(*wanted_roles):
    """
    Devuelve True si el usuario actual tiene alguno de los roles requeridos.
    Compatible con distintas estructuras de usuario:
      - current_user.role_code en {1,2,3}
      - current_user.role (str o enum)
      - current_user.roles (lista/conjunto)
      - current_user.has_role('admin')
    """
    if not current_user.is_authenticated:
        return False

    # 1) role_code numérico (ej.: 1=viewer, 2=admin, 3=superadmin)
    code = getattr(current_user, "role_code", None)
    if code is not None:
        # mapea alias comunes
        code_alias = {
            "viewer": 1, "user": 1,
            "admin": 2,
            "superadmin": 3, "owner": 3, "root": 3,
        }
        wanted_codes = {code_alias.get(r, r) for r in wanted_roles}
        return code in wanted_codes

    # 2) role único como string (ej.: 'admin'/'superadmin')
    role = getattr(current_user, "role", None)
    if isinstance(role, str):
        role_lower = role.lower()
        return any(role_lower == str(r).lower() for r in wanted_roles)

    # 3) roles múltiples (lista/conjunto) o método has_role
    if hasattr(current_user, "has_role"):
        return any(current_user.has_role(r) for r in wanted_roles)

    roles = getattr(current_user, "roles", None)
    if roles:
        roles_lower = {str(r).lower() for r in roles}
        return any(str(r).lower() in roles_lower for r in wanted_roles)

    return False

def superadmin_required(view):
    """Restringe acceso a superadmin (cubre role_code=3 o role 'superadmin')."""
    @wraps(view)
    @_flask_login_required
    def wrapper(*args, **kwargs):
        if not _user_has_role(3) and not _user_has_role("superadmin"):
            flash("No tienes permisos de superadministrador.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapper

def login_required_scope(*required_scopes):
    """
    Valida que el usuario esté logeado y tenga AL MENOS uno de los 'scopes'
    requeridos (o bien sea superadmin/admin). Define cómo leer 'scopes' desde
    tu modelo de usuario:
      - current_user.scopes -> set/list de strings
      - current_user.has_scope('x')
    """
    def decorator(view):
        @wraps(view)
        @_flask_login_required
        def wrapper(*args, **kwargs):
            # superadmin pasa siempre
            if _user_has_role(3) or _user_has_role("superadmin"):
                return view(*args, **kwargs)

            # admin podría pasar (si quieres), descomenta si aplica:
            # if _user_has_role(2) or _user_has_role("admin"):
            #     return view(*args, **kwargs)

            # Scopes por método
            if hasattr(current_user, "has_scope"):
                if any(current_user.has_scope(s) for s in required_scopes):
                    return view(*args, **kwargs)

            # Scopes por atributo iterable
            user_scopes = getattr(current_user, "scopes", [])
            user_scopes_lower = {str(s).lower() for s in user_scopes} if user_scopes else set()
            if any(str(s).lower() in user_scopes_lower for s in required_scopes):
                return view(*args, **kwargs)

            # Sin permisos
            # Puedes usar 403 si prefieres: return abort(403)
            flash("No tienes los permisos necesarios para acceder a esta sección.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return wrapper
    return decorator


def superadmin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # no autenticado
        row = db.session.execute(
            text("SELECT 1 FROM superadmins WHERE user_id = :uid LIMIT 1"),
            {"uid": int(current_user.id)}
        ).first()
        if not row:
            abort(403)  # autenticado, pero sin permiso
        return f(*args, **kwargs)
    return wrapper
