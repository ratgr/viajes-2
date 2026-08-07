# -*- coding: utf-8 -*-
"""write_report.py — genera scratch/reporte_lineas.md (entregable QA)."""
import io

CONTENT = """# Reporte QA — Líneas de transporte y links "Abrir en Maps"

Fecha: 2026-08-07 · Fuente: `src/2026-Japon/viaje.yaml` (solo lectura) · Scripts: `scratch/verifica_lineas.py`, `scratch/fetch_osm.py`, `scratch/match_stations.py`, `scratch/check_maps.py`, `scratch/nominatim_check.py`, `scratch/analyze_maps.py` · Datos: Overpass API (16,585 nodos estación/parada cacheados en `scratch/osm_cache/`), navegador real vía puente de la extensión (cola `lineas-queue`).

## Parte 1 — Transits con `stations:` (71)

Método: (a) geometría — duplicados, retrocesos >500 m contra el rumbo general, giros >120°, ratio largo/recta; (b) cada estación (nombre jp) buscada en OSM y comparada contra el vértice que le corresponde (vértice i = estación i cuando `len(coords)==len(stations)`); (c) nombre de línea contra la línea real que conecta esas estaciones. Detalle completo en `scratch/geometria.json` y `scratch/station_match.json`.

### (a) Tabla por línea

| Transit(s) | Línea | Geometría | Estaciones vs OSM | Nombre |
|---|---|---|---|---|
| itami-monorail | Osaka Monorail | ok | 6/6 ≤300 m | ok |
| yamada-hankyu | Hankyu Senri | ok | 13/13 ≤300 m | ok (últimas 4 ya son Sakaisuji en through-service; rótulo aceptable) |
| metro-tanimachi / metro-sennichimae | Metro Tanimachi / Sennichimae | ok | todas ≤300 m | ok |
| metro-midosuji, d5-2, d8-3, d8-5 | Metro Midosuji | ok | todas ≤300 m | ok |
| **d5-12** | Metro Midosuji | **SIN coords** | existen (sin posición que validar) | ok |
| d5-3 / d5-11 | Shinkansen | ok (esquemático recto) | 4/4 (Shin-Kōbe y Okayama verificadas) | ok |
| **d5-4** | JR San-yō (local) | trazo denso ok | **`stops:` es copia exacta de `coords:` — no mapea las 10 estaciones** | ok |
| d5-5 / d5-6 | Ferry JR Miyajima | ok | extremos = muelles reales (los "far" del matcher son falsos positivos) | ok |
| **d5-7** | JR San-yō (local) | ok | 9/9 ≤300 m; omite 新白島 que sí lista d5-4 (el local para en ambos sentidos) | ok |
| d5-8 / d5-10 | Tranvía Hiroden | ok | 9+9 paradas reales, rutas 1/2/6 correctas | ok |
| d6-1, d7-1, d7-10, d8-1 | Metro Sakaisuji | ok | todas ≤300 m, códigos K correctos | ok |
| d6-2 / d6-7 | Metro Chūō (Osaka) | ok | 5/5 | ok |
| d6-3 / d6-6 | JR Osaka Loop | ok | 2/2 | ok |
| **d6-8** | JR Osaka Loop | **SIN coords** | 5 estaciones existen, orden real correcto | ok |
| **d6-4 / d6-5** | JR Yumesaki | ok | **安治川口 Ajikawaguchi 453 m fuera** | ok |
| d7-3 / d7-9 | Kintetsu Nara Line | ok | 7/7, códigos A02–A28 correctos | ok |
| **d8-6** | HARUKA Ltd. Express | ok (tramo 36.8 km recto = esquemático) | **大阪(うめきた) 407 m del nodo OSM** (andén Umekita ≈ 34.7040,135.4939) | ok (HARUKA sí para ahí desde 2023) |
| d8-7, d9-5, d10-1, d11-1, d12-1 | Metro Karasuma | ok | K10/K11 ≤300 m | ok |
| d9-3 | Bus urbano de Kioto | SIN coords | 7 paradas existen (ruta real 206/86) | ok (`mode: bus` correcto) |
| **d9-4** | Bus urbano de Kioto | SIN coords | 3 paradas existen (206/208) | **`mode: train` — es bus** |
| d10-2 / d10-3 / d10-8 | Hankyu Kioto/Arashiyama | ok | todas ≤300 m (transbordo Katsura correcto) | ok |
| **d10-6** | "Bus urbano de Kioto" | SIN coords | 2 paradas existen | **`mode: train` — es bus** · **operador equivocado: 愛宕寺前 solo lo sirve 京都バス (privado, rutas 62/72/92/94), NO 京都市バス** |
| d10-7 | Randen | ok | 13/13 en orden | ok (西院 "Sai" correcto en Randen) |
| d11-2 | JR Nara Line | ok | 3/3 | ok |
| **d11-4 / d11-5** | Bus urbano de Kioto | SIN coords | paradas existen (rutas reales 205 y 12) | **`mode: train` — son buses** |
| d11-6 | Metro Tōzai (Kioto) | ok | 5/5, T10–T14 correctos | ok |
| d12-2 | Shinkansen | ok | 5/5 (Nagoya, Shin-Yokohama verificadas) | ok |
| d12-3, d13-1, d14-1, d14-3, d15-1 | JR Chūō rápida | ok | todas ≤110 m | ok |
| d13-2 / d13-8 | Metro Ginza | ok | G13–G19 ≤300 m | ok |
| d13-6 | Tobu Skytree Line | ok | 2/2 | ok |
| d13-7 | Toei Asakusa | ok | A18–A20 ≤300 m | ok |
| **d13-12** | JR Yamanote | **SIN coords** | 13 existen, JY05–JY17 correctos | ok |
| **d15-2** | JR Keiyo | **último segmento 8.3 km, giro 157°** | **舞浜 Maihama 9,864 m fuera** | ok |
| d15-3 / d15-6 | JR Yamanote | ok | ≤300 m | ok |
| **d15-8** | JR Yamanote | **SIN coords** | existen | ok |
| **d16-1** | JR Shōnan-Shinjuku | **ROTA: 153.6 km dibujados vs ~50 reales; retrocesos de 33–48 km, zigzag violento** | **5 estaciones con coordenada basura** (detalle abajo) | ok (patrón del 普通 a Zushi correcto, incl. Nishi-Ōi) |
| d16-2 | Enoden | ok | EN15→EN12 ≤300 m | ok |
| **d16-4** | Yurikamome | **zigzag Big Sight→Ariake→Tennis-no-mori (retroceso ~850 m)** | **有明 Ariake (U12) 837 m fuera**; resto 14/15 exactas, orden U01–U15 correcto | ok |
| **d16-5** | "JR Chūō Line (rápida)" | trazo ok | 10/10 ≤300 m | **NOMBRE EQUIVOCADO: códigos JB = Chūō-Sōbu LOCAL (amarilla). La rápida (JC naranja, como está pintado) NO para en Akihabara/Suidōbashi/Iidabashi/Ichigaya/Shinanomachi/Sendagaya** |
| d17-1 | Metro Marunouchi | ok | M08–M16 ≤300 m | ok |
| d17-2 / d17-6 / d17-7 | Metro Hibiya | ok | ≤300 m | ok |
| **d18-1** | Airport Limousine Bus | SIN coords | Busta Shinjuku y Haneda T3 existen | **`mode: train` — es bus** |

### (b) Problemas concretos accionables

1. **d16-1 (Shōnan-Shinjuku) — la línea rota.** 5 vértices con coordenadas basura (caen en el este de Tokio / Ikebukuro). Correcciones (nodo OSM):
   - 武蔵小杉 Musashi-Kosugi: `35.619905,139.703567` → **`35.576624,139.660717`** (6.2 km fuera)
   - 横浜 Yokohama: `35.628527,139.742672` → **`35.466207,139.623195`** (21.0 km)
   - 東戸塚 Higashi-Totsuka: `35.695362,139.841711` → **`35.430361,139.556762`** (39.1 km)
   - 戸塚 Totsuka: `35.716965,139.694456` → **`35.401106,139.535079`** (38.0 km)
   - 大船 Ōfuna: `35.689501,139.848863` → **`35.354309,139.531432`** (47.1 km)
2. **d15-2 (Keiyo) — 舞浜 Maihama:** `35.616744,139.776085` → **`35.635631,139.882719`** (9.9 km fuera; por eso el trazo "regresa" hacia la bahía).
3. **d16-4 (Yurikamome) — 有明 Ariake U12:** `35.641511,139.796789` → **`35.634556,139.793256`** (837 m; elimina el zigzag).
4. **d5-4 — `stops:` inservible:** es copia byte a byte de `coords:` (53 pts para 10 estaciones). Sustituir por las 10 coordenadas de estación (los vértices de d5-7 sirven, más 新白島 ≈ `34.402083,132.457678`).
5. **d6-4 / d6-5 — 安治川口:** `34.669932,135.441938` → **`34.673624,135.444024`** (453 m).
6. **d8-6 — 大阪(うめきた):** `34.705027,135.498427` está ~407 m NE; andén Umekita ≈ **`34.7040,135.4939`** (menor).
7. **`mode:` equivocado (buses marcados como tren):** `d9-4`, `d10-6`, `d11-4`, `d11-5`, `d18-1`.
8. **d16-5 — renombrar:** es la **Chūō-Sōbu local (JB, amarilla #ffd400)**, no "JR Chūō (rápida)" (JC naranja #f15a22 como está). Cambiar line/name_jp/chip/color, o si quieren la rápida, quitar las estaciones intermedias.
9. **d10-6 — operador:** 愛宕寺前 (Otagi Nenbutsu-ji) solo lo sirve **京都バス** (verificado en relaciones de ruta OSM: 62/72/92/94 desde Arashiyama); no es bus municipal (ojo: el pase diario municipal no aplica ahí).
10. **d5-7 vs d5-4:** el regreso omite 新白島 Shin-Hakushima (el local para en ambos sentidos) — consistencia menor.
11. **10 transits sin `coords`:** d5-12, d6-8, d9-3, d9-4, d10-6, d11-4, d11-5, d13-12, d15-8, d18-1 — no se pueden dibujar ni validar posiciones.

Falsos positivos descartados: ratios largos de d12-3/d13-2/d17-6/d17-7 (curvatura real de esas líneas), "far" del ferry Miyajima (los extremos correctos son muelles, no estaciones de tren).

## Parte 2 — Links "Abrir en Maps" (navegador real vía puente)

Método: pestaña nueva en background (pinned, nunca activada), `setTabUrl` por cada `maps:` de cada place con `gps` (primero los 54 usados como `location` en days, luego POIs), espera 5 s, lectura de `h1` y del panel lateral (`[role="main"]`). 251/251 links navegados, espaciados 3.5–5 s. Sin captchas ni fallos de carga. Cross-check auxiliar: Nominatim (geocodificación por nombre) para los places de itinerario. Datos crudos: `lineas-queue/maps_results.jsonl` y `scratch/nominatim_results.jsonl`.

**Contadores: OK confirmado por nombre: 0 · Neutral (pin de coordenadas, localidad coherente): 250 · ERROR: 1**

Los links usan `query=lat,lon`, así que Google siempre muestra la tarjeta de coordenadas (h1 = coordenadas, nunca un nombre de lugar) — por el criterio acordado eso es "neutral": el pin cae exactamente donde dice `gps`. Como verificación adicional se extrajo la localidad del plus-code del panel (59 Kyoto, 55 Osaka, 78 wards de Tokio, 11 Nara, 13 Hiroshima/Hatsukaichi, 7 Hakone, 6 Kamakura, y 1 c/u Itami, Fujikawaguchiko, Fujinomiya, Urayasu, etc.) y TODAS son coherentes con la ciudad del lugar. Además Nominatim confirmó con <500 m unos 30 lugares clave del itinerario (Castillo de Osaka 13 m, Hōzen-ji 16 m, Itsukushima 79 m, Tōdai-ji 83 m, Kiyomizu 45 m, Tenryū-ji 86 m, Otagi 29 m, Sensō-ji 183 m, Meiji 175 m, Shibuya Sky 50 m, Torre de Tokio 17 m…).

### ERROR encontrado

| Place | Qué está mal | Sugerencia |
|---|---|---|
| **nabezo-shinjuku** ("Nabezo Shinjuku", POI de comida) | `gps: 35.668070,139.740806` cae en **Minato-ku (zona Akasaka/Toranomon)**, a ~3 km de Shinjuku | la sucursal Nabezō Shinjuku 3-chōme está en ≈ `35.69065,139.70495` (la de Nishi-Shinjuku en ≈ `35.69259,139.69867`); corregir gps y maps |

Notas neutrales (no son errores): `osaka-itami` resuelve "Itami, Hyogo" (correcto — el aeropuerto está en Itami); `yanaka-ginza` resuelve Taito (correcto — Yanaka no está en Ginza); `fushimi-inari` está pineado ~600 m monte arriba del honden (zona Okusha/senbon torii — parece intencional); `jardin-hamarikyu` y `haneda-t3` pinean dentro del recinto correcto.

## Estado de la infraestructura QA

- Driver `lineas-qa` detenido con `{"id":9999,"method":"stop"}`; la pestaña pinned de Google Maps quedó abierta en background (según lo pedido, no se cerró ni se activó).
- Para re-correr: `python scratch/verifica_lineas.py` · `python scratch/match_stations.py` (usa `scratch/osm_cache/`) · `python scratch/check_maps.py <queue-dir> <yaml>` · `python scratch/analyze_maps.py <maps_results.jsonl>`.
"""

with io.open(r"d:\dev\viajes\japon\viajes-2\scratch\reporte_lineas.md", "w", encoding="utf-8", newline="\n") as f:
    f.write(CONTENT)
print("written", len(CONTENT), "chars")
