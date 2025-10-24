from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from enum import Enum
from sqlalchemy.dialects.mysql import BIGINT as MyBIGINT
from sqlalchemy import UniqueConstraint
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT



from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db



# models.py
from datetime import date, datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.mysql import INTEGER, BIGINT, TINYINT
from sqlalchemy import UniqueConstraint, Index, and_, or_


# =========================
#        ROLES
# =========================
class Role(db.Model):
    __tablename__ = "roles"

    id         = db.Column(db.SmallInteger, primary_key=True)
    code       = db.Column(db.String(50), unique=True, nullable=False)
    name       = db.Column(db.String(120), nullable=False)
    level      = db.Column(db.SmallInteger, nullable=False, default=3)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)

    def __repr__(self):
        return f"<Role {self.code} ({self.name})>"

# =========================
#        USERS
# =========================
# al inicio del archivo (si no lo tienes)
from datetime import date
from sqlalchemy import and_, or_

class User(db.Model):
    __tablename__ = "users"

    id                   = db.Column(BIGINT(unsigned=True), primary_key=True)
    email                = db.Column(db.String(190), unique=True, nullable=False, index=True)
    name                 = db.Column(db.String(120), nullable=False)
    rut                  = db.Column(db.String(16))
    cargo                = db.Column(db.String(120))
    password_hash        = db.Column(db.String(255), nullable=False, default="")
    role_id              = db.Column(db.SmallInteger, db.ForeignKey("roles.id", onupdate="CASCADE"), nullable=False)
    is_active            = db.Column(db.Boolean, default=True, nullable=False)  # <- columna OK (no la toques)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    created_at           = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    password_changed_at = db.Column(db.DateTime, nullable=True)

    def mark_password_changed(self):
        self.must_change_password = False
        self.password_changed_at = datetime.utcnow()


    role = db.relationship("Role", lazy="joined")

    # ======  AÑADE ESTO (compatibilidad Flask-Login) ======
    @property
    def is_authenticated(self) -> bool:
        return True  # una instancia cargada desde BD siempre está autenticada una vez logueada

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        return str(self.id)
    # ====== FIN: métodos/properties requeridos por Flask-Login ======

    # (mantén aquí tus relaciones corregidas con foreign_keys, como te pasé antes)
    recintos_asignaciones = db.relationship(
        "UserRecinto",
        foreign_keys=lambda: [UserRecinto.user_id],
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    recintos = db.relationship(
        "Recinto",
        secondary="user_recintos",
        primaryjoin=lambda: and_(
            UserRecinto.user_id == id,
            UserRecinto.is_active == True,
            or_(UserRecinto.hasta == None, UserRecinto.hasta >= date.today()),
        ),
        secondaryjoin=lambda: UserRecinto.recinto_id == Recinto.id,
        viewonly=True,
        lazy="selectin",
    )

    def __repr__(self):
        return f"<User {self.email}>"

# =========================
#       RECINTOS
# =========================
class Recinto(db.Model):
    __tablename__ = "recintos"

    id         = db.Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    code       = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name       = db.Column(db.String(120), nullable=False, index=True)
    is_active  = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)

            
    usuarios_asignaciones = db.relationship(
        "UserRecinto",
        foreign_keys=lambda: [UserRecinto.recinto_id],
        back_populates="recinto",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Recinto code={self.code} name={self.name}>"
    # vínculos a cuentas
    cuentas_vinculos = db.relationship(
        "RecintoCuenta",
        back_populates="recinto",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    cuentas = db.relationship(
        "Cuenta",
        secondary="recinto_cuentas",
        primaryjoin=lambda: and_(RecintoCuenta.recinto_id == Recinto.id, RecintoCuenta.is_active == True),
        secondaryjoin=lambda: and_(RecintoCuenta.cuenta_id == Cuenta.id, Cuenta.is_active == True),
        viewonly=True,
        lazy="selectin",
    )

    # vínculos a usuarios
    usuarios_asignaciones = db.relationship(
        "UserRecinto",
        back_populates="recinto",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Recinto code={self.code} name={self.name}>"

# =========================
#        CUENTAS
# =========================
class Cuenta(db.Model):
    __tablename__ = "cuentas"

    id          = db.Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    code        = db.Column(db.String(64), unique=True, nullable=False, index=True)  # p.ej. PDY/BRF/PGW/...
    name        = db.Column(db.String(120), nullable=False)
    sap_code    = db.Column(db.String(64))
    cost_center = db.Column(db.String(64))
    is_active   = db.Column(db.Boolean, default=True, nullable=False)
    created_at  = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)

    # backref desde RecintoCuenta
    recintos_vinculos = db.relationship(
        "RecintoCuenta",
        back_populates="cuenta",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Cuenta {self.code}>"

# =======================================
#  N–N: RECINTO <-> CUENTA  (recinto_cuentas)
# =======================================
class RecintoCuenta(db.Model):
    __tablename__ = "recinto_cuentas"

    recinto_id = db.Column(INTEGER(unsigned=True),
                           db.ForeignKey("recintos.id", ondelete="CASCADE", onupdate="CASCADE"),
                           primary_key=True)
    cuenta_id  = db.Column(INTEGER(unsigned=True),
                           db.ForeignKey("cuentas.id", ondelete="CASCADE", onupdate="CASCADE"),
                           primary_key=True)
    is_active  = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)

    recinto = db.relationship("Recinto", back_populates="cuentas_vinculos")
    cuenta  = db.relationship("Cuenta",  back_populates="recintos_vinculos")

    __table_args__ = (
        Index("idx_rc_recinto", "recinto_id"),
        Index("idx_rc_cuenta",  "cuenta_id"),
        UniqueConstraint("recinto_id", "cuenta_id", name="uq_recinto_cuenta"),
    )

    def __repr__(self):
        return f"<RecintoCuenta recinto={self.recinto_id} cuenta={self.cuenta_id} active={self.is_active}>"

# =======================================
#  N–N: USER <-> RECINTO  (user_recintos)
# =======================================
class UserRecinto(db.Model):
    __tablename__ = "user_recintos"

    user_id    = db.Column(BIGINT(unsigned=True),
                           db.ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
                           primary_key=True, index=True)
    recinto_id = db.Column(INTEGER(unsigned=True),
                           db.ForeignKey("recintos.id", ondelete="CASCADE", onupdate="CASCADE"),
                           primary_key=True, index=True)

    # permiso y vigencia
    nivel      = db.Column(TINYINT(unsigned=True), default=1, nullable=False)  # 1=lectura,2=operador,3=admin
    desde      = db.Column(db.Date, default=date.today, nullable=True)
    hasta      = db.Column(db.Date, nullable=True)  # None = sin vencimiento
    is_active  = db.Column(db.Boolean, default=True, nullable=False, index=True)
    granted_by = db.Column(BIGINT(unsigned=True), db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=db.func.current_timestamp())

    # 🔧 Ya correcto: especifica la FK a users por user_id
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="recintos_asignaciones",
        lazy="joined",
        overlaps="granted_by_user",   # opcional
    )
    recinto = db.relationship(
        "Recinto",
        foreign_keys=[recinto_id],
        back_populates="usuarios_asignaciones",
        lazy="joined",
    )
    # Segunda relación a users (quien otorgó)
    granted_by_user = db.relationship(
        "User",
        foreign_keys=[granted_by],
        lazy="joined",
        overlaps="user,recintos_asignaciones",  # opcional
    )

    def __repr__(self):
        return f"<UserRecinto user={self.user_id} recinto={self.recinto_id} nivel={self.nivel} active={self.is_active}>"

















# ======================================================
# ------------------ SUPERADMINS ------------------------
# ======================================================
class SuperAdmin(db.Model):
    __tablename__ = "superadmins"

    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)

    user = db.relationship("User", lazy="joined")

    def __repr__(self):
        return f"<SuperAdmin user_id={self.user_id}>"













