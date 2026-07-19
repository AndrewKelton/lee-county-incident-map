"""
This module was prepared as a prototype demonstration of the FFTKDE class
of the KDEpy python package.  It ultimately generates an png image of the 
KDE algorithm for a set of x-y coordinates from a sample of County incident report data.
Then takes the image data and overlays the image data onto a folium map which
is a wrapper of the Leaflet javascript library.
"""

import os
import time
import pandas as pd
import numpy as np
from pyproj import Transformer
from scipy.optimize import minimize
from scipy.interpolate import RegularGridInterpolator
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.colors import PowerNorm
from KDEpy import FFTKDE
from scipy.ndimage import gaussian_filter
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.transform import from_origin
import folium

# REPLACE CLUSTER LEVEL ASSIGNMENTS WITH CALL TO DBSCAN MODULE DURING APP INTEGRATION
# cluster level for testing (-1 == noise; 0 = less dense; 1 = more dense)
dbscan_cluster_level = np.array([0, 0, 1, 1, 1, 1, 1, -1, 1, -1, 1, 0, 1, 1, 0, 1, 1, 0, -1, 1, 1, 
                        0, 0, 0, -1, 1, 1, 1, 0, 1, 1, -1, 1, 1, 1, 1, 0, 1, 1, 0, 1, 0, 
                        0, 1, -1, 1, 1, 1, 1, 1, -1, 1, 1, 0, 1, -1, 0, 1, 1, 0, 1, 1, 1, 
                        1, 1, -1, 0, 1, 0, 1, 1, -1, 1, 1, 1, 1, 0, 0, 0, 0, -1, 1, 1, 0, 
                        -1, 0, 1, 1, -1, 1, 0, -1, -1, 1, 0, 1, 1, -1, 1, -1, 1, 1, 1, 1, 
                        -1, 1, 0, 1, 1, 0, 1, 0, -1, 1, 0, 0, 1, 1, -1, 0, -1, 1, 1, 1, -1, 
                        1, 0, 1, -1, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, -1, 1, 0, 1, 1, 1, 1, 1, 
                        -1, 1, 1, 0, 0, 1, 1, 0, 1, 1, 0, 1, -1, 1, 1, 1, -1, 1, 0, 1, -1, 
                        -1, 0, 0, 1, 1, -1, 0, 0, -1, 1, 1, -1, 1, 1, 1, 1, 0, 0, -1, 0, 1, 
                        1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 0, 1, 0, 1, 1, 
                        1, 1, -1, -1, -1, 1, 0, 0, 1, 1, -1, 1, 1, 0, 0, 0, 1, -1, -1, 0, 1, 
                        -1, -1, -1, -1, -1, 1, 1, 1, 1, 1, 1, -1, 1, 0, 1, -1, 0])

#CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv")
CSV_PATH = os.path.join(
    os.path.dirname(__file__), 
    "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv"
)

def load_points() -> np.ndarray:
    """
    Load N_POINTS incidents from late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv and return a (N, 2)
    array of projected x/y coordinates suitable for euclidean distance.
    """

    incidents_df = pd.read_csv(CSV_PATH).dropna(subset=["lat", "lon"])
    
    latitude = incidents_df["lat"].to_numpy()
    longitude = incidents_df["lon"].to_numpy()

    # NAD 1983 StatePlane Florida West FIPS 0902 Feet
    transformer = Transformer.from_crs("EPSG:4269", "EPSG:2882", always_xy=True)
    easting, northing = transformer.transform(longitude, latitude)

    points = np.column_stack([easting, northing])
    
    return points, latitude, longitude

# function ensures bandwidth bounds for optimization
# input is array of log(bw_i - bw_i+1) for i<(n-1) and log(val_i+lower_bound) for i==n
# output is array of bandwidths such that bw_i > bw_i+1 and bw_i > 0
def unpack_bandwidths(bw_diffs: list[float]) -> np.ndarray:
    lower_bound = 50
    # density increases as index increases (lower density corresponds to higher bandwidth)
    num_bandwidths = len(bw_diffs)
    reversed_bw_diffs = bw_diffs[::-1].copy()
    reversed_bandwidths = np.zeros(num_bandwidths)
    for i, bw_diff in enumerate(reversed_bw_diffs):
        if i == 0:
            reversed_bandwidths[i] = lower_bound + np.exp(bw_diff)
        elif i > 0:
            reversed_bandwidths[i] = reversed_bandwidths[i - 1] + np.exp(bw_diff)
    bandwidths = reversed_bandwidths[::-1].copy()
    return bandwidths

