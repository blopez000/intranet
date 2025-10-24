from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash
from functools import wraps

from app.extensions import db, login_manager, csrf
from app.models import User
from .forms import LoginForm


from . import bp

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

from app.extensions import db, login_manager, csrf
from app.models import User
from .forms import LoginForm



from . import bp

# ------------ Flask-Login ------------
@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None


# ------------ Decoradores de acceso ------------
def nivel_requerido(nivel_minimo: int):
    def deco(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.url))
            if getattr(current_user, "is_admin", False):
                return view(*args, **kwargs)
            try:
                nivel_user = int(getattr(current_user, "nivel_acceso", 99))
            except Exception:
                nivel_user = 99
            if nivel_user <= int(nivel_minimo):
                return view(*args, **kwargs)
            flash("No tienes permisos suficientes.", "warning")
            return redirect(url_for("dashboard.index"))
        return wrapper
    return deco


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.url))
        if getattr(current_user, "is_admin", False) or (getattr(current_user, "role", "") or "").upper() == "ADMIN":
            return view(*args, **kwargs)
        flash("Solo administradores.", "warning")
        return redirect(url_for("dashboard.index"))
    return wrapper


# ------------ Login / Logout ------------
@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        # Si el usuario ya inició sesión y debe cambiar su password
        if getattr(current_user, "must_change_password", False):
            return redirect(url_for("auth.first_password"))
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if not user or not check_password_hash(user.password_hash, form.password.data):
            flash("Usuario o contraseña inválidos", "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember.data)

        # Si el usuario debe cambiar su contraseña al ingresar
        if getattr(user, "must_change_password", False):
            return redirect(url_for("auth.first_password"))

        return redirect(request.args.get("next") or url_for("dashboard.index"))

    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@csrf.exempt
def logout():
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("auth.login"))





@bp.before_app_request
def force_password_change_gate():
    """
    Si el usuario tiene must_change_password = True, se le fuerza a ir a /auth/first-password
    y se bloquea el resto de rutas (excepto login, logout, first_password y static).
    """
    # Rutas permitidas mientras cambia contraseña
    allowed = {
        "auth.login",              # GET/POST /auth/login
        "auth.logout",             # POST /auth/logout
        "auth.first_password",     # GET/POST /auth/first-password
        "static",                  # assets
    }

    # No autenticado: no gate
    if not current_user.is_authenticated:
        return

    # Usuarios que NO requieren cambio: no gate
    if not getattr(current_user, "must_change_password", False):
        return

    # Si ya está en una ruta permitida, dejar pasar
    if request.endpoint in allowed:
        return

    # Si no, redirigir a la pantalla de primer cambio de contraseña
    return redirect(url_for("auth.first_password"))


# ------------ Forzar cambio de contraseña ------------
@bp.route("/first-password", methods=["GET", "POST"])
@login_required
def first_password():
    user = current_user
    if not getattr(user, "must_change_password", False):
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        new_pass = request.form.get("password1")
        repeat_pass = request.form.get("password2")

        if not new_pass or len(new_pass) < 8:
            flash("La nueva contraseña debe tener al menos 8 caracteres.", "warning")
            return render_template("auth/first_password.html")

        if new_pass != repeat_pass:
            flash("Las contraseñas no coinciden.", "danger")
            return render_template("auth/first_password.html")

        user.password_hash = generate_password_hash(new_pass)
        user.must_change_password = False
        user.password_changed_at = db.func.now()
        db.session.commit()

        flash("Contraseña actualizada correctamente.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/first_password.html")
