import os
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from shapely.geometry import Point, mapping
from shapely.ops import unary_union, transform as shp_transform
from pyproj import Transformer

CLUSTER_COLORS = ["#E63946", "#2A9D8F", "#E9C46A", "#457B9D", "#F4A261"]

_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data",
    "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv",
)


def load_csv_incidents() -> list:
    """Load incidents from the late-paper CSV and return as a list of dicts
    with 'lat' and 'lng' keys, matching the format returned by get_incidents()."""
    df = pd.read_csv(_CSV_PATH).dropna(subset=["lat", "lon"])
    return df[["lat", "lon"]].rename(columns={"lon": "lng"}).to_dict(orient="records")


def run_clusters(incidents: list, eps: float, min_pts: int) -> dict:
    """
    Run DBSCAN on geocoded incidents and return a GeoJSON FeatureCollection.

    Parameters
    ----------
    incidents : list of dicts with 'lat' and 'lng' keys (from cache.get_incidents)
    eps       : neighborhood radius in US survey feet (EPSG:2882 units)
    min_pts   : DBSCAN min_samples

    Returns
    -------
    GeoJSON FeatureCollection dict with a top-level 'metadata' key.
    Each feature is a cluster polygon in WGS84 with properties:
        cluster_id, point_count, color
    """
    mappable = [
        inc for inc in incidents
        if inc.get("lat") is not None and inc.get("lng") is not None
    ]
    if not mappable:
        return {
            "type": "FeatureCollection",
            "features": [],
            "metadata": {"n_clusters": 0, "n_noise": 0, "n_total": 0},
        }

    lats = np.array([inc["lat"] for inc in mappable], dtype=float)
    lons = np.array([inc["lng"] for inc in mappable], dtype=float)

    # Project NAD83 geographic → NAD83 StatePlane Florida West (US survey feet)
    to_proj = Transformer.from_crs("EPSG:4269", "EPSG:2882", always_xy=True)
    easting, northing = to_proj.transform(lons, lats)
    points = np.column_stack([easting, northing])

    labels = DBSCAN(eps=eps, min_samples=min_pts).fit(points).labels_
    
    # Get noise points
    noise_mask = labels == -1
    noise_points = [
        {"lat": float(lats[i]), "lng": float(lons[i])}
        for i in range(len(labels))
        if noise_mask[i]
    ]

    # Back-projector: projected feet → WGS84 lon/lat for GeoJSON
    to_wgs84 = Transformer.from_crs("EPSG:2882", "EPSG:4326", always_xy=True)

    NOISE_COLOR = "#AAAAAA"

    # Point features (one per incident) 
    point_features = []
    for i, (lat, lon, label) in enumerate(zip(lats, lons, labels)):
        color = NOISE_COLOR if label == -1 else CLUSTER_COLORS[int(label) % len(CLUSTER_COLORS)]
        point_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "properties": {
                "feature_type": "point",
                "cluster_id": int(label),
                "color": color,
            },
        })

    # Polygon features (one per cluster) 
    polygon_features = []
    for label in sorted(set(labels) - {-1}):
        mask = labels == label
        color = CLUSTER_COLORS[int(label) % len(CLUSTER_COLORS)]

        cluster_pts = points[mask]
        union = unary_union([Point(p).buffer(eps) for p in cluster_pts])
        wgs84_geom = shp_transform(to_wgs84.transform, union)

        polygon_features.append({
            "type": "Feature",
            "geometry": mapping(wgs84_geom),
            "properties": {
                "feature_type": "polygon",
                "cluster_id": int(label),
                "point_count": int(mask.sum()),
                "color": color,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": polygon_features + point_features,
        "metadata": {
            "n_clusters": len(set(labels) - {-1}),
            "n_noise": int((labels == -1).sum()),
            "n_total": len(mappable),
            "eps": eps,
            "min_pts": min_pts,
        },
        "noise_points": noise_points,
    }
