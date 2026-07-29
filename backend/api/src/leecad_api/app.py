import os
from dataclasses import replace

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from psycopg import OperationalError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

from leecad_api import filters as filters_module
from leecad_api import queries

API = "/api/v1"


def create_app(database_url: str | None = None) -> Flask:
    load_dotenv()
    url = database_url or os.environ["DATABASE_URL"]
    origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

    app = Flask(__name__)
    app.pool = ConnectionPool(url, min_size=1, max_size=8, timeout=5, open=True,
                              kwargs={"row_factory": dict_row})
    CORS(app, resources={rf"{API}/*": {"origins": origins}})

    @app.errorhandler(ValueError)
    def bad_request(exc):
        return jsonify({"error": str(exc)}), 400

    @app.get(f"{API}/health")
    def health():
        try:
            with app.pool.connection() as conn:
                row = conn.execute("SELECT revision FROM dataset_revision").fetchone()
        except (OperationalError, PoolTimeout):
            return jsonify({"status": "error", "database": "unreachable"}), 503
        return jsonify({"status": "ok", "dataset_revision": row["revision"]})

    cached_types: dict = {}

    @app.get(f"{API}/incident-types")
    def incident_types():
        with app.pool.connection() as conn:
            revision = conn.execute("SELECT revision FROM dataset_revision").fetchone()["revision"]
            if cached_types.get("dataset_revision") != revision:
                rows = conn.execute(queries.INCIDENT_TYPES).fetchall()
                cached_types.update(types=rows, dataset_revision=revision)
        return jsonify(cached_types)

    @app.get(f"{API}/incidents/<source>/<source_incident_id>")
    def incident_detail(source, source_incident_id):
        with app.pool.connection() as conn:
            row = conn.execute(queries.INCIDENT_DETAIL, (source, source_incident_id)).fetchone()
        if row is None:
            return jsonify({"error": "incident not found"}), 404
        return jsonify(_serialize(row))

    @app.get(f"{API}/stats/summary")
    def stats_summary():
        parsed = filters_module.parse(request.args)
        sql, params = queries.stats_summary(parsed)

        with app.pool.connection() as conn:
            stats = conn.execute(sql, params).fetchone()
            revision = conn.execute("SELECT revision FROM dataset_revision").fetchone()

        return jsonify({**stats, "dataset_revision": revision["revision"]})

    @app.get(f"{API}/incidents")
    def incidents():
        fmt = request.args.get("format", "json")
        if fmt not in ("json", "geojson"):
            raise ValueError("format must be json or geojson")

        parsed = filters_module.parse(request.args)
        if fmt == "geojson" and "mapped" not in request.args:
            parsed = replace(parsed, mapped_only=True)

        limit = filters_module.parse_limit(request.args)
        sql, params = queries.incident_list(parsed, limit, request.args.get("cursor"))

        with app.pool.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            revision = conn.execute("SELECT revision FROM dataset_revision").fetchone()

        next_cursor = queries.encode_cursor(rows[limit - 1]) if len(rows) > limit else None
        page = rows[:limit]

        if fmt == "geojson":
            return jsonify({
                "type": "FeatureCollection",
                "features": [_feature(r) for r in page],
                "next_cursor": next_cursor,
                "dataset_revision": revision["revision"],
            })
        return jsonify({
            "incidents": [_serialize(r) for r in page],
            "next_cursor": next_cursor,
            "dataset_revision": revision["revision"],
        })

    return app


def _serialize(row: dict) -> dict:
    return {**row, "occurred_at": row["occurred_at"].isoformat()}


def _feature(row: dict) -> dict:
    properties = _serialize(row)
    lon, lat = properties.pop("lon"), properties.pop("lat")
    return {
        "type": "Feature",
        "id": f"{row['source']}:{row['source_incident_id']}",
        "geometry": None if lat is None else {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties,
    }
