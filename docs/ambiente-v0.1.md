# Ambiente v0.1 — Autonomous Rally

> Equipo: _______ · Versión 0.1 · 28 oct 2026
> Mapa: [mapa-ambiente-v0.1.svg](mapa-ambiente-v0.1.svg) · Ficha original: [ficha-autonomous-rally.png](ficha-autonomous-rally.png)
>
> Diseño previo a la implementación. Los valores son propuestas iniciales que hay que calibrar en simulación.

## Mision y mapa

**Misión:** dar una vuelta completa a la pista pasando los checkpoints **en orden** (CP1 → CP2 → CP3 → Meta) sin salirse ni chocar, en el menor tiempo posible.

![Mapa del ambiente](mapa-ambiente-v0.1.svg)

**Geometría (vista superior, 2D, coordenadas en metros, origen en el centro del mapa, eje y hacia arriba):**

| Elemento | Definición |
|---|---|
| Mapa | Rectángulo de 100 × 70 m (x ∈ [−50, 50], y ∈ [−35, 35]) rodeado por un muro |
| Línea central de la pista | Rectángulo redondeado de 80 × 50 m (x ∈ [−40, 40], y ∈ [−25, 25]) con radio de curva de 12 m |
| Ancho de pista | w = 8 m (borde interior a radio 8 m y exterior a radio 16 m en las curvas) |
| Largo de vuelta | L = 4 rectas (2·56 + 2·26 = 164 m) + 4 cuartos de curva (4 · 18.85 = 75.40 m) = **239.40 m** |
| Sentido | Antihorario: baja por la recta izquierda, sigue a la derecha por la de abajo, sube por la derecha y vuelve a la izquierda por la de arriba |
| Salida / Meta | (−40, 0), s = 0 m (y s = 239.40 m al cerrar la vuelta). El carro arranca mirando al sur (ψ = −90°) |
| CP1 | Puerta en (0, −25), s = 59.85 m |
| CP2 | Puerta en (40, 0), s = 119.70 m |
| CP3 | Puerta en (0, 25), s = 179.55 m |
| Superficies | Asfalto dentro de la pista; césped entre la pista y el muro y en todo el interior |
| Obstáculos | 4 bloques de concreto de 6 × 2 m en el césped interior: B1 (−15, −8), B2 (15, −10), B3 (−12, 10) y B4 (18, 9), este último en vertical |

Cada checkpoint es una puerta perpendicular a la pista que cubre todo su ancho. `s` es la distancia recorrida sobre la línea central desde la salida.

**Carro:** largo 4.0 m, ancho 1.8 m, distancia entre ejes 2.5 m. Se usa un modelo cinemático de bicicleta.

## Variables y unidades

### Parámetros del escenario (se fijan antes de cada ejecución)

| Parámetro | Símbolo | Unidad | Base | Rango | Justificación | ¿Lo ve el agente? |
|---|---|---|---|---|---|---|
| Ancho de pista | w | m | 8 | [6, 12] | El carro mide 1.8 m. Con 6 m quedan unos 2 m por lado (pista exigente); con 12 m sobra espacio para trazar la curva | Indirectamente (rayos) |
| Adherencia del asfalto | μ | coeficiente | 0.9 | [0.4, 1.0] | 0.9 ≈ asfalto seco y 0.5 ≈ mojado. Limita la aceleración total a μ·g | No |
| Adherencia del césped | μ_c | coeficiente | 0.35 | fija | Fuera de pista se agarra mucho menos | No |
| Aceleración máxima | a_max | m/s² | 4 | [2, 6] | 4 m/s² equivale a 0→100 km/h en unos 7 s, como un carro compacto | No |
| Frenado máximo | b_max | m/s² | 8 | fijo | Frenada fuerte en seco (≤ μ·g = 8.83) | No |
| Alcance de sensores | r_max | m | 20 | [10, 40] | Una curva de radio 12 m con μ = 0.9 admite como máximo √(μ·g·12) ≈ 10.3 m/s. Frenando a 8 m/s², 20 m de visión alcanzan para entrar a ≈ 20.6 m/s; con 40 m se podría ir a v_max | Indirectamente (rayos) |
| Velocidad máxima | v_max | m/s | 25 | fija | 90 km/h. La vuelta ideal dura unos 20 s | No |
| Dirección máxima | δ_max | ° | 30 | fija | Ángulo típico de las ruedas delanteras | No |
| Paso de tiempo | dt | s | 0.1 | fijo | 10 Hz es suficiente para este control | No |
| Resistencia | k | 1/s | 0.05 | fija | Hace que el carro pierda velocidad si no acelera | No |

