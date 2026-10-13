"""Normalização dos locais do Overture para o catálogo do projeto."""

import geopandas as gpd
from shapely.geometry import Point

from .config import ROOT


def load_pois(city, catalog):
    """Seleciona apenas POIs pertencentes aos tipos cadastrados."""
    source = gpd.read_parquet(ROOT / city["overture_file"])
    wanted = {
        poi_type: set(item["overture_categories"])
        for poi_type, item in catalog.items()
    }
    rows = []

    for place in source.itertuples(index=False):
        if place.geometry is None or place.geometry.is_empty:
            continue

        taxonomy = place.taxonomy if isinstance(place.taxonomy, dict) else {}
        hierarchy = taxonomy.get("hierarchy")
        tags = set(hierarchy) if hierarchy is not None else set()
        tags.add(taxonomy.get("primary"))
        tags.add(place.basic_category)
        name = place.names.get("primary") if isinstance(place.names, dict) else None
        point = place.geometry
        if not isinstance(point, Point):
            point = point.representative_point()

        for poi_type, categories in wanted.items():
            if categories.isdisjoint(tags):
                continue
            rows.append(
                {
                    "poi_id": f"{place.id}:{poi_type}",
                    "poi_type": poi_type,
                    "name": name,
                    "geometry": point,
                }
            )

    if not rows:
        raise ValueError(f"Nenhum POI reconhecido em {city['id']}")
    pois = gpd.GeoDataFrame(rows, geometry="geometry", crs=source.crs).to_crs(4326)
    pois = pois.drop_duplicates(subset=["poi_id"])

    # Categoria vazia geraria uma coluna inteira de tempos ausentes.
    missing = set(catalog) - set(pois.poi_type)
    if missing:
        raise ValueError(f"Categorias sem POIs em {city['id']}: {sorted(missing)}")
    return pois
