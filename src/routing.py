"""Ponte pequena entre nossos dados e o r5py."""

from datetime import datetime, timedelta

import geopandas as gpd
import pandas as pd

from .config import ROOT


def make_network(city):
    """Carrega uma vez a rede de ruas e o GTFS da cidade."""
    import r5py

    return r5py.TransportNetwork(
        ROOT / city["osm_file"],
        [ROOT / city["gtfs_file"]],
    )


def grid_points(grid):
    """Usa o centro de cada hexágono como origem das viagens."""
    return gpd.GeoDataFrame(
        {"id": grid.cell_id.astype(str).to_numpy()},
        geometry=gpd.points_from_xy(grid.centroid_lon, grid.centroid_lat),
        crs=4326,
    )


def destination_points(destinations):
    """Converte destinos manuais em pontos aceitos pelo r5py."""
    return gpd.GeoDataFrame(
        {"id": [item["id"] for item in destinations]},
        geometry=gpd.points_from_xy(
            [item["longitude"] for item in destinations],
            [item["latitude"] for item in destinations],
        ),
        crs=4326,
    )


def travel_times(network, origins, destinations, modes, date, max_minutes):
    """Calcula minutos entre todos os pares de dois conjuntos pequenos."""
    import r5py

    if origins.empty or destinations.empty:
        return pd.DataFrame(columns=["from_id", "to_id", "travel_time"])
    matrix = r5py.TravelTimeMatrix(
        network,
        origins=origins,
        destinations=destinations,
        departure=datetime.fromisoformat(date),
        departure_time_window=timedelta(minutes=10),
        transport_modes=[getattr(r5py.TransportMode, mode) for mode in modes],
        max_time=timedelta(minutes=max_minutes),
    )
    return pd.DataFrame(matrix[["from_id", "to_id", "travel_time"]])
