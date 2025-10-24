# app/blueprints/docs/__init__.py
from flask import Blueprint

bp = Blueprint(
    "docs",
    __name__,
    static_folder="static",
    template_folder="templates",
)
from . import routes  # noqa: E402,F401
