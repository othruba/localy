"""Formato aceito para os critérios extraídos da pergunta."""

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class DestinationChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination_id: str
    weight: StrictInt = Field(ge=1, le=5)


class PoiChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    poi_type: str
    weight: StrictInt = Field(ge=1, le=5)


class QueryCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city_id: str
    destinations: list[DestinationChoice]
    poi_preferences: list[PoiChoice]

    @model_validator(mode="after")
    def check_items(self):
        """Impede consultas vazias e critérios repetidos."""
        if not self.destinations and not self.poi_preferences:
            raise ValueError("Informe pelo menos um destino ou tipo de POI")

        destination_ids = [item.destination_id for item in self.destinations]
        poi_types = [item.poi_type for item in self.poi_preferences]
        if len(destination_ids) != len(set(destination_ids)):
            raise ValueError("Há destinos repetidos")
        if len(poi_types) != len(set(poi_types)):
            raise ValueError("Há tipos de POI repetidos")
        return self


def validate_choices(criteria, city_id, destinations, catalog):
    """Confere se todos os IDs retornados existem na cidade e no catálogo."""
    if criteria.city_id != city_id:
        raise ValueError(f"Cidade incorreta: {criteria.city_id!r}")

    destination_ids = {item["id"] for item in destinations}
    for choice in criteria.destinations:
        if choice.destination_id not in destination_ids:
            raise ValueError(f"Destino não cadastrado: {choice.destination_id!r}")

    for choice in criteria.poi_preferences:
        if choice.poi_type not in catalog:
            raise ValueError(f"Tipo de POI não cadastrado: {choice.poi_type!r}")
    return criteria
