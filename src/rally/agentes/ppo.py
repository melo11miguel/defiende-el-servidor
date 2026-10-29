"""Agente con red neuronal: PPO (Stable-Baselines3 + PyTorch).

1. Preentrenamiento por imitación (behavior cloning) con las demostraciones
   del dataset: la red aprende a imitar al piloto experto.
2. Aprendizaje por refuerzo con PPO en varias simulaciones en paralelo: la red
   mejora sola con prueba y error, a partir de la recompensa.
3. Dominio aleatorio (opcional): en cada episodio la adherencia se sortea en un
   rango, para que el modelo aprenda a manejar también con lluvia.
"""

import json
from pathlib import Path

import gymnasium as gym
import mlflow
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv

from rally.env import AutonomousRallyEnv


class AdherenciaAleatoria(gym.Wrapper):
    """En cada reset sortea μ (el agente no ve el valor, solo si llueve).

    Con `prob_lluvia`, esa fracción de episodios es con lluvia (μ en [lluvia_min,
    lluvia_max]) y el resto en seco (μ en [mu_min, mu_max]). Así el modelo practica
    con lluvia la mitad del tiempo y no aprende solo a ir rápido en seco (lo que le
    pasó a la v2).
    """

    def __init__(self, env, mu_min, mu_max, prob_lluvia=None, lluvia_min=0.45, lluvia_max=0.6):
        super().__init__(env)
        self.mu_min, self.mu_max = mu_min, mu_max
        self.prob_lluvia, self.lluvia_min, self.lluvia_max = prob_lluvia, lluvia_min, lluvia_max

    def reset(self, **kw):
        r = self.np_random
        if self.prob_lluvia is not None and r.random() < self.prob_lluvia:
            mu = r.uniform(self.lluvia_min, self.lluvia_max)
        else:
            mu = r.uniform(self.mu_min, self.mu_max)
        self.env.unwrapped.cfg.mu = float(mu)
        return self.env.reset(**kw)


def crear_env(ambiente, ppo_params, rank):
    def _f():
        env = AutonomousRallyEnv(**ambiente)
        if ppo_params.get("dominio_aleatorio"):
            env = AdherenciaAleatoria(env, ppo_params["mu_min"], ppo_params["mu_max"],
                                      ppo_params.get("prob_lluvia"), ppo_params.get("lluvia_min", 0.45),
                                      ppo_params.get("lluvia_max", 0.6))
        env.reset(seed=200_000 + ppo_params["semilla"] * 1000 + rank)  # lejos de las semillas de evaluación
        return env
    return _f


def imitar(model, demos_path, epocas, lr=1e-3, batch=1024):
    """Behavior cloning: maximiza la probabilidad de las acciones del experto."""
    datos = np.load(demos_path)
    obs = torch.as_tensor(datos["obs"], dtype=torch.float32)
    acts = torch.as_tensor(np.clip(datos["acciones"], -0.999, 0.999), dtype=torch.float32)
    pol = model.policy
    opt = torch.optim.Adam(pol.parameters(), lr=lr)
    n = len(obs)
    perdidas = []
    for ep in range(epocas):
        perm = torch.randperm(n)
        total = 0.0
        for i in range(0, n, batch):
            idx = perm[i:i + batch]
            _, log_prob, entropia = pol.evaluate_actions(obs[idx], acts[idx])
            loss = -log_prob.mean() - 1e-3 * entropia.mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)
        perdidas.append(total / n)
        mlflow.log_metric("bc_perdida", perdidas[-1], step=ep)
    return perdidas


