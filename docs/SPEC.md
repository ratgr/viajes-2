# SPEC — viajes-2: la herramienta (YAML → itinerario + mapa + PWA + edición en línea)

Este documento especifica LA HERRAMIENTA: el formato de datos, el build, las
dos páginas generadas, la PWA y la edición en línea. Con solo este documento
otra implementación debe poder recrear la infraestructura completa y obtener
un sistema equivalente. **Nada de lo que sigue es específico de un viaje**:
las reglas de contenido de cada viaje (anclas, horarios límite, cadencias)
viven junto a sus datos, p.ej. `src/2026-Japon/REGLAS.md`. Donde aparezca
"Japón" es solo un ejemplo. La contraparte de verificación manual es
[QA.md](QA.md); los umbrales ajustables están en la tabla de tornillos (§13).

---

## 1. Estructura del repo y pipeline

```
src/<viaje>/           viaje.yaml (LA fuente) · plantilla.html · plantilla-mapa.html
                       config.yaml · REGLAS.md (reglas del viaje, no del tool)
                       static/  (páginas/fotos propias del viaje: van tal cual al release)
build/                 pipeline (Python 3, dependencia única: PyYAML)
build/assets/          css/js compartidos + vendor/ (Leaflet local, sin CDN)
pages/<viaje>/         release generado, autocontenido (NO vive en git: lo publica la Action)
scratch/               herramientas fuera del pipeline (migraciones, OSM, POIs)
docs/                  SPEC.md · QA.md
.github/workflows/build.yml
```

Scripts y contratos de invocación:

| script | hace | salida |
|---|---|---|
| `build/build_itinerario.py [viaje]` | render + verify | `pages/<viaje>/itinerario.html` |
| `build/build_mapa.py [viaje]` | render + GEO + verify + PWA | `pages/<viaje>/mapa.html`, `sw.js` |
| `build/verify_roundtrip.py <viaje> [página]` | HTML → YAML normalizado → diff | exit 0/1 |
| `build/dev_server.py [puerto] [--share]` | server local de edición (opcional) | — |
| `build-japan.sh` / `.bat` | conveniencia: los dos builds del viaje ejemplo | — |

Resolución del viaje (`common.resolve_trip`): `argv[1]` si existe como
directorio en `src/`; sin argumento, el ÚNICO directorio de `src/`; ambigüedad
o nombre desconocido → abort con la lista de viajes. `trip_paths` devuelve
`(src_dir, pages_dir, config)`; `config.yaml` es un mapeo opcional — hoy solo
`photo_base` (prefijo de las imágenes relativas de los modales; `""` = van
relativas al release).

Módulos del build y su papel:

- **`common.py`** — raíz del repo, `parse_pts` (parser de coordenadas, ver §2.1),
  estilo de casa para escribir YAML (`allow_unicode`, `sort_keys=False`,
  `width=100000`).
- **`contract.py`** — el VOCABULARIO compartido renderer ↔ verificador. Cada
  literal que ambos lados deben acordar vive aquí una sola vez:
  `MODAL_PREFIX = "m-"` · `SKIP_DUR = (None, 0, "0")` (duraciones que cuentan
  como ausencia) · `SEP = " - "` (separador de campos de fila) ·
  `ANCHOR_LABEL = "Ancla: "` · `TIME_TO_DASH = "–"` · `norm_flex` (normaliza
  el spec flex quitando espacios y paréntesis) · `clean_title` (defensa: quita
  `*` de títulos) · `modal_key` (`'#m-xxx' → 'xxx'`).
- **`render.py`** — YAML → fragmentos HTML (días, filas, options, modales) +
  ensamblado sobre plantilla con tokens + horarios derivados + diagnósticos.
  Compartido por ambas páginas: el markup de los días es EL MISMO.
- **`build_mapa.py`** — agrega el payload GEO (§6), las anclas precalculadas y
  los spans de edición, y genera `sw.js` (§8).
- **`verify_roundtrip.py`** — invierte el render y compara (§4).
- **`dev_server.py`** — edición por spans + API local (§10).

---

## 2. Modelo de datos: `src/<viaje>/viaje.yaml`

Un solo YAML es la fuente canónica. Claves de nivel raíz: `title` (string,
informativo), `places` (mapeo), `transits` (mapeo), `lines` (mapeo), `days`
(lista). Las claves de entidad (`places`/`transits`/`lines`) son slugs
`[a-z0-9][a-z0-9-]*` y son el vocabulario de referencia de todo el sistema
(pasos, links `@[…](clave)`, GEO, hash `#m-clave`).

### 2.1 Coordenadas

Formato universal: string `'lat,lon lat,lon …'` — pares decimales separados
por coma, puntos separados por espacio (ej. `'34.6872,135.5258'`). El parser
(`common.parse_pts`) devuelve lista de tuplas float o `None` si CUALQUIER
token está malformado; el dato roto NO mata el build: se reporta como
diagnóstico (§5.4) y esa geometría se omite. Un punto = string con un solo
par. Distancias internas: aproximación equirectangular
(`dy = Δlat·111000`, `dx = Δlon·111000·cos(lat)`).

### 2.2 `places` (lugares)

| campo | tipo | opcional | uso |
|---|---|---|---|
| `name` | string | no | nombre visible (título del modal, refs derivadas) |
| `gps` | coord (1 punto) | sí (`''` = sin geometría) | marcador en el mapa |
| `maps` | URL | sí | botón «Abrir en Maps ↗» del modal |
| `description` | string md | sí | párrafo principal del modal |
| `info` | string md | sí | párrafo secundario (`.modal-note`) |
| `hours` | string | sí | renglón «🕒 Horario:» |
| `hours_source` | URL o literal `maps` | sí | `maps` añade la etiqueta «· Google Maps»; una URL solo documenta la fuente |
| `image` | ruta relativa o URL http | sí | imagen del modal; si no empieza con `http` se antepone `photo_base` |
| `poi` | string (nombre de cluster) | sí | mete el lugar a la capa 📍 agrupado por ese cluster |
| `zone` | coords (≥3 puntos) | sí | polígono (calle/barrio): el mapa lo pinta como zona dorada punteada en vez de punto |

### 2.3 `transits` (trayectos)

