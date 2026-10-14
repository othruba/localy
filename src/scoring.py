"""Pontuação determinística das células e explicação dos critérios."""

import numpy as np


POI_CURVE = ([0, 5, 10, 20, 30], [100, 100, 80, 50, 0])
DESTINATION_CURVE = ([0, 15, 30, 45, 60], [100, 100, 80, 50, 0])


def score_minutes(minutes, curve):
    """Interpola a curva; falta de rota equivale a zero ponto."""
    values = np.asarray(minutes, dtype=float)
    scores = np.interp(values, *curve)
    return np.where(np.isfinite(values), scores, 0)


def get_minutes(table, field, selected_id, value_column, cell_ids):
    """Alinha os tempos de um critério à ordem da malha."""
    rows = table.loc[table[field] == selected_id, ["cell_id", value_column]]
    if rows.empty:
        raise ValueError(f"Não há pré-cálculo para {selected_id!r}; execute a Etapa 1 novamente")
    if rows.cell_id.duplicated().any():
        raise ValueError(f"Células repetidas no pré-cálculo de {selected_id!r}")
    if set(rows.cell_id) != set(cell_ids):
        raise ValueError(f"Pré-cálculo incompleto para {selected_id!r}; execute a Etapa 1 novamente")
    return rows.set_index("cell_id")[value_column].reindex(cell_ids).to_numpy(dtype=float)


def score_cells(criteria, grid, poi_access, destination_access):
    """Aplica média ponderada aos tempos já calculados, sem usar IA ou rotas."""
    result = grid.copy()
    cell_ids = result.cell_id
    total = np.zeros(len(result), dtype=float)
    total_weight = 0

    for choice in criteria.destinations:
        minutes = get_minutes(
            destination_access,
            "destination_id",
            choice.destination_id,
            "best_minutes",
            cell_ids,
        )
        result[f"destination_{choice.destination_id}_minutes"] = minutes
        total += score_minutes(minutes, DESTINATION_CURVE) * choice.weight
        total_weight += choice.weight

    for choice in criteria.poi_preferences:
        minutes = get_minutes(
            poi_access, "poi_type", choice.poi_type, "nearest_walk_minutes", cell_ids
        )
        result[f"poi_{choice.poi_type}_minutes"] = minutes
        if "nearest_poi_name" in poi_access:
            names = poi_access.loc[
                poi_access.poi_type == choice.poi_type, ["cell_id", "nearest_poi_name"]
            ].set_index("cell_id")["nearest_poi_name"]
            result[f"poi_{choice.poi_type}_name"] = names.reindex(cell_ids).to_numpy()
        total += score_minutes(minutes, POI_CURVE) * choice.weight
        total_weight += choice.weight

    if not total_weight:
        raise ValueError("A consulta não contém critérios")
    result["score"] = np.round(np.clip(total / total_weight, 0, 100), 1)
    return result


def explain(criteria, destinations, catalog):
    """Descreve escolhas e regra de mobilidade sem nova chamada de IA."""
    names = {item["id"]: item["name"] for item in destinations}
    lines = ["Consulta interpretada:"]

    if criteria.destinations:
        lines.append("Destinos principais:")
        for choice in criteria.destinations:
            lines.append(f"- {names[choice.destination_id]} — importância {choice.weight}/5")

    if criteria.poi_preferences:
        lines.append("Serviços considerados:")
        for choice in criteria.poi_preferences:
            label = catalog[choice.poi_type]["label"]
            lines.append(f"- {label} — importância {choice.weight}/5")

    lines.append(
        "A avaliação usa caminhada até serviços e o menor tempo entre caminhada "
        "e transporte público até cada destino principal."
    )
    return "\n".join(lines)
