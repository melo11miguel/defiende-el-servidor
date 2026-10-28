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
    """En cada reset sortea μ en [mu_min, mu_max] (el agente no lo observa)."""

    def __init__(self, env, mu_min, mu_max):
        super().__init__(env)
        self.mu_min, self.mu_max = mu_min, mu_max

    def reset(self, **kw):
        self.env.unwrapped.cfg.mu = float(self.np_random.uniform(self.mu_min, self.mu_max))
        return self.env.reset(**kw)


def crear_env(ambiente, ppo_params, rank):
    def _f():
        env = AutonomousRallyEnv(**ambiente)
        if ppo_params.get("dominio_aleatorio"):
            env = AdherenciaAleatoria(env, ppo_params["mu_min"], ppo_params["mu_max"])
        env.reset(seed=ppo_params["semilla"] * 1000 + rank)
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

    def __init__(self, grabador, evaluador, eval_cada, n_envs):
        super().__init__()
        self.grabador = grabador
        self.evaluador = evaluador
        self.eval_cada = eval_cada
        self.totales = np.zeros(n_envs)
        self.recientes = []
        self.n_ep = 0
        self.prox_eval = eval_cada

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
        return True


class PilotoPPO:
    """Usa el modelo entrenado como piloto (acción determinista)."""

    def __init__(self, ruta):
        self.model = PPO.load(ruta, device="cpu")

    def __call__(self, obs, info):
        a, _ = self.model.predict(np.asarray(obs, dtype=np.float32), deterministic=True)
        return np.clip(a, -1, 1)


def entrenar(ambiente, p, demos_path, salida, grabador=None, evaluador=None):
    n_envs = p["n_envs"]
    venv = SubprocVecEnv([crear_env(ambiente, p, i) for i in range(n_envs)])
    model = PPO(
        "MlpPolicy", venv, learning_rate=p["learning_rate"], n_steps=p["n_steps"],
        batch_size=p["batch_size"], gamma=p["gamma"], gae_lambda=0.95, ent_coef=p["ent_coef"],
        clip_range=0.2, policy_kwargs={"net_arch": dict(pi=p["capas"], vf=p["capas"]),
                                       "log_std_init": -1.0},
        seed=p["semilla"], device="cpu", verbose=0,
    )
    perdidas = imitar(model, demos_path, p["bc_epocas"]) if p["bc_epocas"] > 0 else []
    cb = Seguimiento(grabador, evaluador, p["eval_cada"], n_envs)
    model.learn(total_timesteps=p["pasos"], callback=cb, progress_bar=False)
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    model.save(salida / "modelo.zip")
    (salida / "info.json").write_text(json.dumps({
        "algoritmo": "PPO", "pasos": p["pasos"], "episodios": cb.n_ep,
        "bc_perdida_final": perdidas[-1] if perdidas else None,
        "observacion": int(venv.observation_space.shape[0]),
    }, indent=2), encoding="utf-8")
    venv.close()
    return model, cb.n_ep
