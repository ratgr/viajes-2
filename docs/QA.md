# QA — viajes-2 (mapa + itinerario + PWA)

Contraparte de verificación de [SPEC.md](SPEC.md). Cada historia se ejecuta a
mano sobre la página desplegada (ver **Marco** al final). Los umbrales citados
(821 px, 260 px/70 vw, 40 %, etc.) salen de la tabla de tornillos del SPEC:
si un tornillo cambia, ajusta aquí el número y la historia sigue valiendo.

---

## Historia 1 — Carga inicial

**Preparación**: navegador limpio (o localStorage borrado para el origen),
URL sin hash: `…/2026-Japon/mapa.html`.

**Pasos**:
1. Abrir la página.
2. No tocar nada durante ~2 s.

**Esperado**:
- El día 1 llega abierto en la barra, con TODAS sus casillas marcadas y su
  maestro en ✔ pleno.
- El mapa encuadra la geometría del viaje (bbox del build) y luego ajusta a
  las capas del día 1; sin popup abierto.
- El caminador (abajo) muestra el primer paso concreto del día 1; `‹` del
  caminador deshabilitado.
- El stepper de día muestra el día 1; `‹ día` deshabilitado.
- La URL sigue SIN hash (la carga por defecto no escribe hash).

**Bordes**:
- Recargar 3 veces seguidas: mismo estado siempre (nada acumula).
- Abrir con `#` a secas o `#basura` → mismo estado por defecto, cero errores
  en consola.
- GEO vacío (día hipotético sin build completo): el mapa cae al setView de
  respaldo de Japón, la página no truena.

## Historia 2 — Disposición: columna vs overlay y cruce en vivo

**Preparación**: ventana de escritorio con ancho > 900 px.

**Pasos**:
1. Cargar la página con ancho ≥ 821 px → el panel es COLUMNA junto al mapa,
   con splitter visible; no hay botón ☰.
2. REDIMENSIONAR la ventana en vivo hasta < 821 px.
3. Volver a estirar a ≥ 821 px.
4. En modo angosto, abrir el panel con ☰ y elegir una fila.

**Esperado**:
- ≥ 821 px: panel en columna, mapa ocupa el resto, zoom de Leaflet abajo a
  la derecha.
- Al cruzar a < 821 px: el panel pasa a sobrepuesto que abre/cierra ☰; el
  mapa recupera el ancho completo (invalidateSize: sin tiles grises).
- Al volver a ≥ 821 px: columna de nuevo, con el ancho que tenía.
- En angosto, elegir algo (fila, opción, grupo) CIERRA el panel solo para
  dejar ver el popup.

**Bordes**:
- Cruzar 821 con un popup abierto: el popup sobrevive y el des-recorte lo
  reacomoda si quedó fuera.
- Cruzar 821 con el selector de opciones del caminador abierto: los botones
  siguen usables y no tapan el mapa roto.
- Rotar un teléfono (portrait↔landscape) equivale al cruce: verificarlo.
- Pantalla táctil: ☰, casillas y caminador responden al primer tap (sin
  doble-tap fantasma).
- **Fichas de pestañas vs caminador (teléfono)**: en < 821 px la barra de
  pestañas (Itinerario/Mapa/Info/…) debe quedar en UNA sola fila deslizable
  horizontalmente (sin scrollbar visible) y NUNCA envolverse en 2+ renglones
  tapando el chip del caminador que vive justo debajo (top 36 px). Verificar
  en ~360 px de ancho: chip del paso legible y tocable, fichas deslizables
  con el dedo, y el selector de opciones (Take/Ai/Shu) tampoco queda
  cubierto por las fichas.

## Historia 3 — Splitter (divisor arrastrable)

**Preparación**: escritorio ≥ 821 px, sin `mapa-panel-w` en localStorage.

