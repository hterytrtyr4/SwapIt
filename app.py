"""Application entry point.

Run locally:      python app.py
Production:       gunicorn app:app
Serverless:       api/index.py exposes `app` to Vercel.
"""
from __future__ import annotations

import os
import time

from dotenv import load_dotenv

load_dotenv()  # read .env before config is evaluated

from flask import Flask, render_template  # noqa: E402
from flask_login import LoginManager, current_user  # noqa: E402
from flask_wtf.csrf import CSRFProtect  # noqa: E402

from config import CONFIG_MAP, Config  # noqa: E402
from models import (  # noqa: E402
    SWAP_PENDING,
    Item,
    SwapRequest,
    User,
    db,
)

login_manager = LoginManager()
csrf = CSRFProtect()


def _ensure_sqlite_columns(app: Flask) -> None:
    """Tiny upgrade helper: add columns introduced after a DB was created
    (SQLite and PostgreSQL — fresh databases are fully created by
    db.create_all())."""
    from sqlalchemy import inspect, text

    try:
        engine = db.engine
        insp = inspect(engine)
        if "items" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("items")}
        need = []
        if "image_data" not in cols:
            need.append("image_data")
        if "image_mimetype" not in cols:
            need.append("image_mimetype")
        if not need:
            return
        with engine.begin() as conn:
            for col in need:
                coltype = "BLOB" if engine.dialect.name == "sqlite" else "BYTEA"
                if col == "image_mimetype":
                    coltype = "VARCHAR(40)"
                if engine.dialect.name == "sqlite":
                    conn.execute(text(f"ALTER TABLE items ADD COLUMN {col} {coltype}"))
                else:
                    conn.execute(
                        text(f"ALTER TABLE items ADD COLUMN IF NOT EXISTS {col} {coltype}")
                    )
    except Exception:  # pragma: no cover - never block startup on this
        pass


def create_app(config_object=None) -> Flask:
    if config_object is None:
        config_object = CONFIG_MAP.get(os.environ.get("FLASK_CONFIG", ""), Config)

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    # Ensure the upload folder exists (best effort — serverless FS may be
    # read-only; with MEDIA_BACKEND=db no files are written anyway).
    try:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    except OSError:
        pass

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access that page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # ------------------------------------------------------------------ #
    # Blueprints
    # ------------------------------------------------------------------ #
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.items import items_bp
    from routes.marketplace import marketplace_bp
    from routes.swaps import swaps_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(swaps_bp)
    app.register_blueprint(dashboard_bp)

    # ------------------------------------------------------------------ #
    # Template context
    # ------------------------------------------------------------------ #
    @app.context_processor
    def inject_globals():
        pending_incoming = 0
        if current_user.is_authenticated:
            pending_incoming = (
                SwapRequest.query.filter_by(
                    receiver_id=current_user.id, status=SWAP_PENDING
                ).count()
            )
        return {
            "pending_incoming": pending_incoming,
            "current_year": __import__("datetime").datetime.now().year,
        }

    # ------------------------------------------------------------------ #
    # Error handlers
    # ------------------------------------------------------------------ #
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    # Create tables on first run (SQLite demo / single-instance deploys).
    # In production set AUTO_CREATE_DB=0 and run migrations instead.
    if app.config.get("AUTO_CREATE_DB", True):
        for attempt in (1, 2, 3):
            try:
                with app.app_context():
                    db.create_all()
                    _ensure_sqlite_columns(app)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2)

    return app


app = create_app()


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 5000)),
        debug=debug,
    )