| campo | tipo | opcional | uso |
|---|---|---|---|
| `mode` | `walk`·`train`·`bus`·`ferry`·`monorail`·`flight`·`tramite`·`tour` | sí (default `walk` en GEO) | icono de fila y estilo de línea (walk = fina punteada) |
| `coords` | coords | sí | polilínea; si FALTA y un paso lo referencia → conector automático (§7.8) |
| `color` | hex | sí (default `#7a6f63`) | color de la línea y del chip |
| `line` | string | sí | nombre de línea; liga la identidad de `lines` por nombre |
| `name_jp`, `chip`, `recognize` | string | sí | tarjeta de línea (nombre nativo, letra del círculo, «se reconoce») |
| `platform` | `[letrero_nativo, romaji]` | sí | renglón «Andén correcto» |
| `reverse` | string | sí | aviso «si la primera parada es X van al revés» |
| `stations` | lista de `[código, nativo, romaji]` | sí | paradas; si `len(stations) == len(coords)` cada vértice ES una parada con nombre |
| `stops` | coords | sí | posiciones de estación cuando `coords` ya es trazo denso (OSM) y perdió la alineación 1 vértice = 1 estación |
| `pois` | claves de places separadas por espacio | sí | POIs pintados junto al trazo (grupo «En el camino») |
| `vehicle` | `tren` (default) · `bus` · `barco` | sí | ajusta iconos y la frase de auxilio del modal |
| `guide` | string md | sí | texto libre del modal (sustituye a `extra` de la línea) |

### 2.4 `lines` (identidad de línea)

Catálogo de líneas de transporte con datos de servicio: `name`, `name_jp`,
`chip`, `color`, `recognize`, `extra` (md), `frequency`, `first_train`,
`last_train`, `frequency_source` (URL). **Regla de identidad**: un transit
hereda `frequency/first_train/last_train/frequency_source` de la línea cuyo
`name` coincide con su campo `line`, o (si no) cuyo `chip` coincide con su
`chip`. Solo se indexan líneas CON `frequency` — una línea sin frecuencia es
invisible para este lookup. Las claves de `lines` también pueden referenciarse
directas con `@[…](clave)` (modal de línea sin datos de viaje).

### 2.5 `days` y `steps`

Cada día: `title` (string; lo que precede al primer `·` es la etiqueta del
chip de navegación), `note`, `anchor` (el "momento estelar", mostrado como
`Ancla: …`), `date` (fecha YAML o string; se serializa ISO), `steps` (lista).

Un paso es un mapeo. Tres formas concretas: **paso-lugar** (`location:
clave`), **paso-trayecto** (`transit: clave`), **paso-nota** (solo `title`).
Campos:

| campo | tipo | semántica |
|---|---|---|
| `location` / `transit` | clave | identidad del paso (excluyentes en la práctica; `location` gana) |
| `title` | string md | título de la fila; si falta y hay `location`, se deriva `@[name](clave)` |
| `note` | string md | nota de la fila |
| `time-from` | `'H:MM'`/`'HH:MM'` | hora de inicio explícita |
| `time-to` | string | hora de fin explícita — se emite y compara LITERAL (no se normaliza: `'9:05'` sobrevive) |
| `fixed` | bool | hora dura (clase `fixed`, roja) — solo presentación/round-trip |
| `duration` | ver §2.6 | duración explícita |
| `mode` | string | override del modo (icono) sin transit de catálogo |
| `hidden-summary` | bool | caminata plegada solo-mapa: fuera del horario, oculta en el itinerario, visible gris en la barra del mapa con duración calculada |
| `select-only` | bool | se emite como `data-select-only` y se round-tripea; hoy sin efecto de UI (reservado) |
| `title-show` / `duration-show` / `note-show` | string | convención `*-show`: sustituye lo MOSTRADO; el dato base viaja en `data-value` y el verificador lo reconstruye. Lo mostrado cuenta como dato explícito |
| `options` | lista | conjunto de elección (§2.7) |
| otros (`cost`, `coords`, `color`, …) | — | TOLERADOS: el render los ignora y el contrato round-trip los exime (§4.2) |

### 2.6 Gramática de `duration`

- `'15 min'` → 15 · `'1 h 05'` → 65 · `'2'` → 2 (primer número si nada calza).
- `0` / `'0'` / ausente = sin dato (`SKIP_DUR`), no se emite.
- **flex** — paso elástico: `flex` · `flex(30)` (mín) · `flex(-60)` (máx) ·
  `flex(30-60)` o `flex(30, 60)` (rango; separador `-` o `,`; cada cota en
  cualquier sintaxis de duración, ej. `flex(30-1 h 30)`). Forma canónica: sin
  espacios ni paréntesis interiores (`flex( 30 - 60 )` ≡ `flex(30-60)`); el
  verificador compara la forma normalizada. En la fila viaja como
  `data-flex="spec"` (o `data-flex` vacío para `flex` pelón).

### 2.7 `options` — conjuntos de elección

`options:` en un paso declara un conjunto de alternativas mutuamente
excluyentes (anidables). Cada elemento de la lista es un GRUPO con `title`,
`class` opcional (clase CSS literal del `li`) y UNA de dos formas:

1. **Plan** (`steps:` directo): el grupo mismo es la opción; sus sub-pasos son
   su itinerario (con horario propio derivado y chequeo de teletransportes).
2. **Tier** (`options:` anidado): la elección real es cada opción interior.
   Una opción interior es **hoja** `{location: clave, price: '¥…'}` (link al
   modal + precio) o **enriquecida** `{title: md, price, steps: […]}` — sus
   sub-pasos (típicamente ida/lugar/regreso) no aparecen en el itinerario
   pero SÍ en el mapa, seleccionables.

Semántica de elección (UI): la PRIMERA opción de cada conjunto queda elegida
por defecto; las no elegidas se pintan fantasma u ocultas (§7.5). La elección
es estado de sesión, NO se persiste ni viaja en el YAML.

### 2.8 IDs extendidos de fila

Cada paso recibe un id DOM determinista, derivado solo de su posición:

```
dN-rMM[-gG[-oO]-sS]
```

- `dN`: día N (1-based). `rMM`: paso M del día, **2 dígitos con cero** (`r05`).
- `-gG`: grupo G (1-based) dentro de `options` del paso.
- Plan: sub-paso S del grupo → `-gG-sS`. Tier: opción O del grupo, sub-paso S
  → `-gG-oO-sS` (estos índices SIN cero-relleno).

La fila `dN-rMM` ES `days[N-1].steps[M-1]` — esta proyección 1:1 es la
identidad que usan la edición en línea, el hash y los spans.

### 2.9 Texto: markdown mínimo y refs

En todo campo de texto renderizado: `**negrita**`, `*itálica*`, salto de
línea → `<br>`, y **refs** `@[texto](clave)` → `<a class="modal-link"
href="#m-clave">…</a>` que abre la tarjeta de esa clave. Si la clave es un
transit con `color`, el link antepone un chip de línea (`<i class="line-chip"
style="--lc:color">chip</i>`; sin `chip` → variante `dot`). El escape HTML
ocurre antes del markdown. El conjunto de claves referenciadas se registra en
ORDEN de primera aparición: solo esas claves generan modal, en ese orden.

---

## 3. Render (YAML → HTML)

### 3.1 Ensamblado de página

`build_page(viaje, plantilla, salida[, extra])`:

1. Cargar `viaje.yaml` (`yaml.safe_load`) e inicializar los catálogos.
2. Renderizar días, navegación y modales; construir el mapeo de tokens
   `{'<!--NAV-->': …, '<!--DAYS-->': …, '<!--MODALS-->': …}` + los tokens del
   callable `extra` (el mapa agrega `<!--GEO-->`).
