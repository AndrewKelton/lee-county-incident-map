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


# instantiate a FFTKDE class
kde_obj = FFTKDE(kernel='gaussian', bw=1500.0)

# fit the kde model to the input data
kde_model = kde_obj.fit(data=data_points_without_noise)

# create a mesh grid (lattice structure) to represent the corrsponding map coordinates
padding = 100
x_min = np.min(easting) - padding
x_max = np.max(easting) + padding
y_min = np.min(northing) - padding
y_max = np.max(northing) + padding
p_bandwidth = 5
print(f'p_bandwidth = {p_bandwidth} corresponds to error tolerance of {100 * (1 - np.exp(-1 / (4 * p_bandwidth**2)))} percent')
increment = kde_obj.bw / p_bandwidth
print(f'kde_obj.bw = {kde_obj.bw}')
print(f'increment = {increment}')
x_coords = np.arange(x_min, x_max + increment, increment)
y_coords = np.arange(y_min, y_max + increment, increment)
xx, yy = np.meshgrid(x_coords, y_coords, indexing='ij')
lattice = np.column_stack([xx.ravel(), yy.ravel()])
print(f'lattice.shape = {lattice.shape}')

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






