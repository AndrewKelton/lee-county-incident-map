import os
import datetime
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from cache import get_incidents   # noqa: E402 — imported after env load
from report import generate_pdf   # noqa: E402

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
allowed_origin = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")
CORS(app, resources={r"/api/*": {"origins": allowed_origin}})


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/incidents")
def incidents():
    data = get_incidents()
    return jsonify(data)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/report", methods=["POST"])
def generate_report():
    # TODO: require JWT before generating reports for registered users
    body   = request.get_json(force=True, silent=True) or {}
    bounds = body.get("bounds", {})
    days   = int(body.get("days", 7))

    north = float(bounds.get("north",  90))
    south = float(bounds.get("south", -90))
    east  = float(bounds.get("east",  180))
    west  = float(bounds.get("west", -180))

    all_inc = get_incidents()

    # Keep only geocoded incidents inside the current viewport
    in_bounds = [
        inc for inc in all_inc
        if inc.get("lat") is not None and inc.get("lng") is not None
        and south <= float(inc["lat"]) <= north
        and west  <= float(inc["lng"]) <= east
    ]

    # Apply date window
    if days > 0:
        cutoff = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=days)

        def _parse(inc):
            d = inc.get("occuredDate")
            if not d:
                return None
            try:
                return datetime.datetime.fromisoformat(d.replace(" ", "T")[:19])
            except Exception:
                return None

        in_bounds = [
            inc for inc in in_bounds
            if (_parse(inc) or datetime.datetime.min) >= cutoff
        ]

    pdf_buf = generate_pdf(
        in_bounds,
        {"north": north, "south": south, "east": east, "west": west},
        days,
    )

    filename = f"lee-county-report-{datetime.date.today()}.pdf"
    return send_file(pdf_buf, mimetype="application/pdf",
                     as_attachment=True, download_name=filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