**Pasos**:
1. Verificar ancho inicial del panel: 380 px.
2. Arrastrar el splitter a la derecha y a la izquierda.
3. Soltar en un ancho cualquiera (p.ej. ~500 px) y RECARGAR.
4. Doble click en el splitter.
5. Recargar de nuevo.

**Esperado**:
- El arrastre mueve panel y splitter juntos; el mapa se reacomoda en vivo
  (sin franjas grises).
- Límites duros: no baja de 260 px ni sube de 70 % del ancho de ventana.
- Tras recargar (paso 3) el ancho elegido persiste (localStorage).
- Doble click restaura 380 px Y borra la persistencia: la recarga del paso 5
  vuelve a 380 px.

**Bordes**:
- Arrastrar hasta pegar el puntero al borde derecho de la pantalla: clava en
  70 vw, no más.
- Arrastrar y soltar FUERA de la ventana (pointer capture): no queda
  "pegado" arrastrando al volver.
- Achicar la ventana después de dejar un panel ancho: el límite 70 vw es del
  momento del arrastre; verificar que la página sigue usable.

## Historia 4 — Casillas: fila, maestro tri-estado, fantasma, ocultas

**Preparación**: día 1 activo por defecto (carga limpia).

**Pasos**:
1. Desmarcar la casilla de UNA fila con lugar.
2. Observar el maestro del día.
3. Desmarcar todas las filas del día.
4. Marcar el maestro del día.
5. En un conjunto de opciones, verificar la geometría de las opciones NO
   elegidas.
6. Pulsar el ojo 👁 del conjunto (pasa a 🙈).
7. Localizar una caminata oculta (`hidden-summary`, fila gris plegada) y
   mirar su trazo.

**Esperado**:
- (1) Su marcador desaparece del mapa; la numeración del día se recalcula
  (los lugares plenos se renumeran sin hueco).
- (2) Maestro pasa a ▬ (indeterminate). (3) Maestro queda vacío.
- (4) TODO el día se enciende, incluidos sub-pasos de opciones aunque estén
  plegadas; maestro en ✔ sin indeterminate.
- (5) Con 👁: opciones no elegidas en fantasma (opacidad ~0.25, insignias
  atenuadas). (6) Con 🙈: van en trazo GORDO tenue (~0.12, +7 px) — visibles
  pero claramente "apagadas", no borradas.
- (7) La caminata oculta marcada dibuja línea punteada de caminata; si su
  opción no está elegida, aplica el peor estado (regla de anidados).

**Esperado extra**: cualquier cambio de casilla refresca capas con un
pequeño debounce (~120 ms); no parpadea todo el mapa.

**Bordes**:
- Marcar/desmarcar MUY rápido varias casillas: el estado final del mapa
  coincide con las casillas (el debounce no pierde el último cambio).
- Una clave repetida en dos filas (mismo lugar dos días): apagar una fila no
  borra la capa si la otra sigue prendida; manda el mejor estado (full >
  ghost > hidden).
- Opciones anidadas (tier dentro de plan): el fantasma respeta TODOS los
  niveles ancestros.

## Historia 5 — Caminador: recorrido completo con ›

**Preparación**: carga limpia, día 1.

**Pasos**:
1. Pulsar `›` repetidamente hasta el final del viaje (ver también
   «Recorrido automatizado»).

**Esperado**:
- Cada `›` avanza al siguiente paso CONCRETO de la ruta elegida; el chip
  central cambia de texto en cada paso.
- Cada paso: la fila se selecciona y se centra en la barra, vuela el mapa
  encuadrando la geometría COMPLETA del paso con tope de zoom 16, abre su
  tarjeta, y el hash pasa a `#@dN-rMM…`.
- En el PRIMER paso `‹` está deshabilitado; en el ÚLTIMO, `›` deshabilitado.
- Al cruzar de día: el día anterior se apaga y pliega; el nuevo se prende
  completo y abre; el stepper de día se actualiza.

**Bordes**:
- Doble click rápido en `›`: no se salta pasos de más ni encola dos vuelos
  que dejen la cámara a medias; el chip y el hash quedan consistentes con la
  fila seleccionada.
