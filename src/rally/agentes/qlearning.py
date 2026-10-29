"""Agente Q-learning con tabla (el primer agente del tablero).

Q(s, a) <- Q(s, a) + α · [r + γ · max_a' Q(s', a') − Q(s, a)]

Usa las acciones discretas y el estado discretizado de `discreto.py`. Aprender
solo con ε-greedy desde cero casi nunca llega a la meta en un circuito de 1 km
(v1–v3: 0 % de vueltas), así que se entrena en dos fases:

1. Imitación con DAgger: la tabla maneja y un piloto maestro dice qué acción
   habría elegido en cada estado visitado (se cuentan sus votos por estado).
2. Q-learning: la tabla Q arranca con esos votos (la acción del maestro vale
   `q_inicial`) y se corrige con la ecuación de Bellman practicando con seco y
   lluvia. Así Q-learning arregla los lugares donde la imitación choca.

En las dos fases se evalúa cada cierto tiempo y se guarda la mejor tabla.
"""

from pathlib import Path

import mlflow
import numpy as np

from rally import track
from rally.agentes.discreto import ACCIONES, N_ESTADOS, NEUTRA, discreta, estado
from rally.policies import PurePursuit

# Semillas de entrenamiento lejos de las de evaluación (0-99) y del dataset (500+)
SEMILLA_BASE = 100_000
SEMILLA_EVAL = 10_000   # evaluación rápida (las mismas que usa PPO)


class AgenteQ:
    def __init__(self, alpha=0.1, gamma=0.99, seed=0):
        self.q = np.zeros((N_ESTADOS, len(ACCIONES)), dtype=np.float32)
        self.visitas = np.zeros(N_ESTADOS, dtype=np.int64)
        self.alpha, self.gamma = alpha, gamma
        self.rng = np.random.default_rng(seed)

    def mejor(self, s):
        fila = self.q[s]
        return NEUTRA if not fila.any() else int(np.argmax(fila))

    def elegir(self, s, epsilon=0.0):
        if self.rng.random() < epsilon:
            return int(self.rng.integers(len(ACCIONES)))
        return self.mejor(s)

    def aprender(self, s, a, r, s2, terminal):
        objetivo = r if terminal else r + self.gamma * self.q[s2].max()
        self.q[s, a] += self.alpha * (objetivo - self.q[s, a])
        self.visitas[s] += 1

    # Como piloto para el visor y la evaluación: sin explorar y determinista
    def __call__(self, obs, info):
        return ACCIONES[self.mejor(estado(obs))]

    def guardar(self, ruta):
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(ruta, q=self.q, visitas=self.visitas,
                            alpha=self.alpha, gamma=self.gamma)

    @classmethod
    def cargar(cls, ruta):
        datos = np.load(ruta)
        ag = cls(float(datos["alpha"]), float(datos["gamma"]))
        ag.q, ag.visitas = datos["q"], datos["visitas"]
        return ag


def maestro(p):
    """Pure pursuit que mira la señal de lluvia. Con lluvia va a 16 m/s en las rectas:
    así la frenada para la curva cabe en los 50 m que la tabla alcanza a ver."""
    seco = PurePursuit(p["maestro_mu_seco"])
    lluvia = PurePursuit(p["maestro_mu_lluvia"], v_recta=p["maestro_v_recta_lluvia"])
    return lambda obs, info: (lluvia if obs[19] > 0.5 else seco)(obs, info)


def puntaje(m):
    """Orden de las evaluaciones rápidas: vueltas, luego avance, luego tiempo."""
    tiempo = (m.get("seco_tiempo_s") or 999) + (m.get("mojado_tiempo_s") or 999)
    return (m["seco_vueltas_pct"] + m["mojado_vueltas_pct"],
            m["seco_progreso_pct"] + m["mojado_progreso_pct"], -tiempo)


def evaluar(politica, env, n=5, mu_seco=0.9, mu_mojado=0.5):
    res = {}
    for nombre, mu in (("seco", mu_seco), ("mojado", mu_mojado)):
        env.unwrapped.cfg.mu = mu
        ok, prog, tiempos = 0, 0.0, []
        for k in range(n):
            obs, info = env.unwrapped.reset(seed=SEMILLA_EVAL + k)
            done = False
            while not done:
                obs, _, term, trunc, info = env.unwrapped.step(ACCIONES[politica(obs)])
                done = term or trunc
            ok += info["outcome"] == "exito"
            prog += info["s_best"] / track.LAP
            if info["outcome"] == "exito":
                tiempos.append(info["t"])
        res[f"{nombre}_vueltas_pct"] = 100 * ok / n
        res[f"{nombre}_progreso_pct"] = 100 * prog / n
        res[f"{nombre}_tiempo_s"] = round(float(np.mean(tiempos)), 2) if tiempos else None
    return res


