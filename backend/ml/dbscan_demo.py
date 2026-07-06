import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Polygon
from scipy.spatial import ConvexHull
from sklearn.cluster import DBSCAN
import folium

# ── Configuration ────────────────────────────────────────────────────────────
# Tweak these to change the shape of the demo without touching any logic.

# Path to the CSV — relative to this file so it works from any cwd.
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv")
N_POINTS = 250           # how many rows to sample from the CSV
RANDOM_SEED = 42          # used only for the random sample so results are reproducible

# EPS is in the same units as the projected coordinates (see load_points).
# After mean-centering and scaling to ~km, a value around 0.3–0.8 is a good start.
EPS         = 0.365         # DBSCAN ε — neighborhood radius
MIN_SAMPLES = 3             # DBSCAN min_samples

'''
Level EPS (km)	MIN_SAMPLES	Rationale
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
    # incidents_20_random_df = incidents_df.sample(n=N_POINTS, random_state=RANDOM_SEED)
    
    lat_mean_rad = np.radians(incidents_df["lat"].mean())
    x = (incidents_df["lon"] - incidents_df["lon"].mean()) * np.cos(lat_mean_rad) * 111.32
    y = (incidents_df["lat"] - incidents_df["lat"].mean()) * 111.32
    
    points = np.column_stack([x, y])
    lats = incidents_df["lat"].to_numpy()
    lons = incidents_df["lon"].to_numpy()
    return points, lats, lons
    


# ── 2. Folium Map ────────────────────────────────────────────────────────────

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

    m.save(FOLIUM_OUT)
    print(f"Folium map saved to {FOLIUM_OUT}")


# ── 2. Run DBSCAN ─────────────────────────────────────────────────────────────

def run_dbscan(points: np.ndarray) -> np.ndarray:
    """
    Fit DBSCAN on the point array and return the label array.

    Steps:
      - Instantiate sklearn.cluster.DBSCAN with eps=EPS, min_samples=MIN_SAMPLES.
      - Call .fit(points) and return model.labels_
        (labels are integers 0..K-1 for clusters; -1 means noise).
    """
    model = DBSCAN(eps=EPS, min_samples=MIN_SAMPLES)
    model.fit(points)
    return model.labels_


# ── 3. Convex Hull Helper ─────────────────────────────────────────────────────

def cluster_hull_patch(points: np.ndarray, color: str, alpha: float = 0.15):
    """
    Given the subset of points belonging to one cluster, return a
    matplotlib Polygon patch tracing the convex hull of those points.

    Steps:
      - If len(points) < 3, skip hull (can't form a polygon) and return None.
      - Use scipy.spatial.ConvexHull(points) to get the hull.
      - Index points[hull.vertices] to get the ordered boundary coordinates.
      - Return a matplotlib.patches.Polygon built from those coordinates,
        with fill=True, facecolor=color, alpha=alpha, edgecolor=color,
        linewidth=1.5.
    """
    if len(points) < 3:
      return None
    
    try:
      hull = ConvexHull(points)
    except:
      return None
    
    return Polygon(xy=points[hull.vertices], fill=True, facecolor=color, alpha=alpha, edgecolor=color, linewidth=1.5)


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
        patch = cluster_hull_patch(points[mask], color)
        if patch is not None:
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


# ── 5. Animation ──────────────────────────────────────────────────────────────

def build_animation_frames(points: np.ndarray, labels: np.ndarray) -> list[dict]:
    """
    Build an ordered list of frame-state dicts that FuncAnimation will consume.
    This simulates DBSCAN's BFS expansion for visualization purposes —
    it does NOT re-run sklearn; it uses the already-computed labels to drive
    the reveal order.

    Frame state dict schema:
        {
          "visited":  set of point indices colored so far,
          "current":  index of the point being "processed" this frame (or None),
          "eps_ring": True if we should draw the ε-circle this frame,
          "cluster_complete": set of cluster ids whose hull should be drawn,
        }

    Steps:
      - Frame 0: visited=empty, current=None, eps_ring=False — all gray dots.
      - Group point indices by label. Process clusters in label order.
        For each cluster:
          - Pick the point with the most neighbors within EPS as the "seed" core.
          - BFS: each iteration = one frame. The frame shows the current point
            highlighted with its ε-circle, then the next frame adds it to visited.
          - Once the cluster queue is empty, emit one "hull reveal" frame
            (eps_ring=False, full cluster colored + hull drawn).
      - After all clusters, process noise points: one frame each, colored gray.
      - Return the list of frame dicts.
    """
    from collections import deque

    frames = []

    # Frame 0: nothing visited
    frames.append({
        'visited': set(),
        'current': None,
        'eps_ring': False,
        'cluster_complete': set(),
    })

    completed_clusters: set = set()
    visited_so_far: set = set()

    cluster_labels = sorted(set(labels) - {-1})
    label_to_indices = {lbl: np.where(labels == lbl)[0].tolist() for lbl in cluster_labels}

    for lbl in cluster_labels:
        indices = label_to_indices[lbl]
        cluster_pts = points[indices]

        # Seed = point with the most neighbors within EPS
        dists = np.linalg.norm(cluster_pts[:, None] - cluster_pts[None, :], axis=2)
        seed_local = int(np.argmax((dists < EPS).sum(axis=1)))
        seed_global = indices[seed_local]

        remaining = sorted([i for i in indices if i != seed_global],
                           key=lambda i: np.linalg.norm(points[i] - points[seed_global]))
        queue = deque([seed_global] + remaining)

        while queue:
            current = queue.popleft()
            frames.append({
                'visited': set(visited_so_far),
                'current': current,
                'eps_ring': True,
                'cluster_complete': set(completed_clusters),
            })
            visited_so_far.add(current)

        completed_clusters = completed_clusters | {lbl}
        frames.append({
            'visited': set(visited_so_far),
            'current': None,
            'eps_ring': False,
            'cluster_complete': set(completed_clusters),
        })

    for i in np.where(labels == -1)[0]:
        frames.append({
            'visited': set(visited_so_far),
            'current': int(i),
            'eps_ring': False,
            'cluster_complete': set(completed_clusters),
        })
        visited_so_far.add(int(i))

    return frames


def animate(frame_idx: int, points: np.ndarray, frames: list[dict], ax) -> list:
    """
    FuncAnimation update function — called once per frame.
    Must clear the axes and redraw the current state from frames[frame_idx].

    Steps:
      - ax.cla() to clear.
      - Re-apply axis labels, title, aspect ratio, and fixed x/y limits
        (compute limits once outside this function so they don't jump).
      - Draw all unvisited points in UNVISITED_COLOR.
      - Draw all visited points colored by their cluster label.
      - If frame["eps_ring"] is True, draw a Circle patch at frame["current"]
        with radius=EPS, fill=False, linestyle='--', color='black'.
      - For each cluster id in frame["cluster_complete"], call
        cluster_hull_patch() and add it to ax.
      - Highlight frame["current"] point with a larger marker if not None.
      - Return a list of all artists drawn (required by FuncAnimation blit=False).
    """
    frame = frames[frame_idx]
    ax.cla()
    ax.set_xlim(ax._xlim_animated)
    ax.set_ylim(ax._ylim_animated)
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('DBSCAN — BFS Expansion')
    ax.set_aspect('equal')

    artists = []
    visited = frame['visited']
    current = frame['current']

    unvisited = [i for i in range(len(points)) if i not in visited and i != current]
    if unvisited:
        artists.append(ax.scatter(points[unvisited, 0], points[unvisited, 1],
                                  c=UNVISITED_COLOR, zorder=2))

    for i in visited:
        color = ax._label_colors.get(i, NOISE_COLOR)
        artists.append(ax.scatter(points[i, 0], points[i, 1], c=color, zorder=3))

    for cid in frame['cluster_complete']:
        mask = ax._cluster_masks[cid]
        color = CLUSTER_COLORS[cid % len(CLUSTER_COLORS)]
        patch = cluster_hull_patch(points[mask], color)
        if patch is not None:
            ax.add_patch(patch)
            artists.append(patch)

    if frame['eps_ring'] and current is not None:
        circle = plt.Circle(points[current], EPS,
                            fill=False, linestyle='--', color='black', zorder=4)
        ax.add_patch(circle)
        artists.append(circle)

    if current is not None:
        color = ax._label_colors.get(current, NOISE_COLOR)
        artists.append(ax.scatter(points[current, 0], points[current, 1],
                                  c=color, s=120, zorder=5,
                                  edgecolors='black', linewidths=1))

    return artists


def save_animation(points: np.ndarray, labels: np.ndarray) -> None:
    """
    Wire up FuncAnimation and save to ANIMATION_OUT.

    Steps:
      - Call build_animation_frames(points, labels) to get the frame list.
      - Create figure and axes; compute and store fixed axis limits
        (min/max of points ± EPS + small padding) so they don't shift mid-animation.
      - Instantiate FuncAnimation(fig, animate, frames=len(frames),
          fargs=(points, frames, ax), interval=ANIM_INTERVAL_MS, repeat=False).
      - Save with anim.save(ANIMATION_OUT, writer='pillow', fps=...).
      - Print a confirmation message.
    """
    frames = build_animation_frames(points, labels)

    fig, ax = plt.subplots()
    pad = EPS * 1.5
    ax._xlim_animated = (points[:, 0].min() - pad, points[:, 0].max() + pad)
    ax._ylim_animated = (points[:, 1].min() - pad, points[:, 1].max() + pad)
    ax._label_colors = {
        i: (CLUSTER_COLORS[lbl % len(CLUSTER_COLORS)] if lbl >= 0 else NOISE_COLOR)
        for i, lbl in enumerate(labels)
    }
    ax._cluster_masks = {
        lbl: np.where(labels == lbl)[0]
        for lbl in set(labels) - {-1}
    }

    fps = max(1, 1000 // ANIM_INTERVAL_MS)
    anim = FuncAnimation(fig, animate, frames=len(frames),
                         fargs=(points, frames, ax),
                         interval=ANIM_INTERVAL_MS, repeat=False)
    anim.save(ANIMATION_OUT, writer='pillow', fps=fps)
    plt.close(fig)
    print(f'Animation saved to {ANIMATION_OUT}')


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
    points, lats, lons = load_points()
    labels = run_dbscan(points)
    plot_snapshot(points, labels)
    plot_folium_map(lats, lons, labels)
    # save_animation(points, labels)

    n_clusters = len(set(labels) - {-1})
    n_noise = int((labels == -1).sum())
    print(f'Clusters found: {n_clusters}  |  Noise points: {n_noise}')


if __name__ == "__main__":
    main()
