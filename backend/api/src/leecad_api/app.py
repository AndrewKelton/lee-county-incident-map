import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from psycopg import OperationalError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

API = "/api/v1"


def create_app(database_url: str | None = None) -> Flask:
    load_dotenv()
    url = database_url or os.environ["DATABASE_URL"]
    origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

    app = Flask(__name__)
    app.pool = ConnectionPool(url, min_size=1, max_size=8, timeout=5, open=True,
                              kwargs={"row_factory": dict_row})
    CORS(app, resources={rf"{API}/*": {"origins": origins}})

    @app.get(f"{API}/health")
    def health():
        try:
            with app.pool.connection() as conn:
                row = conn.execute("SELECT revision FROM dataset_revision").fetchone()
        except (OperationalError, PoolTimeout):
            return jsonify({"status": "error", "database": "unreachable"}), 503
        return jsonify({"status": "ok", "dataset_revision": row["revision"]})

    return app
