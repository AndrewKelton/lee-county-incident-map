import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from cache import get_incidents  # noqa: E402 — imported after env load
from ml.clustering import run_clusters, load_csv_incidents, cluster_levels  # noqa: E402

app = Flask(__name__)

allowed_origin = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")
CORS(app, resources={r"/api/*": {"origins": allowed_origin}})


@app.route("/cluster-lab")
def cluster_lab():
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    return send_from_directory(frontend_dir, "cluster-lab.html")

@app.route("/api/incidents")
def incidents():
    data = get_incidents()
    return jsonify(data)


@app.route("/api/clusters")
def clusters():
    try:
        eps = float(request.args.get("eps", 13123.0))
    #     min_pts = int(request.args.get("min_pts", 20))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid parameters"}), 400

    # eps = 4 # max(500.0, min(50000.0, eps))
    min_pts = 4 # max(2, min(100, min_pts))

    level = request.args.get("level")
    cluster_color = cluster_levels[level]["color"] if level in cluster_levels else None

    data = load_csv_incidents()
    result = run_clusters(data, eps, min_pts, cluster_color=cluster_color)
    return jsonify(result)


@app.route("/api/clusters/multi")
def clusters_multi():
    data = load_csv_incidents()
    
    all_results = {}
    for level, settings in cluster_levels.items():
        result = run_clusters(incidents=data, eps=settings["epsilon"], min_pts=settings["min_pts"], cluster_color=settings.get("color"))
        all_results[level] = result
        
    return jsonify(all_results)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