3. Leer la plantilla del viaje y sustituir cada token EXACTAMENTE una vez;
   un token ausente en la plantilla es error de build (assert).
4. Escribir la página en `pages/<viaje>/` y copiar TODO `build/assets/`
   (recursivo, incluye `vendor/`) junto a ella; después volcar
   `src/<viaje>/static/` tal cual (páginas propias del viaje, fotos,
   `manifest.webmanifest`, iconos). El release no referencia nada fuera de sí.
5. Imprimir resumen (días, modales, KB) y los diagnósticos acumulados.

`build_and_verify` corre después `verify_roundtrip.py` EN SUBPROCESO (aislado
a propósito: el verificador relee YAML y HTML desde cero) y propaga su exit
code. Las plantillas aportan todo el cromo (tabs, panel, `#map`,
`<template id="modal-store">`, `<dialog id="overlay">`, includes de JS y el
registro inline del SW §8.3); el mapa además el contenedor del GEO:
`<script id="geo" type="application/json"><!--GEO--></script>`.

### 3.2 Markup de un día

```html
<section class="day" id="dN" data-fecha="YYYY-MM-DD">
  <header class="day-head"><h3>título</h3><span class="note">nota</span>
    <span class="anchor">Ancla: …</span></header>
  <ul class="steps">
    <li id="dN-rMM" …>…</li> …
  </ul>
</section>
```

TODOS los pasos van al DOM (los `hidden-summary` incluidos, ocultos por CSS
en el itinerario): la fila `rMM` es EXACTAMENTE el paso M. La navegación es
`<a href="#dN">etiqueta</a>` por día (etiqueta = título hasta el primer `·`).

### 3.3 Markup de una fila

`<li>` con: `id`, clase `hidden-summary` si aplica, `data-location` O
`data-transit`, `data-mode`, `data-select-only`, `data-flex` (§2.6) y
`data-free="min"` (hueco libre derivado tras el paso). Contenido:

1. **`<time>`** — clase `time` (+` fixed`); atributo `datetime` si el
   `time-from` es `H:MM` válido. Interior: el `time-from` explícito como TEXTO
   directo; si falta y el horario derivado lo produjo, `<span class="from"
   data-derived="from">HH:MM</span>`. El `time-to` explícito SIEMPRE se emite
   crudo: `<span class="to">–valor</span>`; el fin derivado solo si hay inicio:
   `<span class="to" data-derived="to">–HH:MM</span>`. Conflictos:
   `<span class="warn" data-derived="conflict" title="…">⚠️</span>`;
   teletransportes: igual con `data-derived="teleport"` y 🌀.
2. **`<div class="body">`** — campos SEPARADOS, no un blob:
   - `<b class="title">` con el icono de modo como nodo de texto real
     (`<i class="icon" data-derived="mode">🚇</i>`, tabla: train 🚇 · walk 🚶 ·
     monorail 🚝 · flight ✈️ · tramite 🧳 · bus 🚌 · ferry ⛴️ · tour 🚌) + el
     título en md. Paso-lugar sin título: el lugar mismo como ref clickeable,
     marcado `data-derived="title"`. Convención `-show`: base escapada en
     `data-value`, lo mostrado como contenido.
   - `<span class="duration">` — el separador ` - ` vive DENTRO del span que
     sigue, en `<span class="sep">` (ocultar un campo por CSS se lleva su
     separador). Explícita: cruda. Flex: display derivado — rango `~lo–hi`
     (lo sin unidad si ambos < 60 min), solo mín `>lo`, solo máx `≤hi`, sin
     cotas `relleno+` o `flex`. Sin dato pero derivada: `~valor` (tilde solo
     si es aproximada) con `data-derived="duration"`.
   - `<span class="note">` — md; misma convención `-show`.
   - Los pasos-trayecto envuelven su body en `<span class="transit">` (gris).
   - `options` → §3.4.

### 3.4 Markup de options

`<ul class="options">` con un `<li>` por grupo:

- Plan: `<li data-kind="plan" data-opt="gG"><b>título</b><ul class="steps">
  sub-filas</ul></li>` — sub-filas con ids extendidos y horario propio.
- Tier: `<li data-kind="tier" data-tier="etiqueta" [class="…"]><b>etiqueta</b>
  …opciones…</li>`; cada opción `<span class="option" data-opt="gG-oO">…</span>`
  separadas por `<span class="sep"> · </span>`. Hoja: link al modal + `<span
  class="price">`. Enriquecida: título md + precio + `<ul class="steps">`.

`data-opt` es la marca del CONTENEDOR de elección (sufijo 1-based del id
extendido): el JS resuelve la rama elegida sin heurísticas de DOM. El CSS
decide el render por forma (`:has`): con sub-steps = tarjeta plan, sin ellos
= cajita tier.

### 3.5 Modales

Se emite un `<div class="modal" id="m-clave">` por clave referenciada, dentro
de `<template id="modal-store">` (no se renderiza hasta usarse).

**Lugar**: `<h3>`, `<img loading="lazy">` (prefijo `photo_base` salvo http),
descripción, `.modal-note` (info), horario (+ `src-tag` si `hours_source:
maps`), botón Maps.

**Línea** (clave de `lines`, o transit con `name_jp` — que hereda identidad
propia + `line_meta` §2.4): color como `--lc` inline; `<h3>` con rango
horario derivado; banner con nombre nativo y chip; renglón frecuencia
(+ link «horario oficial ↗» si hay fuente); renglón derivado «🟢 Sale hh:mm
origen → 🔴 Llega hh:mm destino» — calculado del PRIMER paso del itinerario
que usa ese transit (`time-from` + duración; origen/destino = romaji de la
primera/última estación); andén (`platform`, con iconos por `vehicle`);
aviso `reverse`; lista de estaciones con `SUBIR`/`BAJAR` derivados en los
extremos; y una **frase de auxilio** derivada en el idioma local + romaji +
glosa («¿voy bien en este tren/bus/barco?», con el sufijo de estación 駅
cuando aplica) para enseñar el teléfono. Cierra «Se reconoce: …» + `guide`/
`extra`. Todo lo calculado va `data-derived` (`schedule`, `pos`, `phrase`).
Clave sin catálogo → modal esqueleto con solo `<h3>clave</h3>`.

---

## 4. Contrato round-trip 1:1

### 4.1 Qué significa

El HTML generado es una **proyección 1:1** del YAML: todo dato explícito del
YAML es recuperable del HTML, y nada inventado se confunde con dato. Dos
verificaciones distintas lo sostienen:

1. **Semántica (cada build)**: `verify_roundtrip.py` parsea el HTML,
   reconstruye `days` y los compara campo a campo contra el YAML normalizado.
   Cualquier diferencia = build fallido (exit 1, lista hasta 40 diffs).
