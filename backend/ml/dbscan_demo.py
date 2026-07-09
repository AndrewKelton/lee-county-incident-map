import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon
from sklearn.cluster import DBSCAN
from shapely.geometry import Point, mapping
from shapely.ops import unary_union
from kneed import KneeLocator, find_shape
import folium
import sys

# ── Configuration ────────────────────────────────────────────────────────────
# Tweak these to change the shape of the demo without touching any logic.

# Path to the CSV — relative to this file so it works from any cwd.
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv")
N_POINTS = 250           # how many rows to sample from the CSV
RANDOM_SEED = 42          # used only for the random sample so results are reproducible

# EPS is in the same units as the projected coordinates (see load_points).
# After mean-centering and scaling to ~km, a value around 0.3–0.8 is a good start.
EPS         = 4.0           # DBSCAN ε — neighborhood radius
MIN_SAMPLES = 20            # DBSCAN min_samples

'''
Level EPS (km)	min_samples	Rationale
Street	0.365	3	~365m radius — one or two block faces
Neighborhood	0.9	6	~900m radius — walkable neighborhood scale
District	4.0	20	~4km radius — city district / county zone
'''

SNAPSHOT_OUT     = "output/dbscan_snapshot.png"
ANIMATION_OUT    = "output/dbscan_animation.gif"
FOLIUM_OUT       = "output/dbscan_map.html"
ANIM_INTERVAL_MS = 600    # milliseconds between animation frames

# ── Color palette ─────────────────────────────────────────────────────────────
CLUSTER_COLORS = ["#E63946", "#2A9D8F", "#E9C46A", "#457B9D", "#F4A261"]
NOISE_COLOR    = "#AAAAAA"
UNVISITED_COLOR = "#CCCCCC"


# ── 1. Data Loading ──────────────────────────────────────────────────────────

def load_points() -> np.ndarray:
    """
    Load N_POINTS incidents from late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv and return a (N, 2)
    array of projected x/y coordinates suitable for DBSCAN.

    Steps:
      - Read CSV_PATH with pandas; keep only rows where lat and lon are
        not null (mirrors the idx_incidents_location index filter).
      - Sample N_POINTS rows with random_state=RANDOM_SEED so the demo
        is reproducible but draws from real data.
      - Project from WGS84 to a local flat coordinate system:
          x = (lon - lon.mean()) * cos(lat_mean_radians) * 111.32   # km
          y = (lat - lat.mean()) * 111.32                           # km
        This gives axes in kilometres centred at (0, 0) with roughly
        equal x/y scale — appropriate for a small county-level extent.
      - Return np.column_stack([x, y]) as a float64 array.
    """
    incidents_df = pd.read_csv(CSV_PATH).dropna(subset=["lat", "lon"])
    
    lat_mean_rad = np.radians(incidents_df["lat"].mean())
    x = (incidents_df["lon"] - incidents_df["lon"].mean()) * np.cos(lat_mean_rad) * 111.32
    y = (incidents_df["lat"] - incidents_df["lat"].mean()) * 111.32
    
    points = np.column_stack([x, y])
    lats = incidents_df["lat"].to_numpy()
    lons = incidents_df["lon"].to_numpy()
    
    """kneedle DBSCAN optimum epsilon parameter"""
    # direction, curve = find_shape(-x, y)
    # kneedle = KneeLocator(-x, y, curve=curve, direction=direction)

    # min_samples = int(-kneedle.elbow)
    # print(f"min_samples: {min_samples}")
    # kneedle.plot_knee()
    # plt.show()
    
    min_samples=MIN_SAMPLES
    
    return points, lats, lons, min_samples
    

# ── 2. Run DBSCAN ─────────────────────────────────────────────────────────────

def run_dbscan(points: np.ndarray, min_samples: int) -> np.ndarray:
    """
    Fit DBSCAN on the point array and return the label array.

    Steps:
      - Instantiate sklearn.cluster.DBSCAN with eps=EPS, min_samples=min_samples.
      - Call .fit(points) and return model.labels_
        (labels are integers 0..K-1 for clusters; -1 means noise).
    """
    
    model = DBSCAN(eps=EPS, min_samples=min_samples)
    model.fit(points)
    return model.labels_


# ── 3. Cluster Union Buffer Helper ─────────────────────────────────────────────────────

def cluster_union_buffer(points: np.ndarray, eps=EPS):
    """Returns a Shapely Polygon or MultiPolygon: the union of EPS-radius
    circles centred at each point in the cluster."""
    
    shapely_points = [Point(p) for p in points]
    buffers = [p.buffer(eps) for p in shapely_points]
    return unary_union(buffers)

def geometry_to_patches(geometry, color: str, alpha: float = 0.15) -> list:
    """Convert a Shapely Polygon or MultiPolygon into a list of matplotlib
    Polygon patches with the given color.  Returns an empty list for any
    other geometry type (e.g. LineString from a degenerate cluster)."""
    if geometry is None:
        return []
    if geometry.geom_type == 'Polygon':
        geoms = [geometry]
    elif geometry.geom_type == 'MultiPolygon':
        geoms = list(geometry.geoms)
    else:
        return []
    patches = []
    for geom in geoms:
        coords = np.array(geom.exterior.coords)
        patches.append(Polygon(xy=coords, fill=True, facecolor=color,
                               alpha=alpha, edgecolor=color, linewidth=1.5))
    return patches
  

