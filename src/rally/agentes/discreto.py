"""Acciones discretas y discretización del estado (para Q-learning con tabla).

Q-learning con tabla necesita un número finito de estados y de acciones:
- Acciones: 3 de pedal × 5 de dirección = 15.
- Estado: se agrupan en rangos (bins) las 5 observaciones que más importan.
"""

import itertools

import gymnasium as gym
import numpy as np

PEDAL = (-1.0, 0.3, 1.0)  # frenar, mantener, acelerar
DIRECCION = (-1.0, -0.4, 0.0, 0.4, 1.0)  # derecha fuerte ... izquierda fuerte
ACCIONES = np.array(list(itertools.product(PEDAL, DIRECCION)), dtype=np.float32)

# (índice en la observación, bordes de los rangos)
BINS = [
    (4, (-0.6, -0.2, 0.2, 0.6)),  # desvío del centro: 5 rangos
    (5, (-0.08, -0.025, 0.025, 0.08)),  # error de rumbo: 5 rangos
    (0, (0.25, 0.4, 0.55)),  # velocidad: 4 rangos
    (14, (-0.4, -0.12, 0.12, 0.4)),  # curvatura a 25 m: 5 rangos
    (13, (-0.12, 0.12)),  # curvatura a 10 m: 3 rangos
]
FORMA = tuple(len(b) + 1 for _, b in BINS)
N_ESTADOS = int(np.prod(FORMA))


def estado(obs):
    """Convierte la observación continua en un índice de la tabla Q."""
    idx = [int(np.digitize(obs[i], b)) for i, b in BINS]
    return int(np.ravel_multi_index(idx, FORMA))


class AccionesDiscretas(gym.ActionWrapper):
    """Expone las 15 acciones discretas sobre el ambiente continuo."""

    def __init__(self, env):
        super().__init__(env)
        self.action_space = gym.spaces.Discrete(len(ACCIONES))

    def action(self, a):
        return ACCIONES[int(a)]