# peak value of 2D gaussian distribution for bandwidth input
def gaussian_peak_2d(bandwidth):
    return 1.0 / (2 * np.pi * bandwidth**2)

# objective function for negative log-likelihood of leave-one-out cross-validation for FFTKDE class
# input is cur_bw_diffs = array of log bandwidth differences (see the 'unpack_bandwidths' function), point_groups = list of array of x-y coordinates for each cluster level, x_grid and y_grid are x and y coordinates to form lattice
# output is negative log-likelihood for current bandwidths
# CURRENTLY DEVELOPED ONLY FOR A SINGLE CLUSTER LEVEL ASSIGNMENT
def loo_neg_log_likelihood(cur_bw_diffs: np.ndarray, point_groups: list[np.ndarray], x_grid: np.ndarray, y_grid: np.ndarray):
    try:
        bandwidth1 = unpack_bandwidths(cur_bw_diffs)[0]
        N = len(point_groups[0])
        bw_per_point = np.full(N, bandwidth1)

        xx, yy = np.meshgrid(x_grid, y_grid, indexing='ij')
        grid = np.column_stack([xx.ravel(), yy.ravel()])

        # density of the grid
        f_grid = FFTKDE(kernel='gaussian', bw=bandwidth1).fit(point_groups[0]).evaluate(grid)
        f_grid_2d = f_grid.reshape(x_grid.shape[0], y_grid.shape[0])

        # interpolate density surface at input data points
        interpolator = RegularGridInterpolator(
            (x_grid, y_grid), f_grid_2d, bounds_error=False, fill_value=1e-300
        )
        f_at_points = interpolator(point_groups[0])

        # represents the gaussian corresponding to each data point
        self_term = gaussian_peak_2d(bw_per_point) / N

        # leave-one-out density
        f_loo = (N * f_at_points - N * self_term) / (N - 1)
        # set values < 1e-300 to 1e-300 (namely to guard against log(0)
        f_loo = np.clip(f_loo, 1e-300, None)

        # negative log-likelihood
        return -np.sum(np.log(f_loo))
    except(ValueError, FloatingPointError):
        # large penalty to protect against the minimizer searching extremely large bandwidth values that cause an error with FFTKDE
        return 1e10


# input data based on a sample of x-y coordinates (easting/northing) from County incident data
data_points_with_noise, latitude, longitude = load_points()
easting = data_points_with_noise[:, 0]
northing = data_points_with_noise[:, 1]

mask_noise = (dbscan_cluster_level != -1)
data_points_without_noise = data_points_with_noise[mask_noise]


'''

# data points separated into their corresponding cluster levels (as defined from DBSCAN)
# index 0 is least dense; density increases as index increases
num_cluster_levels = np.max(dbscan_cluster_level) + 1
print(f'num_cluster_levels = {num_cluster_levels}')
data_points_per_cluster_level = []
for i in range(0, num_cluster_levels):
    mask = (dbscan_cluster_level == i)
    temp_arr = data_points_with_noise[mask]
    data_points_per_cluster_level.append(temp_arr)
'''


# create a mesh grid (lattice structure) to represent the corrsponding map coordinates
padding = 100
x_min = np.min(easting) - padding
x_max = np.max(easting) + padding
y_min = np.min(northing) - padding
y_max = np.max(northing) + padding
increment = 300
print(f'increment = {increment}')
x_coords = np.arange(x_min, x_max + increment, increment)
y_coords = np.arange(y_min, y_max + increment, increment)
xx, yy = np.meshgrid(x_coords, y_coords, indexing='ij')
lattice = np.column_stack([xx.ravel(), yy.ravel()])
print(f'lattice.shape = {lattice.shape}')

#bandwidth optimization (explore different starting points - optimizer tends to get stuck on floor value without providing range of starting values for lowest bandwidth)
candidate_starts_lowest_bw = [10, 100, 1000]
best_result = None

