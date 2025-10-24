# Flask Pro Skeleton (Blueprints + Extensions)

Estructura pensada para **entornos productivos** (Docker, CI/CD, múltiples módulos) y para escalar.
Incluye **Blueprints**, separación de **extensiones**, **config por entorno** y ejemplos de rutas, forms y templates.

## Árbol de directorios
```
app/
  __init__.py
  extensions.py
  models/
    __init__.py
  blueprints/
    auth/
      __init__.py
      routes.py
      forms.py
      templates/
        auth/
          login.html
    dashboard/
      __init__.py
      routes.py
      templates/
        dashboard/
          index.html
  templates/
    base.html
    403.html
    404.html
  static/
    css/
      app.css
config.py
wsgi.py
manage.py
requirements.txt
```

## Qué hace cada cosa (visión ejecutiva)
- **app/__init__.py**: patrón `create_app()`. Crea la app, carga configuración, registra extensiones y **blueprints**.
- **app/extensions.py**: inicializa librerías (SQLAlchemy, LoginManager, CSRF, Migrate). Evita import cycles.
- **app/models/**: tus modelos ORM. Manténlos desacoplados de vistas.
- **app/blueprints/**: módulos de negocio aislados (auth, dashboard, api, etc.). Cada uno con sus rutas, formularios y templates.
- **app/templates/**: vistas compartidas (base, errores).
- **config.py**: configuración por entorno. Lee variables de entorno (`.env` o Docker env).
- **manage.py**: entrypoint de CLI (`flask --app manage.py ...`).
- **wsgi.py**: entrypoint para servidores WSGI (gunicorn/uwsgi).
- **requirements.txt**: dependencias.
- **migrations/**: Alembic/Flask-Migrate (se crea al correr `flask db init`).

## Cómo migrar tu proyecto actual
1) Copia este esqueleto a tu repo.
2) Mueve tus modelos a `app/models/` (ajusta imports para usar `from app.extensions import db`).
3) Divide tus rutas actuales en **blueprints**. Ejemplos:
   - rutas de login/registro → `app/blueprints/auth/routes.py`
   - vistas de tablero/reportes → `app/blueprints/dashboard/routes.py`
4) Variables sensibles → `.env` o Docker `environment:` (ver `config.py`).
5) Base de datos:
   - Instala: `pip install -r requirements.txt`
   - Inicializa migraciones: `flask --app manage.py db init`
   - Genera migración: `flask --app manage.py db migrate -m "init"`
   - Aplica: `flask --app manage.py db upgrade`
6) Ejecuta:
   - Dev: `flask --app manage.py run --debug`
   - Gunicorn: `gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app`

## Mapa de responsabilidades
- **Blueprints** = frontera del dominio (HTTP). Validan input, llaman servicios/repositorios y devuelven respuesta.
- **Services** (opcional) = reglas de negocio (p.ej., consolidar asistencia).
- **Repositories** (opcional) = consultas SQL/ORM.
- **Models** = entidades persistentes.
- **Extensions** = SDKs y clients (db, cache, etc.).
- **Templates/static** = presentación.

## Seguridad & buenas prácticas
- Nunca hardcodees credenciales. Usa env vars.
- Aplica CSRF a formularios y valida input con WTForms.
- Registra errores 404/403/500 con logging.
- Activa `ProxyFix` si estás detrás de Nginx/ELB.
- Separa acceso por roles en decoradores (ej.: `@admin_required`).

¡Listo! Adapta los módulos y pega tu lógica.