### Estado del mundo (lo que conoce el simulador)

| Variable | Significado | Unidad | Rango | ¿Lo ve el agente? |
|---|---|---|---|---|
| x, y | Posición del centro del carro | m | [−50, 50] × [−35, 35] | No |
| ψ | Orientación (0 = este, sentido antihorario positivo) | rad | (−π, π] | No (solo el error relativo a la pista) |
| v | Velocidad hacia adelante | m/s | [0, 25] | Sí |
| ω | Velocidad de giro | rad/s | [−2, 2] | Sí |
| s | Progreso acumulado sobre la línea central | m | [0, 239.40] | No |
| s_best | Máximo progreso válido alcanzado | m | [0, 239.40] | No |
| d | Desvío lateral del centro (+ a la izquierda) | m | [−8, 8] | Sí (normalizado) |
| next_cp | Siguiente checkpoint que hay que cruzar | entero | {1, 2, 3, 4 = meta} | Indirectamente (dirección) |
| t | Tiempo del episodio | s | [0, 60] | No |
| t_fuera | Tiempo seguido fuera de pista | s | [0, 1.0] | No |
| colision | Si el carro tocó un muro u obstáculo | bool | {0, 1} | No (termina el episodio) |
| u_prev | Acción del paso anterior | — | [−1, 1]² | No |

## Observaciones y acciones

### Observación (vector de 13 valores normalizados)

| # | Componente | Cálculo | Rango |
|---|---|---|---|
| 0 | Velocidad | v / v_max | [0, 1] |
| 1 | Giro | clip(ω / 2, −1, 1) | [−1, 1] |
| 2–3 | Dirección al siguiente checkpoint | sin φ, cos φ, donde φ es el ángulo entre el rumbo del carro y el centro de la próxima puerta (+ = izquierda) | [−1, 1] |
| 4 | Desvío del centro | clip(d / (w/2), −2, 2). Si \|valor\| > 1, el carro está fuera de pista | [−2, 2] |
| 5 | Error de rumbo respecto a la pista | e_ψ / π | [−1, 1] |
| 6–12 | 7 rayos a −90°, −60°, −30°, 0°, +30°, +60° y +90° respecto al rumbo | distancia al borde de pista, obstáculo o muro / r_max (1 si no detecta nada) | [0, 1] |

El componente 5 no está en la ficha original. Lo agregamos porque, sin él, en una recta larga el agente no puede distinguir si va paralelo a la pista.

### Acción (continua, 2 controles)

| Control | Rango | Significado |
|---|---|---|
| u_acel | [−1, 1] | Valores positivos aceleran (u·a_max); valores negativos frenan (u·b_max). No hay reversa: v ≥ 0 |
| u_dir | [−1, 1] | Ángulo de ruedas δ = u_dir · δ_max (+ = izquierda) |

## Dinamica

En cada paso (dt = 0.1 s), el simulador aplica estas reglas en orden:

1. Recorta las acciones a [−1, 1].
2. Calcula la dirección: δ = u_dir · 30°.
3. Calcula la aceleración longitudinal: `a_long = u_acel·a_max` si u_acel ≥ 0; si no, `a_long = u_acel·b_max`. Luego le resta `k·v`.
4. Elige la adherencia: μ_ef = μ si el carro está en pista (|d| ≤ w/2) y μ_c = 0.35 si está en el césped.
5. Aplica el **círculo de fricción**:
   - Recorta |a_long| a μ_ef·g.
   - La aceleración lateral pedida es `a_lat = v²·tan δ / L_ejes`, y el máximo permitido es `√((μ_ef·g)² − a_long²)`.
   - Si se pide más de lo permitido, el carro **subvira**: `tan δ_ef = a_lat_max · L_ejes / v²`. En otras palabras, gira menos de lo que se ordenó y se abre en la curva.
