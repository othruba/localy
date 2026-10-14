"""Prepara o mapa PyDeck a partir das pontuações já calculadas."""

from html import escape
import math

import pydeck as pdk


def score_color(score):
    """Usa tons translúcidos para preservar a leitura do mapa-base."""
    score = max(0, min(100, float(score)))
    low, high = (172, 218, 215), (18, 126, 119)
    return [round(a + (b - a) * score / 100) for a, b in zip(low, high)] + [115]


def select_scores(scores, percent=10):
    """Deixa no mapa só a faixa superior de células com pontuação positiva."""
    if not 0 < percent <= 100:
        raise ValueError("Percentual visível deve ficar entre 0 e 100")
    positive = scores.loc[scores.score > 0]
    count = math.ceil(len(scores) * percent / 100)
    return positive.sort_values(["score", "cell_id"], ascending=[False, True]).head(count)


def format_minutes(value, limit):
    """Mostra tempos ausentes como rota não encontrada dentro do limite."""
    if value is None or not math.isfinite(float(value)):
        return f"não encontrado em até {limit} min"
    return f"{float(value):.0f} min"


def make_details(row, criteria, destinations, catalog):
    """Cria os detalhes de uma célula na mesma ordem dos critérios escolhidos."""
    names = {item["id"]: item["name"] for item in destinations}
    details = []
    for choice in criteria.destinations:
        minutes = row[f"destination_{choice.destination_id}_minutes"]
        details.append(f"{names[choice.destination_id]}: {format_minutes(minutes, 60)}")
    for choice in criteria.poi_preferences:
        minutes = row[f"poi_{choice.poi_type}_minutes"]
        name = row.get(f"poi_{choice.poi_type}_name")
        if isinstance(name, str) and name.strip():
            details.append(
                f"{catalog[choice.poi_type]['label']}: {name} · {format_minutes(minutes, 30)}"
            )
        else:
            details.append(f"{catalog[choice.poi_type]['label']}: {format_minutes(minutes, 30)}")
    return details


def make_map(scores, criteria, city, destinations, catalog, percent=10):
    """Desenha hexágonos e destinos no mesmo mapa, com tooltip por célula."""
    # O PyDeck espera coordenadas longitude/latitude, independentemente do CRS
    # usado na geração da malha hexagonal.
    scores = select_scores(scores, percent).to_crs("EPSG:4326")
    hexagons = []
    for _, row in scores.iterrows():
        if row.geometry.geom_type != "Polygon":
            raise ValueError(f"Geometria inesperada em {row.cell_id}")
        details = make_details(row, criteria, destinations, catalog)
        tooltip = f"<b>Pontuação: {row.score:.1f}/100</b>"
        tooltip += "".join(f"<br>{escape(item)}" for item in details)
        hexagons.append(
            {
                "cell_id": row.cell_id,
                "score": float(row.score),
                "polygon": [[lon, lat] for lon, lat in row.geometry.exterior.coords],
                "color": score_color(row.score),
                "tooltip": tooltip,
                "details": details,
            }
        )

    selected_ids = {choice.destination_id for choice in criteria.destinations}
    points = [
        {
            "name": item["name"],
            "position": [item["longitude"], item["latitude"]],
            "tooltip": f"<b>{escape(item['name'])}</b><br>Destino selecionado",
        }
        for item in destinations
        if item["id"] in selected_ids
    ]

    layers = [
        pdk.Layer(
            "PolygonLayer",
            data=hexagons,
            id="hexagons",
            get_polygon="polygon",
            get_fill_color="color",
            stroked=False,
            pickable=True,
            auto_highlight=True,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            data=points,
            id="destinations",
            get_position="position",
            get_fill_color=[34, 54, 105, 230],
            get_line_color=[255, 255, 255, 240],
            get_radius=100,
            radius_min_pixels=6,
            radius_max_pixels=13,
            line_width_min_pixels=2,
            stroked=True,
            pickable=True,
        ),
    ]
    return pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            latitude=city["map"]["latitude"],
            longitude=city["map"]["longitude"],
            zoom=city["map"]["zoom"],
            pitch=0,
        ),
        map_style=pdk.map_styles.CARTO_LIGHT,
        tooltip={"html": "{tooltip}", "style": {"color": "#243044"}},
    )
