# scratch

Scripts útiles que NO son parte del pipeline principal (build/): migraciones,
resincronizaciones y herramientas de una sola vez. Pueden importar `common`
del build agregando `build/` al path (ver migrate_yaml.py).

- `osm_rail_geometry.py` — trae geometría real de OSM (Overpass + camino más corto en el grafo de vías); se parametriza editando claves/bbox. Los scripts de migración ya aplicados se retiraron (viven en el historial).
- `migrate_yaml.py` — HISTÓRICO, no correr: este repo es el canónico.
