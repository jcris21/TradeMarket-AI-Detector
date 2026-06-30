# Guía de Usuario — Tabla de Oportunidades de Señales

> **Para swing traders.** Esta guía explica cada atributo expuesto en el panel *TOP OPORTUNIDADES*, cómo se calcula internamente, qué condiciones lo afectan, y cómo leerlos juntos para tomar una decisión de compra o espera.

---

## Índice

1. [Flujo general de análisis](#1-flujo-general-de-análisis-4-etapas)
2. [Columnas de la tabla](#2-columnas-de-la-tabla)
   - [\# Rank](#-rank)
   - [Ticker](#ticker)
   - [Band (Banda de Score)](#band-banda-de-score)
   - [Score (Puntuación cuantitativa)](#score-puntuación-cuantitativa)
   - [Δ (Delta de Score)](#-delta-de-score)
   - [R/R (Risk/Reward)](#rr-riskreward)
   - [Entry / Target / Stop](#entry--target--stop)
   - [Señal](#señal)
   - [Freshness (Frescura)](#freshness-frescura)
   - [ATR (Viabilidad del stop)](#atr-viabilidad-del-stop)
   - [Bet Size (Tamaño de apuesta)](#bet-size-tamaño-de-apuesta)
3. [Columna adicional: Estatus (tab Archivo)](#3-columna-adicional-estatus-tab-archivo)
4. [Compuestos de puntuación — desglose detallado](#4-compuestos-de-puntuación--desglose-detallado)
5. [Filtros y Gates del sistema](#5-filtros-y-gates-del-sistema)
6. [Enriquecimiento visual (Enrichment)](#6-enriquecimiento-visual-enrichment)
7. [Calibración y backtesting — cómo retroalimenta el sistema](#7-calibración-y-backtesting--cómo-retroalimenta-el-sistema)
8. [Ejemplo completo: ¿Compro NVDA o espero?](#8-ejemplo-completo-compro-nvda-o-espero)
9. [Checklist rápido de decisión](#9-checklist-rápido-de-decisión)

---

## 1. Flujo general de análisis (4 etapas)

Cuando presionas **"Analizar"**, el sistema ejecuta este pipeline automáticamente:

```
Etapa 1 — DATA
  yfinance descarga indicadores técnicos de cada ticker:
  MACD, RSI, volumen, pivotes (S1/S2/R1/R2), SMA-50, SMA-200, ATR-14, Bandas de Bollinger.
  Simultáneamente se consulta el VIX.

  → Gate SMA-200: si precio ≤ SMA-200 → señal AVOID (suprimida, no sigue al scoring).

Etapa 2 — SCREENSHOT (solo bajo demanda / enriquecimiento)
  El trader sube un gráfico manualmente o el sistema toma auto-screenshot.
  GPT-4o (LLM con visión) extrae niveles S/R visuales del gráfico.
  ⚠ Esta etapa NO ocurre en el análisis automático de batch. No hay LLM aquí.
  Solo se activa cuando el trader sube un chart en el panel de detalle (TraderChartUpload).

Etapa 3 — ANÁLISIS CUANTITATIVO (QuantAgent)  ← CERO LLM
  Código Python 100% determinista. Para cada ticker que pasó el gate SMA-200:
  - Señal (BUY/WAIT/AVOID) por reglas de indicadores (4 condiciones booleanas).
  - Entry = precio actual; Stop = S1 pivot; Target = R2 pivot.
  - R/R ratio calculado aritméticamente.
  Ventaja: reproducible, instantáneo, sin costo de tokens.

Etapa 4 — SCORING Y RANKING (ScoringAgent)  ← CERO LLM
  Código Python 100% determinista. Para cada ticker del paso 3:
  - Calcula score_quant (0–100) sumando 8 componentes numéricos.
  - Calcula bet size (EV por $100 arriesgados).
  - Compara con scores del run anterior → delta.
  - Aplica gate VIX (si VIX > 25, todos los BUY → AVOID).
  - Aplica cap de sector (máx 2 por sector).
  - Solo activos con R/R ≥ 3.0 y señal BUY/WAIT reciben un rank visible.
```

### ¿Por qué las etapas 3 y 4 NO usan LLM?

Esta es una decisión de diseño deliberada con tres razones:

**1. Determinismo y reproducibilidad**
Los indicadores técnicos (RSI, MACD, pivotes, ATR) tienen definiciones matemáticas precisas. Un LLM introduce varianza estocástica en cada llamada — el mismo gráfico puede producir "BUY" o "WAIT" dependiendo del sampling. Para un sistema de ranking que el trader compara entre runs, la consistencia importa más que la "inteligencia".

**2. Latencia y costo**
El batch típico analiza 20–50 tickers simultáneamente. Con LLM por ticker, 50 llamadas × ~1.5s = 75s de pipeline. Con código determinista, el Stage 3+4 completo tarda < 1s para todos los tickers juntos.

**3. El LLM tiene rol donde agrega valor real**
El LLM (GPT-4o con visión) aparece exclusivamente en la Etapa 2: leer un gráfico visual e identificar niveles S/R que el código no puede derivar de OHLCV. Eso sí es un problema que requiere razonamiento visual. Calcular RSI < 30 no lo requiere.

**Resumen arquitectónico:**

| Etapa | Motor | ¿Usa LLM? | Cuándo se ejecuta |
|-------|-------|-----------|-------------------|
| 1 — Data | yfinance + numpy | No | Cada run automático |
| 2 — Screenshot | GPT-4o (visión) | **Sí** | Solo bajo demanda del trader |
| 3 — QuantAgent | Python puro | No | Cada run automático |
| 4 — ScoringAgent | Python puro | No | Cada run automático |

---

## 2. Columnas de la tabla

### `#` Rank

**Qué es:** Posición ordinal en el ranking de oportunidades del run actual (1 = mejor).

**Cómo se calcula:** Los activos calificados (R/R ≥ 3.0, señal BUY o WAIT, `score_quant` disponible) se ordenan por `score_quant` de mayor a menor. El rank se asigna tras aplicar el cap de sector (máx 2 activos por sector).

**Condiciones que afectan el rank:**
- Un activo puede tener score alto pero `rank = null` si fue excluido por el cap sectorial.
- Si el VIX gate está activo, todos los BUY se convierten en AVOID y no reciben rank.

---

### Ticker

**Qué es:** Símbolo del activo analizado (ej: AAPL, NVDA, JPM).

**Indicadores visuales asociados:**
- Tachado (`~~AAPL~~`) si el activo tiene `freshness_status = "expired"` en el tab Archivo.
- Badge `⚠ Orphaned` si han pasado más de 35 días de mercado sin que se detecte un resultado (ni TARGET_HIT ni STOP_HIT).
- Badge `Stale data` si yfinance no estaba disponible en el run y se usaron datos cacheados del run anterior (< 24 h).

---

### Band (Banda de Score)

**Qué es:** Categoría de calidad asignada según el `score_quant` del activo.

| Badge | Umbral | Color |
|-------|--------|-------|
| `ELITE` | score ≥ 75 | Amarillo `#ECAD0A` |
| `STRONG` | score ≥ 60 | Azul `#209DD7` |
| `QUALIFYING` | score ≥ 50 | Gris `#888888` |
| _(sin badge)_ | score < 50 | No aparece en oportunidades activas |

**Por qué importa para el swing trader:** Un activo ELITE con score 75+ tiene múltiples componentes cuantitativos alineados (buen R/R, tendencia, confluencia). QUALIFYING puede ser ruido o una señal marginal; requiere mayor escrutinio manual.

---

### Score (Puntuación cuantitativa)

**Qué es:** Número entre 0 y 100 que mide la calidad cuantitativa del setup técnico. Es el eje central de ranking.

**Tipos de score que puede mostrar:**

| Etiqueta | Campo | Descripción |
|----------|-------|-------------|
| `Q` (quant) | `score_quant` | Score calculado 100% con indicadores numéricos. El caso base. |
| `E` (enriched) | `score_enriched` | `score_quant` + delta por enriquecimiento visual de niveles S/R confirmados por el trader. |

Cuando hay enriquecimiento activo, el número se muestra en **ámbar** con efecto glow. La barra mini debajo del score muestra la proporción de cada componente (ver sección 4).

**Cómo se calcula:** Ver [sección 4](#4-compuestos-de-puntuación--desglose-detallado) para el desglose completo.

---

### Δ (Delta de Score)

**Qué es:** Variación del `score_quant` con respecto al run anterior para ese mismo ticker.

| Símbolo | Condición | Interpretación |
|---------|-----------|----------------|
| `▲ +N` (verde) | delta > +3 pts | El setup mejoró desde el último análisis |
| `▼ -N` (rojo) | delta < -3 pts | El setup se deterioró |
| `=` (gris) | \|delta\| ≤ 3 pts | Sin cambio significativo |
| _(vacío)_ | No hay run anterior | Primera vez que se analiza este ticker |

**Uso práctico:** Un activo que aparecía en STRONG y ahora muestra `▲ +8` está ganando momentum técnico. Un ELITE con `▼ -12` puede estar cerca de salir del ranking o de tocar el stop.

---

### R/R (Risk/Reward)

**Qué es:** Relación riesgo/recompensa del trade planteado.

**Fórmula:**
```
R/R = (target_price − entry_price) / (entry_price − stop_loss)
```

**Condiciones de filtrado:** Solo activos con R/R ≥ 3.0 aparecen rankeados. Este threshold es configurable (`ANALYSIS_MIN_RR_RATIO`).

**Tabla de scoring:**

| R/R | Puntos asignados (componente RR del score) |
|-----|--------------------------------------------|
| ≥ 4.0 | 30 pts |
| ≥ 3.0 | 22 pts |
| ≥ 2.0 | 14 pts |
| < 2.0 | 0 pts |

**Ejemplo:** R/R = 4.2x significa que por cada $1 que se arriesga, el sistema estima que hay $4.20 de ganancia potencial al target.

---

### Entry / Target / Stop

**Qué son:** Los tres precios del trade planteado.

| Campo | Origen |
|-------|--------|
| `entry_price` | Precio actual del activo al momento del análisis (Stage 1) |
| `stop_loss` | Nivel de soporte S1 del pivot diario; si S1 ≥ entry, se usa `entry × 0.97` |
| `target_price` | Nivel de resistencia R2 del pivot diario (más alejado → mayor R/R); si R2 ≤ entry, se usa R1 o `entry × 1.09` |

**Validaciones estructurales** (filtros de guardia):
- Si `stop_loss ≥ entry_price` → activo descartado estructuralmente (no aparece rankeado).
- Si `target_price ≤ entry_price` → idem.
- Si `entry_price ≤ 0` → idem.

> **Nota para el trader:** Estos precios son de referencia. Siempre contrastar con el chart real antes de ejecutar. El sistema usa pivotes del período diario; si el activo cotiza intradía muy alejado de esos niveles, los precios pueden estar desactualizados hasta el próximo análisis.

---

### Señal

**Qué es:** Veredicto de la lógica cuantitativa sobre el activo.

| Badge | Condición | Acción sugerida |
|-------|-----------|-----------------|
| `BUY` (verde) | ≥ 3 factores bullish y bullish > bearish | Candidato activo; revisar ATR y Bet Size |
| `WAIT` (amarillo) | Señales mixtas (entre 1–2 factores de cada lado) | No actuar aún; monitorear |
| `AVOID` (rojo) | ≥ 3 factores bearish, o gate SMA-200, o gate VIX | No operar en largo |

**Factores evaluados para derivar la señal:**

| Indicador | Bullish (+1) | Bearish (+1) |
|-----------|-------------|-------------|
| MACD | Crossover alcista | Crossover bajista |
| RSI | < 30 (oversold) ó 40–60 (momentum) | > 70 (overbought) |
| Volumen | ratio > 1.2× media | ratio < 0.8× media |
| SMA-50 | precio > SMA-50 | precio ≤ SMA-50 |

---

### Freshness (Frescura)

**Qué es:** Indicador de cuánto tiempo hace que se generó el análisis de ese activo.

| Dot color | Estado | Significado |
|-----------|--------|-------------|
| 🟢 Verde | `fresh` | Análisis reciente, datos confiables |
| 🟡 Ámbar | `active` | Algunas horas de antigüedad, vigente |
| 🔴 Rojo | `aged` | Análisis viejo; los precios pueden haber cambiado significativamente |
| 🔴 Rojo | `stale` | Datos del run anterior recuperados (yfinance no disponible) |
| ⚫ Gris | `expired` | Señal expirada (aparece tachada en tab Archivo) |

La edad exacta se muestra junto al dot: `"2h 15m ago"`, `"43m ago"`, etc. Se actualiza cada minuto en pantalla sin recargar.

**Impacto en el score:** Un activo `aged` o `stale` aparece con el score levemente atenuado (opacity 40%) como advertencia visual. Los precios de entry/target/stop pueden no reflejar el mercado actual.

---

### ATR (Viabilidad del stop)

**Qué es:** Indica si el stop loss planteado tiene distancia suficiente respecto al ruido normal del activo (medido por el ATR de 14 periodos).

| Símbolo | Estado | Condición |
|---------|--------|-----------|
| `✔ ATR` (verde) | `stop_viable = true` | La distancia al stop es adecuada |
| `❌ ATR` (rojo) | `stop_viable = false` | Stop demasiado ajustado (penalización en score) |
| `—` | ATR no disponible | No se pudo calcular; no penaliza |

**Lógica de cálculo:**

```
stop_distance_pct = (entry_price - stop_loss) / entry_price
atr = atr_14_pct  (ATR de 14 días como % del precio)

Si stop_distance_pct < 0.5 × atr  →  Hard disqualify (activo excluido del ranking)
Si stop_distance_pct < 0.8 × atr  →  Soft penalty: −15 pts al score
Si stop_distance_pct > 1.5 × atr  →  Boost: +8 pts al score (stop bien colocado)
Zona neutral (0.8–1.5×)            →  0 pts
```

**Ejemplo:** Si AAPL tiene ATR-14 del 1.5% diario y el stop está solo al 0.6% bajo el entry → el stop está dentro del ruido → sistema lo penaliza con ❌ ATR y −15 pts. Si el stop está al 2.5% (> 1.5 × 1.5% = 2.25%) → ✔ ATR +8 pts.

---

### Bet Size (Tamaño de apuesta)

**Qué es:** Estimación del valor esperado del trade **por cada $100 de capital arriesgado**. Aparece solo en señales BUY.

> Los campos internos del sistema se llaman `expected_*_per10` por razones históricas, pero los valores ahora representan resultados sobre $100 de capital en riesgo.

**Campos calculados:**

```
gain_per100 = 100 × (target - entry) / entry   → ganancia si el trade gana
loss_per100 = 100 × (entry - stop)   / entry   → pérdida si el trade pierde
EV_per100   = hit_rate × gain_per100 − (1 − hit_rate) × loss_per100
```

**Ejemplo con NVDA (entry=$890, target=$980, stop=$855):**
```
gain_per100 = 100 × (980 - 890) / 890 = $10.11
loss_per100 = 100 × (890 - 855) / 890 =  $3.93
EV (35%)    = 0.35 × 10.11 − 0.65 × 3.93 = 3.54 − 2.55 = +$0.99
EV (55%)    = 0.55 × 10.11 − 0.45 × 3.93 = 5.56 − 1.77 = +$3.79
```

**Hit rate (tasa de éxito):**

| Fuente | Condición | Valor |
|--------|-----------|-------|
| `observed` | ≥ 30 trades resueltos en el Archivo | Calculado de trades reales propios |
| `assumed` | < 30 trades resueltos | **35%** (valor conservador por defecto) |

**¿Por qué 35% por defecto y no 50%?**

El 35% no es arbitrario — es una estimación conservadora basada en la literatura de trading sistemático:

- En sistemas trend-following con R/R ≥ 3:1, las tasas de éxito reales suelen estar entre **30% y 45%**. Un sistema con R/R 3:1 es matemáticamente rentable incluso ganando solo 1 de cada 3 trades (33.3%).
- Usar 50% sobreestimaría el EV en la fase de bootstrap y podría llevar al trader a sobredimensionar posiciones antes de tener evidencia real.
- El 35% produce EV positivo para cualquier trade con R/R ≥ 3:1 (`0.35 × 3 − 0.65 × 1 = 1.05 − 0.65 = +0.40`), dando señal verde solo a los setups que lo merecen.
- Una vez que el sistema acumula ≥ 30 trades resueltos, reemplaza el 35% con tu tasa observada real — el valor asumido es temporal.

**¿En qué medida N trades Winner incrementan el hit_rate?**

La fórmula es simple:

```
hit_rate = TARGET_HIT_count / (TARGET_HIT_count + STOP_HIT_count)
```

Solo entran trades con resultado conclusivo (TARGET_HIT o STOP_HIT). Los EXPIRED y Orphaned no cuentan.

| Trades resueltos | Winners | Hit rate observado |
|-----------------|---------|-------------------|
| 30 (mínimo) | 12 | 40.0% |
| 30 | 15 | 50.0% |
| 50 | 20 | 40.0% |
| 50 | 28 | 56.0% |
| 100 | 38 | 38.0% |
| 100 | 50 | 50.0% |

Cada nuevo trade resuelto mueve el hit_rate 1/N en la dirección del resultado:

```
Tienes 30 trades, 12 winners → hit_rate = 12/30 = 40%
Agregas 1 winner más        → 13/31 = 41.9%  (+1.9pp)
Agregas 1 loser más         → 12/31 = 38.7%  (−1.3pp)

Tienes 100 trades, 40 winners → hit_rate = 40%
Agregas 1 winner más          → 41/101 = 40.6% (+0.6pp)  ← converge lentamente
```

La sensibilidad de cada trade adicional decrece con N. Con 30 trades, un winner cambia el hit_rate ~1.5pp; con 100 trades, solo ~0.5pp. Esto es estadísticamente sano — el sistema se vuelve más estable a medida que acumulas historia.

**Interpretación del EV:**
- EV > 0 → trade con expectativa positiva a esa tasa de éxito
- EV ≈ 0 → punto de equilibrio
- EV < 0 → trade con expectativa negativa (evitar aunque el R/R luzca atractivo)

---

## 3. Columna adicional: Estatus (tab Archivo)

Cuando una señal se resuelve (el precio toca el target o el stop), el sistema la mueve al tab **Archivo** con un Estatus:

| Badge | Código interno | Significado |
|-------|---------------|-------------|
| `Winner` (verde) | `TARGET_HIT` | El precio alcanzó el target antes del stop |
| `Lost` (rojo) | `STOP_HIT` | El precio tocó el stop loss |
| `Desestimado` (gris) | `EXPIRED` | La señal expiró sin alcanzar ni target ni stop |
| `⚠ Orphaned` (ámbar) | — | Pasaron 35 días de trading sin detección de resultado; revisar manualmente |

El tab Archivo es la base de datos desde la cual se calcula el `hit_rate observed` para el Bet Size.

---

## 4. Compuestos de puntuación — desglose detallado

El `score_quant` se calcula como la suma de estos componentes (máximo teórico: 100 pts):

```
score_quant = RR_pts + Confluencia_pts + Tendencia_pts + ATR_pts
            + BB_squeeze_pts + Soporte_pts + Resistencia_pts + Régimen_pts
```

### Componente R/R (0–30 pts)
El componente más pesado del score.

| R/R del trade | Puntos |
|---------------|--------|
| ≥ 4.0 | **30 pts** |
| ≥ 3.0 | 22 pts |
| ≥ 2.0 | 14 pts |
| < 2.0 | 0 pts |

---

### Componente Confluencia (0–20 pts)
Cuenta cuántos de los 3 indicadores clave están alineados en modo bullish:

| Indicador | Condición bullish |
|-----------|-----------------|
| MACD | `bullish_crossover` |
| RSI | entre 40 y 65 |
| Volumen | ratio > 1.2× media OR texto "above" |

- 3/3 bullish → 20 pts
- 2/3 → ~13 pts
- 1/3 → ~7 pts
- 0/3 → 0 pts

---

### Componente Tendencia (0/3/6/10 pts)

| Condición | Puntos |
|-----------|--------|
| Precio > SMA-50 **y** MACD bullish crossover | **10 pts** |
| Solo precio > SMA-50 ó solo MACD bullish | 6 pts |
| Sin bearish activo (MACD neutro) | 3 pts |
| MACD bearish crossover | 0 pts |

---

### Componente ATR (−15 / 0 / +8 pts)
Ver la columna ATR en sección 2.

---

### Componente BB Squeeze (0 / +8 pts)

| Condición | Puntos |
|-----------|--------|
| Bollinger Band Bandwidth (BBB) < 10 | **+8 pts** |
| BBB ≥ 10 o no disponible | 0 pts |

Una Bandwidth baja indica que el precio está comprimido y puede producir un breakout explosivo.

---

### Componente Soporte (0 / 5 / 10 pts)

| Condición | Puntos |
|-----------|--------|
| Soporte validado Y precio dentro del 3% del S1 | **10 pts** |
| Soporte validado Y precio más lejos | 5 pts |
| Soporte no validado | 0 pts |

El soporte se valida cuando el trader sube un gráfico con niveles marcados (enriquecimiento visual).

---

### Componente Resistencia (−5 / 0 / +8 pts)

| Condición | Puntos |
|-----------|--------|
| R1 está a más del 5% sobre el precio actual | **+8 pts** (espacio de recorrido) |
| R1 entre 1% y 5% | 0 pts |
| R1 a menos del 1% (resistencia encima) | −5 pts |

---

### Componente Régimen RSI (−10 / −5 / 0 / +5 pts)

| RSI | Puntos | Interpretación |
|-----|--------|----------------|
| > 70 | **−10 pts** | Sobrecomprado; riesgo de reversión |
| > 60 | −5 pts | Zona caliente; cautela |
| 30–50 | **+5 pts** | Zona de momentum sin sobrecompra |
| Resto | 0 pts | Neutral |

---

### Resumen visual del score

```
Score = 30 (R/R) + 20 (Confluencia) + 10 (Tendencia) + 8 (ATR) + 8 (BB) + 10 (Soporte) + 8 (Resistencia) + 5 (RSI) = 99 pts (máximo realista)
```

La barra de colores en el detalle expandido de cada fila muestra:
- 🔵 Azul → componente R/R
- 🟡 Amarillo → Confluencia
- 🟣 Morado → Tendencia + BB + Soporte
- ⬜ Gris → Ajustes (ATR, Resistencia, Régimen)
- 🟠 Ámbar → Enriquecimiento visual (si aplica)

---

## 5. Filtros y Gates del sistema

Antes de que un activo llegue al ranking visible, debe pasar por múltiples filtros en serie:

### Gate 1 — SMA-200 (Filtro de régimen estructural)
```
Si precio_actual ≤ SMA-200 → señal = AVOID
                              rank = null
                              argumento: "Suppressed by SMA-200 regime gate"
```
Un activo por debajo de su media de 200 días está en tendencia bajista estructural. No se analiza más; ningún score se calcula.

### Gate 2 — VIX (Filtro de volatilidad de mercado)
```
Si VIX > 25.0 (configurable) → todos los BUY del run → AVOID
                                rank = null
                                argumento: "regime_vix"
```
Cuando el miedo del mercado es alto, el sistema suprime todas las señales de compra. El banner amarillo `⚠ Regime gate active — VIX X.X supera el umbral` aparece visible en el panel.

### Gate 3 — Integridad estructural
```
Si stop_loss ≥ entry_price     → descartado ("inverted stop")
Si target_price ≤ entry_price  → descartado ("inverted target")
Si entry_price ≤ 0             → descartado
```

### Gate 4 — ATR noise floor (Hard disqualify)
```
Si stop_distance_pct < 0.5 × ATR_14_pct → descartado ("atr_disqualify")
```

### Gate 5 — R/R mínimo
```
Si R/R < 3.0 (por defecto) → activo calculado pero rank = null
```

### Gate 6 — Cap de sector
```
Máximo 2 activos del mismo sector en el ranking visible (configurable ANALYSIS_SECTOR_CAP).
El que quede excluido recibe rank_exclusion_reason = "sector_cap:<sector>".
```

---

## 6. Enriquecimiento visual (Enrichment)

El sistema base calcula el score con indicadores numéricos. El enriquecimiento añade información cualitativa del gráfico real.

### Cómo se activa
El trader expande la fila del ticker y sube un screenshot del gráfico desde su plataforma (o el sistema toma un auto-screenshot). El LLM de visión (GPT-4o) extrae los niveles S/R visibles.

### Reglas de puntuación del enriquecimiento

```
Por cada soporte confirmado dentro de 1 ATR del precio de entry:  +4 pts
Por cada resistencia confirmada dentro del 2% del target_price:    +3 pts
Máximo evaluado: 2 niveles
Máximo delta: 15 pts (configurable ENRICHMENT_MAX_DELTA)
```

### Resultado visual
- El score muestra `Quant X → Enriched Y` con el delta en ámbar.
- La columna Score muestra el badge `E` en lugar de `Q`.
- La barra mini añade un segmento ámbar.

### Auto-screenshot enrichment
Cuando el sistema no ha recibido un chart manual pero detecta que el análisis está en estado `pending_enrichment`, puede intentar capturar automáticamente el gráfico desde investing.com. El badge `+N visual, auto screenshot` aparece en la columna cuando esto ocurre.

---

## 7. Calibración y backtesting — cómo retroalimenta el sistema

El sistema no es estático. Aprende de sus propios resultados históricos a través del tab **Archivo**.

### Ciclo de aprendizaje

```
Run de análisis → Señales activas en tabla → (días después) →
precio toca target o stop → se registra TARGET_HIT / STOP_HIT en DB →
_get_hit_rate() recalcula hit_rate → Bet Size del próximo run usa tasa observada
```

### Fases de calibración

| Fase | Criterio | Estado del Bet Size |
|------|----------|---------------------|
| **Bootstrap** | < 30 trades resueltos en Archivo | hit_rate = 35% (`assumed`) — conservador por defecto |
| **Calibrado** | ≥ 30 trades resueltos | hit_rate = % real de Winners en tu historial (`observed`) |

> La fuente del hit rate se indica en el tooltip del Bet Size: `hr: 35% (assumed)` vs `hr: 42% (observed)`.

### Señales Orphaned y su efecto

Si una señal lleva más de 35 días sin resolver (sin TARGET_HIT ni STOP_HIT), aparece `⚠ Orphaned`. Estas señales NO entran en el cálculo del hit_rate para no contaminar las estadísticas con casos ambiguos. Deben revisarse manualmente y cerrarse en el Archivo.

### Score Delta como herramienta de backtesting

La columna `Δ` permite detectar degradación sistemática:
- Si un activo muestra `▼ -8` o más en múltiples runs consecutivos, el setup se está deteriorando.
- Activos que entraron como ELITE y ahora muestran delta negativo pueden estar cerca de caer a STRONG o salir del ranking.

### Impacto de la tasa de éxito en la decisión de bet size

```
Escenario: NVDA, entry $890, target $980, stop $855
  gain_per100 = 100 × (980 - 890) / 890 = $10.11 por cada $100 arriesgados
  loss_per100 = 100 × (890 - 855) / 890 = $3.93 por cada $100 arriesgados

  Con hit_rate = 35% (assumed):
    EV = 0.35 × 10.11 − 0.65 × 3.93 = 3.54 − 2.55 = +$0.99 ← EV positivo

  Con hit_rate = 55% (calibrado después de 50 trades):
    EV = 0.55 × 10.11 − 0.45 × 3.93 = 5.56 − 1.77 = +$3.79 ← EV 3.8× más atractivo
```

El backtesting propio mejora directamente la calidad del Bet Size con el tiempo.

---

## 8. Ejemplo completo: ¿Compro NVDA o espero?

> Este es un escenario ficticio para ilustrar cómo leer la tabla juntos.

### Lo que muestra la tabla para NVDA

| Campo | Valor | Lectura |
|-------|-------|---------|
| **#** | 2 | Segundo mejor setup del run actual |
| **Ticker** | NVDA | NVIDIA Corporation |
| **Band** | `ELITE` | Score ≥ 75 — setup técnico sólido |
| **Score** | 78.5 (Q) | Score cuantitativo, sin enriquecimiento visual |
| **Δ** | ▲ +6 | El setup mejoró 6 pts respecto al run anterior |
| **R/R** | 4.1x | Por cada $1 de riesgo → $4.10 de ganancia potencial |
| **Entry** | $890.20 | Precio actual al momento del análisis |
| **Target** | $980.50 | Resistencia R2 del pivote diario |
| **Stop** | $854.10 | Soporte S1 del pivote diario |
| **Señal** | `BUY` | ≥ 3 factores bullish |
| **Freshness** | 🟢 `fresh` · 18m ago | Análisis reciente — datos confiables |
| **ATR** | ✔ ATR | Stop bien colocado (> 1.5× ATR) |
| **Bet Size** | +$10.11 / −$3.93 · EV +$0.99 | Por cada $100 arriesgados (hit_rate 35% assumed) |

### Desglose del score 78.5

```
R/R 4.1x         → 30 pts  (máximo del componente)
Confluencia 2/3  → 13 pts  (MACD bullish + Volumen alto; RSI = 52 dentro de rango)
Tendencia        → 10 pts  (precio > SMA-50 Y MACD bullish crossover)
ATR              → +8 pts  (stop > 1.5× ATR → boost)
BB Bandwidth     → 0 pts   (BBB = 14, no hay squeeze activo)
Soporte          → 0 pts   (soporte no validado; no se subió chart)
Resistencia      → +8 pts  (R1 está al 6% sobre precio → espacio libre)
Régimen RSI=52   → +5 pts  (RSI en zona 30–50 → momentum sano)
                  ─────────
Total            → ~74 pts (ajuste de redondeo → 78.5 final)
```

### Gates verificados

- [x] SMA-200: precio $890 > SMA-200 $820 → pasa
- [x] VIX: VIX = 18.3 < 25.0 → gate inactivo
- [x] Estructura: stop < entry < target → válido
- [x] ATR hard floor: stop al 4.1% vs ATR 2.7% → 4.1% > 0.5×2.7%=1.35% → pasa
- [x] R/R ≥ 3.0: 4.1x → pasa
- [x] Sector cap: solo 1 activo de Technology en el rank actual → pasa

### ¿Compro?

**Señales para proceder:**
- Score ELITE (78.5), delta positivo (+6), mejorando.
- R/R 4.1x — excelente; la pérdida máxima es pequeña frente al objetivo.
- ✔ ATR: el stop está fuera del ruido diario.
- Freshness fresh: precios confiables.
- EV positivo (+$0.99 por $100 arriesgados) incluso con hit_rate conservador.
- VIX gate inactivo.

**Puntos a considerar antes de ejecutar:**
- Soporte sin validar (0 pts en ese componente) — subir el gráfico podría añadir hasta +7 pts si los S/R visuales confirman el setup.
- Hit rate todavía en `assumed` (35%) — si tu historial real es mayor, el EV real es más alto.
- Verificar en tu plataforma que el precio no se ha movido significativamente desde hace 18 minutos.

**Conclusión del ejemplo:** Setup sólido, ejecutar con size moderado (Kelly conservador). Si se sube el chart y se confirman niveles S/R, el score podría subir a ~85 y reafirmar la posición.

---

### ¿Cuándo NO comprar (mismo activo)?

Imagina el mismo NVDA pero con estos valores alternativos:

| Campo | Valor alternativo | Razón para no comprar |
|-------|------------------|-----------------------|
| **Band** | `QUALIFYING` (score 52) | Setup débil; muchos componentes negativos |
| **Δ** | ▼ −11 | Deterioro rápido desde el run anterior |
| **R/R** | 2.1x | Bajo el mínimo de calidad del sistema (se muestra pero sin rank) |
| **Señal** | `WAIT` | Señales mixtas — no hay consenso técnico |
| **Freshness** | 🔴 `aged` · 6h ago | Precios pueden estar caducos |
| **ATR** | ❌ ATR | Stop demasiado ajustado — dentro del ruido diario |
| **EV** | −$0.14 | Expectativa negativa incluso con R/R 2:1 |
| **Gate VIX** | ⚠ Regime gate active | VIX = 28 → señal BUY suprimida a AVOID |

→ **No operar.** El sistema ya degradó la señal; combinar con delta negativo y ATR inviable es señal de que el trade tiene poca probabilidad de funcionar según los criterios calibrados.

---

## 9. Checklist rápido de decisión

Usa este checklist antes de actuar sobre cualquier señal:

```
□ 1. Band es ELITE o STRONG (score ≥ 60)?
□ 2. R/R ≥ 3.0 (columna R/R)?
□ 3. Señal = BUY (no WAIT ni AVOID)?
□ 4. ✔ ATR (stop fuera del ruido diario)?
□ 5. Delta Δ neutro o positivo (no deteriorándose)?
□ 6. Freshness = fresh o active (no aged)?
□ 7. VIX gate inactivo (no hay banner amarillo)?
□ 8. EV del Bet Size > 0?
□ 9. Verificar en plataforma que los precios aún corresponden?

Si 8/9 o 9/9 → Setup de alta calidad.
Si 6–7/9   → Setup marginal; considera esperar enriquecimiento visual.
Si < 6/9   → No actuar.
```

> **Regla de oro:** El sistema filtra la lista antes de mostrarte resultados, pero **no reemplaza el juicio del trader**. Úsalo como primer filtro sistemático, luego aplica tu análisis contextual (noticias, catalizadores, estructura del sector).

---

*Guía generada para FinAlly v1 — actualizar si cambian los thresholds de scoring o las reglas de gate en `scoring_agent.py`.*
