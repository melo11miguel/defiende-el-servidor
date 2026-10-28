"""Geometría de la pista de Autonomous Rally (ver docs/ambiente-v0.1.md).

La línea central es un rectángulo redondeado: un "núcleo" de 56 x 26 m
(x en [-28, 28], y en [-13, 13]) inflado con un radio R = 12 m.
Así la línea central queda en x en [-40, 40], y en [-25, 25].
Se recorre en sentido antihorario empezando en (-40, 0) hacia el sur.
"""

import math

import numpy as np

R = 12.0  # radio de la línea central en las curvas (m)
CX, CY = 28.0, 13.0  # semiejes del núcleo (m)
Q = R * math.pi / 2  # largo de un cuarto de curva (m)

# Inicio de cada tramo medido sobre la línea central (m)
S_BOTTOM = 13 + Q
S_BR = 69 + Q
S_RIGHT = 69 + 2 * Q
S_TR = 95 + 2 * Q
S_TOP = 95 + 3 * Q
S_TL = 151 + 3 * Q
LAP = 164 + 4 * Q  # 239.40 m

# Puertas en orden: CP1, CP2, CP3, meta. (posición s, centro x, centro y)
GATES = [
    (S_BOTTOM + 28, 0.0, -25.0),
    (S_RIGHT + 13, 40.0, 0.0),
    (S_TOP + 28, 0.0, 25.0),
    (LAP, -40.0, 0.0),
]

MAP_X, MAP_Y = 50.0, 35.0  # muro: x en [-50, 50], y en [-35, 35]

# Bloques de concreto: (centro x, centro y, ancho, alto)
OBSTACLES = [
    (-15.0, -8.0, 6.0, 2.0),
    (15.0, -10.0, 6.0, 2.0),
    (-12.0, 10.0, 6.0, 2.0),
    (18.0, 9.0, 2.0, 6.0),
]


def wrap_angle(a):
    """Lleva un ángulo a (-pi, pi]."""
    return (a + math.pi) % (2 * math.pi) - math.pi


def lateral(x, y):
    """Desvío lateral d respecto a la línea central (+ = izquierda/interior).

    Acepta escalares o arreglos de numpy.
    """
    qx = np.clip(x, -CX, CX)
    qy = np.clip(y, -CY, CY)
    dist = np.hypot(x - qx, y - qy)
    inside = -np.minimum(CX - np.abs(x), CY - np.abs(y))
    return R - np.where(dist > 0, dist, inside)


def project(x, y):
    """Proyecta un punto sobre la línea central.

    Devuelve (s, d, rumbo_tangente) con s en [0, LAP).
    """
    qx = min(max(x, -CX), CX)
    qy = min(max(y, -CY), CY)
    nx, ny = x - qx, y - qy
    dist = math.hypot(nx, ny)
    if dist > 0:
        ux, uy = nx / dist, ny / dist
    else:
        # Punto dentro del núcleo: se usa el borde más cercano.
        edges = [
            (CX + x, (-1.0, 0.0), (-CX, y)),
            (CX - x, (1.0, 0.0), (CX, y)),
            (CY + y, (0.0, -1.0), (x, -CY)),
            (CY - y, (0.0, 1.0), (x, CY)),
        ]
        gap, (ux, uy), (qx, qy) = min(edges, key=lambda e: e[0])
        dist = -gap
    d = R - dist
    cx, cy = qx + R * ux, qy + R * uy
    heading = wrap_angle(math.atan2(uy, ux) + math.pi / 2)

    left, right = qx <= -CX, qx >= CX
    bottom, top = qy <= -CY, qy >= CY
    if left and bottom:
        th = math.atan2(cy + CY, cx + CX)
        if th > 0:
            th -= 2 * math.pi
        s = 13 + R * (th + math.pi)
    elif right and bottom:
        s = S_BR + R * (math.atan2(cy + CY, cx - CX) + math.pi / 2)
    elif right and top:
        s = S_TR + R * math.atan2(cy - CY, cx - CX)
    elif left and top:
        s = S_TL + R * (math.atan2(cy - CY, cx + CX) - math.pi / 2)
    elif bottom:
        s = S_BOTTOM + (cx + CX)
    elif right:
        s = S_RIGHT + (cy + CY)
    elif top:
        s = S_TOP + (CX - cx)
    else:  # recta izquierda
        s = -cy if cy <= 0 else LAP - cy
    return s % LAP, d, heading


def in_obstacle(x, y):
    """True donde el punto está dentro de algún bloque (escalar o arreglo)."""
    hit = np.zeros(np.shape(x), dtype=bool)
    for ox, oy, w, h in OBSTACLES:
        hit |= (np.abs(x - ox) <= w / 2) & (np.abs(y - oy) <= h / 2)
    return hit


def outside_walls(x, y):
    return (np.abs(x) >= MAP_X) | (np.abs(y) >= MAP_Y)


def raycast(x, y, psi, angles, r_max, half_width, step=0.25, refine=8):
    """Distancia (m) de cada rayo al primer borde de pista, bloque o muro.

    Un rayo "choca" cuando cambia el estado en-pista/fuera-de-pista respecto
    al origen, o al tocar un bloque o el muro. Si no choca, devuelve r_max.
    """
    origin_on = abs(float(lateral(x, y))) <= half_width

    def hits(px, py):
        on = np.abs(lateral(px, py)) <= half_width
        return (on != origin_on) | in_obstacle(px, py) | outside_walls(px, py)

    ts = np.arange(step, r_max + 1e-9, step)
    out = []
    for a in angles:
        dx, dy = math.cos(psi + a), math.sin(psi + a)
        h = hits(x + ts * dx, y + ts * dy)
        if not h.any():
            out.append(r_max)
            continue
        i = int(np.argmax(h))
        lo, hi = (ts[i - 1] if i > 0 else 0.0), ts[i]
        for _ in range(refine):  # bisección para afinar el borde
            mid = (lo + hi) / 2
            if hits(x + mid * dx, y + mid * dy):
                hi = mid
            else:
                lo = mid
        out.append(hi)
    return np.array(out)


def car_collides(x, y, psi, length, width):
    """True si el contorno del carro toca un bloque o el muro."""
    c, s = math.cos(psi), math.sin(psi)
    pts = []
    for fx in (-0.5, 0.0, 0.5):
        for fy in (-0.5, 0.0, 0.5):
            lx, ly = fx * length, fy * width
            pts.append((x + lx * c - ly * s, y + lx * s + ly * c))
    px, py = np.array(pts).T
    if (in_obstacle(px, py) | outside_walls(px, py)).any():
        return True
    # Esquinas de los bloques dentro del carro (bloque más pequeño que el carro)
    for ox, oy, w, h in OBSTACLES:
        for ex in (-w / 2, w / 2):
            for ey in (-h / 2, h / 2):
                rx, ry = ox + ex - x, oy + ey - y
                lx, ly = rx * c + ry * s, -rx * s + ry * c
                if abs(lx) <= length / 2 and abs(ly) <= width / 2:
                    return True
    return False