2. **Textual (edición)**: las ediciones NUNCA re-serializan el YAML — cortan
   y empalman TEXTO CRUDO por spans (§9). Editar el paso X y guardarlo sin
   cambios devuelve el archivo byte-idéntico; comentarios y formato del autor
   sobreviven cualquier edición.

### 4.2 Qué está exento

- Todo nodo con `data-derived` (horarios encadenados, duraciones calculadas,
  iconos de modo, títulos derivados, avisos ⚠️/🌀, bloques derivados de los
  modales) y los `<span class="sep">` presentacionales.
- Campos solo-mapa o pasarela: `coords`/`color` de transits (viven en GEO),
  y cualquier campo de paso fuera de la lista de §2.5 (`cost`, `coords`
  inline, `color` inline…): el render los ignora y la normalización los
  descarta EN AMBOS lados, así que no rompen la comparación — pero solo el
  contrato textual (spans) los preserva.
- Los chips `<i class="line-chip">` dentro de refs (decoración derivada).

### 4.3 Normalizaciones acordadas (viven en `contract.py`)

Ambos lados aplican las mismas: títulos sin `*`; duraciones en `SKIP_DUR`
omitidas; `flex` a forma canónica; `time-to` comparado literal; strings
`strip()`; `date` a ISO. La inversión del markdown es exacta: `<b>`↔`**`,
`<i>`↔`*`, `<br>`↔`\n`, `a.modal-link`↔`@[alt](clave)`.

### 4.4 Algoritmo del verificador

Parser HTML propio (árbol simple, sin dependencias). Por `section.day`:
título/nota/ancla/fecha del header y `data-fecha`; por `li`: los `data-*` →
`location/transit/mode/select-only/duration(flex)`, la clase
`hidden-summary`, el `<time>` (texto directo = `time-from`; `span.to` sin
`data-derived` = `time-to`; clase `fixed`), y del body: `b.title`,
`span.duration`, `span.note` (con `data-value` → par base + `*-show`),
`ul.options` recursivo (grupo plan/tier por presencia de `ul.steps`; opción
hoja por `a.modal-link`, enriquecida por sub-`ul`; `class` del `li` del
grupo). El YAML se normaliza a la misma forma (§4.3) y se hace diff
estructural recursivo con rutas legibles (`d3.steps[5].title: 'a' != 'b'`).

---

## 5. Horarios derivados y diagnósticos

### 5.1 Campos por paso

Para cada paso NO `hidden-summary`: inicio (`time-from`), fin explícito
(`time-to`), duración (o flex §2.6). Si los tres existen y `inicio + duración
≠ fin` → conflicto (⚠️ en la fila + diagnóstico). Sin duración pero con
inicio y fin → duración exacta derivada (fin − inicio, sin `~`).

### 5.2 Caminatas: la geometría dicta la duración

Si el paso es caminata (modo `walk` propio o de su transit) con coords y no
es flex: `esperado = round_walk(largo / velocidad)` con velocidad **4 km/h**
y redondeo hacia arriba a múltiplo de 5 (mínimo 5) hasta 45 min; de ahí en
adelante, a múltiplo de 15. Sin duración → se adopta (derivada, aproximada,
gris `~`); duración explícita DISTINTA → diagnóstico («dice X min pero el
camino mide Y m ≈ Z min a 4 km/h»). El mismo cálculo, espejado en JS, alimenta
los mensajes del editor de geometría.

### 5.3 Snap a vecinos

Regla: cada paso debe quedar con 2 de {inicio, fin, duración}. Dos pasadas:

- **Adelante**: sin inicio → fin del paso anterior (cursor). Sin duración con
  inicio → hueco hasta el PRÓXIMO inicio explícito (derivada, `~`). Flex: la
  duración es el relleno disponible acotado por `[mín, máx]` (sin relleno cae
  al mín; siempre derivada `~`). Fin = `time-to` explícito o inicio+duración;
  el cursor avanza al fin (o al inicio si no hay fin).
- **Atrás**: con duración pero sin inicio — un `time-to` explícito propio
  manda (`inicio = fin − duración`); si no, fin = inicio del siguiente
  explícito e `inicio = fin − duración`.

Después: **huecos libres** — para cada paso con fin, si el próximo inicio YA
RESUELTO (explícito o derivado) es posterior, la diferencia se emite como
`data-free` (la UI la muestra bajo demanda, §7.11).

**Diagnósticos de horario**: paso sin inicio anclable; paso no-lugar con solo
inicio (un LUGAR con solo inicio es ancla válida: llegas y punto); inicio y
duración explícitos que se enciman con el inicio explícito del siguiente
(conflicto ⚠️ con minutos de exceso).

### 5.4 Continuidad geométrica (teletransportes)

Por cada secuencia de pasos (día o plan): el fin geométrico de un paso debe
coincidir (± **100 m**, tornillo `GEO_TELEPORT_M`) con el inicio del
siguiente. Punto de un lugar = su `gps`; de un transit = primer/último
vértice. Tres mensajes según el par: transit que arranca lejos · transit
anterior que termina lejos · lugar→lugar sin transit de por medio
(«teletransporte»). Un transit declarado SIN coords corta la cadena sin aviso
(geometría pendiente: el mapa dibuja su conector automático). El aviso se
adjunta a la fila (🌀 `data-derived`, tooltip con la distancia) y a la lista
de diagnósticos. Qué umbral de separación tolera el CONTENIDO de un viaje es
política del viaje (su REGLAS.md), no de la herramienta.

Los diagnósticos (horario + geometría + coords malformadas) se ACUMULAN y se
imprimen al final del build como avisos; no detienen el build (a diferencia
del round-trip). Los `hidden-summary` quedan fuera del horario pero su
duración calculada del trazo SÍ se muestra (gris) en la barra del mapa.

---

## 6. Payload GEO (solo mapa.html)

JSON inyectado en `<script id="geo" type="application/json">`. Claves:

| clave | forma |
|---|---|
| `locations` | `{clave: [lat, lon]}` — places con `gps` parseable |
| `transits` | `{clave: {coords: [[lat,lon]…], color, mode, stations?, stops?, pois?}}` — solo transits CON coords. `stations`: lista de nombres display (romaji, o nativo si falta, o el string tal cual). `stops`: `[[lat,lon]…]`. `pois`: lista de tuplas POI |
| tupla POI | `[lat, lon, clave, nombre, zona?]` — la zona (polígono del `zone:` del place, ≥3 vértices) va como 5º elemento opcional `[[lat,lon]…]` |
| `poiClusters` | `{cluster: [tuplaPOI…]}` — places con `poi:` agrupados |
| `anchors` | `{idFila: {prev: [lat,lon]|null, next: …}}` — SOLO para pasos con `transit:` sin geometría: el punto del vecino con geometría más cercano hacia atrás/adelante, **acotado al mismo día y a la misma rama de opciones** (regla same-branch: un candidato es vecino válido si el paso cuelga de cada conjunto de options ancestro del candidato por el MISMO contenedor; fuera de todo conjunto siempre vale). Vecino lugar → su gps; vecino transit → su último vértice (prev) o primero (next). El JS los consume por id y solo rastrea en vivo si el id no está |
| `edit` | spans de edición (§9.3): `{sha, repo, path, branch, steps: {idFila: [inicio, fin, col]}, entities: {clave: [kind, inicio, fin, col]}}`. `sha` = git blob sha1 del YAML (`sha1("blob N\0" + bytes)`) |
| `trip` | nombre del viaje (identidad para el modo dev, en vez de olfatear la URL) |
| `buildSha` | `GITHUB_SHA` del build de CI (vacío en local) — lo usa el chip de deploy |
| `bbox` | `[minLat, minLon, maxLat, maxLon]` de toda la geometría — vista inicial |

