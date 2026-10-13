"""Geração da malha hexagonal usada como origem dos cálculos."""

import math

import geopandas as gpd
from shapely.geometry import Point, Polygon, box
from shapely.prepared import prep

from .config import ROOT


def make_grid(city):
    """Cria hexágonos cujos centros estão na área de estudo e no município."""
    crs = city["hex_grid"]["crs"]
    radius = city["hex_grid"]["radius_m"]
    bbox = city["study_area_bbox"]

    # Os índices partem da origem fixa do CRS. Assim, o ID não muda quando
    # a área de estudo é ampliada sem alterar raio ou CRS.
    width = math.sqrt(3) * radius
    row_step = 1.5 * radius
    study = gpd.GeoSeries(
        [box(bbox["west"], bbox["south"], bbox["east"], bbox["north"])],
        crs=4326,
    ).to_crs(crs).iloc[0]
    municipality = gpd.read_file(ROOT / city["municipality_file"]).to_crs(crs)
    area = prep(study.intersection(municipality.geometry.union_all()))
    west, south, east, north = study.bounds

    ids, centers, polygons = [], [], []
    for row in range(math.floor(south / row_step), math.ceil(north / row_step) + 1):
        y = row * row_step
        offset = width / 2 if row % 2 else 0
        first = math.floor((west - offset) / width)
        last = math.ceil((east - offset) / width)
        for column in range(first, last + 1):
            x = column * width + offset
            center = Point(x, y)
            if not area.covers(center):
                continue

            vertices = [
                (
                    x + radius * math.cos(math.radians(30 + 60 * side)),
                    y + radius * math.sin(math.radians(30 + 60 * side)),
                )
                for side in range(6)
            ]
            ids.append(f"{city['id']}_{row}_{column}")
            centers.append(center)
            polygons.append(Polygon(vertices))

    if not ids:
        raise ValueError(f"A malha de {city['id']} ficou vazia")

    points = gpd.GeoSeries(centers, crs=crs).to_crs(4326)
    grid = gpd.GeoDataFrame(
        {
            "cell_id": ids,
            "centroid_lon": points.x.to_numpy(),
            "centroid_lat": points.y.to_numpy(),
        },
        geometry=polygons,
        crs=crs,
    ).to_crs(4326)
    return grid