# ── 4. Static Snapshot ────────────────────────────────────────────────────────

def plot_snapshot(points: np.ndarray, labels: np.ndarray) -> None:
    """
    Produce and save the single-frame final result plot.

    Steps:
      - Create a matplotlib figure and axes.
      - Separate noise points (label == -1) and plot them with NOISE_COLOR,
        marker='x', zorder=3.
      - For each unique cluster label (0, 1, 2, …):
          • Pick a color from CLUSTER_COLORS (index by label).
          • Scatter the cluster's points with that color.
          • Call cluster_hull_patch() and add the returned patch to the axes.
      - Build a legend: one entry per cluster ("Cluster 0", "Cluster 1", …)
        plus one "Noise" entry.
      - Set axis labels ("x", "y"), title ("DBSCAN — Final Clusters"), and
        call ax.set_aspect('equal').
      - Save to SNAPSHOT_OUT with dpi=150 and close the figure.
    """
    fig, ax = plt.subplots()

    noise_mask = labels == -1
    if noise_mask.any():
        ax.scatter(points[noise_mask, 0], points[noise_mask, 1],
                   c=NOISE_COLOR, marker='x', zorder=3)

    legend_handles = []
    for label in sorted(set(labels) - {-1}):
        color = CLUSTER_COLORS[label % len(CLUSTER_COLORS)]
        mask = labels == label
        ax.scatter(points[mask, 0], points[mask, 1], c=color, zorder=3)
        geometry = cluster_union_buffer(points[mask])
        for patch in geometry_to_patches(geometry, color):
            ax.add_patch(patch)
        legend_handles.append(mpatches.Patch(color=color, label=f'Cluster {label}'))

    if noise_mask.any():
        legend_handles.append(mpatches.Patch(color=NOISE_COLOR, label='Noise'))

    ax.legend(handles=legend_handles)
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('DBSCAN — Final Clusters')
    ax.set_aspect('equal')
    fig.savefig(SNAPSHOT_OUT, dpi=150)
    plt.close(fig)


# ── 5. Plot Folium Mapping ──────────────────────────────────────────────────────────────

def plot_folium_map(lats: np.ndarray, lons: np.ndarray, labels: np.ndarray) -> None:
    """
    Plot DBSCAN results on an interactive Leaflet map using folium.
    Each point is rendered as a CircleMarker colored by cluster label.
    Noise points (-1) are shown in NOISE_COLOR. Saves to FOLIUM_OUT.
    """
    center_lat = float(lats.mean())
    center_lon = float(lons.mean())
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11)

    for i, (lat, lon, label) in enumerate(zip(lats, lons, labels)):
      if label == -1:
        color = NOISE_COLOR
        tooltip = "Noise"
      else:
        color = CLUSTER_COLORS[int(label) % len(CLUSTER_COLORS)]
        tooltip = f"Cluster {label}"
      folium.CircleMarker(
        location=[lat, lon],
        radius=5,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.8,
        tooltip=tooltip,
      ).add_to(m)

    eps_deg = EPS / 111.32
    for label in sorted(set(labels) - {-1}):
      mask = labels == label
      color = CLUSTER_COLORS[int(label) % len(CLUSTER_COLORS)]
      lonlat_points = np.column_stack([lons[mask], lats[mask]])
      geometry = cluster_union_buffer(lonlat_points, eps=eps_deg)
      folium.GeoJson(
        mapping(geometry),
        style_function=lambda f, c=color: {
          'fillColor': c,
          'color': c,
          'fillOpacity': 0.15,
          'weight': 1.5,
        }
      ).add_to(m)

    m.save(FOLIUM_OUT)
    print(f"Folium map saved to {FOLIUM_OUT}")


# ── 6. Entry Point ────────────────────────────────────────────────────────────

def main():
    """
    Orchestrates the full demo:
      1. load_points()     → (N, 2) array from incidents-small.csv
      2. run_dbscan()
      3. plot_snapshot()   → saves SNAPSHOT_OUT
      4. save_animation()  → saves ANIMATION_OUT
      5. Print a summary: how many clusters found, how many noise points.
    """
    
    option = -1
    if len(sys.argv) > 1:
      option = sys.argv[1]
    
    points, lats, lons, min_samples = load_points()
    labels = run_dbscan(points, min_samples)
    
    if option == -1 or option == "snapshot":
      # plot normal snapshot grid
      plot_snapshot(points, labels)
      
    if option == -1 or option == "mapping":
      # plot mapping of clusters
      plot_folium_map(lats, lons, labels)

    n_clusters = len(set(labels) - {-1})
    n_noise = int((labels == -1).sum())
    print(f'Clusters found: {n_clusters}  |  Noise points: {n_noise}  | min_samples: {min_samples}')


if __name__ == "__main__":
    main()
