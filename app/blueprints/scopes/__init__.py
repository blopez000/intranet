from flask import Blueprint
bp = Blueprint("scopes", __name__, template_folder="templates")
from . import routes  # noqa
