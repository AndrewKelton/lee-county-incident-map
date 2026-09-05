"""
This module defines class BandwidthOptimizer, which finds the optimum KDE
bandwidth for each cluster level by mimimizing an objective function derived
from Negative-Log Likelihood (NLL) with Leave-One-Out (LOO) Cross-Validation (CV).
The likelihood is computed from the density surface produced by a KDE model
at the candidate bandwidths, using the FFTKDE class from the KDEpy package.

Note: The current implementation supports optimization for a single cluster
level only; multi-cluster support is not yet implemented.
"""

import numpy as np
from scipy.optimize import minimize
from scipy.interpolate import RegularGridInterpolator
from KDEpy import FFTKDE

class BandwidthOptimizer:

    #explore different starting points - optimizer tends to get stuck on floor value without providing range of starting diff values
    candidate_start_diffs = np.array([10, 100, 1000])
    # lowest acceptable bandwidth value
    lower_bound = 50

    def __init__(self, points, cluster_levels, x_min, y_min, x_max, y_max, increment):

        self.points = points
        self.cluster_levels = cluster_levels
        self.increment_lattice = increment
        self.x_coords = np.arange(x_min, x_max + increment, increment)
        self.y_coords = np.arange(y_min, y_max + increment, increment)  
        # separate points into clusters (number of clusters may vary from 1 to 3) -1==noise; 0==least dense; 1==denser than 0; 2==denser than 1
        unique_cluster_levels = np.unique(cluster_levels)
        self.num_bandwidths = np.count_nonzero(unique_cluster_levels != -1)
        # create array of start diffs, each element is an array of size num_bandwidths
        self.candidate_start_bw_diffs = np.tile(self.candidate_start_diffs[:, None], self.num_bandwidths)
        self.points_per_cluster = []
        for cluster_level in unique_cluster_levels:
            # do not include points associated with noise
            if cluster_level != -1:
                mask = (self.cluster_levels == cluster_level)
                self.points_per_cluster.append(points[mask])

    def _unpack_bandwidths(self, bw_log_diffs: list[float]) -> np.ndarray:
        """function ensures bandwidth bounds for optimization input is 
        array of log(bw_i - bw_i+1) for i<(n-1) and log(val_i+lower_bound) for i==n
        output is array of band widths such that bw_i > bw_i+1 and bw_i > 0"""

        if len(bw_log_diffs) != self.num_bandwidths:
            raise ValueError(
                f"Expected number of bandwidth diffs to match number of bandwidths: got "
                f"{len(bw_log_diffs)} bandwidth diffs while "
                f"number of bandwidths is {self.bandwidths}."
            )
        # reverse such that bandwidth increases as index increases
        reversed_bw_log_diffs = bw_log_diffs[::-1].copy()
        reversed_bandwidths = np.zeros(self.num_bandwidths)
        for i, bw_log_diff in enumerate(reversed_bw_log_diffs):
            if i == 0:
                reversed_bandwidths[i] = self.lower_bound + np.exp(bw_log_diff)
            elif i > 0:
                reversed_bandwidths[i] = reversed_bandwidths[i - 1] + np.exp(bw_log_diff)
        bandwidths = reversed_bandwidths[::-1].copy()
        return bandwidths

    def _gaussian_peak_2d(self, bandwidth):
        """peak value of 2D gaussian distribution for bandwidth input"""
        return 1.0 / (2 * np.pi * bandwidth**2)

    # CURRENTLY DEVELOPED ONLY FOR A SINGLE CLUSTER LEVEL ASSIGNMENT
    def _loo_neg_log_likelihood(self, cur_bw_log_diffs: list[np.ndarray]):
        """objective function for negative log-likelihood of leave-one-out cross-validation for FFTKDE class;
        input is cur_bw_log_diffs = array of log bandwidth differences
        output is negative log-likelihood for current bandwidths"""

        try:
            bandwidth1 = self._unpack_bandwidths(cur_bw_log_diffs)[0]
            N = len(self.points_per_cluster[0])
            bw_per_point = np.full(N, bandwidth1)

            xx, yy = np.meshgrid(self.x_coords, self.y_coords, indexing='ij')
            grid = np.column_stack([xx.ravel(), yy.ravel()])

            # density of the grid
            f_grid = FFTKDE(kernel='gaussian', bw=bandwidth1).fit(self.points_per_cluster[0]).evaluate(grid)
            f_grid_2d = f_grid.reshape(self.x_coords.shape[0], self.y_coords.shape[0])

            # interpolate density surface at input data points
            interpolator = RegularGridInterpolator(
                (self.x_coords, self.y_coords), f_grid_2d, bounds_error=False, fill_value=1e-300
            )
            f_at_points = interpolator(self.points_per_cluster[0])

            # represents the gaussian corresponding to each data point
            self_term = self._gaussian_peak_2d(bw_per_point) / N

            # leave-one-out density
            f_loo = (N * f_at_points - N * self_term) / (N - 1)
            # set values < 1e-300 to 1e-300 (namely to guard against log(0)
            f_loo = np.clip(f_loo, 1e-300, None)

            # negative log-likelihood
            return -np.sum(np.log(f_loo))
        except (ValueError, FloatingPointError):
            # large penalty to protect against the minimizer searching extremely large bandwidth values that cause an error with FFTKDE
            return 1e10
   
    def optimize_bandwidths(self):
        """function finds the optimum bandwidth over a range of smallest bandwidths"""

        self.best_result = None

        for bw_guess_diffs in self.candidate_start_bw_diffs:
            initial_bw_log_diffs = np.log(bw_guess_diffs)
            res = minimize(self._loo_neg_log_likelihood, initial_bw_log_diffs, args=(), method='Nelder-Mead')
            if self.best_result is None or res.fun < self.best_result.fun:
                self.best_result = res

        print("best objective:", self.best_result.fun)
        print("best bandwidth:", self._unpack_bandwidths(self.best_result.x))

        return self._unpack_bandwidths(self.best_result.x)


