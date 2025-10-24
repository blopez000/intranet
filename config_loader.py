# config_loader.py

from dotenv import load_dotenv
import os

# Cargar el archivo .env
load_dotenv()

# Acceder a las variables
SECRET_KEY = os.getenv("SECRET_KEY")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")



# Mostrar resultados
print("SECRET_KEY:", SECRET_KEY)
print("DB_PORT:", DB_PORT)
print("DB_USER:", DB_USER)
print("DB_PASS:", DB_PASS)
print("DB_NAME",DB_NAME)