6. Actualiza la velocidad: v' = clip(v + a_long·dt, 0, v_max).
7. Actualiza la orientación: ψ' = ψ + (v'·tan δ_ef / L_ejes)·dt.
8. Actualiza la posición: x' = x + v'·cos ψ'·dt e y' = y + v'·sin ψ'·dt.
9. Proyecta la posición sobre la línea central para obtener s' y d'.
10. Aplica las reglas:
    - **Checkpoint:** si s cruza la puerta de `next_cp` hacia adelante con |d'| ≤ w/2, entonces `next_cp += 1`. Cruzar hacia atrás no cambia nada.
    - **Progreso válido:** si |d'| ≤ w/2, entonces `s_best = max(s_best, min(s', s_puerta(next_cp)))`. El progreso no puede pasar la próxima puerta sin haberla cruzado.
    - **Colisión:** si el rectángulo del carro toca un bloque o el muro, termina el episodio.
    - **Fuera de pista:** si |d'| > w/2, se suma dt a t_fuera; si vuelve a la pista, t_fuera = 0.
    - **Tiempo:** t' = t + dt.

Consecuencia importante: con μ = 0.9 la curva de radio 12 m solo se puede tomar a ≈ 10.3 m/s, y con μ = 0.5 a ≈ 7.7 m/s. El agente tiene que aprender a **frenar antes de la curva**.

## Recompensa

Recompensa por paso: `r = r_prog + r_cp + r_vuelta + r_tiempo + r_fuera + r_suave + r_fin`

| Término | Valor | Cuándo |
|---|---|---|
| r_prog | +0.1 por metro de **aumento de s_best** | Solo cuando el carro está en pista y hasta la siguiente puerta |
| r_cp | +10 | Al cruzar el checkpoint que toca (CP1, CP2, CP3), una sola vez |
| r_vuelta | +50 | Al cruzar la meta con next_cp = 4 |
| r_tiempo | −0.05 por paso | Siempre (−0.5 por segundo) |
| r_fuera | −1.0 por paso | Mientras \|d\| > w/2 |
| r_suave | −0.2·\|Δu_dir\| − 0.05·\|Δu_acel\| | Penaliza los cambios bruscos de mando |
| r_fin | −50 | Al chocar o salir de la pista por ≥ 1 s |

**Escala esperada:**
- Una vuelta limpia en ~21 s da ≈ +24 (progreso) + 30 (CP) + 50 (vuelta) − 10.7 (tiempo) − (suavidad) ≈ **+90**.
- Un choque temprano da ≈ **−50**.
- Quedarse quieto hasta el límite de tiempo da **−30**.

Este orden de valores (vuelta ≫ quieto > choque) es intencional.

## Exito, fracaso y limite de tiempo

| Resultado | Condición | Tipo de fin |
|---|---|---|
| **Éxito** | Cruzar CP1, CP2, CP3 y la meta en orden, en pista | `terminated`, éxito |
| **Fracaso: choque** | El carro toca un bloque o el muro | `terminated`, −50 |
| **Fracaso: salida de pista** | t_fuera ≥ 1.0 s (10 pasos seguidos con \|d\| > w/2) | `terminated`, −50 |
| **Fracaso: estancado** | s_best no mejora durante 10 s | `terminated`, sin penalización extra (ya acumuló la de tiempo) |
| **Límite de tiempo** | t = 60 s (600 pasos), unas 3 veces la vuelta esperada | `truncated`, no cuenta como éxito |

**Estado inicial:** posición (−40, 0) más un desvío lateral U(−0.5, 0.5) m, rumbo −90° ± U(−5°, 5°), v = 0, next_cp = 1 y u_prev = (0, 0). Se usa una semilla fija por episodio de evaluación.

## Metricas e incidente

**Protocolo:** 100 episodios con semillas 0–99, con la política en modo determinista.

| # | Métrica | Definición | Por qué |
|---|---|---|---|
| 1 | **Tasa de vueltas completas** | % de episodios que terminan en éxito | Mide si cumple la misión |
| 2 | **Tiempo de vuelta** | Mediana y p90 del tiempo, en segundos, de los episodios exitosos | Mide la calidad, no solo si termina |
| 3 | **Incidentes por episodio** | Promedio de (salidas de pista + colisiones) por episodio | Mide la seguridad; una vuelta rápida que se sale no sirve |

**Incidente (perturbación): asfalto mojado.** μ baja de 0.9 a **0.5** y no se cambia nada más.

- Se evalúan el modelo base y el candidato con las mismas 100 semillas, en seco (μ = 0.9) y en mojado (μ = 0.5).
- **El candidato se acepta si:**
  - su tasa de vueltas en mojado es mayor que la del modelo base, y
  - en seco su tasa de vueltas no cae más de 5 puntos porcentuales y su tiempo mediano no sube más de 5 %.
- Para que la comparación sea justa, el agente **no observa μ**: tiene que adaptarse a partir de su propio comportamiento (velocidad y giro).

## Cinco transiciones

Parámetros base: w = 8, μ = 0.9, a_max = 4, b_max = 8, k = 0.05, dt = 0.1 y g = 9.81.

Formato de la observación: `[v, ω, sinφ, cosφ, d, eψ, r−90, r−60, r−30, r0, r+30, r+60, r+90]`.

### T1 — Arranque desde la salida
- **Estado:** (x, y) = (−40, 0), ψ = −90°, v = 0, s = 0, next_cp = 1, t = 0, u_prev = (0, 0).
- **Observación:** `[0.00, 0.00, 0.85, 0.53, 0.00, 0.00, 0.20, 0.23, 0.40, 1.00, 0.40, 0.23, 0.20]`. CP1 está a +58° (a la izquierda y adelante).
- **Acción:** u_acel = +1.0, u_dir = 0.0.
- **Física:** a_long = 4 − 0.05·0 = 4 → v' = 0.40 m/s y y' = −0.04.
- **Nuevo estado:** (−40, −0.04), v = 0.40, s = 0.04, d = 0, t = 0.1.
- **Recompensa:** +0.004 (progreso) − 0.05 (tiempo) − 0.05 (Δu_acel = 1) = **−0.096**.
- **Fin:** no.

### T2 — Cruce del CP1 en la recta inferior
- **Estado:** (−1.0, −25.5), ψ = 0°, v = 15, s = 58.85, d = −0.5, next_cp = 1, t = 8.0, u_prev = (0.5, 0).
- **Observación:** `[0.60, 0.00, 0.45, 0.89, −0.13, 0.00, 0.18, 0.20, 0.35, 1.00, 0.45, 0.26, 0.23]`.
- **Acción:** u_acel = +0.3, u_dir = +0.05 (δ = 1.5°).
- **Física:**
  - a_long = 1.2 − 0.75 = 0.45 → v' = 15.05.
  - a_lat = 2.37 m/s², por debajo del límite de 8.83, así que no hay derrape.
  - ψ' = 0.9°.
- **Nuevo estado:** (0.50, −25.48), s = 60.35, d = −0.48. Cruzó CP1 (59.85) en pista → **next_cp = 2**.
- **Recompensa:** +0.150 (1.50 m) + 10 (CP1) − 0.05 − 0.01 (Δdir) − 0.01 (Δacel) = **+10.08**.
- **Fin:** no.

### T3 — Entrada a curva demasiado rápido (subviraje)
- **Estado:** (28, −25), al inicio de la curva inferior derecha, ψ = 0°, v = 18, s = 87.85, d = 0, next_cp = 2, t = 12.0, u_prev = (0.2, 0).
- **Observación:** `[0.72, 0.00, 0.90, 0.43, 0.00, 0.00, 0.20, 0.22, 0.31, 0.53, 0.91, 0.26, 0.20]`.
- **Acción:** u_acel = 0.0, u_dir = +1.0 (todo a la izquierda).
- **Física:**
  - a_long = −0.9.
  - Se piden 74.8 m/s² laterales, pero el máximo es √(8.83² − 0.9²) = 8.78 → δ_ef = 3.9° en vez de 30°. El carro traza un radio de ≈ 37 m, cuando la curva tiene 12 m.
  - v' = 17.91 y ψ' = 2.78°.
- **Nuevo estado:** (29.79, −24.91), s = 89.64, d = −0.05. Sigue en pista, pero se está abriendo.
- **Recompensa:** +0.179 − 0.05 − 0.20 (Δdir = 1) − 0.01 = **−0.081**.
- **Fin:** no. Si no frena en los próximos pasos, se sale de la pista.

### T4 — Décimo paso seguido en el césped (salida de pista)
- **Estado:** (39.53, −24.53), a 16.3 m del centro de la curva → d = −4.3, fuera de pista. ψ = 30°, v = 12, s_best = 96.0, next_cp = 2, t = 14.0, t_fuera = 0.9 s, u_prev = (0.5, 1.0).
- **Observación (rayos aproximados):** `[0.48, 0.13, 0.86, 0.52, −1.08, −0.08, 0.60, 0.60, 0.52, 0.60, 0.07, 0.02, 0.02]`.
- **Acción:** u_acel = +0.5, u_dir = +1.0. El agente intenta volver a la pista acelerando.
- **Física:**
  - En el césped μ_c·g = 3.43, y a_long = 2 − 0.6 = 1.4.
  - La aceleración lateral máxima es √(3.43² − 1.4²) = 3.13 → δ_ef = 3.1°.
  - v' = 12.14 y ψ' = 31.5°.
- **Nuevo estado:** (40.57, −23.90), d = −4.63, sigue fuera. t_fuera = 1.0 s.
- **Recompensa:**
  - El progreso es 0, porque fuera de pista s_best no se actualiza aunque s = 98.1.
  - Total: −0.05 (tiempo) − 1.0 (fuera de pista) − 50 (fin) = **−51.05**.
- **Fin:** **sí, fracaso por salida de pista.**

### T5 — Cierre de vuelta en la meta
- **Estado:** (−40, 1.0), ψ = −90°, v = 16, s = 238.40, d = 0, **next_cp = 4 (meta)**, t = 21.3, u_prev = (0.8, 0).
- **Observación:** `[0.64, 0.00, 0.00, 1.00, 0.00, 0.00, 0.20, 0.23, 0.40, 1.00, 0.40, 0.23, 0.20]`.
- **Acción:** u_acel = +1.0, u_dir = 0.0.
- **Física:** a_long = 4 − 0.8 = 3.2 → v' = 16.32 y y' = −0.63.
- **Nuevo estado:** s = 240.03, mayor que L = 239.40, así que cruza la meta. s_best queda topado en 239.40. t = 21.4 s.
- **Recompensa:** +0.10 (1.0 m hasta el tope) + 50 (vuelta) − 0.05 − 0.01 = **+50.04**.
- **Fin:** **sí, éxito.** Tiempo de vuelta: 21.4 s.

## Posibles trampas y decisiones pendientes

### Reto: ¿puede ganar puntos repitiendo un checkpoint o tomando un atajo?

| Trampa | ¿Funcionaría con un diseño ingenuo? | Cómo la evitamos |
|---|---|---|
| **Ir y volver por un checkpoint** para cobrarlo muchas veces | Sí, si se premia cada vez que se cruza la puerta | Solo cuenta `next_cp`. Al cruzarlo el índice avanza y nunca retrocede, así que cada CP paga una sola vez por vuelta |
| **Oscilar adelante y atrás** para acumular progreso | Sí, si se premia Δs positivo | El progreso se paga sobre `s_best`, que solo aumenta. Retroceder no cuesta puntos, pero volver a avanzar tampoco paga |
| **Arrancar en reversa** y cruzar la meta de inmediato (s salta de 0 a 239) | Sí, si s da la vuelta con módulo | s es acumulado sin módulo, y la meta solo cuenta con next_cp = 4. Además no hay reversa (v ≥ 0) |
| **Atajo por el césped interior** de CP1 a CP3 | Sí, si el progreso se mide solo por proyección | (1) No hay progreso fuera de pista; (2) s_best queda topado en la próxima puerta no cruzada; (3) a 1 s fuera de pista el episodio termina con −50; (4) los bloques del interior se pueden chocar |
| **Zigzag** para alargar el recorrido | No: el progreso se mide sobre la línea central, no por distancia recorrida | Además lo castigan r_suave y r_tiempo |
| **Quedarse quieto** para no arriesgar | Con −0.05 por paso pierde −30 | El detector de estancamiento lo corta a los 10 s |
| **Suicidio rápido** para cortar las penalizaciones de tiempo | Solo si el choque costara menos que seguir | El choque (−50) cuesta más que agotar todo el tiempo (−30) |

**Pruebas a programar después** (una por trampa): un agente con un guion fijo para cada caso. Hay que verificar que su retorno total es menor que el de una vuelta lenta pero legal.

### Decisiones pendientes

1. **"Fuera de pista": ¿centro del carro o carrocería completa?** Hoy se usa el centro (|d| > w/2), lo que permite cortar curvas con dos ruedas en el borde. Hay que decidir si eso es una trazada legal o una trampa.
2. **¿El agente debe ver el tiempo restante?** Sin él, el truncamiento a 60 s no es markoviano. Opciones: agregar t/60 a la observación o tratar el truncamiento sin cortar el bootstrap.
3. **Pesos de r_suave** (0.2 / 0.05): son tentativos. Si el agente se vuelve demasiado tímido, hay que bajarlos.
4. **Ruido en los rayos:** v0.1 no tiene ruido. ¿Lo agregamos como segunda perturbación (σ = 0.2 m)?
5. **Una vuelta o varias:** v0.1 es de una vuelta. Con varias vueltas habría que reiniciar next_cp y sumar el tiempo por vuelta.
6. **Variación de la pista:** ¿trazado fijo o aleatorio en cada episodio para evitar memorización? En v0.1 es fijo.
7. **Calibración:** confirmar con la simulación que la vuelta "experta" dura ~20 s y ajustar el límite de 60 s y el detector de estancamiento.
