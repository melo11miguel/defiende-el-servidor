"""Ambiente Gymnasium de Autonomous Rally (diseño: docs/ambiente-v0.1.md)."""

import math
from dataclasses import dataclass

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from rally import track

G = 9.81
RAY_ANGLES = np.radians([-90, -60, -30, 0, 30, 60, 90])


@dataclass
class RallyConfig:
    # Parámetros del escenario
    track_width: float = 8.0  # w (m)
    mu: float = 0.9  # adherencia del asfalto
    mu_grass: float = 0.35  # adherencia del césped
    a_max: float = 4.0  # m/s²
    b_max: float = 8.0  # m/s²
    r_max: float = 20.0  # alcance de sensores (m)
    v_max: float = 25.0  # m/s
    delta_max_deg: float = 30.0  # dirección máxima (°)
    dt: float = 0.1  # s
    drag: float = 0.05  # 1/s
    # Carro
    wheelbase: float = 2.5
    car_length: float = 4.0
    car_width: float = 1.8
    # Episodio
    max_steps: int = 600  # 60 s
    off_track_limit: int = 10  # pasos seguidos fuera de pista (1 s)
    stall_limit: int = 100  # pasos sin mejorar s_best (10 s)
    start_lateral_noise: float = 0.5  # m
    start_heading_noise_deg: float = 5.0
    # Recompensa
    w_progress: float = 0.1  # por metro
    r_checkpoint: float = 10.0
    r_lap: float = 50.0
    r_time: float = -0.05  # por paso
    r_off_track: float = -1.0  # por paso
    w_steer_change: float = 0.2
    w_throttle_change: float = 0.05
    r_fail: float = -50.0


