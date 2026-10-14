"""Leitura e validação simples dos arquivos YAML do projeto."""

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]


def read_yaml(path):
    """Carrega um YAML e informa qual arquivo falhou quando ele é inválido."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"Não foi possível ler {path}: {error}") from error


def load_city(city_id):
    """Carrega uma cidade sem permitir caminhos fora de config/cities."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", city_id):
        raise ValueError(f"ID de cidade inválido: {city_id!r}")

    path = ROOT / "config" / "cities" / f"{city_id}.yaml"
    city = read_yaml(path)
    if not isinstance(city, dict) or city.get("id") != city_id:
        raise ValueError(f"ID incorreto em {path}")

    for key in ("osm_file", "gtfs_file", "overture_file", "municipality_file"):
        file = ROOT / city[key]
        if not file.is_file():
            raise ValueError(f"Arquivo ausente para {city_id}: {file}")

    # O r5py usa apenas o nome do arquivo ao criar sua cópia em cache.
    # Nomes iguais em cidades distintas podem misturar OSM ou GTFS.
    for other_path in path.parent.glob("*.yaml"):
        if other_path == path:
            continue
        other = read_yaml(other_path)
        for key in ("osm_file", "gtfs_file"):
            if Path(other[key]).name == Path(city[key]).name and other[key] != city[key]:
                raise ValueError(
                    f"{key} de {city_id} e {other['id']} têm o mesmo nome de arquivo"
                )

    bbox = city["study_area_bbox"]
    if not (bbox["west"] < bbox["east"] and bbox["south"] < bbox["north"]):
        raise ValueError(f"Bounding box inválida em {path}")
    if city["hex_grid"]["radius_m"] <= 0:
        raise ValueError(f"Raio hexagonal inválido em {path}")
    return city


def load_catalog():
    """Carrega os tipos de POI aceitos pelo sistema."""
    catalog = read_yaml(ROOT / "config" / "poi_catalog.yaml")
    if not isinstance(catalog, dict) or not catalog:
        raise ValueError("O catálogo de POIs está vazio ou inválido")
    for poi_type, item in catalog.items():
        if not item.get("overture_categories"):
            raise ValueError(f"Categoria sem termos Overture: {poi_type}")
        if item.get("priority", "standard") not in ("standard", "secondary"):
            raise ValueError(f"Prioridade inválida para {poi_type}")
    return catalog


def load_overture_options():
    """Lê o filtro de confiança dos POIs brutos do Overture."""
    options = read_yaml(ROOT / "config" / "overture.yaml")
    if not isinstance(options, dict):
        raise ValueError("config/overture.yaml deve conter um mapa")

    threshold = options.get("min_confidence")
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not 0 <= threshold <= 1
    ):
        raise ValueError("min_confidence deve ser um número entre 0 e 1")
    if not isinstance(options.get("include_missing_confidence"), bool):
        raise ValueError("include_missing_confidence deve ser true ou false")
    return options


def load_destinations(city_id):
    """Retorna apenas os destinos completos da cidade solicitada."""
    destinations = read_yaml(ROOT / "config" / "destinations.yaml")
    if not isinstance(destinations, list):
        raise ValueError("config/destinations.yaml deve conter uma lista")

    selected = [item for item in destinations if item["city_id"] == city_id]
    ids = [item["id"] for item in selected]
    if len(ids) != len(set(ids)):
        raise ValueError(f"IDs de destino repetidos em {city_id}")
    if not selected:
        raise ValueError(f"Nenhum destino cadastrado em {city_id}")
    for item in selected:
        lat, lon = item.get("latitude"), item.get("longitude")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise ValueError(f"Coordenadas ausentes no destino {item['id']}")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"Coordenadas inválidas no destino {item['id']}")
    return selected
