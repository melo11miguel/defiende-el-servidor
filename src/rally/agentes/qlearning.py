"""Agente Q-learning con tabla (el primer agente del tablero).

Q(s, a) <- Q(s, a) + α · [r + γ · max_a' Q(s', a') − Q(s, a)]

Usa las 15 acciones discretas y el estado discretizado de `discreto.py`.
Explora con ε-greedy: al principio casi todo es al azar y con los episodios
va confiando más en lo aprendido.
"""

from pathlib import Path

import numpy as np

from rally.agentes.discreto import ACCIONES, N_ESTADOS, estado

# Semillas de entrenamiento lejos de las de evaluación (0-99) y del dataset (500+)
SEMILLA_BASE = 100_000


class AgenteQ:
    def __init__(self, alpha=0.1, gamma=0.99, seed=0):
        self.q = np.zeros((N_ESTADOS, len(ACCIONES)), dtype=np.float32)
        self.visitas = np.zeros(N_ESTADOS, dtype=np.int64)
        self.alpha, self.gamma = alpha, gamma
        self.rng = np.random.default_rng(seed)

    def elegir(self, s, epsilon=0.0):
        if self.rng.random() < epsilon:
            return int(self.rng.integers(len(ACCIONES)))
        fila = self.q[s]
        return int(self.rng.choice(np.flatnonzero(fila == fila.max())))

    def aprender(self, s, a, r, s2, terminal):
        objetivo = r if terminal else r + self.gamma * self.q[s2].max()
        self.q[s, a] += self.alpha * (objetivo - self.q[s, a])
        self.visitas[s] += 1

    # Como piloto para el visor y la evaluación: sin explorar y determinista
    # (los empates se rompen siempre igual, así la evaluación es reproducible)
    def __call__(self, obs, info):
        return ACCIONES[int(np.argmax(self.q[estado(obs)]))]

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


def entrenar(env_fn, params, grabador=None, al_terminar_episodio=None):
    """Entrena episodio a episodio. Devuelve el agente y la lista de resúmenes."""
    p = params
    env = env_fn()
    ag = AgenteQ(p["alpha"], p["gamma"], p["semilla"])
    historia, pasos = [], 0
    for ep in range(p["episodios"]):
        frac = ep / max(p["episodios"] - 1, 1)
        eps = p["epsilon_inicial"] + (p["epsilon_final"] - p["epsilon_inicial"]) * min(1.0, frac / 0.8)
        obs, info = env.reset(seed=SEMILLA_BASE + p["semilla"] * 10_000 + ep)
        s, done, total = estado(obs), False, 0.0
        while not done:
            a = ag.elegir(s, eps)
            obs, r, term, trunc, info = env.step(ACCIONES[a])
            s2 = estado(obs)
            ag.aprender(s, a, r, s2, term)
            if grabador is not None:
                grabador.paso(obs, info, ACCIONES[a], r)
            s, total, pasos, done = s2, total + r, pasos + 1, term or trunc
        res = {"episodio": ep + 1, "recompensa": total, "resultado": info["outcome"],
               "tiempo": info["t"], "progreso": info["s_best"], "epsilon": eps, "pasos": pasos}
        if grabador is not None:
            grabador.fin(info, pasos, {"epsilon": eps})
        historia.append(res)
        if al_terminar_episodio:
            al_terminar_episodio(res, ag)
    return ag, historia
