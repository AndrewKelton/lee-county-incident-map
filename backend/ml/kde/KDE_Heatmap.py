"""
This module defines class KDE_Heatmap.  The class uses the FFTKDE module from
the KDEpy package to build a KDE (kernel density estimation) 
model for inputs of x-y coordinate data points and bandwidths cooresponding 
to each data point.  It ultimately generates a png image of a KDE heat map.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.colors import PowerNorm
from KDEpy import FFTKDE
from scipy.ndimage import gaussian_filter
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.transform import from_origin

class KDE_Heatmap:
    """Heat map class for generating a png image of a KDE density surface."""

    def __init__(self, points, cluster_levels, bandwidths, x_min, y_min, x_max, y_max, increment):

        self.points = points
        self.cluster_levels = cluster_levels
        self.bandwidths = bandwidths
        self.x_min_lattice = x_min
        self.y_min_lattice = y_min
        self.x_max_lattice = x_max
        self.y_max_lattice = y_max
        self.increment_lattice = increment
        self.x_coords = np.arange(x_min, x_max + increment, increment)
        self.y_coords = np.arange(y_min, y_max + increment, increment)
        xx, yy = np.meshgrid(self.x_coords, self.y_coords, indexing='ij')
        self.lattice = np.column_stack([xx.ravel(), yy.ravel()])
        print(f'lattice.shape = {self.lattice.shape}')
        
        # separate points into clusters (number of clusters may vary from 1 to 3) -1==noise; 0==least dense; 1==denser than 0; 2==denser than 1
        unique_cluster_levels = np.unique(cluster_levels)
        self.points_per_cluster = []
        for cluster_level in unique_cluster_levels:
            # do not includes points associated with noise
            if cluster_level != -1:
                mask = (self.cluster_levels == cluster_level)
                self.points_per_cluster.append(points[mask])

        # instantiate a FFTKDE class, one per bandwidth
        self.kde_obj_per_cluster = []
        for bw in bandwidths:
            obj = FFTKDE(kernel='gaussian', bw=bw)
            self.kde_obj_per_cluster.append(obj)

    def fit_kde_model(self):
        # fit a kde model for each cluster of input data
        if len(self.kde_obj_per_cluster) != len(self.points_per_cluster):
            raise ValueError(
                f"Expected one bandwidth per cluster: got "
                f"{len(self.kde_obj_per_cluster)} bandwidths and "
                f"{len(self.points_per_cluster)} clusters."
            )
        self.kde_model_per_cluster = []
        for kde_obj, points in zip(self.kde_obj_per_cluster, self.points_per_cluster):
            model = kde_obj.fit(data=points)
            self.kde_model_per_cluster.append(model)

    def evaluate_kde_model(self):
        # apply the kde model to the mesh grid
        start = time.perf_counter()
        density_surface_per_cluster = []
        for kde_model in self.kde_model_per_cluster:
            density_surface_per_cluster.append(kde_model.evaluate(grid_points=self.lattice))
        # summation represents the density surface of the full model    
        self.density_surface = np.sum(density_surface_per_cluster, axis=0)
        end = time.perf_counter()
        print(f'time to compute density_surface: {end - start:.4f} seconds')
        print(f'density_surface.shape = {self.density_surface.shape}')

    def generate_heatmap_image(self):
        # reshape the density values to a rectangular grid
        density_grid = self.density_surface.reshape(self.x_coords.shape[0], self.y_coords.shape[0]).T
        # apply gaussian_filter to fix the square/blocky artifact
        density_grid_smoothed = gaussian_filter(density_grid, sigma=2)

        # set a threshold for removing very low density values
        threshold_percentile = np.percentile(density_grid_smoothed, 1)
        threshold_based_on_max = density_grid_smoothed.max() * 0.01
        threshold = max(threshold_percentile, threshold_based_on_max)
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
            extent=[self.x_min_lattice, self.x_max_lattice, self.y_min_lattice, self.y_max_lattice],
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
        transform_src = from_origin(self.x_min_lattice, self.y_max_lattice, self.increment_lattice, self.increment_lattice)

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

        # write the colorized array out to a PNG file
        plt.imsave("density_overlay.png", rgba)

        # being returned to define the bounds for Folium
        return bounds

