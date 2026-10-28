"""Pruebas del ambiente: ficha, física, reglas y trampas de recompensa."""

import math

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from rally import AutonomousRallyEnv, policies, track
from rally.transitions import TRANSICIONES, ejecutar, _en_pista


@pytest.fixture
def env():
    return AutonomousRallyEnv()


def correr(env, piloto, seed=0):
    pol = policies.crear(piloto, seed)
    obs, info = env.reset(seed=seed)
    total, done = 0.0, False
    while not done:
        obs, r, term, trunc, info = env.step(pol(obs, info))
        total += r
        done = term or trunc
    return info, total


# ------------------------------------------------------------------ diseño

def test_trazado_valido():
    rep = track.check_design()
    assert rep["problemas"] == []
    giro = sum(math.degrees(c["theta"]) for c in track.CORNERS)
    assert giro == pytest.approx(360.0, abs=1e-6)  # una sola vuelta, sin cruces
    assert 900 < track.LAP < 1300


def test_gymnasium_check_env(env):
    check_env(env, skip_render_check=True)


@pytest.mark.parametrize("tr", TRANSICIONES, ids=[t["id"] for t in TRANSICIONES])
def test_transiciones_de_la_ficha(env, tr):
    _, r, info = ejecutar(env, tr)
    e = tr["esperado"]
    assert r == pytest.approx(e["recompensa"], abs=0.01)
    assert info["next_cp"] == e["next_cp"]
    assert info["outcome"] == e["fin"]


def test_reproducible():
    a, b = AutonomousRallyEnv(), AutonomousRallyEnv()
    ia, ra = correr(a, "aleatoria", seed=3)
    ib, rb = correr(b, "aleatoria", seed=3)
    assert ra == rb and ia["x"] == ib["x"] and ia["t"] == ib["t"]


# ------------------------------------------------------------------ física

def test_sin_reversa(env):
    env.reset(seed=0)
    for _ in range(5):
        _, _, _, _, info = env.step([-1.0, 0.0])
    assert info["v"] == 0.0


def test_subviraje_en_horquilla(env):
    tr = next(t for t in TRANSICIONES if t["id"] == "T3")
    _, _, info = ejecutar(env, tr)
    assert info["skidding"]


def test_experto_completa_en_seco():
    info, total = correr(AutonomousRallyEnv(mu=0.9), "experto")
    assert info["outcome"] == "exito"
    assert total > 100


def test_experto_falla_con_lluvia_y_prudente_no():
    assert correr(AutonomousRallyEnv(mu=0.5), "experto")[0]["outcome"] != "exito"
    assert correr(AutonomousRallyEnv(mu=0.5), "prudente")[0]["outcome"] == "exito"


# ------------------------------------------------------------------ trampas

def test_checkpoint_no_paga_dos_veces(env):
    """Cruzar de nuevo una puerta ya pasada no da los +10."""
    s = track.GATES[0][0]
    env.reset(options={"state": {**_en_pista(s - 1.0), "v": 20.0, "next_cp": 2,
                                 "s_cum": s - 1.0, "s_best": s}})
    _, r, _, _, info = env.step([0.0, 0.0])
    assert r < 1 and info["next_cp"] == 2


def test_atajo_no_paga(env):
    """Llegar a una puerta posterior sin pasar las anteriores no da puntos ni progreso."""
    s = track.GATES[2][0]
    env.reset(options={"state": {**_en_pista(s - 1.0), "v": 20.0, "next_cp": 1,
                                 "s_cum": s - 1.0, "s_best": 0.0}})
    _, r, _, _, info = env.step([0.0, 0.0])
    assert info["next_cp"] == 1
    assert info["s_best"] <= track.GATES[0][0]
    assert r < 0.5


def test_ir_y_volver_no_acumula(env):
    """El progreso se paga sobre el máximo alcanzado: volver al mismo sitio no paga."""
    env.reset(options={"state": {**_en_pista(50.0), "v": 10.0, "s_cum": 50.0, "s_best": 60.0}})
    _, r, _, _, info = env.step([0.0, 0.0])
    assert info["s_best"] == 60.0
    assert r < 0


def test_quedarse_quieto_termina_estancado(env):
    env.reset(seed=0)
    for _ in range(200):
        _, _, term, _, info = env.step([0.0, 0.0])
        if term:
            break
    assert info["outcome"] == "estancado"


def test_choque_cuesta_mas_que_quedarse_quieto():
    """Chocar a propósito nunca conviene más que quedarse quieto hasta el estancamiento."""
    cfg = AutonomousRallyEnv().cfg
    assert cfg.r_fail < cfg.r_time * cfg.stall_limit


def test_salto_de_proyeccion_no_es_avance(env):
    """Si el carro aparece cerca de otro tramo (la horquilla), s no salta."""
    env.reset(seed=0)
    s0 = env.s_cum
    env.x, env.y = track.point_at(track.LAP / 2)  # teletransporte (no físico)
    env.step([0.0, 0.0])
    assert abs(env.s_cum - s0) < 5