# ---------------- ASIGNACIÓN DE TURNOS ----------------
class AsignacionTurno(db.Model):
    __tablename__ = "asignacion_turnos"

    id = db.Column(db.BigInteger, primary_key=True)
    id_recinto       = db.Column("idRecinto", db.Integer, index=True, nullable=False)
    nombre_recinto   = db.Column("nombreRecinto", db.String(255))
    codigo_recinto   = db.Column("codigoRecinto", db.String(100))
    dni              = db.Column("dni", db.String(20), index=True, nullable=False)
    nombre_trabajador = db.Column("nombreTrabajador", db.String(255))
    area_trabajador   = db.Column("areaTrabajador", db.String(255))
    art22_trabajador  = db.Column("art22Trabajador", db.String(10))
    tipo_trabajador   = db.Column("tipoTrabajador", db.String(100))
    idTurno       = db.Column("idTurno", db.String(50), index=True, nullable=False)
    nombreTurno   = db.Column("nombreTurno", db.String(255))
    dia_turno     = db.Column("diaTurno", db.String(10), index=True, nullable=False)  # 'YYYY-MM-DD'
    tipoTurno     = db.Column("tipoTurno", db.String(50))
    horarioTurno  = db.Column("horarioTurno", db.String(25))
    colacionTurno = db.Column("colacionTurno", db.String(25))
    cuenta_area   = db.Column("cuenta_area", db.String(120), index=True)

    def __repr__(self) -> str:
        return f"<AsignacionTurno dni={self.dni} dia={self.dia_turno} turno={self.nombreTurno}>"


