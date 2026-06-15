import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Polygon
from scipy.spatial import ConvexHull
from sklearn.cluster import DBSCAN

# ── Configuration ────────────────────────────────────────────────────────────
# Tweak these to change the shape of the demo without touching any logic.

# Path to the CSV — relative to this file so it works from any cwd.
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "incidents-small.csv")
N_POINTS = 20             # how many rows to sample from the CSV
RANDOM_SEED = 42          # used only for the random sample so results are reproducible

# EPS is in the same units as the projected coordinates (see load_points).
# After mean-centering and scaling to ~km, a value around 0.3–0.8 is a good start.
EPS         = 0.5         # DBSCAN ε — neighborhood radius
MIN_SAMPLES = 2           # DBSCAN min_samples

SNAPSHOT_OUT     = "dbscan_snapshot.png"
ANIMATION_OUT    = "dbscan_animation.gif"
ANIM_INTERVAL_MS = 600    # milliseconds between animation frames

# ── Color palette ─────────────────────────────────────────────────────────────
CLUSTER_COLORS = ["#E63946", "#2A9D8F", "#E9C46A", "#457B9D", "#F4A261"]
NOISE_COLOR    = "#AAAAAA"
UNVISITED_COLOR = "#CCCCCC"


# ── 1. Data Loading ──────────────────────────────────────────────────────────

def load_points() -> np.ndarray:
    """
    Load N_POINTS incidents from incidents-small.csv and return a (N, 2)
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
    incidents_df = pd.read_csv(CSV_PATH)
    incidents_20_random_df = incidents_df.sample(n=N_POINTS, random_state=RANDOM_SEED)
    
    lat_mean_rad = np.radians(incidents_20_random_df["lat"].mean())
    x = (incidents_20_random_df["lon"] - incidents_20_random_df["lon"].mean()) * np.cos(lat_mean_rad) * 111.32
    y = (incidents_20_random_df["lat"] - incidents_20_random_df["lat"].mean()) * 111.32
    
    points = np.column_stack([x, y])
    return points
    


# ── 2. Run DBSCAN ─────────────────────────────────────────────────────────────

def run_dbscan(points: np.ndarray) -> np.ndarray:
    """
    Fit DBSCAN on the point array and return the label array.

    Steps:
      - Instantiate sklearn.cluster.DBSCAN with eps=EPS, min_samples=MIN_SAMPLES.
      - Call .fit(points) and return model.labels_
        (labels are integers 0..K-1 for clusters; -1 means noise).
    """
    pass


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
    pass


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
    pass


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
    pass


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
    pass


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
    pass


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
    pass


if __name__ == "__main__":
    main()
