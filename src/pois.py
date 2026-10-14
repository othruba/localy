"""Normalização dos locais do Overture para o catálogo do projeto."""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from .config import ROOT, load_overture_options


def load_pois(city, catalog):
    """Seleciona apenas POIs pertencentes aos tipos cadastrados."""
    options = load_overture_options()
    source = gpd.read_parquet(ROOT / city["overture_file"])
    wanted = {
        poi_type: set(item["overture_categories"])
        for poi_type, item in catalog.items()
    }
    rows = []

    for place in source.itertuples(index=False):
        if place.geometry is None or place.geometry.is_empty:
            continue
        # Confidence é qualidade/existência do registro, não o peso dado pelo
        # usuário ao serviço. O limiar 0 preserva os de baixa confiança.
        confidence = place.confidence
        if pd.isna(confidence):
            if not options["include_missing_confidence"]:
                continue
            confidence = None
        elif confidence <= 0 or confidence < options["min_confidence"]:
            continue
        if place.operating_status == "permanently_closed":
            continue

        taxonomy = place.taxonomy if isinstance(place.taxonomy, dict) else {}
        hierarchy = taxonomy.get("hierarchy")
        tags = set(hierarchy) if hierarchy is not None else set()
        tags.add(taxonomy.get("primary"))
        # Overture permite categorias alternativas para um mesmo local.
        # Elas também contam quando correspondem a um tipo do catálogo.
        alternates = taxonomy.get("alternates")
        if alternates is not None:
            tags.update(alternates)
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
                    "confidence": confidence,
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
