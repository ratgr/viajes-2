# Especificación — viajes-2 (mapa + itinerario + PWA)

Qué hace cada pieza y con qué umbrales. Los números de la última sección son
los tornillos: afloja o aprieta ahí y el resto del documento sigue valiendo.

## 1. Datos (`src/<viaje>/viaje.yaml`)

Un solo YAML es la fuente canónica; el HTML se genera 1:1 y un cambio de
ida y vuelta (`verify_roundtrip.py`) debe devolver el YAML byte-idéntico.
Los comentarios del YAML sobreviven cualquier edición (edición por spans de
texto crudo, nunca re-serialización).

### places
| campo | uso |
|---|---|
| `name` | nombre visible |
| `gps` | `lat,lon` — UN punto |
| `maps` | link de Google Maps (búsqueda por gps) |
| `description`, `info`, `hours`, `hours_source`, `image` | tarjeta |
| `poi: <Cluster>` | lo mete a la capa 📍 agrupado por cluster |
| `zone: 'lat,lon lat,lon …'` | polígono (calle/barrio): el mapa lo pinta como zona dorada en vez de punto. 3+ vértices. |

### transits
| campo | uso |
|---|---|
| `mode` | `walk` / `train` / `ferry`… (estilo de línea) |
| `coords` | polilínea `lat,lon …`; si falta y el paso la referencia → conector automático entre vecinos |
| `line`, `name_jp`, `chip`, `recognize`, `platform`, `reverse` | tarjeta de línea |
| `stations` | `[código, jp, romaji]` por parada; si nº de vértices == nº de estaciones, cada vértice es una parada |
| `stops` | posiciones de estación cuando `coords` ya es trazo denso OSM |
| `pois` | claves de places (espacio-separadas) pintadas junto al trazo («En el camino») |

### days / steps
- Paso concreto: `{location: clave}` o `{transit: clave}` o solo `title`
  (paso-nota). `time-from`, `fixed` (hora dura), `duration`.
- `hidden-summary: true`: caminata plegada (gris, duración calculada).
- `options:`/tiers (`Take`/`Ai`/`Shu`) con `steps:` anidados; la 1ª opción
  queda elegida por defecto. IDs extendidos `dN-rMM[-gG[-oO]-sS]`.
- Links inline `@[texto](clave)` abren la tarjeta de esa clave.

## 2. Reglas del itinerario
- Anclas de madrugada: el paso "Arriba/desayuno" lleva la location del
  HOTEL, nunca la del monumento del día.
- Sin teletransportes: pasos consecutivos a >150 m sin transit entre ellos
  son diagnóstico. Caminatas ocultas intercaladas donde ocurren.
- Duraciones derivadas: caminata sin horario recibe duración calculada del
  trazo (~4.5 km/h) y se muestra en gris.
- Días terminan ≤ 22:00; el desayuno arranca el día en el hotel.

## 3. UI del mapa
- **Disposición**: ≥ 821 px el panel es COLUMNA junto al mapa con divisor
  arrastrable (ancho persistente, doble-click restaura 380 px); < 821 px el
  panel flota (☰) y se cierra solo al elegir algo.
- **Casillas**: por fila; maestro del día tri-estado; capa apagada = la
  geometría desaparece; opciones no elegidas = fantasma (0.25); caminatas
  ocultas = trazo gordo tenue (0.12, +7 px).
- **Caminador (stepper)**: recorre pasos concretos; en un conjunto de
  opciones `›` se convierte en botones de elección (elegir entra, `‹`
  cancela); dentro de una opción hay «saltar a». El vuelo encuadra la
  geometría COMPLETA del paso con tope de zoom; repetir click sobre lo ya
  elegido acerca (+2). El hash sigue al caminador (`#@dN-rMM`).
- **Stepper de día** (abajo): `‹ día / día ›` — oculta el día anterior,
  activa el nuevo completo.
- **Pasos sin geometría**: transit sin coords → conector automático entre
  vecinos y encuadre de ambos; paso-nota (ni lugar ni transporte) → vuelo
  al ancla previa con zoom de calle.
