import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-prod")

    DB_USER = os.getenv("DB_USER", "ingenieria")
    DB_PASS = os.getenv("DB_PASS", "A6V4j6NWQP6V8mE")
    DB_HOST = os.getenv("DB_HOST", "10.62.115.242")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "ingenieria")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MYSQL_COLLATION = os.getenv("MYSQL_COLLATION", "utf8mb4_unicode_ci")

    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = False  # True en prod detrás de HTTPS
    REMEMBER_COOKIE_SECURE = False

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


class DevConfig(Config):
    DEBUG = True


class ProdConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
