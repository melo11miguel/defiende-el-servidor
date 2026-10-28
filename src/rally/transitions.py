"""Las cinco transiciones de ejemplo de docs/ambiente-v0.1.md.

Cada una trae el estado inicial, la acción y lo que la ficha calculó a mano.
La CLI (`rally transiciones`) y las pruebas las comparan con el ambiente.
"""

import math

TRANSICIONES = [
    {
        "id": "T1",
        "nombre": "Arranque desde la salida",
        "estado": dict(x=-40, y=0, psi=-math.pi / 2),
        "accion": (1.0, 0.0),
        "esperado": dict(recompensa=-0.096, x=-40.00, y=-0.04, next_cp=1, fin=None),
        "obs": [0.00, 0.00, 0.85, 0.53, 0.00, 0.00, 0.20, 0.23, 0.40, 1.00, 0.40, 0.23, 0.20],
    },
    {
        "id": "T2",
        "nombre": "Cruce del CP1 en la recta inferior",
        "estado": dict(x=-1, y=-25.5, psi=0, v=15, t=8, prev_action=(0.5, 0)),
        "accion": (0.3, 0.05),
        "esperado": dict(recompensa=10.08, x=0.50, y=-25.48, next_cp=2, fin=None),
        "obs": [0.60, 0.00, 0.45, 0.89, -0.13, 0.00, 0.18, 0.20, 0.35, 1.00, 0.45, 0.26, 0.23],
    },
    {
        "id": "T3",
        "nombre": "Entrada a curva demasiado rápido",
        "estado": dict(x=28, y=-25, psi=0, v=18, next_cp=2, t=12, prev_action=(0.2, 0)),
        "accion": (0.0, 1.0),
        "esperado": dict(recompensa=-0.081, x=29.79, y=-24.91, next_cp=2, fin=None),
        "obs": [0.72, 0.00, 0.90, 0.43, 0.00, 0.00, 0.20, 0.22, 0.31, 0.53, 0.91, 0.26, 0.20],
    },
    {
        "id": "T4",
        "nombre": "Décimo paso en el césped",
        "estado": dict(x=39.53, y=-24.53, psi=math.radians(30), v=12, omega=0.26, next_cp=2,
                       t=14, off_steps=9, prev_action=(0.5, 1.0), s_best=96.0),
        "accion": (0.5, 1.0),
        "esperado": dict(recompensa=-51.05, x=40.57, y=-23.90, next_cp=2, fin="salida"),
        "obs": [0.48, 0.13, 0.86, 0.52, -1.08, -0.08, 0.60, 0.60, 0.52, 0.60, 0.07, 0.02, 0.02],
    },
    {
        "id": "T5",
        "nombre": "Cierre de vuelta en la meta",
        "estado": dict(x=-40, y=1, psi=-math.pi / 2, v=16, next_cp=4, t=21.3,
                       prev_action=(0.8, 0), s_cum=238.4),
        "accion": (1.0, 0.0),
        "esperado": dict(recompensa=50.04, x=-40.00, y=-0.63, next_cp=5, fin="exito"),
        "obs": [0.64, 0.00, 0.00, 1.00, 0.00, 0.00, 0.20, 0.23, 0.40, 1.00, 0.40, 0.23, 0.20],
    },
]


def ejecutar(env, tr):
    """Corre una transición y devuelve (obs_inicial, recompensa, info)."""
    obs, _ = env.reset(options={"state": tr["estado"]})
    _, r, _, _, info = env.step(tr["accion"])
    return obs, r, info
