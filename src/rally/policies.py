"""Pilotos de referencia para probar el ambiente mientras no hay agente entrenado.

No son el agente: "experto" y "prudente" leen el estado interno (info) del
simulador, información que el agente no ve. Sirven como línea base.
"""

import math
from pathlib import Path

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
        self.a_lat = margen * mu_supuesto * G  # aceleración lateral que se permite
        self.v_recta = v_recta
        self.freno = freno * mu_supuesto / 0.9
        self.wheelbase = wheelbase
        self.delta_max = math.radians(delta_max_deg)

    def v_curva(self, kappa):
        """Velocidad máxima en una curva de curvatura kappa: v² · |κ| <= a_lat."""
        return math.sqrt(self.a_lat / abs(kappa)) if kappa else self.v_recta

    def __call__(self, obs, info):
        x, y, psi, v = info["x"], info["y"], info["psi"], info["v"]
        s = info["s"]

        # Dirección: pure pursuit sobre la línea central
        ld = min(max(4.0 + 0.5 * v, 5.0), 14.0)
        tx, ty = track.point_at(s + ld)
        alpha = track.wrap_angle(math.atan2(ty - y, tx - x) - psi)
        delta = math.atan2(2 * self.wheelbase * math.sin(alpha), ld)
        u_dir = float(np.clip(delta / self.delta_max, -1, 1))

        # Velocidad objetivo: la que permita frenar a tiempo para cada curva que viene
        v_obj = self.v_recta
        for k in range(0, 61, 2):
            vc = self.v_curva(track.curvature_at(s + k))
            v_obj = min(v_obj, math.sqrt(vc**2 + 2 * self.freno * max(k - 2, 0)))
        u_acel = float(np.clip(0.8 * (v_obj - v), -1, 1))
        return np.array([u_acel, u_dir], dtype=np.float32)


class Aleatoria:
    """Acciones al azar: sirve para ver que el ambiente no regala puntos."""

    def __init__(self, seed=None):
        self.rng = np.random.default_rng(seed)

    def __call__(self, obs, info):
        return self.rng.uniform(-1, 1, size=2).astype(np.float32)


MODELOS = {"qlearning": Path("models/qlearning/q_table.npz"), "ppo": Path("models/ppo/modelo.zip")}
_cache = {}


def _modelo(nombre):
    """Carga una sola vez el modelo entrenado (models/, versionado con DVC)."""
    if nombre not in _cache:
        if nombre == "ppo":
            from rally.agentes.ppo import PilotoPPO
            _cache[nombre] = PilotoPPO(MODELOS[nombre])
        else:
            from rally.agentes.qlearning import AgenteQ
            _cache[nombre] = AgenteQ.cargar(MODELOS[nombre])
    return _cache[nombre]


POLITICAS = {
    "experto": ("Pure pursuit, asume piso seco (μ=0.9)", lambda seed: PurePursuit(0.9)),
    "prudente": ("Pure pursuit, asume lluvia (μ=0.5)", lambda seed: PurePursuit(0.5)),
    "aleatoria": ("Acciones al azar", lambda seed: Aleatoria(seed)),
    "qlearning": ("Agente Q-learning entrenado (tabla)", lambda seed: _modelo("qlearning")),
    "ppo": ("Agente PPO entrenado (red neuronal)", lambda seed: _modelo("ppo")),
}


def disponible(nombre):
    return nombre in POLITICAS and (nombre not in MODELOS or MODELOS[nombre].exists())


def crear(nombre, seed=None):
    if not disponible(nombre):
        raise FileNotFoundError(f"El modelo '{nombre}' no está entrenado todavía: "
                                f"corre `dvc repro` o `rally entrenar {nombre}`")
    return POLITICAS[nombre][1](seed)
