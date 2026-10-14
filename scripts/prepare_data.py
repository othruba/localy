"""Gera a malha e normaliza os POIs de uma cidade."""

import argparse
from pathlib import Path

from src.config import ROOT, load_catalog, load_city
from src.grid import make_grid
from src.pois import load_pois


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", required=True, help="ID da cidade, como ponta_grossa")
    parser.add_argument("--output", type=Path, help="Pasta alternativa para preparar sem substituir os dados atuais")
    args = parser.parse_args()

    city = load_city(args.city)
    grid = make_grid(city)
    pois = load_pois(city, load_catalog())

    output = args.output or ROOT / "data" / "processed" / args.city
    output.mkdir(parents=True, exist_ok=True)
    grid.to_parquet(output / "grid.parquet")
    pois.to_parquet(output / "pois.parquet")
    print(f"{args.city}: {len(grid)} hexágonos e {len(pois)} POIs normalizados")
    print(pois.poi_type.value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