def entrenar(env_fn, params, grabador=None, al_terminar_episodio=None):
    """Entrena en dos fases (DAgger y Q-learning). Devuelve el agente y la lista de resúmenes."""
    from rally.agentes.ppo import AdherenciaAleatoria

    p = params
    env = AdherenciaAleatoria(env_fn(), p["mu_min"], p["mu_max"], p["prob_lluvia"], p["lluvia_min"], p["lluvia_max"])
    env.reset(seed=SEMILLA_BASE + p["semilla"] * 10_000)
    env_eval = env_fn()
    ag = AgenteQ(p["alpha"], p["gamma"], p["semilla"])
    profe = maestro(p)
    rng = np.random.default_rng(p["semilla"])
    cuentas = np.zeros((N_ESTADOS, len(ACCIONES)), dtype=np.float32)
    historia, pasos = [], 0

    def imitada(s):
        fila = cuentas[s]
        return NEUTRA if not fila.any() else int(np.argmax(fila))

    def episodio(elegir, fase, valor, etiquetar=False, aprender=False):
        nonlocal pasos
        obs, info = env.reset()
        s, done, total = estado(obs), False, 0.0
        while not done:
            if etiquetar:
                cuentas[s, discreta(profe(obs, info))] += 1
            a = elegir(s, obs, info)
            obs, r, term, trunc, info = env.step(ACCIONES[a])
            s2 = estado(obs)
            if aprender:
                ag.aprender(s, a, r, s2, term)
            else:
                ag.visitas[s] += 1
            if grabador is not None:
                grabador.paso(obs, info, ACCIONES[a], r)
            s, total, pasos, done = s2, total + r, pasos + 1, term or trunc
        res = {"episodio": len(historia) + 1, "recompensa": total, "resultado": info["outcome"],
               "tiempo": info["t"], "progreso": info["s_best"], "epsilon": valor, "pasos": pasos, "fase": fase}
        if grabador is not None:
            grabador.fin(info, pasos, {"epsilon": valor})
        historia.append(res)
        if al_terminar_episodio:
            al_terminar_episodio(res, ag)

    def revisar(politica, paso, prefijo, mejor):
        m = evaluar(politica, env_eval)
        mlflow.log_metrics({f"{prefijo}_{k}": v for k, v in m.items() if v is not None}, step=paso)
        print(f"  {prefijo} {paso}: seco {m['seco_vueltas_pct']:.0f}% · mojado {m['mojado_vueltas_pct']:.0f}%", flush=True)
        return (puntaje(m), m) if mejor is None or puntaje(m) > mejor[0] else None

    # ---- Fase 1: imitación con DAgger
    mejor, mejores_cuentas = None, cuentas.copy()
    for it in range(p["dagger_iter"]):
        beta = 1.0 if it == 0 else max(0.0, 0.6 - 0.06 * (it - 1))   # probabilidad de que maneje el maestro
        for _ in range(p["dagger_episodios"]):
            episodio(lambda s, obs, info: discreta(profe(obs, info)) if rng.random() < beta else imitada(s),
                     "dagger", beta, etiquetar=True)
        nuevo = revisar(lambda o: imitada(estado(o)), it + 1, "dagger", mejor)
        if nuevo:
            mejor, mejores_cuentas = nuevo, cuentas.copy()

    # ---- Fase 2: Q-learning desde la mejor imitación
    total = mejores_cuentas.sum(1, keepdims=True)
    ag.q = np.where(total > 0, p["q_inicial"] * mejores_cuentas / np.maximum(total, 1), 0).astype(np.float32)
    mejor_q = (mejor[0], ag.q.copy(), mejor[1], 0)
    for k in range(p["episodios"]):
        frac = k / max(p["episodios"] - 1, 1)
        eps = p["epsilon_inicial"] + (p["epsilon_final"] - p["epsilon_inicial"]) * frac
        episodio(lambda s, obs, info: ag.elegir(s, eps), "qlearning", eps, aprender=True)
        if (k + 1) % p["eval_cada"] == 0:
            nuevo = revisar(lambda o: ag.mejor(estado(o)), k + 1, "q", mejor_q)
            if nuevo:
                mejor_q = (nuevo[0], ag.q.copy(), nuevo[1], k + 1)
    ag.q = mejor_q[1]
    mlflow.log_metrics({f"mejor_{k}": v for k, v in mejor_q[2].items() if v is not None})
    mlflow.set_tag("mejor_episodio_qlearning", mejor_q[3])
    print(f"  Mejor tabla: episodio de Q-learning {mejor_q[3]} · {mejor_q[2]}")
    return ag, historia
