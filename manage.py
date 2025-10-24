# manage.py (sin Flask-Migrate)
from flask import Flask
from app import create_app

app: Flask = create_app()

# Ejemplos:
#   flask --app manage.py run --debug

if __name__ == "__main__":
    app.run(debug=True)
