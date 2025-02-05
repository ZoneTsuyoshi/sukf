"""
======================================================
Inference with Expectation Maximization Kalman Filter
======================================================
This module implements the Expectation Maximization Kalman Filter
for Linear-Gaussian state space models
"""

import math

import numpy as np

from utils import array1d, array2d
from util_functions import _parse_observations, _last_dims, \
    _determine_dimensionality


class ExpectationMaximizationKalmanFilter(object) :
    """Implements the EMKF.
    This class implements the expectation maximization Kalman filter
    for a Linear Gaussian model specified by,
    .. math::
        x_{t+1}   &= F_{t} x_{t} + b_{t} + v_{t} \\
        y_{t}     &= H_{t} x_{t} + d_{t} + w_{t} \\
        [v_{t}, w_{t}] &\sim N(0, [[Q_{t}, O], [O, R_{t}]])
    The Kalman Filter is an algorithm designed to estimate
    :math:`P(x_t | y_{0:t})`.  As all state transitions and observations are
    linear with Gaussian distributed noise, these distributions can be
    represented exactly as Gaussian distributions with mean
    `x_filt[t]` and covariances `V_filt[t]`.
    Similarly, the Kalman Smoother is an algorithm designed to estimate
    :math:`P(x_t | y_{0:T-1})`.

    Args:
        observation [n_time, n_dim_obs] {numpy-array, float}
            also known as :math:`y`. observation value
        initial_mean [n_dim_sys] {float} 
            also known as :math:`\mu_0`. initial state mean
        initial_covariance [n_dim_sys, n_dim_sys] {numpy-array, float} 
            also known as :math:`\Sigma_0`. initial state covariance
        transition_matrices [n_dim_sys, n_dim_sys] 
            or [n_dim_sys, n_dim_sys]{numpy-array, float}
            also known as :math:`F`. transition matrix from x_{t-1} to x_{t}
        observation_matrices [n_time, n_dim_sys, n_dim_obs] or [n_dim_sys, n_dim_obs]
             {numpy-array, float}
            also known as :math:`H`. observation matrix from x_{t} to y_{t}
        transition_covariance [n_time - 1, n_dim_noise, n_dim_noise]
             or [n_dim_sys, n_dim_noise]
            {numpy-array, float}
            also known as :math:`Q`. system transition covariance for times
        observation_covariance [n_time, n_dim_obs, n_dim_obs] {numpy-array, float} 
            also known as :math:`R`. observation covariance for times.
        update_interval {int}
            : interval of update transition matrix F
        eta (in (0,1])
            : update rate for transition matrix F
        cutoff {float}
            : cutoff distance for update transition matrix F
        etab (in (0,1])
            : update rate for transition offset b
        cutoffb {float}
            : cutoff distance for update transition offset b
        em_vars {list, string}
            variable name list for EM algorithm. subset of ['transition_matrices', \
            'observation_matrices', 'transition_offsets', 'observation_offsets', \
            'transition_covariance', 'observation_covariance', 'initial_mean', \
            'initial_covariance']
        iteration {int}
            : number of iterations for EM algorithm
        mode {str}
            : update mode of EMKF
            "smooth": normal mode, using smoothed value while caluculating M-step
            "filter": substituting filtered for smoothed while calculating M-step
        n_dim_sys {int}
            : dimension of system transition variable
        n_dim_obs {int}
            : dimension of observation variable
        dtype {type}
            : data type of numpy-array
        use_gpu {bool}
            wheather use gpu and cupy.
            if True, you need install package `cupy`.
            if False, set `numpy` for calculation.

    Attributes:
        y : `observation`
        F : `transition_matrices`
        Q : `transition_covariance`
        H : `observation_matrices`
        R : `observation_covariance`
    """

    def __init__(self, observation = None,
                initial_mean = None, initial_covariance = None,
                transition_matrices = None, observation_matrices = None,
                transition_covariance = None, observation_covariance = None,
                transition_offsets = None, observation_offsets = None,
                update_interval = 1, eta = 0.1, cutoff = 0.1, etab = 0.1, cutoffb=0.1,
                iteration = 1,
                store_transition_matrices_on = True,
                em_vars = ["F"],
                mode = "smooth",
                n_dim_sys = None, n_dim_obs = None, dtype = "float32",
                use_gpu = False):
        """Setup initial parameters.
        """
        self.use_gpu = use_gpu
        if use_gpu:
            import cupy
            self.xp = cupy
        else:
            self.xp = np

        # determine dimensionality
        self.n_dim_sys = _determine_dimensionality(
            [(transition_matrices, array2d, -2),
             (initial_mean, array1d, -1),
             (initial_covariance, array2d, -2),
             (observation_matrices, array2d, -1)],
            n_dim_sys
        )

        self.n_dim_obs = _determine_dimensionality(
            [(observation_matrices, array2d, -2),
             (observation_covariance, array2d, -2)],
            n_dim_obs
        )

        self.y = self.xp.asarray(observation)

        if initial_mean is None:
            self.initial_mean = self.xp.zeros(self.n_dim_sys, dtype = dtype)
        else:
            self.initial_mean = initial_mean.astype(dtype)
        
        if initial_covariance is None:
            self.initial_covariance = self.xp.eye(self.n_dim_sys, dtype = dtype)
        else:
            self.initial_covariance = initial_covariance.astype(dtype)

        if transition_matrices is None:
            self.F = self.xp.eye(self.n_dim_sys, dtype = dtype)
        else:
            self.F = transition_matrices.astype(dtype)

        if transition_covariance is not None:
            self.Q = transition_covariance.astype(dtype)
        else:
            self.Q = self.xp.eye(self.n_dim_sys, dtype = dtype)

        if observation_matrices is None:
            self.H = self.xp.eye(self.n_dim_obs, self.n_dim_sys, dtype = dtype)
        else:
            self.H = observation_matrices.astype(dtype)
        
        if observation_covariance is None:
            self.R = self.xp.eye(self.n_dim_obs, dtype = dtype)
        else:
            self.R = observation_covariance.astype(dtype)

        if transition_offsets is None :
            self.b = self.xp.zeros(self.n_dim_sys, dtype = dtype)
        else :
            self.b = transition_offsets.astype(dtype)

        if observation_offsets is None :
            self.d = self.xp.zeros(self.n_dim_obs, dtype = dtype)
        else :
            self.d = observation_offsets.astype(dtype)

        if mode in ["filter", "smooth"]:
            self.mode = mode
        else:
            raise ValueError("Your choice \"{}\" is mistaken. " 
                            + "You can only select \"filter\" or \"smooth\" mode.")


        self.tau = int(update_interval)
        self.store_transition_matrices_on = store_transition_matrices_on

        if store_transition_matrices_on:
            self.Fs = self.xp.zeros(((len(self.y)-1)//self.tau+1+1,
                                self.F.shape[0], self.F.shape[1]))
            self.Fs[0] = self.F

        self.em_vars = []
        if "F" in em_vars or "transition_matrices" in em_vars:
            self.em_vars.append("F")
        if "b" in em_vars or "transition_offsets" in em_vars:
            self.em_vars.append("b")

        self.iteration = iteration
        self.eta = eta
        self.cutoff = cutoff
        self.etab = etab
        self.cutoffb = cutoffb
        self.dtype = dtype


    def forward(self):
        """Calculate prediction and filter for observation times.

        Attributes:
            T {int}
                : length of data y
            x_pred [n_time, n_dim_sys] {numpy-array, float}
                : mean of hidden state at time t given observations
                 from times [0...t-1]
            V_pred [n_time, n_dim_sys, n_dim_sys] {numpy-array, float}
                : covariance of hidden state at time t given observations
                 from times [0...t-1]
            x_filt [n_time, n_dim_sys] {numpy-array, float}
                : mean of hidden state at time t given observations from times [0...t]
            V_filt [n_time, n_dim_sys, n_dim_sys] {numpy-array, float}
                : covariance of hidden state at time t given observations
                 from times [0...t]
            x_smooth [n_time, n_dim_sys] {numpy-array, float}
                : mean of hidden state distributions for times
                 [0...n_times-1] given all observations
            V_smooth [n_time, n_dim_sys, n_dim_sys] {numpy-array, float}
                : covariances of hidden state distributions for times
                 [0...n_times-1] given all observations
            V_pair [n_time, n_dim_sys, n_dim_sys] {numpy-array, float}
                : Covariance between hidden states at times t and t-1
                 for t = [1...n_timesteps-1].  Time 0 is ignored.
        """

        T = self.y.shape[0]
        self.x_pred = self.xp.zeros((T, self.n_dim_sys), dtype = self.dtype)
        self.V_pred = self.xp.zeros((T, self.n_dim_sys, self.n_dim_sys),
             dtype = self.dtype)
        self.x_filt = self.xp.zeros((T, self.n_dim_sys), dtype = self.dtype)
        self.V_filt = self.xp.zeros((T, self.n_dim_sys, self.n_dim_sys),
             dtype = self.dtype)
        self.x_smooth = self.xp.zeros((T, self.n_dim_sys), dtype = self.dtype)
        self.V_smooth = self.xp.zeros((T, self.n_dim_sys, self.n_dim_sys),
             dtype = self.dtype)
        self.V_pair = self.xp.zeros((T, self.n_dim_sys, self.n_dim_sys),
             dtype = self.dtype)

        # initial setting
        self.x_pred[0] = self.initial_mean.copy()
        self.V_pred[0] = self.initial_covariance.copy()


        # calculate prediction and filter for every time
        # for t in range(T):
        if self.mode=="smooth":
            for s in range(0, T, self.tau):
                F_est = self.F.copy()
                if s!=0:
                    self._predict_update(s, F_est)
                self._filter_update(s)

                for n in range(self.iteration):
                    if n!=0:
                        self.x_pred[s] = self.x_smooth[s].copy()
                        self.V_pred[s] = self.V_smooth[s] \
                                    - self.xp.outer(self.x_smooth[s], self.x_smooth[s])
                    for t in range(s+1, min(s + self.tau + 1, T)):
                        # visualize calculating time
                        print("\r filter calculating... t={}".format(t) + "/" + str(T), end="")
                        self._predict_update(t, F_est)
                        self._filter_update(t)
                    F_est = self._update_transition_matrix(t, len(range(s, min(s + self.tau + 1, T))) - 1, F_est)

                # update transition matrix
                self.F = self.F - self.eta * self.xp.minimum(self.xp.maximum(-self.cutoff, self.F - F_est),
                                                            self.cutoff)
                if self.store_transition_matrices_on:
                    self.Fs[s//self.tau+1] = self.F
        elif self.mode=="filter":
            self._filter_update(0)

            for t in range(1, T):
                print("\r filter calculating... t={}".format(t) + "/" + str(T), end="")
                if (t-1)%self.tau == 0 and t < T-self.tau:
                    for s in range(t, t+self.tau+1):
                        self._predict_update(s)
                        self._filter_update(s)
                    self._update_transition_matrix_approximately(t)
                self._predict_update(t)
                self._filter_update(t)



    def _predict_update(self, t, F=None):
        """Calculate fileter update

        Args:
            t {int} : observation time
        """
        # extract parameters for time t-1
        if F is None:
            F = _last_dims(self.F, t - 1, 2)
        Q = _last_dims(self.Q, t - 1, 2)
        b = _last_dims(self.b, t - 1, 1)

        # calculate predicted distribution for time t
        self.x_pred[t] = F @ self.x_filt[t-1] + b
        self.V_pred[t] = F @ self.V_filt[t-1] @ F.T + Q


    def _predict_update_pair(self, t, F=None):
        """Calculate fileter update

        Args:
            t {int} : observation time
        """
        # extract parameters for time t-1
        if F is None:
            F = _last_dims(self.F, t - 1, 2)
        Q = _last_dims(self.Q, t - 1, 2)
        b = _last_dims(self.b, t - 1, 1)

        # calculate predicted distribution for time t
        self.x_pred[t] = F @ self.x_filt[t-1] + b
        self.V_pred[t] = F @ self.V_filt[t-1] @ F.T + Q
        self.V_pair[t] = self.V_filt[t-1] @ F.T


    def _filter_update(self, t):
        """Calculate fileter update without noise

        Args:
            t {int} : observation time

        Attributes:
            K [n_dim_sys, n_dim_obs] {numpy-array, float}
                : Kalman gain matrix for time t
        """
        # extract parameters for time t
        H = _last_dims(self.H, t, 2)
        R = _last_dims(self.R, t, 2)
        d = _last_dims(self.d, t, 1)

        # calculate filter step
        K = self.V_pred[t] @ (
            H.T @ self.xp.linalg.pinv(H @ (self.V_pred[t] @ H.T) + R)
            )
        self.x_filt[t] = self.x_pred[t] + K @ (
            self.y[t] - (H @ self.x_pred[t] + d)
            )
        self.V_filt[t] = self.V_pred[t] - K @ (H @ self.V_pred[t])


    def _filter_update_pair(self, t):
        """Calculate fileter update without noise

        Args:
            t {int} : observation time

        Attributes:
            K [n_dim_sys, n_dim_obs] {numpy-array, float}
                : Kalman gain matrix for time t
        """
        # extract parameters for time t
        H = _last_dims(self.H, t, 2)
        R = _last_dims(self.R, t, 2)
        d = _last_dims(self.d, t, 1)

        # calculate filter step
        K = self.V_pred[t] @ (
            H.T @ self.xp.linalg.pinv(H @ (self.V_pred[t] @ H.T) + R)
            )
        self.x_filt[t] = self.x_pred[t] + K @ (
            self.y[t] - (H @ self.x_pred[t] + d)
            )
        self.V_filt[t] = self.V_pred[t] - K @ (H @ self.V_pred[t])
        self.V_pair[t] = self.V_pair[t] - K @ H @ self.V_pair[t]
        


    def _update_transition_matrix(self, s, tau, F=None):
        """Calculate estimation of state transition matrix by maximization of likelihood.

        Args:
            s {int} : last time for fixed-interval smoothing
        """
        self._backward(s, tau, F)

        if "F" in self.em_vars:
            res1 = self.xp.zeros((self.n_dim_sys, self.n_dim_sys), dtype = self.dtype)
            res2 = self.xp.zeros((self.n_dim_sys, self.n_dim_sys), dtype = self.dtype)
            for t in range(s - tau + 1, s + 1):
                b = _last_dims(self.b, t - 1, 1)
                res1 += self.V_pair[t] + self.xp.outer(
                    self.x_smooth[t], self.x_smooth[t - 1]
                    )
                res1 -= self.xp.outer(b, self.x_smooth[t - 1])            
                res2 += self.V_smooth[t - 1] \
                    + self.xp.outer(self.x_smooth[t - 1], self.x_smooth[t - 1])
 
            F_est = res1 @ self.xp.linalg.pinv(res2)

        if "b" in self.em_vars and tau > 1:
            b_est = self.xp.zeros(self.n_dim_sys, dtype = self.dtype)

            for t in range(s-tau+1, s):
                F = _last_dims(self.F, t - 1)
                b_est += self.x_smooth[t] - F @ self.x_smooth[t - 1]
            b_est *= (1.0 / (tau - 1))

            # update transition offset
            self.b = self.b - self.etab * self.xp.minimum(self.xp.maximum(-self.cutoffb, self.b - b_est),
                                                        self.cutoffb)

        return F_est


    def _update_transition_matrix_approximately(self, t):
        res1 = self.xp.zeros((self.n_dim_sys, self.n_dim_sys), dtype = self.dtype)
        res2 = self.xp.zeros((self.n_dim_sys, self.n_dim_sys), dtype = self.dtype)
        for s in range(t+1, t+self.tau+1):
            b = _last_dims(self.b, s - 1, 1)
            res1 += self.V_pair[s] + self.xp.outer(
                self.x_filt[s], self.x_filt[s - 1]
                )
            res1 -= self.xp.outer(b, self.x_filt[s - 1])            
            res2 += self.V_filt[s - 1] \
                + self.xp.outer(self.x_filt[s - 1], self.x_filt[s - 1])

        F_est = res1 @ self.xp.linalg.pinv(res2)

        # update transition matrix
        self.F = self.F - self.eta * self.xp.minimum(self.xp.maximum(-self.cutoff, self.F - F_est),
                                                    self.cutoff)
        if self.store_transition_matrices_on:
            self.Fs[t//self.tau+1] = self.F


    def _backward(self, s, tau, F=None):
        """Calculate smoothed estimation by RTS-smoother.

        Args:
            s {int} : last time for fixed-interval smoothing

        Attributes:
            A [n_dim_sys, n_dim_sys] {numpy-array, float}
                : fixed interval smoothed gain
        """
        if F is None:
            F = _last_dims(self.F, t - 1, 2)

        # pairwise covariance
        A = self.xp.zeros((self.n_dim_sys, self.n_dim_sys), dtype = self.dtype)

        self.x_smooth[s] = self.x_filt[s].copy()
        self.V_smooth[s] = self.V_filt[s].copy()

        # t in [s-tau, s-1]
        for t in reversed(range(s-tau, s)) :
            # visualize calculating time
            print("\r expectation step calculating... t={}".format(s - t)
                 + "/" + str(tau), end="")

            # calculate fixed interval smoothing gain
            A = self.V_filt[t] @ F @ self.xp.linalg.pinv(self.V_pred[t + 1])
            
            # fixed interval smoothing
            self.x_smooth[t] = self.x_filt[t] \
                + A @ (self.x_smooth[t + 1] - self.x_pred[t + 1])
            self.V_smooth[t] = self.V_filt[t] \
                + A @ (self.V_smooth[t + 1] - self.V_pred[t + 1]) @ A.T

            # calculate pairwise covariance
            self.V_pair[t + 1] = self.V_smooth[t + 1] @ A.T



    def get_predicted_value(self, dim = None):
        """Get predicted value

        Args:
            dim {int} : dimensionality for extract from predicted result

        Returns (numpy-array, float)
            : mean of hidden state at time t given observations
            from times [0...t-1]
        """
        # if not implement `forward`, implement `forward`
        try :
            self.x_pred[0]
        except :
            self.forward()

        if dim is None:
            return self.x_pred
        elif dim <= self.x_pred.shape[1]:
            return self.x_pred[:, int(dim)]
        else:
            raise ValueError('The dim must be less than '
                 + self.x_pred.shape[1] + '.')


    def get_filtered_value(self, dim = None):
        """Get filtered value

        Args:
            dim {int} : dimensionality for extract from filtered result

        Returns (numpy-array, float)
            : mean of hidden state at time t given observations
            from times [0...t]
        """
        # if not implement `forward`, implement `forward`
        try :
            self.x_filt[0]
        except :
            self.forward()

        if dim is None:
            return self.x_filt
        elif dim <= self.x_filt.shape[1]:
            return self.x_filt[:, int(dim)]
        else:
            raise ValueError('The dim must be less than '
                 + self.x_filt.shape[1] + '.')


    def get_transition_matrices(self, ids = None):
        """Get transition matrices
        
        Args:
            ids {numpy-array, int} : ids of transition matrices

        Returns {numpy-array, float}:
            : transition matrices
        """
        if self.store_transition_matrices_on:
            if ids is None:
                return self.Fs
            else:
                return self.Fs[ids]
        else:
            return self.F

            
    def get_smoothed_value(self, dim = None):
        """Get RTS smoothed value

        Args:
            dim {int} : dimensionality for extract from RTS smoothed result

        Returns (numpy-array, float)
            : mean of hidden state at time t given observations
            from times [0...T]
        """
        # if not implement `smooth`, implement `smooth`
        try :
            self.x_smooth[0]
        except :
            self.smooth()

        if dim is None:
            return self.x_smooth
        elif dim <= self.x_smooth.shape[1]:
            return self.x_smooth[:, int(dim)]
        else:
            raise ValueError('The dim must be less than '
                 + self.x_smooth.shape[1] + '.')
