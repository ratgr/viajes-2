# -*- coding: utf-8 -*-
"""Utilidades compartidas de los scripts de build: raíz del repo, viaje activo
(argumento o el único en src/), y su config.yaml."""
import os
import sys

import yaml

BUILD = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BUILD)
ASSETS = os.path.join(BUILD, "assets")


def resolve_trip(argv):
    """nombre del viaje: argv[1], o el único directorio dentro de src/."""
    src_root = os.path.join(ROOT, "src")
    trips = sorted(d for d in os.listdir(src_root)
                   if os.path.isdir(os.path.join(src_root, d)))
    if len(argv) > 1:
        if argv[1] not in trips:
            sys.exit(f"viaje desconocido: {argv[1]} (hay: {', '.join(trips)})")
        return argv[1]
    if len(trips) == 1:
        return trips[0]
    sys.exit(f"especifica el viaje: {', '.join(trips)}")


def trip_paths(trip):
    """(src_dir, pages_dir, config) del viaje."""
    src = os.path.join(ROOT, "src", trip)
    pages = os.path.join(ROOT, "pages", trip)
    cfg_path = os.path.join(src, "config.yaml")
    cfg = {}
    if os.path.exists(cfg_path):
        cfg = yaml.safe_load(open(cfg_path, encoding="utf-8")) or {}
    return src, pages, cfg