# --------------------- INASISTENCIAS -------------------
class Inasistencia(db.Model):
    __tablename__ = "inasistencias"

    id = db.Column(db.BigInteger, primary_key=True)
    id_recinto = db.Column("obra_id", db.Integer, index=True)
    dni        = db.Column("DNI", db.String(20), index=True, nullable=False)
    ano        = db.Column("ano", db.Integer, nullable=False)
    mes        = db.Column("mes", db.Integer, nullable=False)
    dia        = db.Column("dia", db.Integer, nullable=False)
    motivo     = db.Column("motivo", db.String(100))

    def __repr__(self) -> str:
        return f"<Inasistencia dni={self.dni} fecha={self.ano}-{self.mes:02d}-{self.dia:02d}>"


# ----------------------- ASISTENCIA --------------------
class Asistencia(db.Model):
    __tablename__ = "asistencia"

    id               = db.Column(db.BigInteger, primary_key=True)
    rut_trabajador   = db.Column("rut_trabajador", db.String(20), index=True, nullable=False)
    nombre           = db.Column("nombre", db.String(255))
    apellido_materno = db.Column("apellido_materno", db.String(255))
    apellido_paterno = db.Column("apellido_paterno", db.String(255))
    id_recinto       = db.Column("id_recinto", db.Integer, index=True)
    nombre_recinto   = db.Column("nombre_recinto", db.String(255))
    codigo_recinto   = db.Column("codigo_recinto", db.String(100))
    rut_empleado     = db.Column("rut_empleado", db.String(50))
    especialidad     = db.Column("especialidad", db.String(255))
    area             = db.Column("area", db.String(255))
    contrato         = db.Column("contrato", db.String(100))
    supervisor       = db.Column("supervisor", db.String(255))
    entrada          = db.Column("entrada", db.DateTime)
    salida           = db.Column("salida", db.DateTime)
    entrada_turno    = db.Column("entrada_turno", db.DateTime)
    salida_turno     = db.Column("salida_turno", db.DateTime)
    turno_noche      = db.Column("turno_noche", db.Boolean, default=False, nullable=False)
    cuenta_area      = db.Column("cuenta_area", db.String(120), index=True)
    cargo_resumido   = db.Column("cargo_resumido", db.String(120), index=True)

    def __repr__(self) -> str:
        return f"<Asistencia rut={self.rut_trabajador} entrada={self.entrada} salida={self.salida}>"




