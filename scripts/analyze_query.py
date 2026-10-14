"""Interpreta uma consulta e calcula scores sem iniciar a interface ou o r5py."""

import argparse
from pathlib import Path

from src.config import load_catalog, load_destinations
from src.data import load_data
from src.llm import interpret_query
from src.scoring import explain, score_cells


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", required=True, help="ID da cidade")
    parser.add_argument("--query", required=True, help="Descrição do que você procura")
    parser.add_argument("--output", type=Path, help="GeoParquet opcional com todos os scores")
    args = parser.parse_args()

    # Confere os pré-cálculos antes de fazer uma chamada à API.
    grid, pois, destinations = load_data(args.city)
    criteria = interpret_query(args.query, args.city)
    scores = score_cells(criteria, grid, pois, destinations)

    print(criteria.model_dump_json(indent=2))
    print(explain(criteria, load_destinations(args.city), load_catalog()))
    print("\nCinco células com maior pontuação:")
    print(scores.nlargest(5, "score")[["cell_id", "score"]].to_string(index=False))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        scores.to_parquet(args.output)
        print(f"Scores salvos em {args.output}")


if __name__ == "__main__":
    main()