---

## 7. UI del mapa (`mapa.js` + `mapa.css` sobre el markup común)

Mapa base Leaflet vendorizado (tiles CARTO Positron `light_all`, maxZoom 20,
zoom control abajo-derecha). Si `GEO.bbox` existe, la vista inicial lo
encuadra (padding 40); si no, un setView de respaldo. El acento de color se
lee de la variable CSS `--shu`.

### 7.1 Disposición

- **≥ 821 px** (tornillo): el panel es COLUMNA junto al mapa con **splitter**
  arrastrable (pointer events con capture): ancho inicial 380 px, límites
  260 px – 70 % del viewport, persistente en localStorage (`mapa-panel-w`),
  doble-click restaura 380 y borra la persistencia; cada movimiento
  `invalidateSize()` del mapa. El ancho vivo se publica como variable CSS
  `--panel-w` (lo usan los tabs).
- **< 821 px**: el panel flota (botón ☰); elegir algo (fila, opción, grupo)
  lo cierra solo para dejar ver el popup.

### 7.2 Días y casillas

Cada fila (y sub-fila de options) recibe una casilla `.ck`; cada día un
maestro `.ck-day` + caret. **Invariante del maestro** (tri-estado): todo
prendido = ✔ · algo = indeterminate ▬ · nada = vacío; se recalcula tras
CUALQUIER cambio, venga de click o de código. El maestro prende TODO el día,
incluidos sub-pasos plegados. Click en cabecera = plegar/abrir (abrir también
ENCUADRA la geometría del día sin dibujarla). Los chips de la barra de días
abren ese día EXCLUSIVO (los demás se pliegan) y encuadran. Arranque: día 1
abierto.

### 7.3 Capas vivas

SOLO las filas marcadas dibujan su geometría. Sincronización con debounce de
120 ms tras cualquier click/change del panel. Por clave se calcula el estado
deseado `full | ghost | hidden` (§7.5); si la clave se repite en varias
filas, gana el MEJOR estado (full > ghost > hidden). Lugares → marcador con
**insignia numerada**: los lugares plenos (full) de cada día se numeran en
orden del documento (`1`, `2`; clave repetida acumula `2·5`). Transportes →
grupo: polilínea (walk = 3 px punteada `4 7`; resto 5 px sólida; opacidad
.85) + una línea de IMPACTO invisible de 16 px (las punteadas casi no se
atinan) + flechas de rumbo ❯ a ¼, ½ y ¾ del recorrido + puntos de estación
con tooltip (de `stops` si calzan con `stations`, o de los vértices si
calzan 1 a 1) + POIs del tramo. Click en geometría: SIEMPRE (re)abre su
tarjeta, selecciona la fila correspondiente en la barra (si la clave sale en
varios días gana la del día abierto), sincroniza el caminador; segundo click
consecutivo acerca el zoom (+2, máx 19; trazas → fitBounds pad .02).

### 7.4 Modelo de elección (choice-path)

Cada `ul.options` es un conjunto de radios mutuamente excluyentes
(anidables). Plan: el radio vive en el grupo (`group-choice`); tier: en cada
opción de abajo (`option-choice`), compartiendo `name` por conjunto. La
primera opción queda marcada por defecto (sin volar). Primitivas: «¿está el
elemento en la ruta elegida?» (todas sus elecciones ancestras lo contienen,
resueltas por `data-opt` con recorrido DOM de respaldo) y «¿misma rama?»
(para vecinos/anclas). Elegir un grupo muestra su geometría completa
(capa temporal + halo + vuelo); las opciones con sub-pasos llevan pliegue
propio (plegadas por defecto); los grupos y las filas con options llevan
caret que pliega SIN elegir.

### 7.5 Estados full/ghost/hidden

Cada conjunto lleva un ojo: 👁 (default) = no elegidos en fantasma; 🙈 = no
elegidos "ocultos". El estado de un elemento marcado es el PEOR entre todos
sus conjuntos ancestros. Estilos (tornillos): capa normal — full opacidad
.85/1; ghost .25; hidden .12 con la línea ENGORDADA +7 px (visible: distinta,
no borrada); insignias de lugar atenuadas en ghost/hidden. Conectores
automáticos — full .7; ghost .2; hidden .1 con grosor 9.

### 7.6 Caminador (stepper principal)

Barra flotante `‹ [paso actual] ›` sobre el mapa; TODOS los eventos de ratón
se tragan (un click que burbujee a Leaflet cerraría el popup recién abierto).
Recorre los pasos CONCRETOS (con `data-location`/`data-transit`) que estén en
la ruta elegida. En cada paso: activa el día si cambió (apaga el día activo
anterior, prende el nuevo completo), abre su día, selecciona y centra la
fila, escribe el hash `#@idFila` (replaceState), vuela encuadrando la
geometría COMPLETA del paso con **tope de zoom 16** (`ST_MAX_ZOOM` — regla:
nada de promedios de zoom) y abre su tarjeta.

- **Modo elección**: si el paso siguiente entra a un conjunto de options
  distinto del actual, `›` NO avanza: cierra el popup y muestra botones de
  elección (planes = un botón por grupo; tiers = columnas por grupo con
  cabecera fija y color del tier; botón `on` = contiene el paso actual,
  `chosen` = radio marcado). Elegir marca el radio y entra al PRIMER paso
  concreto de esa opción; una opción PLANA (sin sub-pasos) marca el radio y
  muestra su referencia en el mapa. `‹` en modo elección es CANCELAR (siempre
  habilitado). Dentro de una opción se ofrece «saltar a ▾» (plegable,
  persistente) con TODAS las opciones del conjunto.
- **Pasos sin geometría**: transit sin coords → encuadra sus dos anclas
  vecinas (de `GEO.anchors` o rastreo en vivo) con el mismo tope y abre la
  tarjeta al centro; paso-NOTA (ni lugar ni transporte) → vuela al ANCLA
  PREVIA con zoom de calle (encuadrar ambos vecinos podía dejar un vacío de
  50 km).