for bw_guess in candidate_starts_lowest_bw:
    initial_bw_diffs = np.log([bw_guess])
    res = minimize(loo_neg_log_likelihood, initial_bw_diffs, args=([data_points_without_noise], x_coords, y_coords), method='Nelder-Mead')
    if best_result is None or res.fun < best_result.fun:
        best_result = res

print("best objective:", best_result.fun)
print("best bandwidth:", unpack_bandwidths(best_result.x))

optimized_bandwidth = unpack_bandwidths(best_result.x)[0]


print(f'optimized_bandwidth = {optimized_bandwidth}')
p_bandwidth = optimized_bandwidth / increment
print(f'p_bandwidth = {p_bandwidth} corresponds to error tolerance of {100 * (1 - np.exp(-1 / (4 * p_bandwidth**2)))} percent')

# instantiate a FFTKDE class
kde_obj = FFTKDE(kernel='gaussian', bw=optimized_bandwidth)

# fit the kde model to the input data
kde_model = kde_obj.fit(data=data_points_without_noise)

# apply the kde model to the mesh grid (store output as log(density))
start = time.perf_counter()
density_surface = kde_model.evaluate(grid_points=lattice)
end = time.perf_counter()

print(f'time to compute density_surface: {end - start:.4f} seconds')
print(f'density_surface.shape = {density_surface.shape}')

# reshape the density values to a rectangular grid
density_grid = density_surface.reshape(x_coords.shape[0], y_coords.shape[0]).T
# Then apply gaussian_filter to fix the square/blocky artifact
density_grid_smoothed = gaussian_filter(density_grid, sigma=2)

# set a threshold for removing very low density values
threshold_percentile = np.percentile(density_grid_smoothed, 1)
threshold_max_based = density_grid_smoothed.max() * 0.01
threshold = max(threshold_percentile, threshold_max_based)
print("threshold = " + str(threshold))
density_grid_masked = np.ma.masked_where(density_grid_smoothed < threshold, density_grid_smoothed)

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
	extent=[x_min, x_max, y_min, y_max],
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


# transform from pixel coordinates to real-world spatial coordinates
transform_src = from_origin(x_min, y_max, increment, increment)

src_meta = {
    "driver": "GTiff",
    "height": density_grid_masked.shape[0],
    "width": density_grid_masked.shape[1],
    "count": 1,
    "dtype": "float32",
    "crs": "EPSG:2882",
    "transform": transform_src
}

# create tif file with the masked density surface values and coordinates
with rasterio.open("density_src.tif", "w", **src_meta) as dst:
    dst.write(np.flipud(density_grid_masked.filled(0)).astype("float32"), 1)

# re-project the tif file into latitude/longitude coordinate system
with rasterio.open("density_src.tif") as src:
    dst_transform, width, height = calculate_default_transform(
        src.crs, "EPSG:4326", src.width, src.height, *src.bounds
    )
    dst_meta = src.meta.copy()
    dst_meta.update({
        "crs": "EPSG:4326",
        "transform": dst_transform,
        "width": width,
        "height": height,
    })

    with rasterio.open("density_wgs84.tif", "w", **dst_meta) as dst:
        reproject(
            source=rasterio.band(src, 1),
            destination=rasterio.band(dst, 1),
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs="EPSG:4326",
            resampling=Resampling.bilinear,
        )

# retrieve the pixel values and min/max boundary coordinates from the tif file
with rasterio.open("density_wgs84.tif") as src:
    warped = src.read(1)
    bounds = src.bounds  # left, bottom, right, top in lat/lon

# normalization object that maps data values from 0 to 1 range
norm = PowerNorm(gamma=0.5)(warped)
# apply color-coding from png file to the latitude/longitude re-projection
rgba = cmap(norm)

# create a map centered on the boundaries of the density surface values
m = folium.Map(location=[(bounds.top + bounds.bottom)/2, (bounds.left + bounds.right)/2], zoom_start=12)

# lay the colorized image of the lat/long re-projected tif file onto the map
folium.raster_layers.ImageOverlay(
    image=rgba,
    bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
    opacity=0.8,
).add_to(m)

m.save("heatmap.html")






