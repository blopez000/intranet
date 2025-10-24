from flask import Flask, render_template, url_for, redirect, current_app, request, flash
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFError, generate_csrf
from app.blueprints.auth import bp as auth_bp
from app.blueprints.dashboard import bp as dashboard_bp
from app.blueprints.admin import bp as admin_bp
from app.blueprints.scopes import bp as scopes_bp
from app.blueprints.desvinculaciones import bp as desv_bp
from app.blueprints.docs import bp as docs_bp

from .extensions import db, login_manager, csrf

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # Extensiones
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # === Helpers para templates ===
    @app.context_processor
    def inject_has_endpoint():
        def has_endpoint(name: str) -> bool:
            try:
                return name in current_app.view_functions
            except Exception:
                return False
        return dict(has_endpoint=has_endpoint)

    # 🚩 CSRF: exponer un token ya generado y sincronizado con la cookie
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf())

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    # 🚩 Manejador de errores CSRF con feedback y redirección amable
    @app.errorhandler(CSRFError)
    def handle_csrf(e):
        # Muestra el motivo exacto del fallo (token ausente/expirado/origen inválido, etc.)
        flash(f"CSRF inválido: {e.description}", "danger")
        # Preferimos volver a la página anterior; si no existe, vamos al formulario de creación
        ref = request.headers.get("Referer")
        if ref:
            return redirect(ref)
        return redirect(url_for("admin.users_create"))

    
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(scopes_bp, url_prefix="/scopes")
    app.register_blueprint(desv_bp, url_prefix="/desvinculaciones")
    app.register_blueprint(docs_bp)         # expone /docs y /openapi.json


    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app