class AutonomousRallyEnv(gym.Env):
    """Una vuelta a la pista pasando CP1 -> CP2 -> CP3 -> meta.

    Observación (13): [v, ω, sinφ, cosφ, d, eψ, 7 rayos], normalizada.
    Acción (2): [u_acel, u_dir] en [-1, 1].
    """

    metadata = {"render_modes": ["ansi"], "render_fps": 10}

    def __init__(self, config: RallyConfig | None = None, render_mode=None, **overrides):
        self.cfg = config or RallyConfig()
        for k, v in overrides.items():
            setattr(self.cfg, k, v)
        self.render_mode = render_mode
        self.delta_max = math.radians(self.cfg.delta_max_deg)

        low = np.array([0, -1, -1, -1, -2, -1] + [0] * 7, dtype=np.float32)
        high = np.array([1, 1, 1, 1, 2, 1] + [1] * 7, dtype=np.float32)
        self.observation_space = spaces.Box(low, high, dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32)

    # ------------------------------------------------------------------ API

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        cfg = self.cfg
        state = (options or {}).get("state")
        if state is None:
            # Salida en (-40, 0) mirando al sur, con ruido.
            lat = self.np_random.uniform(-cfg.start_lateral_noise, cfg.start_lateral_noise)
            dpsi = math.radians(
                self.np_random.uniform(-cfg.start_heading_noise_deg, cfg.start_heading_noise_deg)
            )
            state = {"x": -40.0 + lat, "y": 0.0, "psi": -math.pi / 2 + dpsi}

        self.x = float(state["x"])
        self.y = float(state["y"])
        self.psi = float(state["psi"])
        self.v = float(state.get("v", 0.0))
        self.omega = float(state.get("omega", 0.0))
        self.next_cp = int(state.get("next_cp", 1))
        self.steps = int(round(state.get("t", 0.0) / cfg.dt))
        self.off_steps = int(state.get("off_steps", 0))
        self.prev_action = np.array(state.get("prev_action", (0.0, 0.0)), dtype=np.float64)

        s_raw, self.d, _ = track.project(self.x, self.y)
        default_cum = s_raw if s_raw <= track.LAP / 2 else s_raw - track.LAP
        self.s_raw = s_raw
        self.s_cum = float(state.get("s_cum", default_cum))
        self.s_best = float(state.get("s_best", max(self.s_cum, 0.0)))
        self.stall_steps = 0
        self.off_track_events = 0
        self.outcome = None

        return self._obs(), self._info()

    def step(self, action):
        cfg = self.cfg
        u = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        u_acel, u_dir = float(u[0]), float(u[1])

        # 1-5. Mandos -> aceleraciones, limitadas por el círculo de fricción
        delta = u_dir * self.delta_max
        a_long = u_acel * (cfg.a_max if u_acel >= 0 else cfg.b_max) - cfg.drag * self.v
        mu = cfg.mu if abs(self.d) <= cfg.track_width / 2 else cfg.mu_grass
        grip = mu * G
        a_long = max(-grip, min(grip, a_long))
        tan_d = math.tan(delta)
        if self.v > 0:
            a_lat = self.v**2 * abs(tan_d) / cfg.wheelbase
            a_lat_max = math.sqrt(max(grip**2 - a_long**2, 0.0))
            if a_lat > a_lat_max:  # subviraje: gira menos de lo pedido
                tan_d = math.copysign(a_lat_max * cfg.wheelbase / self.v**2, tan_d)

        # 6-8. Integración (bicicleta cinemática)
        v_new = min(max(self.v + a_long * cfg.dt, 0.0), cfg.v_max)
        dpsi = v_new * tan_d / cfg.wheelbase * cfg.dt
        self.psi = track.wrap_angle(self.psi + dpsi)
        self.omega = dpsi / cfg.dt
        self.v = v_new
        self.x += v_new * math.cos(self.psi) * cfg.dt
        self.y += v_new * math.sin(self.psi) * cfg.dt
        self.steps += 1

        # 9. Proyección sobre la pista; s acumulado sin módulo
        s_raw, self.d, _ = track.project(self.x, self.y)
        ds = (s_raw - self.s_raw + track.LAP / 2) % track.LAP - track.LAP / 2
        s_prev = self.s_cum
        self.s_cum += ds
        self.s_raw = s_raw
        on_track = abs(self.d) <= cfg.track_width / 2

        # 10. Reglas
        reward = cfg.r_time
        reward -= cfg.w_steer_change * abs(u_dir - self.prev_action[1])
        reward -= cfg.w_throttle_change * abs(u_acel - self.prev_action[0])
        self.prev_action = u

        terminated = False
        if self.next_cp <= len(track.GATES) and on_track:
            gate_s = track.GATES[self.next_cp - 1][0]
            if s_prev < gate_s <= self.s_cum:
                if self.next_cp == len(track.GATES):
                    reward += cfg.r_lap
                    terminated, self.outcome = True, "exito"
                else:
                    reward += cfg.r_checkpoint
                self.next_cp += 1

        if on_track:
            cap = track.GATES[min(self.next_cp, len(track.GATES)) - 1][0]
            new_best = max(self.s_best, min(self.s_cum, cap))
            gain = new_best - self.s_best
            reward += cfg.w_progress * gain
            self.s_best = new_best
            self.off_steps = 0
        else:
            gain = 0.0
            if self.off_steps == 0:
                self.off_track_events += 1
            self.off_steps += 1
            reward += cfg.r_off_track
        self.stall_steps = 0 if gain > 1e-9 else self.stall_steps + 1

        if not terminated:
            if track.car_collides(self.x, self.y, self.psi, cfg.car_length, cfg.car_width):
                terminated, self.outcome = True, "choque"
                reward += cfg.r_fail
            elif self.off_steps >= cfg.off_track_limit:
                terminated, self.outcome = True, "salida"
                reward += cfg.r_fail
            elif self.stall_steps >= cfg.stall_limit:
                terminated, self.outcome = True, "estancado"

        truncated = not terminated and self.steps >= cfg.max_steps
        if truncated:
            self.outcome = "tiempo"

        return self._obs(), float(reward), terminated, truncated, self._info()

    def render(self):
        if self.render_mode == "ansi":
            return self._ascii()
        return None

    # ------------------------------------------------------------ Internos

    def _obs(self):
        cfg = self.cfg
        _, d, tangent = track.project(self.x, self.y)
        cp = track.GATES[min(self.next_cp, len(track.GATES)) - 1]
        phi = track.wrap_angle(math.atan2(cp[2] - self.y, cp[1] - self.x) - self.psi)
        e_psi = track.wrap_angle(self.psi - tangent)
        rays = track.raycast(
            self.x, self.y, self.psi, RAY_ANGLES, cfg.r_max, cfg.track_width / 2
        )
        obs = [
            self.v / cfg.v_max,
            np.clip(self.omega / 2.0, -1, 1),
            math.sin(phi),
            math.cos(phi),
            np.clip(d / (cfg.track_width / 2), -2, 2),
            e_psi / math.pi,
            *(rays / cfg.r_max),
        ]
        return np.array(obs, dtype=np.float32)

    def _info(self):
        return {
            "x": self.x,
            "y": self.y,
            "psi": self.psi,
            "v": self.v,
            "d": self.d,
            "s": self.s_cum,
            "s_best": self.s_best,
            "next_cp": self.next_cp,
            "t": self.steps * self.cfg.dt,
            "off_track_events": self.off_track_events,
            "outcome": self.outcome,
        }

    def _ascii(self, cols=50, rows=18):
        """Mapa en texto: '#' pista, '.' césped, 'B' bloque, números CP, '@' carro."""
        xs = np.linspace(-track.MAP_X, track.MAP_X, cols)
        ys = np.linspace(track.MAP_Y, -track.MAP_Y, rows)
        gx, gy = np.meshgrid(xs, ys)
        on = np.abs(track.lateral(gx, gy)) <= self.cfg.track_width / 2
        grid = np.where(on, "#", ".").astype("<U1")
        grid[track.in_obstacle(gx, gy)] = "B"

        def cell(x, y):
            c = int(round((x + track.MAP_X) / (2 * track.MAP_X) * (cols - 1)))
            r = int(round((track.MAP_Y - y) / (2 * track.MAP_Y) * (rows - 1)))
            return min(max(r, 0), rows - 1), min(max(c, 0), cols - 1)

        for i, (_, gx_, gy_) in enumerate(track.GATES):
            grid[cell(gx_, gy_)] = "M" if i == 3 else str(i + 1)
        grid[cell(self.x, self.y)] = "@"
        status = (
            f"t={self.steps * self.cfg.dt:5.1f}s v={self.v:5.2f}m/s s={self.s_cum:7.2f}m "
            f"d={self.d:+.2f}m sig.CP={self.next_cp}"
        )
        return "\n".join("".join(r) for r in grid) + "\n" + status
