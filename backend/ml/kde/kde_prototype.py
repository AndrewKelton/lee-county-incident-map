"""
This module was prepared as a prototype demonstration of the KernDensity class
of the scikit-learn python package.  It ultimately generates an png image of the 
KDE algorithm for a set of x-y coordinates.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.colors import PowerNorm
from sklearn.neighbors import KernelDensity

# test input data that represents two x-y coordinates on a map
data_points = np.array([[10.5, 10.5], [20.5, 26.5], [15, 15.2], [12.5, 20.1], [22, 15], [11, 15], [12, 16], [12.4, 18.1], [13.3, 17.4], [13.5, 12.9]])

# instantiate a KernelDensity class
kde_obj = KernelDensity(bandwidth=1.0, kernel='gaussian')

# fit the kde model to the input data
kde_model = kde_obj.fit(data_points)

# create a x_len x y_len mesh grid (lattice structure) to represent the corrsponding map coordinates
x_len = 50
y_len = 50
increment = 0.01
x_coords = np.arange(increment, x_len, increment)
y_coords = np.arange(increment, y_len, increment)
xx, yy = np.meshgrid(x_coords, y_coords)
lattice = np.column_stack([xx.ravel(), yy.ravel()])

# apply the kde model to the mesh grid - output of the kde model is log(density)
log_density_surface = kde_model.score_samples(lattice)

# reshape the density values to a square grid
density_grid = np.exp(log_density_surface.reshape(x_coords.shape[0], y_coords.shape[0]))

# set a threshold for removing very low density values
threshold_percentile = np.percentile(density_grid, 1)
threshold_max_based = density_grid.max() * 0.01
threshold = max(threshold_percentile, threshold_max_based)
print("threshold = " + str(threshold))
density_grid_masked = np.ma.masked_where(density_grid < threshold, density_grid)

# color map for coloring the heat map
colors = [
    (0, 0, 1, 0),      # transparent blue (lowest density)
    (0, 0, 1, 1),      # opaque blue
    (1, 1, 0, 1),      # yellow
    (1, 0.5, 0, 1),    # orange
    (1, 0, 0, 1),      # red (highest density)
]

heat_cmap = LinearSegmentedColormap.from_list('heat_fade', colors)

# set the figure size to 8-inches x 8-inches
fig, ax = plt.subplots(figsize=(8, 8))
cmap = heat_cmap.copy()
cmap.set_bad(alpha=0)

# create the image and output as a png file
im = ax.imshow(
	density_grid_masked,
	origin='lower',
	extent=[0, x_len, 0, y_len],
	cmap=cmap,
	aspect='equal',
	interpolation='bilinear',
	norm=PowerNorm(gamma=0.5)
)

# ax.axis('off')
fig.colorbar(im, ax=ax, label='Density')
ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_title('KDE Density Surface')

plt.savefig('density_surface.png', dpi=300, bbox_inches='tight', transparent=True)
plt.close()








