# app/security.py
from __future__ import annotations
from typing import Optional
from werkzeug.security import generate_password_hash, check_password_hash

_PBKDF2_SPEC = "pbkdf2:sha256:600000"


def hash_password(plain: str) -> str:
    if not plain:
        raise ValueError("Password vacío")
    return generate_password_hash(plain, method=_PBKDF2_SPEC)


def _check_bcrypt_compat(stored: str, plain: str) -> bool:
    # Compatibilidad opcional para $2a/$2b/$2y (si tienes la lib bcrypt instalada).
    try:
        import bcrypt  # type: ignore
    except Exception:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("utf-8"))
    except Exception:
        return False


def verify_password(stored: Optional[str], plain: str) -> bool:
    """
    Verifica contraseña soportando:
      - PBKDF2 (Werkzeug): 'pbkdf2:sha256:...$salt$hash'
      - bcrypt ($2a/$2b/$2y) si está instalada la lib
    NUNCA llama a check_password_hash si el formato es desconocido.
    """
    if not stored:
        return False

    stored = stored.strip().strip('"').strip("'")  # limpia espacios y comillas

    # bcrypt crudo
    if stored.startswith("$2a$") or stored.startswith("$2b$") or stored.startswith("$2y$"):
        return _check_bcrypt_compat(stored, plain)

    # PBKDF2 (formatos típicos que genera Werkzeug)
    if stored.startswith("pbkdf2:sha256"):
        try:
            return check_password_hash(stored, plain)
        except Exception:
            return False

    # Formato desconocido → inválido (evita ValueError de Werkzeug)
    return False


def verify_and_maybe_rehash(user, plain: str, db=None, commit=True) -> bool:
    """
    Verifica la contraseña y, si el hash no es pbkdf2:sha256, lo migra automáticamente.
    Retorna True/False según verificación.
    """
    h = (user.password_hash or "")
    if not h or not check_password_hash(h, plain):
        return False

    # Si el hash actual no es pbkdf2:sha256, lo re-hasheamos y guardamos
    if not h.startswith("pbkdf2:sha256:"):
        user.password_hash = generate_password_hash(plain, method="pbkdf2:sha256")
        if db is not None and commit:
            db.session.commit()

    return True