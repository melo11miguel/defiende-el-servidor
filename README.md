# Defiende el servidor

Detección de tráfico de ataque en conexiones de red con **UNSW-NB15**, construida como un ciclo de MLOps
reproducible: datos versionados con DVC, experimentos registrados en MLflow, pipeline orquestado con
Prefect y código en Git.

Curso MLOps, Universidad Externado de Colombia (2026-II).

## Pregunta central

¿Puede otra persona comprender y reproducir mi solución con la evidencia que entrego?

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
