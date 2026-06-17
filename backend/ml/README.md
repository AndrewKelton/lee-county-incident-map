# DBSCAN Demo

`dbscan_demo.py` is a self-contained script that visualizes how DBSCAN clusters a small sample of real Lee County incidents. It serves as a working reference for the clustering logic that will run live on the incident map.

## What it does

1. Loads `N_POINTS` rows from `data/incidents-small.csv` and projects lat/lon to a local kilometre coordinate system centred at the sample's centroid.
2. Runs `sklearn.cluster.DBSCAN` with configurable `EPS` (neighbourhood radius in km) and `MIN_SAMPLES`.
3. Produces two outputs:
   - **`dbscan_snapshot.png`** — a static plot of the final clusters with convex-hull overlays.
   - **`dbscan_animation.gif`** — a frame-by-frame animation of DBSCAN's BFS expansion, showing the ε-ring sweep, point classification, and hull reveal.

## Configuration

All tunable parameters are at the top of the file:

| Variable | Default | Description |
|---|---|---|
| `N_POINTS` | `50` | Number of incidents to sample |
| `RANDOM_SEED` | `42` | Seed for reproducible sampling |
| `EPS` | `0.5` | DBSCAN ε in km |
| `MIN_SAMPLES` | `2` | DBSCAN min_samples |
| `ANIM_INTERVAL_MS` | `600` | Milliseconds between animation frames |

## Running

```bash
# from the repo root (venv activated)
python backend/ml/dbscan_demo.py
```

Outputs are written to the **current working directory**.

## Relation to the live map

This demo is a prototype for the clustering feature planned for the incident map backend. When integrated:

- The same **coordinate projection** (WGS84 → local km) will be applied to live incident coordinates before clustering.
- The same **DBSCAN parameters** (`EPS`, `MIN_SAMPLES`) will be exposed as query parameters or config so operators can tune sensitivity without redeploying.
- Cluster results (centroid, point count, label) will be returned by the API and rendered on the map as heatmap-style overlays or convex-hull polygons, mirroring the hull patches drawn here.
- Noise points (label `-1`) will be shown as individual markers rather than grouped, matching the demo's visual distinction between clustered and isolated incidents.