- Repetir la misma clave acerca (+2; lugares nunca bajo 16, máx 19). Vuelos:
  lugar zoom `max(actual, 15)` (o 16 con fit), traza `pad .25, maxZoom 18`
  (16 con fit).

### 7.7 Stepper de día

Barra inferior `‹ día / etiqueta / día ›`. La fuente de verdad es el **día
ACTIVO** (visible en el mapa), NO el día del paso seleccionado (divergen si
el usuario clickea filas de otro día sin activarlo). Avanzar: apaga y pliega
el día anterior, prende y abre el nuevo, salta al primer paso concreto (día
sin pasos concretos: queda activo y navegable, hash `#dN`). Extremos
deshabilitados.

### 7.8 Conectores automáticos

Un paso con `transit:` SIN geometría dibuja (si su casilla está marcada) un
conector recto punteado gris (`2.5 px`, guiones `2 8`, una flecha al centro)
entre el ancla previa y la siguiente — mismo día, misma rama (§6 anchors).
Sin alguno de los dos vecinos: no hay conector. Respeta full/ghost/hidden con
sus propios estilos.

### 7.9 Capa 📍 POIs

Control bajo la barra de días: maestro tri-estado «📍 Puntos de interés (N)»
+ desglose plegable con un checkbox por cluster (persistencia por cluster:
localStorage `mapa-poi-<cluster>`; default apagado). Los `pois` de los
transits forman el grupo extra «En el camino». Punto dorado (#c9a227) con
tooltip, o POLÍGONO dorado punteado con relleno tenue y tooltip pegajoso si
la entrada trae zona. Click → tarjeta + selección de fila si existe. Qué POIs
se enganchan a qué caminata y cómo se derivan las zonas es trabajo de
herramientas de `scratch/` que escriben el YAML (fuera del pipeline).

### 7.10 Popups (tarjetas en el mapa)

`L.popup` maxWidth 320, **autoPan APAGADO** (pelearía con el vuelo en curso).
Contenido: el modal de la clave + (lugares) una pieza `<details>` por día que
usa el lugar — colapsada a «día + una línea», expandida la del día abierto o
la fila clickeada. Si la tarjeta excede el **40 % de la pantalla** llega
colapsada con botón «Ver más ↓»/«Ver menos ↑» (sin re-render del contenido:
mutar el DOM del popup, nunca `update()`). **Des-recorte**: 620 ms tras
abrir, si el popup quedó bajo el chrome o pegado a un borde, panear LO MÍNIMO
para destaparlo — márgenes 96 px arriba, 54 px derecha, 44 px abajo, 10 px
izquierda. Guardias: no tocar la cámara con la pestaña oculta, y si un vuelo
sigue animando REINTENTAR (hasta 8× cada 400 ms) en vez de panear — `panBy`
CANCELA un `flyTo` en curso. Abrir el selector de opciones cierra el popup.
Halo de selección debajo de las capas: disco (radio 14, acento, .3) o línea
gorda (13 px, color de la línea, .35).

### 7.11 Cromo adicional

- **∅**: toda fila hoja sin geometría (nota, o transit sin coords) recibe un
  indicador ∅ con tooltip — para cazarlas al editar.
- **⏳ tiempo libre**: toggle flotante; muestra bajo cada fila con `data-free`
  el renglón «⏳ N min libres» (CSS). Persistente (`mapa-free`).
- **Chip de deploy**: la página vigila su propia Action (repo público, sin
  auth): GET del último run cada 90 s (pausado con pestaña oculta;
  `visibilitychange` fuerza un check). Run no completado → «🚀 publicando
  cambios…» (no clickeable); completado con éxito y `head_sha ≠ buildSha`
  del build servido → «✨ hay versión nueva — toca para recargar»: al tocar
  pide `registration.update()` del SW ANTES de recargar (recargar a secas
  re-serviría la versión vieja del caché). Errores de red: el chip
  simplemente no aparece.
- **Links a modal en el panel** (listener en CAPTURA, para ganarle al dialog
  de itinerario.js): si la clave tiene geometría → popup del mapa + selección
  + hash; si no → cae al dialog. Click en fila (fuera de casillas/links):
  selecciona, sincroniza el caminador, vuela + tarjeta + hash; fila
  contenedora sin clave propia: halo + encuadre de TODO su subárbol.

### 7.12 Hash y restauración

Gramática: `#m-<clave>` (tarjeta) · `#@<idFila>` (posición) ·
`#m-<clave>@<idFila>` (ambos) · `#d<N>` (día exclusivo). El hash SIGUE al
caminador y a la selección (replaceState, sin ensuciar el historial); la
visibilidad de casillas NO se codifica. Al cargar: `#dN` → ese día activo y
caminador en su primer paso; `#@fila` → llegar EXACTO a ese paso con el
caminador (día activo, vuelo y tarjeta; si la fila ya no existe y no hay
modal → default); `#m-clave` → tarjeta (con vuelo si hay geometría); si el
mapa restauró la cámara, el encuadre de arranque NO la pisa (bandera
`restoredView`); en modo dev la fila reabre su editor; el dialog que
itinerario.js hubiera abierto por el mismo hash se cierra (en el mapa manda
el mapa). Hash inválido → estado por defecto (día 1 completo, stepper en su
primer paso), NUNCA página rota. La recarga tras un rebuild vuelve así al
mismo punto.

---

## 8. PWA

### 8.1 `sw.js` generado (último paso del build del mapa)

Se genera DESPUÉS de tener el release completo, listando todo `pages/<viaje>/`
(excluyendo el propio `sw.js`). Contenido normativo:

- `CACHE = 'viaje-<versión>'` — versión = `GITHUB_SHA[:12]` en CI; en local,
  sha1 de (ruta + BYTES de cada archivo)[:12]. **Nunca solo la lista de
  archivos**: una edición del mismo tamaño no cambiaría el SW y los
  navegadores se quedarían con la versión vieja para siempre.
- `install`: precache de TODA la lista (más `./`) en **lotes de 20** con
  `Promise.allSettled` (tolerante: una imagen caída no tira la instalación) y
  `Request(u, {cache: 'no-cache'})` — GitHub Pages sirve `max-age=600`; sin
  esto una instalación nueva copiaría assets VIEJOS del caché HTTP y quedaría
  una versión mixta. Cierra con `skipWaiting()`.
- `activate`: borra todo caché que no sea el actual ni `viaje-tiles`;
  `clients.claim()`.
- `fetch` (solo GET): host de tiles (`*.cartocdn.com`) → caché de RUNTIME
  `viaje-tiles`, red primero con copia al caché y respaldo de lo ya visto
  (offline se ve lo visitado). Mismo origen → caché primero
  (`ignoreSearch`), red de respaldo. Todo lo demás pasa de largo.

Cache Storage, no localStorage (los archivos no caben ahí). Resultado: el
sitio ENTERO funciona offline, imágenes incluidas.

### 8.2 Manifest

`manifest.webmanifest` + iconos van en `static/` del viaje (se copian tal
cual); las plantillas lo referencian.

### 8.3 Registro y auto-recarga

Inline en las plantillas: capturar ANTES de registrar si la página ya estaba
controlada (`had = !!navigator.serviceWorker.controller`); registrar `sw.js`;
en `updatefound` → `statechange` del worker: al llegar a `activated`, recargar
UNA vez SOLO si `had` — la primera visita (SW recién instalado, página no
controlada) nunca se recarga sola.

---

## 9. Edición en línea

Dos transportes con LA MISMA semántica y las mismas herramientas visuales; la
página elige sola: si `/api/ping` responde → dev server (§10); si no y el
build trae `GEO.edit.steps` → modo GitHub sin servidor. La paridad byte a
byte entre ambos es requisito (los ports de dedent/reindent son exactos).

### 9.1 Principio: edición por SPANS de texto crudo

Nunca parsear-y-re-serializar. El YAML se trata como texto; `yaml.compose()`
(el árbol de nodos con marks de línea/columna) solo UBICA cada pieza:

- **Span de un item de secuencia** (un paso): `[línea_inicio,
  línea_fin_exclusiva, col]` donde inicio = línea del item, fin = línea del
  item SIGUIENTE (o, para el último, la línea del `end_mark` del ITEM — +1 si
  su columna > 0 — nunca el `end_mark` de la secuencia, que en listas
  anidadas se pasa de largo hacia afuera), y `col` = columna del guion
  (columna del item − 2).
- **Navegación a sub-pasos**: el sufijo del id (`-g1-s2`, `-g1-o2-s3`) se
  interpreta segmento a segmento: `g`/`o` descienden por `options`, `s` por
  `steps`, con validación de rango.
- **Extraer** (editor ← archivo): cortar las líneas del span y DESINDENTAR:
  primera línea sin el `col+2` del `- `; las demás sin `col+2` espacios (solo
  si ese prefijo es blanco; si no, `lstrip`); las líneas EN BLANCO se
  preservan como `\n` (no se comen).
- **Reinyectar** (editor → archivo): validar que el texto parsea a un mapeo
  YAML; REINDENTAR (primera línea `col·espacios + '- ' + …`, resto `col+2`,
  blancas intactas); EMPALMAR reemplazando las líneas del span; validar que
  el ARCHIVO COMPLETO sigue siendo YAML válido antes de escribir; escritura
  atómica (tmp + replace). En el server todo bajo un RLock que cubre cada
  secuencia leer-modificar-guardar completa.
- **Entidades** (places/transits/lines): span del PAR completo `clave: …`
  (incluye la línea de la clave; col = columna de la clave; búsqueda en
  places → transits → lines si no se da el kind). Guardar exige que el texto
  sea un mapeo con exactamente esa clave. Clave NUEVA: se crea al FINAL de su
  catálogo.
- **Insertar paso**: empalme de `- title: (nuevo paso)` antes/después del
  span; devuelve la posición 1-based nueva. **Mover**: intercambio de los
  bloques de texto de los dos items adyacentes.

### 9.2 `dev_server.py` (opcional, local)

Sirve el directorio PADRE del repo con `Cache-Control: no-store` (preview
instantáneo). Puerto default 8791. API JSON:

| endpoint | semántica |
|---|---|
| `GET /api/ping` | `{ok, auth: 'ok'|'required', user}` — la sonda que enciende el modo dev |
| `GET /api/step?trip&day&step[&sub]` | texto CRUDO desindentado del paso |
| `POST /api/step {trip,day,step,sub,yaml}` | valida y empalma (SIN rebuild: se editan varios y luego…) |
| `GET /api/entity?trip&key[&kind]` | `{kind, yaml}` de la entidad |
| `POST /api/entity {trip,kind,key,yaml}` | escribe/crea la entidad en su catálogo |
| `POST /api/step-insert {trip,day,step,where,sub}` | inserta antes/después; devuelve `step` nuevo |
| `POST /api/step-move {trip,day,step,dir,sub}` | mueve ±1; devuelve `step` nuevo |
| `POST /api/rebuild {trip[,deploy]}` | corre ambos builds BAJO EL LOCK (si no, un Guardar entre los dos scripts produce itinerario y mapa de versiones distintas); `deploy` = `git push` (la Action publica) |

Cada guardado se auto-commitea (`dev: paso dN-rMM… (usuario)`). Seguridad:
localhost pasa directo; con `--share` (bind 0.0.0.0 para túnel/LAN) todo
`/api/` exige sesión por **OAuth device flow** de GitHub
(`/api/login/start` + `/api/login/poll`; el server habla con GitHub, el
navegador solo enseña el código; cookie HttpOnly) contra un allowlist de
usuarios (`TF_DEV_ALLOW`). El path del viaje se valida contra `src/`
(con separador final: sin él `../srcotra` pasaba el filtro).

### 9.3 `dev-github.js` (sin servidor: contents API)

El build precalcula TODOS los spans (§6 `edit`) y el blob sha del YAML. El
cliente:

- **Token**: PAT fine-grained pegado UNA vez → localStorage (`gh-pat`). El
  popup de login trae las instrucciones completas: Only select repositories →
  este repo; permisos **Contents, Pages y Pull requests: Read and write**, lo
  demás No access; se valida con `GET /user` antes de aceptarlo. El usuario
  además debe ser colaborador del repo.
- **Estado**: al primer uso baja el archivo por contents API; si el sha real
  ≠ `edit.sha` del build y aún no hay ediciones propias → error «el sitio va
  detrás del último commit — espera el deploy y recarga» (nunca commitear a
  ciegas sobre una base distinta). Cachea texto + copia de los spans.
- **Commit**: cada Guardar es UN commit `PUT contents` (mensaje `dev: … (web)`,
  base64, `sha` del blob actual). El sha devuelto ENCADENA el siguiente
  commit. Tras cada empalme, los spans en memoria se CORREN por el delta de
  líneas (`nuevas − (fin − inicio)`): spans que empiezan en/después del corte
  se desplazan completos; los que solo terminan después, solo el fin —
  ediciones sucesivas caen en su lugar sin re-deploy.
- **Operaciones**: mismas de §9.1/§9.2 con los ports exactos de
  dedent/reindent; entidad nueva se inserta tras el último span de su kind;
  «fila sin span» (ids renumerados sin deploy) es error legible.
- **`rebuild` en este modo = `waitAction()`**: no hay build local — se sondea
  el último workflow run cada 12 s hasta verlo completado (creado dentro de
  la ventana de la edición) o hasta 6 min («sigue corriendo — recarga en un
  rato»). El deploy real lo hace la Action al recibir el commit.

### 9.4 Cajón de edición (UI, ambos modos)

El botón 🛠 (persistencia `mapa-dev`) activa el modo: click en fila = editar.
El cajón muestra: identidad (`fila dN-rMM = days[N-1].steps[M-1] …sub`),
claves, horario visible y avisos; textarea con el YAML crudo del paso;
botones Guardar (solo escribe; se editan varias filas), Rebuild (reconstruye
y recarga — el hash `#@fila` regresa al mismo punto), Deploy 🚀, Cancelar;
operaciones de paso (+ antes / + después / ▲ / ▼) que tras guardar RE-APUNTAN
el cajón al número nuevo (el índice que cambia es el último segmento del id)
y ofrecen rebuild+recarga posicionada; botones de REFERENCIAS (location/
transit/@refs de la fila) que cargan la entidad para editarla; alta de
referencia nueva (clave validada `[a-z0-9-]`) con PLANTILLAS (lugar/caminata/
tren/bus/ferry) — una referencia aún sin catálogo queda «pendiente de
geometría» y el mapa la trata como conector automático.

**Editor de geometría** (solo transits): dibuja la línea editable sobre el
mapa — arrastrar vértices, click en punto medio inserta, click derecho borra
(mínimo 2); cada cambio reescribe la línea `coords:` del textarea de la
entidad (6 decimales; la escalar puede venir PLEGADA en varias líneas: se
reemplaza el bloque completo) y refleja en GEO. Transit nuevo sin coords: se
siembra entre las anclas vecinas del paso. «Ajustar a calle»: snap punto por
punto contra OSRM `/nearest` (perfil peatonal de FOSSGIS para walks, auto
para el resto; respuestas tardías de un segmento anterior se descartan).
«Geo auto»: traza `coords` completas por ruta OSRM entre las anclas vecinas
(`overview=full&geometries=geojson`). Los mensajes de caminata anexan
`· N m ≈ ~M min a pie` con el espejo exacto del cálculo del build (§5.2).

---

## 10. UI del itinerario (`itinerario.js`)

- **Modales en `<dialog>`**: los links `.modal-link` abren la tarjeta desde
  `#modal-store`; Escape/backdrop/× los maneja el dialog nativo. El hash
  comparte la gramática `#m-clave[@fila]`: al abrir se escribe
  (replaceState); al llegar con hash se hace scroll a la fila (o a la primera
  que referencia la clave) con un destello de 2 s y se abre la tarjeta;
  `hashchange` re-aplica; cerrar limpia el hash.
- **Barra de días**: sticky; IntersectionObserver (rootMargin
  `-50px 0px -55% 0px`) resalta el día visible y auto-scrollea su chip;
  arriba del día 1 conserva el resaltado previo.
- **Carruseles** (`.options`, `.day-nav` desbordadas): arrastre lateral con
  mouse (umbral 5 px; un arrastre real suprime el click que suelta); el touch
  scrollea nativo.
- **Imágenes rotas** de modales: se ocultan (listener de error en captura).
- Lo derivado se esconde por CSS en esta página (el mapa sí muestra
  DESDE–HASTA); las filas `hidden-summary` no se muestran aquí.

---

## 11. ⚙️ Configuración (`cfg.js`, todas las páginas)

Botón ⚙️ + menú (se cierra al tocar fuera; sus clicks no llegan al mapa):

- **🔎 Texto**: zoom por niveles cíclicos 1 → 1.12 → 1.25 → 1.4, persistente
  (`cfg-zoom`). En el mapa aplica al PANEL (zoomear el body descuadra los
  clicks de Leaflet); en las demás páginas al body.
- **🔄 Buscar actualización**: `registration.update()` del SW y recarga (sin
  SW, recarga igual).

---

## 12. Deploy (GitHub Actions + Pages)

Workflow `build & deploy`: dispara en push a `main` que toque `src/**`,
`build/**` o el propio workflow, y manual (`workflow_dispatch`).
**Concurrencia**: grupo único `build-deploy` con `cancel-in-progress` (una
ráfaga de commits de la edición en línea colapsa al último). Permisos:
`contents: read`, `pages: write`, `id-token: write`. Job build: checkout,
Python 3.12, `pip install pyyaml`, corre AMBOS builds (el round-trip fallido
tumba el job), escribe un `pages/index.html` de redirección y sube `pages/`
como **artefacto de Pages**; job deploy: `deploy-pages` (environment
`github-pages`). El sitio se sirve del artefacto: `pages/` NO vive en git.
El repo es auto-sostenible: cualquier edición del src (web, API o push)
republica sola; el chip (§7.11) y `waitAction` (§9.3) observan este workflow.

---

## 13. Tornillos (valores reales del código)

| perilla | valor | dónde |
|---|---|---|
| breakpoint columna/overlay | 821 px | mapa.css `@media` · mapa.js `matchMedia` |
| ancho panel default / mín / máx | 380 px / 260 px / 70 vw | mapa.css `.panel` · mapa.js splitter |
| tope de zoom del caminador | 16 (`ST_MAX_ZOOM`) | mapa.js |
| zoom al repetir click | +2 (máx 19; lugares ≥ 16) | mapa.js `showOnMap` |
| colapso de tarjeta | 40 % del alto de pantalla | mapa.js `openCardPopup` |
| des-recorte: márgenes / espera / reintentos | 96↑ 54→ 44↓ 10← px / 620 ms / 8 × 400 ms | mapa.js `openCardPopup` |
| opacidades full/ghost/hidden | .85 / .25 / .12 (+7 px) | mapa.js `STYLE` |
| conectores automáticos | .7 / .2 / .1 (grosor 9) | mapa.js `AUTO_STYLE` |
| debounce de sincronización de capas | 120 ms | mapa.js `schedSync` |
| línea de impacto de clicks | 16 px invisible | mapa.js `transitGroup` |
| umbral de teletransporte | 100 m (`GEO_TELEPORT_M`) | render.py `check_teleports` |
| velocidad de caminata derivada | 4 km/h | render.py `WALK_M_PER_MIN` (espejo mapa.js `walkMins`) |
| redondeo de caminatas | ↑ múltiplo de 5 (mín 5) hasta 45; luego ↑ múltiplo de 15 | render.py `round_walk` |
| lote y tolerancia del precache | 20 por lote, `allSettled`, `cache:'no-cache'` | build_mapa `gen_pwa` |
| versión del SW | `GITHUB_SHA[:12]` o sha1(contenido)[:12] | build_mapa `gen_pwa` |
| chequeo del chip de deploy | cada 90 s; pausado con pestaña oculta | mapa.js `deployWatch` |
| sondeo de `waitAction` | 12 s, tope 6 min | dev-github.js |
| niveles de zoom de texto | 1 / 1.12 / 1.25 / 1.4 | cfg.js `ZOOMS` |
| puerto del dev server | 8791 | dev_server.py |
| radio POI↔caminata («En el camino») | 100 m | scratch/attach_pois.py `RADIO` (fuera del pipeline) |
| zonas: búsqueda / recorte / margen | 200–350 / 120–350 / 12–25 m por zona | scratch/zonas_poi.py `ZONAS` (fuera del pipeline) |
