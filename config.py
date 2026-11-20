"""Application configuration for SwapIt.

Secrets and environment-specific values are read from environment
variables (optionally loaded from a local .env file). Safe development
fallbacks are provided so the app runs out of the box.

Environment knobs (all optional):
    SECRET_KEY            session/CSRF signing key
    DATABASE_URL          SQLAlchemy URI (SQLite locally, Postgres in prod)
    FLASK_CONFIG          "production" | "testing" | anything else = default
    SESSION_COOKIE_SECURE "1" to force HTTPS-only cookies
    AUTO_CREATE_DB        "1" (default) to create tables at startup
    MEDIA_BACKEND         "local" (default) stores item images on disk under
                          static/uploads; "db" stores them in the database
                          (used on serverless hosts with read-only filesystems)
    ASSET_CDN             "1" to load Bootstrap/Icons from jsDelivr CDN
                          instead of the vendored copies in static/vendor
    MAX_UPLOAD_MB         max request/upload size in MB (default 5)
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default) == "1"


class Config:
    """Base configuration."""

    # Security
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-key")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_flag("SESSION_COOKIE_SECURE")
    REMEMBER_COOKIE_HTTPONLY = True

    # Database. Relative SQLite paths resolve inside the instance/ folder.
    # (postgres:// and postgresql:// URIs are normalised to the psycopg2
    # driver so the same env var works everywhere.)
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL", "sqlite:///swapit.db")
        .replace("postgres://", "postgresql+psycopg2://", 1)
        .replace("postgresql://", "postgresql+psycopg2://", 1)
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Uploads / media
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(BASE_DIR, "static", "uploads"))
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "5")) * 1024 * 1024
    MAX_IMAGE_DIMENSION = 1280  # longest side after processing
    MEDIA_BACKEND = os.environ.get("MEDIA_BACKEND", "local")  # "local" | "db"

    # Frontend assets
    ASSET_CDN = _env_flag("ASSET_CDN")

    # Database bootstrap
    AUTO_CREATE_DB = _env_flag("AUTO_CREATE_DB", "1")

    # Categories available for listings
    CATEGORIES = ["Books", "Electronics", "Stationery", "Accessories", "Sports", "Other"]
    CONDITIONS = ["New", "Good", "Used"]


class TestingConfig(Config):
    """Configuration used by the automated test-suite."""

    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SERVER_NAME = "localhost"
    MEDIA_BACKEND = "local"
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "tests", "_uploads")
    AUTO_CREATE_DB = False


class ProductionConfig(Config):
    """Production configuration (FLASK_CONFIG=production)."""

    SESSION_COOKIE_SECURE = True


CONFIG_MAP = {
    "production": ProductionConfig,
    "testing": TestingConfig,
}