- `‹` desde el primer paso de un día regresa al último del día anterior con
  el mismo cruce limpio.
- Paso cuyo transit no tiene coords: encuadra sus dos anclas vecinas
  (conector automático) con tope 16 y abre tarjeta en el centro.
- Paso-nota (ni lugar ni transporte): vuela al ANCLA PREVIA con zoom de
  calle (no encuadra ambos vecinos: evitar el vacío de 50 km).

## Historia 6 — Caminador: modo elección en options

**Preparación**: navegar con `›` hasta la fila anterior a un conjunto de
opciones (plan o tiers).

**Pasos**:
1. Pulsar `›` al llegar al conjunto.
2. Pulsar `‹` sin elegir.
3. Pulsar `›` de nuevo y ELEGIR una opción.
4. Dentro de la opción, abrir «saltar a ▾» y saltar a otra opción.
5. Plegar «saltar a» con su toggle.

**Esperado**:
- (1) `›` se convierte en botones de elección (tiers: columnas por grupo con
  cabecera fija y color del tier); el botón `›` se oculta; si había popup
  abierto, SE CIERRA (no queda debajo de los botones). El hash no cambia aún.
- (2) `‹` en modo elección es CANCELAR: vuelve al chip normal sin moverse;
  `‹` disponible aunque no haya paso anterior.
- (3) Elegir marca el radio de esa opción, entra a su PRIMER paso concreto,
  vuela y abre tarjeta; la opción elegida queda resaltada (`chosen`) y las
  demás pasan a fantasma en el mapa.
- (4) «saltar a» lista TODAS las opciones del conjunto; saltar a otra opción
  la marca y arranca en su primer paso.
- (5) El pliegue de «saltar a» persiste mientras se navega dentro del
  conjunto.

**Bordes**:
- Opción PLANA (sin sub-pasos concretos): elegirla marca el radio y muestra
  su referencia en el mapa — no debe quedarse "sin hacer nada".
- `›` dentro del mismo conjunto no re-abre el selector (solo al ENTRAR desde
  fuera).
- Con la primera opción elegida por defecto (build), la geometría default es
  la de esa opción.

## Historia 7 — Caminador: click en fila, click en geometría, repetir click

**Preparación**: día con varias filas y capas visibles.

**Pasos**:
1. Click en una fila (fuera de casilla y links).
2. Click en la MISMA fila otra vez.
3. Click en una línea de transporte dibujada en el mapa.
4. Click en la misma línea otra vez.
5. Click en una fila de OTRO día (sin usar el stepper de día).

**Esperado**:
- (1) La fila se selecciona, el caminador se posiciona ahí (el chip cambia),
  vuela + tarjeta + hash `#@fila`.
- (2) Repetir click sobre lo ya elegido ACERCA el zoom (+2, máx 19; lugares
  nunca por debajo de 16).
- (3) Click en geometría abre su tarjeta Y selecciona la fila
  correspondiente en la barra (si la clave sale en varios días, gana la del
  día abierto); el caminador se sincroniza.
- (4) Segundo click en la misma geometría acerca el zoom.
- (5) La fila de otro día se selecciona y muestra SIN activar ese día (las
  casillas del día activo no cambian); el stepper de día sigue mostrando el
  día ACTIVO.

**Bordes**:
- Click en fila-contenedor sin clave propia: encuadra TODO su subárbol con
  halo, sin popup individual.
- Las líneas punteadas finas se atinan gracias a la línea de impacto
  invisible (~16 px): probar clicks ligeramente fuera del trazo.
- Click en el caret ▼ de una fila NO selecciona ni vuela (solo pliega).

## Historia 8 — Stepper de día (barra inferior)

**Preparación**: carga limpia (día 1 activo).

**Pasos**:
1. Pulsar `día ›`.
2. Recorrer con `día ›` hasta el último día.
3. Regresar con `‹ día` hasta el primero.

