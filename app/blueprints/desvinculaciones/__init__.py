from flask import Blueprint

bp = Blueprint(
    "desvinculaciones",
    __name__,
    url_prefix="/desvinculaciones",   # ⬅ agrego el prefijo aquí
    template_folder="templates",      # tienes subcarpeta 'desv/' dentro
    static_folder="static",
    static_url_path="/static"
)

from . import routes  # registra endpoints