# ---------------------- NÓMINA -------------------
class NominaColaborador(db.Model):
    __tablename__ = "nomina_colaborador"

    id            = db.Column(db.Integer, primary_key=True)
    obra_id       = db.Column(db.Integer)
    dni           = db.Column(db.String(50), index=True)
    empresa       = db.Column(db.String(120))
    contrato      = db.Column(db.String(120))
    especialidad  = db.Column(db.String(120))
    estado        = db.Column(db.String(50), index=True)

    def __repr__(self) -> str:
        return f"<NominaColaborador id={self.id} dni={self.dni} obra={self.obra_id}>"
    



class Desvinculacion(db.Model):
    __tablename__ = 'desvinculaciones'
    id = db.Column(db.Integer, primary_key=True)
    RUT = db.Column(db.String(12), nullable=False)
    UNIDAD_DE_NEGOCIO = db.Column(db.String(100))
    EMPRESA = db.Column(db.String(100))
    APELLIDOS_NOMBRES = db.Column(db.String(150))
    CARGO = db.Column(db.String(50))
    FECHA_CTTO = db.Column(db.Date)        # DATE en MySQL
    CAUSA_EGRESO = db.Column(db.String(100))
    FECHA_TERMINO = db.Column(db.Date)     # DATE en MySQL
    MOTIVO_SALIDA = db.Column(db.String(200))
    Contrato = db.Column(db.String(50))
    fecha_contrato = db.Column(db.String(10))
    centro_costo_area= db.Column(db.String(100)) 
     # en tu schema actual es VARCHAR(10)

    # helpers de formato
    @staticmethod
    def _parse_ddmmyyyy(s: str):
        if not s: return None
        s = s.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
        raise ValueError("Fecha inválida. Usa dd/mm/yyyy.")

    @staticmethod
    def _fmt_ddmmyyyy(d: date):
        return d.strftime("%d/%m/%Y") if d else ""

    @property
    def FECHA_CTTO_str(self):  # para mostrar en el form
        return self._fmt_ddmmyyyy(self.FECHA_CTTO)

    @property
    def FECHA_TERMINO_str(self):
        return self._fmt_ddmmyyyy(self.FECHA_TERMINO)
    



    # =======================================
#  N–N: USER <-> RECINTO <-> CUENTA  (user_recinto_cuentas)
# =======================================

class UserRecintoCuenta(db.Model):
    __tablename__ = "user_recinto_cuentas"

    id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)

    user_id = db.Column(
        BIGINT(unsigned=True),
        db.ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    recinto_id = db.Column(
        INTEGER(unsigned=True),
        db.ForeignKey("recintos.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    cuenta_id = db.Column(
        INTEGER(unsigned=True),
        db.ForeignKey("cuentas.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    nivel = db.Column(TINYINT(unsigned=True), nullable=False, default=1)
    desde = db.Column(db.Date, nullable=True)
    hasta = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    granted_by = db.Column(
        BIGINT(unsigned=True),
        db.ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"),
    )

    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=db.func.current_timestamp())

    __table_args__ = (
        db.UniqueConstraint("user_id", "recinto_id", "cuenta_id", name="ux_user_recinto_cuenta"),
        db.Index("ix_user_recinto", "user_id", "recinto_id"),
        db.Index("ix_cuenta", "cuenta_id"),
    )



class UserCuenta(db.Model):
    __tablename__ = "user_cuentas"

    id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id   = db.Column(BIGINT(unsigned=True),  db.ForeignKey("users.id"),   nullable=False, index=True)
    cuenta_id = db.Column(INTEGER(unsigned=True), db.ForeignKey("cuentas.id"), nullable=False, index=True)  # 👈 usa INTEGER si cuentas.id es INT
    is_active  = db.Column(db.Boolean, nullable=False, default=True, index=True)
    granted_by = db.Column(BIGINT(unsigned=True), db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=db.func.current_timestamp())

    __table_args__ = (
        db.UniqueConstraint("user_id", "cuenta_id", name="ux_user_cuenta"),
        db.Index("ix_user_cuenta_active", "user_id", "is_active"),
        db.Index("ix_cuenta_active", "cuenta_id", "is_active"),
    )
