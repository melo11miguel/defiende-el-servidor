"""Visor 3D (three.js) del ambiente: `rally web`.

El servidor corre los episodios con el ambiente de Python y le entrega al
navegador cada paso (posición, acción, rayos, recompensa...). El navegador solo
dibuja: la física y las reglas viven en el simulador.
"""

import json
import math
import mimetypes
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from rally import policies, track
from rally.env import RAY_ANGLES, AutonomousRallyEnv, RallyConfig

STATIC = Path(__file__).parent / "static"
console = Console()
mimetypes.add_type("application/javascript", ".js")


def _r(v, n=3):
    return round(float(v), n)


def datos_pista():
    cfg = RallyConfig()
    centro = []
    s = 0.0
    while s < track.LAP:
        x, y = track.point_at(s)
        _, _, h = track.project(x, y)
        centro.append([_r(s, 2), _r(x), _r(y), _r(h, 4), int(track.in_corner(s))])
        s += 0.5
    puertas = []
    for i, (gs, gx, gy) in enumerate(track.GATES):
        _, _, h = track.project(gx, gy)
        puertas.append({"id": i + 1, "s": _r(gs), "x": gx, "y": gy, "h": _r(h, 4),
                        "nombre": "META" if i == 3 else f"CP{i + 1}"})
    return {
        "largo": _r(track.LAP),
        "ancho": cfg.track_width,
        "radio": track.R,
        "mapa": [track.MAP_X, track.MAP_Y],
        "centro": centro,
        "puertas": puertas,
        "bloques": [list(o) for o in track.OBSTACLES],
        "carro": {"largo": cfg.car_length, "ancho": cfg.car_width, "ejes": cfg.wheelbase},
        "rayos": {"angulos": [_r(a, 4) for a in RAY_ANGLES], "alcance": cfg.r_max},
        "pilotos": {k: v[0] for k, v in policies.POLITICAS.items()},
        "dt": cfg.dt,
        "max_t": cfg.max_steps * cfg.dt,
        "delta_max": math.radians(cfg.delta_max_deg),
    }


def correr_episodio(piloto="experto", mu=0.9, semilla=0):
    env = AutonomousRallyEnv(mu=mu)
    pol = policies.crear(piloto, semilla)
    obs, info = env.reset(seed=semilla)
    total = 0.0
    frames = []

    def frame(obs, info, accion, r):
        return {
            "t": _r(info["t"], 2), "x": _r(info["x"]), "y": _r(info["y"]),
            "psi": _r(info["psi"], 4), "v": _r(info["v"]), "d": _r(info["d"]),
            "s": _r(max(info["s_best"], 0), 2), "cp": info["next_cp"],
            "agarre": _r(info["grip_use"]), "derrape": bool(info["skidding"]),
            "fuera": _r(info["off_steps"] * env.cfg.dt, 2),
            "rayos": [_r(v) for v in np.asarray(obs[6:13]) * env.cfg.r_max],
            "a": [_r(accion[0]), _r(accion[1])], "r": _r(r), "R": _r(total, 2),
            "fin": info["outcome"],
        }

    frames.append(frame(obs, info, (0.0, 0.0), 0.0))
    done = False
    while not done:
        accion = pol(obs, info)
        obs, r, term, trunc, info = env.step(accion)
        total += r
        frames.append(frame(obs, info, accion, r))
        done = term or trunc
    return {
        "piloto": piloto, "mu": mu, "semilla": semilla,
        "resultado": info["outcome"], "tiempo": _r(info["t"], 2), "recompensa": _r(total, 2),
        "salidas": info["off_track_events"], "frames": frames,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def log_message(self, fmt, *args):  # silencio: registramos solo los episodios
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, data):
        body = json.dumps(data, separators=(",", ":")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/pista":
            return self._json(datos_pista())
        if url.path == "/api/episodio":
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            piloto = q.get("piloto", "experto")
            if piloto not in policies.POLITICAS:
                self.send_error(400, "piloto desconocido")
                return
            mu = min(max(float(q.get("mu", 0.9)), 0.1), 1.2)
            semilla = int(q.get("semilla", 0))
            t0 = time.perf_counter()
            ep = correr_episodio(piloto, mu, semilla)
            ms = (time.perf_counter() - t0) * 1000
            color = "green" if ep["resultado"] == "exito" else "red"
            console.print(
                f"[grey50]{time.strftime('%H:%M:%S')}[/]  [bold]{piloto:9s}[/] "
                f"{'☀ seco  ' if mu >= 0.75 else '☂ mojado'}  semilla {semilla:<3d} → "
                f"[bold {color}]{ep['resultado']:9s}[/] {ep['tiempo']:5.1f} s  "
                f"recompensa {ep['recompensa']:+7.1f}  [grey50]({len(ep['frames'])} pasos, {ms:.0f} ms)[/]"
            )
            return self._json(ep)
        return super().do_GET()


def servir(puerto=8765, host="127.0.0.1"):
    try:
        server = ThreadingHTTPServer((host, puerto), partial(Handler))
    except OSError:
        console.print(f"[bold yellow]El puerto {puerto} ya está en uso.[/] Puede que ya haya un visor "
                      f"abierto en http://localhost:{puerto}. Usa otro con: [bold]rally web --puerto 8766[/]")
        return 1
    url = f"http://localhost:{puerto}"
    t = Text()
    t.append("AUTONOMOUS RALLY · visor 3D\n\n", style="bold bright_white")
    t.append("Abierto en  ", style="grey70")
    t.append(url + "\n\n", style="bold bright_cyan underline")
    t.append("Dentro de VS Code: ", style="grey70")
    t.append("Ctrl+Shift+P → Simple Browser: Show → " + url + "\n", style="bold")
    t.append("La física corre aquí en Python; el navegador solo dibuja.\n", style="grey62")
    t.append("Ctrl+C para detener.", style="grey50")
    console.print(Panel(t, border_style="bright_blue", padding=(1, 3)))
    console.print("[bold]Episodios[/]")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Servidor detenido.[/]")
    finally:
        server.server_close()
    return 0