class Seguimiento(BaseCallback):
    """Registra cada episodio en MLflow y transmite el episodio del env 0 al visor."""

    def __init__(self, grabador, evaluador, eval_cada, n_envs, punto=None, pasos_iniciales=0, episodios_iniciales=0):
        super().__init__()
        self.grabador = grabador
        self.evaluador = evaluador
        self.eval_cada = eval_cada
        self.totales = np.zeros(n_envs)
        self.recientes = []
        self.n_ep = episodios_iniciales
        self.prox_eval = (pasos_iniciales // eval_cada + 1) * eval_cada
        self.punto = punto
        self.prox_punto = (pasos_iniciales // PUNTO_CADA + 1) * PUNTO_CADA

    def _on_step(self):
        infos, dones = self.locals["infos"], self.locals["dones"]
        rewards, actions = self.locals["rewards"], self.locals["actions"]
        self.totales += rewards
        if self.grabador is not None:
            obs0 = infos[0].get("terminal_observation", self.locals["new_obs"][0])
            self.grabador.paso(obs0, infos[0], np.clip(actions[0], -1, 1), float(rewards[0]))
        for i, d in enumerate(dones):
            if not d:
                continue
            info = infos[i]
            self.n_ep += 1
            self.recientes.append({"r": self.totales[i], "ok": info["outcome"] == "exito",
                                   "t": info["t"], "s": info["s_best"]})
            self.recientes = self.recientes[-50:]
            self.totales[i] = 0.0
            if i == 0 and self.grabador is not None:
                self.grabador.fin(info, self.num_timesteps)
            if self.n_ep % 10 == 0:
                rec = self.recientes
                mlflow.log_metrics({
                    "episodio_recompensa": float(np.mean([e["r"] for e in rec])),
                    "episodio_vueltas_pct": 100 * float(np.mean([e["ok"] for e in rec])),
                    "episodio_progreso_m": float(np.mean([e["s"] for e in rec])),
                    "episodios": self.n_ep,
                }, step=self.num_timesteps)
        if self.evaluador and self.num_timesteps >= self.prox_eval:
            self.prox_eval += self.eval_cada
            m = self.evaluador(self.model)
            mlflow.log_metrics({f"eval_{k}": v for k, v in m.items()}, step=self.num_timesteps)
        if self.punto and self.num_timesteps >= self.prox_punto:
            self.prox_punto += PUNTO_CADA
            self.punto.guardar(self.model, self.n_ep)
        return True


PUNTO_CADA = 200_000   # pasos entre puntos de guardado


class PuntoGuardado:
    """Guarda el entrenamiento a medias para seguir si el computador se apaga.

    Vive en runs/ (fuera de DVC, que borra models/ppo al empezar la etapa). Solo se
    reanuda si los parámetros y la versión del ambiente son los mismos (huella).
    """

    def __init__(self, carpeta, huella):
        self.carpeta, self.huella = Path(carpeta), huella

    def guardar(self, model, n_ep):
        self.carpeta.mkdir(parents=True, exist_ok=True)
        tmp = self.carpeta / "modelo.tmp.zip"
        model.save(tmp)
        tmp.replace(self.carpeta / "modelo.zip")    # escritura atómica
        (self.carpeta / "estado.json").write_text(json.dumps(
            {"huella": self.huella, "pasos": int(model.num_timesteps), "episodios": n_ep}), encoding="utf-8")

    def cargar(self):
        try:
            est = json.loads((self.carpeta / "estado.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if est.get("huella") != self.huella or not (self.carpeta / "modelo.zip").exists():
            return None
        return est

    def borrar(self):
        for f in ("modelo.zip", "estado.json"):
            (self.carpeta / f).unlink(missing_ok=True)


class PilotoPPO:
    """Usa el modelo entrenado como piloto (acción determinista)."""

    def __init__(self, ruta):
        self.model = PPO.load(ruta, device="cpu")

    def __call__(self, obs, info):
        a, _ = self.model.predict(np.asarray(obs, dtype=np.float32), deterministic=True)
        return np.clip(a, -1, 1)


def entrenar(ambiente, p, demos_path, salida, grabador=None, evaluador=None, punto=None):
    n_envs = p["n_envs"]
    venv = SubprocVecEnv([crear_env(ambiente, p, i) for i in range(n_envs)])
    previo = punto.cargar() if punto else None
    if previo:
        # Se reanuda donde quedó (el computador se apagó a mitad del entrenamiento)
        model = PPO.load(punto.carpeta / "modelo.zip", env=venv, device="cpu")
        perdidas = []
        print(f"  Reanudando desde el paso {previo['pasos']:,} (punto de guardado)")
        mlflow.set_tag("reanudado_desde_paso", previo["pasos"])
    else:
        model = PPO(
            "MlpPolicy", venv, learning_rate=p["learning_rate"], n_steps=p["n_steps"],
            batch_size=p["batch_size"], gamma=p["gamma"], gae_lambda=0.95, ent_coef=p["ent_coef"],
            clip_range=0.2, policy_kwargs={"net_arch": dict(pi=p["capas"], vf=p["capas"]),
                                           "log_std_init": -1.0},
            seed=p["semilla"], device="cpu", verbose=0,
        )
        perdidas = imitar(model, demos_path, p["bc_epocas"]) if p["bc_epocas"] > 0 else []
    hechos = previo["pasos"] if previo else 0
    cb = Seguimiento(grabador, evaluador, p["eval_cada"], n_envs, punto, hechos,
                     previo["episodios"] if previo else 0)
    model.learn(total_timesteps=max(p["pasos"] - hechos, 0), callback=cb, progress_bar=False,
                reset_num_timesteps=not previo)
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    model.save(salida / "modelo.zip")
    (salida / "info.json").write_text(json.dumps({
        "algoritmo": "PPO", "pasos": p["pasos"], "episodios": cb.n_ep,
        "bc_perdida_final": perdidas[-1] if perdidas else None,
        "observacion": int(venv.observation_space.shape[0]),
        "reanudado_desde_paso": hechos or None,
    }, indent=2), encoding="utf-8")
    venv.close()
    if punto:
        punto.borrar()   # terminó: el punto de guardado ya no hace falta
    return model, cb.n_ep
