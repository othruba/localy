"""Pré-cálculo dos tempos entre hexágonos, destinos e tipos de POI."""

import geopandas as gpd
import pandas as pd

from .routing import destination_points, grid_points, travel_times


def destination_access(network, grid, destinations, date, batch_size=100):
    """Calcula caminhada e transporte público para cada destino cadastrado."""
    origins = grid_points(grid)
    targets = destination_points(destinations)
    batches = []

    for start in range(0, len(origins), batch_size):
        group = origins.iloc[start : start + batch_size]
        walk = travel_times(network, group, targets, ["WALK"], date, 60)
        transit = travel_times(network, group, targets, ["TRANSIT"], date, 60)
        # O R5 pode devolver valores acima do limite solicitado; deixamos
        # esses pares sem tempo porque a pontuação já é zero após 60 min.
        walk["travel_time"] = walk.travel_time.where(walk.travel_time <= 60)
        transit["travel_time"] = transit.travel_time.where(transit.travel_time <= 60)
        walk = walk.rename(columns={"travel_time": "walk_minutes"})
        transit = transit.rename(columns={"travel_time": "transit_minutes"})
        times = walk.merge(transit, on=["from_id", "to_id"], how="outer")
        times["best_minutes"] = times[["walk_minutes", "transit_minutes"]].min(axis=1)
        batches.append(times)
        end = min(start + batch_size, len(origins))
        if end == len(origins) or (start // batch_size + 1) % 10 == 0:
            print(f"Destinos: {end}/{len(origins)} células", flush=True)

    result = pd.concat(batches, ignore_index=True)
    return result.rename(columns={"from_id": "cell_id", "to_id": "destination_id"})[
        ["cell_id", "destination_id", "walk_minutes", "transit_minutes", "best_minutes"]
    ]


def poi_access(network, grid, pois, poi_types, date, crs, batch_size=20):
    """Busca o POI mais próximo a pé para cada tipo, até 30 minutos.

    Com caminhada a 3,6 km/h, nenhuma rota de até 30 minutos pode terminar
    a mais de 1,8 km em linha reta. A busca usa 2 km por segurança.
    """
    origins = grid_points(grid)
    targets = gpd.GeoDataFrame(
        {"id": pois.poi_id.to_numpy()},
        geometry=pois.geometry.to_numpy(),
        crs=pois.crs,
    )
    projected_origins = origins.to_crs(crs)
    projected_targets = targets.to_crs(projected_origins.crs)
    index = projected_targets.sindex
    types = pois[["poi_id", "poi_type"]].rename(columns={"poi_id": "to_id"})
    batches = []

    for start in range(0, len(origins), batch_size):
        end = min(start + batch_size, len(origins))
        group = origins.iloc[start:end]
        # Cada lote só contém POIs que poderiam ser alcançados no limite de
        # 30 minutos por alguma origem do lote.
        nearby = set()
        for point in projected_origins.geometry.iloc[start:end]:
            nearby.update(index.query(point.buffer(2000), predicate="intersects"))

        all_rows = pd.MultiIndex.from_product(
            [group.id.to_list(), list(poi_types)], names=["cell_id", "poi_type"]
        ).to_frame(index=False)
        if nearby:
            selected = targets.iloc[sorted(nearby)]
            matrix = travel_times(network, group, selected, ["WALK"], date, 30)
            matrix["travel_time"] = matrix.travel_time.where(matrix.travel_time <= 30)
            matrix = matrix.merge(types, on="to_id", how="left")
            nearest = (
                matrix.groupby(["from_id", "poi_type"], as_index=False)["travel_time"]
                .min()
                .rename(columns={"from_id": "cell_id", "travel_time": "nearest_walk_minutes"})
            )
            all_rows = all_rows.merge(nearest, on=["cell_id", "poi_type"], how="left")
        else:
            all_rows["nearest_walk_minutes"] = float("nan")
        batches.append(all_rows)
        if end == len(origins) or (start // batch_size + 1) % 10 == 0:
            print(f"POIs: {end}/{len(origins)} células", flush=True)

    return pd.concat(batches, ignore_index=True)[
        ["cell_id", "poi_type", "nearest_walk_minutes"]
    ]