- **Popups**: tarjeta completa; si excede 40 % de pantalla se colapsa con
  «Ver más»; tras el vuelo se des-recorta (paneo mínimo si quedó bajo el
  chip superior o los bordes). Abrir el selector de opciones cierra el
  popup. Click en geometría del mapa selecciona su fila.
- **Capa 📍 POIs**: maestro tri-estado + un checkbox por cluster (+ grupo
  «En el camino»: POIs a ≤ 100 m de caminatas). Punto dorado, o polígono
  dorado punteado si el place tiene `zone:`. Click → tarjeta. Estado
  persistente por cluster (localStorage).
- **Chip de deploy**: la página vigila su Action (repo público, sin auth):
  «🚀 publicando…» durante el run; «✨ hay versión nueva» si el último run
  exitoso ≠ su buildSha — al tocarlo pide el SW nuevo y recarga.
- **⚙️ config**: zoom de texto por niveles (en el mapa aplica al panel para
  no descuadrar Leaflet; en las demás páginas al body) y «Buscar
  actualización». Se cierra al tocar fuera.
- **Hash**: `#@fila` restaura día activo + vuelo + tarjeta; `#m-clave`
  abre la tarjeta; `#dN` día completo; hash viejo/inválido → estado por
  defecto (día 1), nunca página rota.

## 4. PWA / actualizaciones
- `sw.js` generado en el build: precache de TODO el release (imágenes
  incluidas — Cache Storage). Offline funciona el sitio entero; los tiles
  del mapa son caché de runtime (red primero, respaldo lo ya visto).
- Versión del caché = `GITHUB_SHA` (en CI) o hash del contenido real.
  El precache baja con `cache:'no-cache'` (Pages sirve `max-age=600`; sin
  esto una instalación podía mezclar assets viejos).
- Al activarse un SW nuevo la página se recarga sola UNA vez (solo si ya
  estaba controlada: la primera visita no recarga).

## 5. Edición en línea (sin servidor)
- `dev-github.js`: todo por la API de GitHub con un PAT fino por persona
  (instrucciones dentro del popup de login: Only select repositories →
  este repo; Contents / Pages / Pull requests: Read and write).
- Edita el YAML por spans de texto (paridad byte a byte con el dev-server
  opcional), commit por guardado, la Action publica.

## 6. Tornillos (afloja/aprieta aquí)
| perilla | valor | dónde |
|---|---|---|
| breakpoint columna/overlay | 821 px | mapa.css `@media`, mapa.js `matchMedia` |
| ancho panel por defecto / mín / máx | 380 px / 260 px / 70 vw | mapa.css `.panel` |
| tope de zoom del caminador | 16 (`ST_MAX_ZOOM`) | mapa.js |
| zoom al repetir click | +2 (máx 19) | mapa.js `showOnMap` |
| colapso de tarjeta | 40 % de pantalla | mapa.js `openCardPopup` |
| des-recorte de popup: márgenes | 96 px arriba · 54 px derecha · 44 px abajo · 10 px izq. | mapa.js `openCardPopup` |
| opacidades full/ghost/hidden | .85 / .25 / .12 (+7 px) | mapa.js `STYLE` |
| radio de enganche POI↔caminata | 100 m | scratch/attach_pois.py `RADIO` |
| dedupe POI investigado vs catálogo | 80 m | merge de POIs |
| zonas: recorte de nodos / margen | 120–350 m / 12–60 m por zona | scratch/zonas_poi.py `ZONAS` |
| umbral de teletransporte | 150 m | diagnostics del build |
| velocidad de caminata derivada | 4 km/h | render.py `walk_calc` (espejo en mapa.js `walkMins`) |
| lote y tolerancia del precache | 20 por lote, tolerante | build_mapa.gen_pwa |
| chequeo del chip de deploy | 90 s visible / pausado oculto | mapa.js `deployWatch` |
| niveles de zoom de texto | 1 / 1.12 / 1.25 / 1.4 | cfg.js `ZOOMS` |
