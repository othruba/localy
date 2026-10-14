"""Leitura dos resultados pré-calculados, sem iniciar o r5py."""

import geopandas as gpd
import pandas as pd
import re

from .config import ROOT


def load_data(city_id):
    """Carrega malha e tempos necessários à análise de uma cidade."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", city_id):
        raise ValueError(f"ID de cidade inválido: {city_id!r}")
    folder = ROOT / "data" / "processed" / city_id
    paths = {
        "grid": folder / "grid.parquet",
        "pois": folder / "poi_access.parquet",
        "destinations": folder / "destination_access.parquet",
    }
    for path in paths.values():
        if not path.is_file():
            raise ValueError(f"Pré-cálculo ausente: {path}. Execute os scripts da Etapa 1.")

    grid = gpd.read_parquet(paths["grid"])
    pois = pd.read_parquet(paths["pois"])
    destinations = pd.read_parquet(paths["destinations"])
    required = (
        (grid, {"cell_id"}),
        (pois, {"cell_id", "poi_type", "nearest_walk_minutes"}),
        (destinations, {"cell_id", "destination_id", "best_minutes"}),
    )
    for table, columns in required:
        if not columns.issubset(table.columns):
            raise ValueError(f"Parquet sem colunas obrigatórias: {sorted(columns - set(table.columns))}")
    if grid.empty or grid.cell_id.isna().any() or grid.cell_id.duplicated().any():
        raise ValueError("A malha contém células vazias ou IDs repetidos")
    return grid, pois, destinations