**Esperado**:
- Cada `día ›`: se APAGA y pliega el día anterior, se prende el nuevo
  completo, el caminador salta a su primer paso concreto y el hash sigue.
- En el día 1 `‹ día` deshabilitado; en el último, `día ›` deshabilitado.
- La etiqueta central muestra el título del día activo.

**Bordes**:
- Día sin pasos concretos: queda activo y navegable (hash `#dN`), el
  stepper NO se atora.
- Alternar `día ›` / `‹ día` rápido: el estado de casillas termina con UN
  solo día prendido.
- Tras seleccionar una fila de otro día con click (historia 7 paso 5), el
  stepper de día opera sobre el día ACTIVO, no el de la fila clickeada.

## Historia 9 — Capa 📍 POIs

**Preparación**: carga limpia; localizar el control «📍 Puntos de interés
(N)» bajo la barra de días.

**Pasos**:
1. Abrir el desglose con ▸.
2. Marcar UN cluster.
3. Marcar el maestro 📍.
4. Desmarcar un cluster con el maestro lleno.
5. Recargar la página.

**Esperado**:
- (2) Aparecen solo los puntos dorados de ese cluster; tooltip con nombre al
  pasar; click abre su tarjeta y selecciona la fila si existe.
- (3) Maestro prende TODOS los clusters. (4) Maestro pasa a ▬ tri-estado;
  con cero clusters queda vacío.
- (5) El estado por cluster PERSISTE (localStorage `mapa-poi-*`).
- Existe el grupo «En el camino» con los POIs a ≤ 100 m de caminatas; se
  comporta como un cluster más.

**Bordes**:
- El caret ▸/▾ solo pliega el desglose, no cambia casillas.
- Un POI presente en un cluster Y en «En el camino»: prenderlo por ambos
  lados no duplica visualmente de forma molesta ni truena al apagar uno.
- Borrar localStorage y recargar: todos los clusters apagados (default).

## Historia 10 — Polígonos de zona (calles/barrios)

**Preparación**: cluster que contenga un place con `zone:` (p.ej. una calle
comercial o barrio).

**Pasos**:
1. Prender su cluster (o su caminata si viene como POI «En el camino»).
2. Pasar el puntero por el polígono.
3. Click dentro del polígono.

**Esperado**:
- Se dibuja como POLÍGONO dorado punteado con relleno tenue (no un punto).
- El tooltip es PEGAJOSO (sigue al puntero dentro de la zona).
- Click abre la tarjeta del place y selecciona su fila si existe.

**Bordes**:
- Zoom lejano: el polígono sigue visible (aunque chico) y clickeable.
- Un place con `zone:` que TAMBIÉN aparece como paso del itinerario: ambos
  representaciones coexisten sin pelearse el click.

## Historia 11 — Popups: des-recorte, «Ver más», cierre por selector

**Preparación**: escritorio con panel en columna; una tarjeta ALTA (mucha
descripción + imagen) y una tarjeta cerca del borde del mapa.

**Pasos**:
1. Abrir la tarjeta alta.
2. Pulsar «Ver más ↓» y luego «Ver menos ↑».
3. Abrir una tarjeta de un punto que caiga pegado al panel (izquierda) tras
   el vuelo.
4. Abrir una de un punto que caiga arriba, bajo el chip/toolbar.
5. Con un popup abierto, avanzar `›` hasta entrar a un selector de opciones.

**Esperado**:
- (1) Si la tarjeta excede 40 % de la pantalla llega COLAPSADA con botón
  «Ver más ↓». (2) Expande con scroll interno topado; el botón alterna.
- (3–4) Tras terminar la animación (~0.6 s) el mapa panea LO MÍNIMO para
  destapar el popup: márgenes ≈ 96 px arriba, 54 px derecha, 44 px abajo,
  10 px junto al panel.
- (5) Abrir el selector de opciones CIERRA el popup.

