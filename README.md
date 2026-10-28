# Defiende el servidor

Detección de tráfico de ataque en conexiones de red con **UNSW-NB15**, construida como un ciclo de MLOps
reproducible: datos versionados con DVC, experimentos registrados en MLflow, pipeline orquestado con
Prefect y código en Git.

Curso MLOps, Universidad Externado de Colombia (2026-II).

## Pregunta central

¿Puede otra persona comprender y reproducir nuestra solución con la evidencia que entregamos?

## Objetivo

1. **Principal:** clasificación binaria, tráfico normal (`label = 0`) contra ataque (`label = 1`).
2. **Ampliación:** reconocer la familia del ataque (`attack_cat`).

## Estado

Repositorio en construcción. Plan de trabajo:

- [ ] Obtener UNSW-NB15 desde la fuente oficial de UNSW y documentar versión, checksums y condiciones de uso.
- [ ] Exploración: clases, ausentes, duplicados, significado del `id` y variables que filtran la respuesta.
- [ ] Particiones fijas de entrenamiento, validación y test, sin duplicados cruzados.
- [ ] Referencia sencilla y al menos cuatro configuraciones con hipótesis previa (dos tipos de modelo).
- [ ] Selección de modelo y umbral con validación; evaluación única en test.
- [ ] Pipeline en Prefect: preparación, entrenamiento, comparación y registro.
- [ ] Modelo completo (preprocesamiento incluido) versionado y cargable para predecir.
- [ ] Decisión final y limitaciones del dataset.

## Estructura (prevista)

```
data/          datos crudos y procesados (controlados por DVC, no por Git)
src/defiende/  código del proyecto
flows/         pipeline de Prefect
docs/          dataset, experimentos y decisión final
tests/         pruebas
```

## Atribución del dataset

UNSW-NB15 fue creado por el Cyber Range Lab de UNSW Canberra. Si se usa, se deben citar:

- Moustafa, N. y Slay, J. (2015). UNSW-NB15: a comprehensive data set for network intrusion detection
  systems (UNSW-NB15 network data set). *Military Communications and Information Systems Conference (MilCIS)*.
- Moustafa, N. y Slay, J. (2016). The evaluation of Network Anomaly Detection Systems: Statistical analysis
  of the UNSW-NB15 data set and the comparison with the KDD99 data set. *Information Security Journal:
  A Global Perspective*, 25(1-3), 18-31.

Fuente: https://research.unsw.edu.au/projects/unsw-nb15-dataset

## Ambiente Autonomous Rally (aprendizaje por refuerzo)

Diseño en [docs/ambiente-v0.1.md](docs/ambiente-v0.1.md). Implementación en `src/rally/` como ambiente
Gymnasium `AutonomousRally-v0`.

### Instalación

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"      # Windows: .venv\Scripts\pip install -e ".[dev]"
source .venv/bin/activate              # Windows: .venv\Scripts\activate
```

### Ver y evaluar en la terminal

```bash
rally ver                          # una vuelta en vivo (piloto experto, piso seco)
rally ver --lluvia                 # incidente: asfalto mojado (μ = 0.5)
rally ver --piloto prudente --lluvia
rally ver --piloto aleatoria       # sin estrategia: no completa la vuelta
rally ver --velocidad 2            # el doble de rápido
rally evaluar                      # métricas de la ficha, seco vs mojado, y veredicto
rally transiciones                 # las 5 transiciones de la ficha contra el ambiente
rally mapa                         # la pista
```

Los pilotos `experto` y `prudente` son líneas base que leen el estado interno del simulador; no son el
agente. Para que el mapa se vea grande, maximiza la terminal.

### Uso desde Python

```python
import gymnasium as gym
import rally

env = gym.make("AutonomousRally-v0")          # o AutonomousRally-v0 con mu=0.5 para lluvia
obs, info = env.reset(seed=0)
obs, recompensa, terminado, truncado, info = env.step([1.0, 0.0])  # [acelerador, dirección]
```
