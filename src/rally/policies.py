"""Pilotos de referencia para probar el ambiente mientras no hay agente entrenado.

No son el agente: "experto" y "prudente" leen el estado interno (info) del
simulador, información que el agente no ve. Sirven como línea base.
"""

import math

import numpy as np

from rally import track

G = 9.81


class PurePursuit:
    """Sigue la línea central mirando un punto adelante y frena antes de las curvas.

    `mu_supuesto` es la adherencia que el piloto CREE que hay. No conoce la real:
    si cree que está seco y llueve, entra demasiado rápido a las curvas.
    """

    def __init__(self, mu_supuesto=0.9, margen=0.85, v_recta=22.0, freno=6.0,
                 wheelbase=2.5, delta_max_deg=30.0):
        self.v_curva = math.sqrt(margen * mu_supuesto * G * track.R)
        self.v_recta = v_recta
        self.freno = freno * mu_supuesto / 0.9
        self.wheelbase = wheelbase
        self.delta_max = math.radians(delta_max_deg)

    def __call__(self, obs, info):
        x, y, psi, v = info["x"], info["y"], info["psi"], info["v"]
        s = info["s"]

        # Dirección: pure pursuit sobre la línea central
        ld = min(max(4.0 + 0.5 * v, 5.0), 14.0)
        tx, ty = track.point_at(s + ld)
        alpha = track.wrap_angle(math.atan2(ty - y, tx - x) - psi)
        delta = math.atan2(2 * self.wheelbase * math.sin(alpha), ld)
        u_dir = float(np.clip(delta / self.delta_max, -1, 1))

        # Velocidad objetivo: lo que permita frenar a tiempo para la próxima curva
        v_obj = self.v_recta
        for k in range(0, 41, 2):
            if track.in_corner(s + k):
                v_obj = min(v_obj, math.sqrt(self.v_curva**2 + 2 * self.freno * max(k - 2, 0)))
                break
        u_acel = float(np.clip(0.8 * (v_obj - v), -1, 1))
        return np.array([u_acel, u_dir], dtype=np.float32)


class Aleatoria:
    """Acciones al azar: sirve para ver que el ambiente no regala puntos."""

    def __init__(self, seed=None):
        self.rng = np.random.default_rng(seed)

    def __call__(self, obs, info):
        return self.rng.uniform(-1, 1, size=2).astype(np.float32)


POLITICAS = {
    "experto": ("Pure pursuit, asume piso seco (μ=0.9)", lambda seed: PurePursuit(0.9)),
    "prudente": ("Pure pursuit, asume lluvia (μ=0.5)", lambda seed: PurePursuit(0.5)),
    "aleatoria": ("Acciones al azar", lambda seed: Aleatoria(seed)),
}


def crear(nombre, seed=None):
    return POLITICAS[nombre][1](seed)