**Bordes**:
- El des-recorte no dispara si el usuario ya cerró el popup antes de los
  620 ms.
- Expandir/colapsar «Ver más» no re-renderiza la tarjeta (imágenes no
  parpadean, el botón no desaparece).
- Lugar usado en varios días: la tarjeta lista una pieza por día, con la del
  día abierto (o la fila clickeada) expandida.
- Clicks dentro del popup no burbujean al mapa (no cierran el propio popup).

## Historia 12 — Hash y restauración

**Preparación**: conocer un id de fila real (p.ej. `d3-r05`) y una clave de
modal real (p.ej. `fushimi-inari`).

**Pasos**:
1. Navegar con el caminador y copiar la URL (`#@dN-rMM`).
2. Pegarla en una pestaña nueva.
3. Abrir `#m-<clave>` en pestaña nueva.
4. Abrir `#dN` en pestaña nueva.
5. Abrir `#@d99-r99` (fila inexistente) y `#m-no-existe`.
6. Con la app abierta, editar y recargar (F5) sobre un hash de fila.

**Esperado**:
- (2) Restaura EXACTO: día activo prendido, fila seleccionada y centrada,
  vuelo al paso y tarjeta abierta; el encuadre de arranque NO pisa el vuelo
  del restore.
- (3) Abre la tarjeta de esa clave (con vuelo si tiene geometría).
- (4) Ese día completo activo, caminador en su primer paso concreto.
- (5) Hash viejo/inválido → estado por defecto (día 1), sin errores, nunca
  página rota ni en blanco.
- (6) La recarga vuelve al mismo punto (es el mecanismo post-rebuild).

**Bordes**:
- `#m-clave@fila`: tarjeta + fila a la vez.
- La visibilidad de casillas NO viaja en el hash: tras recargar, las
  casillas vuelven al default del día activo.
- Hash de un `#dN` de día inexistente → default.
- Si itinerario.js abrió su dialog por el mismo hash, el mapa manda y el
  dialog se cierra.

## Historia 13 — PWA: modo avión

**Preparación**: visitar la página desplegada UNA vez con red (dejar que el
SW precachee); navegar un poco por el mapa (algunos tiles vistos).

**Pasos**:
1. Activar modo avión.
2. Recargar la página.
3. Navegar: caminador, días, tarjetas con imagen, itinerario.

**Esperado**:
- TODO el sitio funciona offline (HTML, JS, CSS, imágenes de tarjetas:
  precache completo del release).
- Tiles del mapa: solo lo ya visitado (caché de runtime, red primero); las
  zonas nuevas quedan grises SIN romper la app.
- El chip de deploy simplemente no aparece (la API de GitHub falla en
  silencio).

**Bordes**:
- Primera visita SIN llegar a completar el precache → offline parcial: la
  página no debe quedar a medias irrecuperable al volver la red.
- Volver de modo avión: los tiles nuevos cargan al mover el mapa, sin
  recargar.

## Historia 14 — PWA: flujo de actualización

**Preparación**: página abierta en la versión N; hacer un deploy (commit a
main → Action de Pages).

**Pasos**:
1. Con la Action corriendo, esperar el siguiente chequeo del chip (o cambiar
   de pestaña y volver: visibilitychange fuerza un check).
2. Esperar a que la Action termine.
3. Tocar el chip «✨ hay versión nueva».
4. Aparte: primera visita de un navegador limpio.

**Esperado**:
- (1) Chip «🚀 publicando cambios…» visible mientras el run no está
  `completed`; NO clickeable para recargar.
- (2) Al terminar con éxito y `head_sha ≠ buildSha` del build servido:
  «✨ hay versión nueva — toca para recargar».
- (3) Muestra «⏳ actualizando…», pide el SW nuevo ANTES de recargar y
  recarga; tras la recarga (auto-recarga extra al activarse el SW si ya
  estaba controlada) la página es la versión nueva y el chip desaparece.
