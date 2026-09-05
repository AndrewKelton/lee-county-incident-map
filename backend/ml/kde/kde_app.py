"""
This module is the driver script for generating a KDE-based incident heat map.
It loads incident location data, uses BandwidthOptimizer to find the optimum
KDE bandwidth per cluster level, and instantiates a KDEHeatMap object to
generate a PNG heat map image.  This image is then overlaid onto a folium map,
a Python wrapper around the Leaflet JavaScript library.
"""

from KDEHeatMap import KDEHeatMap
from BandwidthOptimizer import BandwidthOptimizer
import os
import pandas as pd
import numpy as np
from pyproj import Transformer
import folium


#----------------------KDE heatmap overflay generated below--------------------------------------------------------------------

def load_points() -> np.ndarray:
    """
    Load N_POINTS incidents from late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv and return a (N, 2)
    array of projected x/y coordinates suitable for euclidean distance.
    """

    incidents_df = pd.read_csv(CSV_PATH).dropna(subset=["lat", "lon"])
    
    latitude = incidents_df["lat"].to_numpy()
    longitude = incidents_df["lon"].to_numpy()

    # NAD 1983 StatePlane Florida West FIPS 0902 Feet
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)
    easting, northing = transformer.transform(longitude, latitude)

    points = np.column_stack([easting, northing])
    
    return points, latitude, longitude


# REPLACE CLUSTER LEVEL ASSIGNMENTS WITH CALL TO DBSCAN MODULE DURING APP INTEGRATION
# cluster level for testing (-1 == noise; 0 = least dense; 1 = denser than 0)
dbscan_cluster_levels = np.array([0, 0, 1, 1, 1, 1, 1, -1, 1, -1, 1, 0, 1, 1, 0, 1, 1, 0, -1, 1, 1, 
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

# TESTING - reallocate all non-noise points to the same cluster (i.e. cluster == 0)
dbscan_cluster_levels[dbscan_cluster_levels == 1] = 0

#CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv")
CSV_PATH = os.path.join(
    os.path.dirname(__file__), 
    "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv"
)

# input data based on a sample of x-y coordinates (easting/northing) from County incident data
data_points_with_noise, latitude, longitude = load_points()
easting = data_points_with_noise[:, 0]
northing = data_points_with_noise[:, 1]
mask_noise = (dbscan_cluster_levels != -1)
data_points_without_noise = data_points_with_noise[mask_noise]

# define range of mesh grid (lattice structure) to represent the corresponding map coordinates
padding = 100
x_min = np.min(easting) - padding
x_max = np.max(easting) + padding
y_min = np.min(northing) - padding
y_max = np.max(northing) + padding
increment = 300
print(f'increment = {increment}')

# find optimized bandwidth
optimized_bandwidths = BandwidthOptimizer(data_points_with_noise, dbscan_cluster_levels, x_min, y_min, x_max, y_max, increment).optimize_bandwidths()
print(f'optimized_bandwidths = {optimized_bandwidths}')

p_bandwidth = optimized_bandwidths / increment
print(f'p_bandwidth = {p_bandwidth} corresponds to error tolerance of {100 * (1 - np.exp(-1 / (p_bandwidth**2)))} percent')


# instantiate a KDE object
kde_obj = KDEHeatMap(points=data_points_with_noise, cluster_levels=dbscan_cluster_levels, bandwidths=optimized_bandwidths, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, increment=increment)
# fit the KDE model
kde_obj.fit_kde_model() 
# evaluate the KDE model
kde_obj.evaluate_kde_model()
# generate the heat map overlay PNG image file
bounds = kde_obj.generate_heatmap_image()
print(f'bounds = {bounds}')




#----------------------API functionality below--------------------------------------------------------------------

# API will transmit PNG image file (as URL or base64-encoded string) and boundary coordinates to frontend as JSON

#----------------------Frontend functionality below---------------------------------------------------------------

# create a map centered on the boundaries of the density surface values
m = folium.Map(location=[(bounds.top + bounds.bottom)/2, (bounds.left + bounds.right)/2], zoom_start=12)

# lay the colorized PNG image of the lat/long re-projected tif file onto the map
folium.raster_layers.ImageOverlay(
    image="density_overlay.png",
    bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
    opacity=0.8,
).add_to(m)

m.save("heatmap.html")






