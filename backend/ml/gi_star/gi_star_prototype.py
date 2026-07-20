"""
This module was prepared as a prototype demonstration of the G_Local class
of the esda python package for Getis-Ord Gi*.  It ultimately generates a png image of the
Gi* algorithm for a set of x-y coordinates.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from libpysal.weights import DistanceBand, fill_diagonal
from esda.getisord import G_Local

# test input data that represents two x-y coordinates on a map
data_points = np.array([[10.5, 10.5], [20.5, 26.5], [15.1, 15.2], [12.5, 20.1], [22, 15.2], [11, 15.3], [12.6, 16], [12.4, 18.1], [13.3, 17.4], [13.5, 12.9]])

x_len, y_len = 50, 50

# create a x_len x y_len grid where cells will be used as boundaries to count the number of data points for the algorithm
cell_size = 3.0
x_edges = np.arange(0, x_len + cell_size, cell_size)
y_edges = np.arange(0, y_len + cell_size, cell_size)

counts, x_edges, y_edges = np.histogram2d(
    data_points[:, 0], data_points[:, 1], bins=[x_edges, y_edges]
)

# cell centroids, one per grid cell, in the same order as the flattened counts
x_centers = (x_edges[:-1] + x_edges[1:]) / 2
y_centers = (y_edges[:-1] + y_edges[1:]) / 2
cx, cy = np.meshgrid(x_centers, y_centers, indexing='ij')
cell_centroids = np.column_stack([cx.ravel(), cy.ravel()])
y = counts.ravel()  # point count per cell = the attribute Gi* looks for clustering in

# spatial weight matrix using a fixed-distance band and binary weights of 1
distance_threshold = cell_size * 1.5  # neighbors = cell centroids within this radius
w = DistanceBand(cell_centroids, threshold=distance_threshold, binary=True)
w = fill_diagonal(w, val=1.0)  # self-weight = 1, which is what makes this Gi* rather than Gi

# instantiate object of class G_Local to perform the Gi* algorithm
gi_star = G_Local(y, w, transform='R', star=True, permutations=999)

# Zs output represents the observed Gi* which is equivalent to the z-score
z_scores = gi_star.Zs
# p_sim output represents the p-values of each cell for the model simulated random distribution
p_values = gi_star.p_sim

print("Gi* z-scores (grid cells with at least one point):")
for centroid, count, z, p in zip(cell_centroids, y, z_scores, p_values):
    if count > 0:
        print(f"  cell centroid ({centroid[0]:.3f}, {centroid[1]:.3f}): count = {int(count)}, Z = {z:.3f}, p = {p:.3f}")

# reshape z-scores back into the grid shape for imaging
z_grid = z_scores.reshape(counts.shape)

# color map for coloring the heat map
colors = [
    (0.0,   (0, 0, 1, 1)),        # Z = -3 blue
    (0.2,   (0.5, 0.5, 1, 0.6)),  # Z = -1.8 light blue
    (0.5,   (1, 1, 1, 0)),        # Z =  0 fully transparent
    (0.583, (1, 1, 0, 0.15)),     # Z =  0.5 pale yellow
    (0.75,  (1, 1, 0, 0.7)),      # Z =  1.5 yellow
    (0.83, (1, 0.6, 0, 0.85)),   # Z =  2.0 orange
    (0.958, (1, 0, 0, 1)),        # Z =  2.75 bright red
    (1.0,   (1, 0, 0, 1)),        # Z =  3.0: still bright red
]

heat_cmap = LinearSegmentedColormap.from_list('gi_star_fade', colors)

# set the figure size to 8x8
fig, ax = plt.subplots(figsize=(8, 8))
cmap = heat_cmap.copy()
cmap.set_bad(alpha=0)

# diverging norm centered at 0 so blue/red are symmetric around "not significant"
finite_z = z_grid[np.isfinite(z_grid)]
z_abs_max = max(np.abs(finite_z).max(), 1e-6) if finite_z.size else 1.0
norm = TwoSlopeNorm(vmin=-z_abs_max, vcenter=0, vmax=z_abs_max)

# create the image and output as a png file
im = ax.imshow(
    np.ma.masked_invalid(z_grid.T),
    origin='lower',
    extent=[0, x_len, 0, y_len],
    cmap=cmap,
    aspect='equal',
    interpolation='bilinear',
    norm=norm,
)

ax.vlines(x_edges, ymin=0, ymax=y_len, color='gray', linewidth=0.5, alpha=0.5, zorder=3)
ax.hlines(y_edges, xmin=0, xmax=x_len, color='gray', linewidth=0.5, alpha=0.5, zorder=3)

ax.set_xlim(0, x_len)
ax.set_ylim(0, y_len)

ax.scatter(data_points[:, 0], data_points[:, 1], c='black', s=15, zorder=5, label='data points')

fig.colorbar(im, ax=ax, label='Gi* Z-score')
ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_title('Getis-Ord Gi* Hot Spot / Cold Spot Surface')
ax.legend(loc='upper right')

plt.savefig('gi_star_surface_basic.png', dpi=300, bbox_inches='tight', transparent=True)
plt.close()