- (4) La PRIMERA visita nunca se recarga sola (SW recién instalado, página
  no controlada).

**Bordes**:
- Pestaña oculta: el chequeo se pausa (no gasta rate limit); al volver a la
  pestaña chequea de inmediato.
- Run fallido: el chip NO ofrece versión nueva.
- API de GitHub caída o rate-limited: el chip simplemente no aparece /
  desaparece, cero errores visibles (ver historia 18).
- SW viejo terco: una recarga doble manual (ver **Marco**) resuelve; el chip
  no debe entrar en bucle de recargas.

## Historia 15 — ⚙️ Configuración

**Preparación**: página cargada, cualquier estado.

**Pasos**:
1. Tocar ⚙️ → se abre el menú.
2. Tocar «🔎 Texto más grande» varias veces (ciclo 100 → 112 → 125 → 140 →
   100 %).
3. Con el texto al 140 %, hacer clicks precisos en el mapa (marcadores,
   líneas, popups).
4. Recargar.
5. Abrir ⚙️ y tocar FUERA del menú.
6. Tocar «🔄 Buscar actualización».

**Esperado**:
- (2) El zoom aplica al PANEL, no al body — la etiqueta muestra el nivel.
- (3) Los clicks de Leaflet siguen cayendo EXACTOS donde apunta el cursor
  (zoomear el body descuadraría el mapa: no debe pasar).
- (4) El nivel de texto persiste (localStorage `cfg-zoom`).
- (5) Tocar fuera cierra el menú; los listeners del mapa no se tragan ese
  click ni el menú dispara acciones del mapa.
- (6) «⏳ Actualizando…» → pide update del SW y recarga; sin SW igual
  recarga sin error.

**Bordes**:
- ⚙️ visible y funcional en overlay (< 821 px) y con popup abierto.
- En páginas SIN panel (itinerario), el zoom aplica al body completo.

## Historia 16 — Edición en línea (modo GitHub, sin server)

**Preparación**: página desplegada en Pages (sin dev server); usuario
colaborador del repo, SIN token guardado (`gh-pat` borrado).

**Pasos**:
1. Verificar que existe el botón 🛠 (build con GEO.edit).
2. Tocarlo: aparece el popup de PAT con instrucciones.
3. Seguir las instrucciones (Only select repositories → este repo;
   Contents/Pages/Pull requests RW), pegar el token, «Entrar».
4. Activar el modo dev y clickear una fila.
5. Editar el YAML del paso y «Guardar».
6. Probar «+ después» (insertar) y «▲ subir» (mover).
7. «Rebuild» / esperar la Action y observar el chip.

**Esperado**:
- (2) El popup trae los 4 pasos con el link directo a crear el token; token
  inválido → «✗ …» y NO se guarda; Cancelar cierra sin guardar.
- (4) En modo dev el click en fila abre el cajón con identidad
  (`fila dN-rMM = days[N-1].steps[M-1]`), claves y horario.
- (5) Cada Guardar es UN COMMIT por contents API; mensaje `dev: paso …
  (web)`; comentarios del YAML intactos (edición por spans).
- (6) Insertar/mover re-apunta el cajón al número nuevo de la fila; al
  aceptar el rebuild, la recarga vuelve posicionada en el paso (`#@fila`).
- (7) El deploy se ve DESDE la página: chip 🚀 mientras corre, ✨ al
  terminar; tocar recarga a la versión nueva.

**Bordes**:
- Sitio detrás del último commit: la primera edición avisa «el sitio va
  detrás… espera el deploy (~90 s) y recarga», no comitea a ciegas.
- Ids renumerados sin deploy: «fila sin span» — esperar el deploy.
- Referencia nueva sin catálogo: flujo de plantilla (lugar/caminata/tren…)
  y «Guardar referencia» la agrega al final del catálogo.
- Dos ediciones seguidas: los spans se corren por el delta de líneas; el
  segundo Guardar cae en el lugar correcto.
