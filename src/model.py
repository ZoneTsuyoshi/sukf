import numpy as np
import math

class ODE(object):
    def __init__(self, xp_type="numpy"):
        if xp_type=="numpy":
            self.xp = np
        elif xp_type=="cupy":
            import cupy
            self.xp = cupy

    def f(self, x, t):
        pass


class DampedOscillationModel(ODE):
    def __init__(self, m, k, r, w, xp_type="numpy"):
        super(DampedOscillationModel, self).__init__(xp_type)
        self.m = m
        self.k = k
        self.r = r
        self.w = w


    def f(self, x, t):
        perturbation = self.xp.zeros_like(x)
        perturbation[0] = x[1]
        perturbation[1] = (- self.k * x[0] - self.r * x[1] + self.w(t)) / self.m
        return perturbation


class CoefficientChangedDampedOscillationModel(ODE):
    def __init__(self, m, k, r, w, xp_type="numpy"):
        super(CoefficientChangedDampedOscillationModel, self).__init__(xp_type)
        self.m = m
        self.k = k
        self.r = r
        self.w = w


    def f(self, x, t):
        perturbation = self.xp.zeros_like(x)
        perturbation[0] = x[1]
        perturbation[1] = (- self.k(t) * x[0] - self.r(t) * x[1] + self.w(t)) / self.m
        return perturbation


class DuffingModel(ODE):
    def __init__(self, m, alpha, beta, xp_type="numpy"):
        super(DuffingModel, self).__init__(xp_type)
        self.m = m
        self.alpha = alpha
        self.beta = beta


    def f(self, x, t):
        perturbation = self.xp.zeros_like(x)
        perturbation[0] = x[1]
        perturbation[1] = (- self.alpha * x[0] - self.beta * x[0]**3) / self.m
        return perturbation


class Lorentz63Model(ODE):
    def __init__(self, sigma, rho, beta, xp_type="numpy"):
        super(Lorentz63Model, self).__init__(xp_type)
        self.sigma = sigma
        self.rho = rho
        self.beta = beta

    def f(self, x, t):
        perturbation = self.xp.zeros_like(x)
        perturbation[0] = self.sigma * (x[1] - x[0])
        perturbation[1] = x[0] * (self.rho - x[2]) - x[1]
        perturbation[2] = x[0] * x[1] - self.beta * x[2]
        return perturbation


class VanderPol(ODE):
    def __init__(self, mu, xp_type="numpy"):
        super(VanderPol, self).__init__(xp_type)
        self.mu = mu

    def f(self, x, t):
        perturbation = self.xp.zeros_like(x)
        perturbation[0] = x[1]
        perturbation[1] = self.mu * (1 - x[0]**2) * v - x[0]
        return perturbation


class FitzHughNagumo(ODE):
    def __init__(self, a, b, c, I, xp_type="numpy"):
        super(FitzHughNagumo, self).__init__(xp_type)
        self.a = a
        self.b = b
        self.c = c
        self.I = I

    def f(self, x, t):
        perturbation = self.xp.zeros_like(x)
        perturbation[0] = self.c * (x[0] - x[1] - x[0]**3 / 3 + self.I(t))
        perturbation[1] = self.a + x[0] - self.b * x[1]
        return perturbation


class LotkaVolterra(ODE):
    def __init__(self, a, b, c, d, xp_type="numpy"):
        super(LotkaVolterra, self).__init__(xp_type)
        self.a = a
        self.b = b
        self.c = c
        self.d = d

    def f(self, x, t):
        perturbation = self.xp.zeros_like(x)
        perturbation[0] = self.a * x[0] - self.b * x[0] * x[1]
        perturbation[1] = self.c * x[0] * x[1] - self.d * x[1]
        return perturbation


class ClockReaction(ODE):
    def __init__(self, k1, k2, xp_type="numpy"):
        super(ClockReaction, self).__init__(xp_type)
        self.k1 = k1
        self.k2 = k2

    def f(self, x, t):
        #x0:A, x1:B, x2:T, x3:L
        perturbation = self.xp.zeros_like(x)
        perturbation[0] = - self.k1 * x[0] * x[1]
        perturbation[1] = - self.k1 * x[0] * x[1]
        perturbation[2] = self.k1 * x[0] * x[1] - self.k2 * x[2] * x[3]
        perturbation[3] = - self.k2 * x[2] * x[3]
        return perturbation
        


def rotation_matrix_3d(theta):
    result = self.xp.eye(3)
    R = self.xp.array([[1, 0, 0],
                  [0, math.cos(theta[0]), -math.sin(theta[0])],
                  [0, math.sin(theta[0]), math.cos(theta[0])]])
    result = R @ result
    R = self.xp.array([[math.cos(theta[1]), 0, -math.sin(theta[1])],
                  [0, 1, 0],
                  [math.sin(theta[1]), 0, math.cos(theta[1])]])
    result = R @ result
    R = self.xp.array([[math.cos(theta[2]), -math.sin(theta[2]), 0],
                  [math.sin(theta[2]), math.cos(theta[2]), 0],
                  [0, 0, 1]])
    return R @ result


def Rodrigues_rotation_matrix(n, theta):
    if self.xp.linalg.norm(n)!=0:
        n = n / self.xp.linalg.norm(n) 
    else:
        raise ValueError("norm of n must be greater than 0.")

    return self.xp.array([[math.cos(theta)+n[0]*n[0]*(1-math.cos(theta)),
                        n[0]*n[1]*(1-math.cos(theta))-n[2]*math.sin(theta),
                        n[0]*n[2]*(1-math.cos(theta))+n[1]*math.sin(theta)],
                     [n[0]*n[1]*(1-math.cos(theta))+n[2]*math.sin(theta),
                        math.cos(theta)+n[1]*n[1]*(1-math.cos(theta)),
                        n[1]*n[2]*(1-math.cos(theta))-n[0]*math.sin(theta)],
                     [n[0]*n[2]*(1-math.cos(theta))-n[1]*math.sin(theta),
                        n[1]*n[2]*(1-math.cos(theta))+n[0]*math.sin(theta),
                        math.cos(theta)+n[2]*n[2]*(1-math.cos(theta))]])
