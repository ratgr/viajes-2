# REGLAS — Japón 2026 (política del VIAJE, no de la herramienta)

Estas son las reglas de CONTENIDO de este viaje: cómo se escribe y se cuida
`viaje.yaml`. La herramienta (formato, build, mapa, PWA, edición) está en
[docs/SPEC.md](../../docs/SPEC.md) y no sabe nada de esto.

## Estructura del día

- **Anclas de madrugada**: el paso «Arriba / desayuno» lleva la `location`
  del HOTEL, nunca la del monumento del día. El desayuno arranca el día en el
  hotel.
- **Los días terminan ≤ 22:00.**
- **Las horas `fixed` (rojas) son las únicas duras**: vuelos, aperturas,
  reservas y el tour. Todo lo demás se estira o se cae sin culpa; los bloques
  de tarde son los que se sacrifican, nunca el ancla de la mañana.
- **Cadencias por ciudad**: Kioto madruga (día arranca 6:00 — el silencio se
  compra con sueño); Tokio abre tarde y ahí se descansa.

## Continuidad geométrica

- **Sin teletransportes**: pasos consecutivos separados a más de ~150 m sin
  un transit de por medio no se aceptan en este itinerario. Donde ocurren, se
  intercala una caminata oculta (`hidden-summary: true`) con su trazo. (El
  diagnóstico 🌀 del build dispara desde 100 m — tornillo del tool; la
  tolerancia editorial de este viaje es esa y se resuelve siempre con la
  caminata oculta, no ignorando el aviso.)
- **Duraciones de caminata: no escribirlas a mano.** El build las deriva del
  trazo (4 km/h) y avisa si el YAML dice otra cosa; se deja que la geometría
  mande.

## Física de 10 personas

- **+15 min de reagrupe en cada movimiento** (alguien siempre está en el
  baño), ya sumados en las horas del YAML.
- **Ninguna comida sentada dura menos de 1 h** (con 10 son 1 h 15 reales).
- **Regla de los 10**: mañana juntos en el ancla, tarde en subgrupos, cena
  juntos si sale natural.

## Reglas de Juan (las ★)

- **Salida EN PUNTO** los días de ancla dura (regla ★): la hora de salida del
  hotel es `fixed`.
- **Ventanas cerradas**: donde Juan fijó ventana (p.ej. Miyajima 2 h 15), esa
  duración no se renegocia en el YAML.
- **Filas tempranas como boleto**: USJ = formarse 6:45 en la reja (★); la
  fila temprana ES la entrada a Nintendo sin ticket cronometrado.
- **Check-in tomado desde la noche anterior** donde se pactó (Osaka), para
  entrar al cuarto en cuanto se llegue.
- El Keep de Juan es la referencia de detalle: cada conmutación lleva su
  línea, estación y transbordo — nivel Keep, y un poco más.

## Comidas (tiers y desayunos)

- Los tiers son **Take (barato) · Ai (medio) · Shu (caro)** — el orden de
  precio es fijo; juntas son el rango del momento. Las opciones son de donde
  el grupo ESTÁ a esa hora; las recomendaciones grandes (★) solo aparecen en
  noches libres, cuando sí pueden moverse a ellas; los barrios 🏮 son la
  opción de llegar y escoger ahí.
- Cada opción de comida lleva 3 alternativas clickeables con precio.
- **Desayunos**: 🏨 incluido en el hotel · ☕ comprarlo cerca · 🏪 konbini
  precomprado la noche anterior (los madrugones no perdonan el buffet).

## Convenciones del YAML de este viaje

- Los huecos de mediodía se dejan libres a propósito (peregrinar a un lugar
  específico); días de ~12 h con holgura: si un lugar gusta, se quedan.
- Punto de reunión explícito en las notas cuando el grupo se dispersa
  (p.ej. «el letrero de Glico a las 21:30»).
- `poi:` agrupa la guía por barrio-cluster (Dotonbori-Namba, Gion-Higashiyama,
  …); las calles/mercados llevan `zone:` (polígono) en vez de punto.
- Custodia de decisiones: lo reservado/pagado se anota en la nota del paso
  (confirmaciones, precios pp).