- Token de OTRO repo o sin permisos: error legible en el cajón, no commit.

## Historia 17 — Filas sin geometría (∅ y conectores)

**Preparación**: localizar en la barra una fila-nota (solo `title`) y un
transit referenciado SIN coords.

**Pasos**:
1. Revisar el ícono de esas filas en la barra.
2. Marcar la casilla del transit sin coords.
3. Llegar a ambas con el caminador.

**Esperado**:
- (1) Las filas sin geometría llevan el indicador ∅ (nota o transit sin
  coords) — se distinguen de las filas con capa.
- (2) El transit sin coords dibuja el CONECTOR automático: punteado recto
  gris entre el último punto del paso previo y el primero del siguiente
  (mismo día, misma rama de opciones), con una flecha al centro; respeta
  full/ghost/hidden con sus propios estilos.
- (3) Caminador: transit sin coords encuadra ambos vecinos; nota vuela al
  ancla previa (ver historia 5, bordes).

**Bordes**:
- Transit sin coords al INICIO o FIN de un día (sin vecino de un lado): no
  hay conector y no truena.
- Vecinos en otra rama de opciones NO sirven de ancla (el conector no debe
  brincar a la opción de al lado).

## Historia 18 — Casos borde generales

**Preparación**: página desplegada, estado cualquiera.

**Pasos y esperado** (uno por viñeta):
- **Doble click rápido en ›**: sin saltos dobles ni cámara a medias
  (historia 5); chip/hash/fila consistentes.
- **Redimensionar con el selector de opciones abierto**: los botones se
  reacomodan, elegir sigue funcionando (historia 2).
- **Popup del último paso**: en el último paso del viaje el popup abre bien
  y `›` queda deshabilitado sin comerse el popup.
- **Día sin geometría**: activarlo no truena; fitToLayers no vuela a (0,0);
  el stepper de día sigue navegable.
- **localStorage borrado a MITAD de sesión** (DevTools → Clear storage sin
  recargar): la sesión viva sigue; la próxima recarga simplemente vuelve a
  defaults (panel 380, POIs off, texto 100 %).
- **API de GitHub caída** (bloquear api.github.com en DevTools): el chip de
  deploy desaparece / no aparece; edición en línea da error legible; nada
  más se degrada.
- **Táctil vs mouse**: arrastre del splitter con dedo (pointer events),
  tooltips pegajosos de zonas en táctil (tap muestra tarjeta directo),
  tap en casillas pequeñas, pinch-zoom del mapa no dispara clicks.
- **Rueda/scroll sobre el caminador y la barra de día**: no zoomea el mapa
  (los eventos se tragan).
- **Cambiar de pestaña y volver**: check inmediato del chip; el mapa no
  pierde estado.

---

## Recorrido automatizado

La regresión más valiosa es mecánica: un script (consola o Playwright)
que pulsa `›` en bucle por los ~300 pasos del viaje, y en cada iteración
verifica que el texto del chip central (`.st-cur`) CAMBIÓ respecto al paso
anterior y que no hubo errores de consola. Si el chip se repite dos veces
seguidas (fuera del modo elección, donde hay que elegir la primera opción y
seguir), hay un paso atorado — así se han cazado las regresiones del
caminador (opciones planas, cruces de día, pasos sin geometría). Variante:
el mismo bucle hacia atrás con `‹`, y una pasada por `día ›` verificando la
etiqueta del stepper de día.

## Marco

El QA se corre sobre la página DESPLEGADA:
`https://ratgr.github.io/viajes-2/2026-Japon/mapa.html`

Antes de empezar: esperar a que la Action del deploy termine (chip 🚀 → nada
o ✨) y, si el service worker venía viejo, hacer UNA recarga doble (recargar,
dejar que el SW nuevo se active — la página se auto-recarga una vez — y
verificar que `buildSha` ya es el actual). Nunca reportar un fallo de una
sesión que estaba sirviendo el build anterior.
