"""Pré-calcula tempos de caminhada e transporte público para uma cidade."""

import argparse
from pathlib import Path
import sys

import geopandas as gpd

from src.accessibility import destination_access, poi_access
from src.config import ROOT, load_catalog, load_city, load_destinations
from src.routing import make_network


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", required=True, help="ID da cidade")
    parser.add_argument("--cell-id", help="Calcula somente uma célula para inspeção")
    parser.add_argument("--output", type=Path, help="Pasta alternativa para inspeções")
    parser.add_argument("--input", type=Path, help="Pasta com grid.parquet e pois.parquet preparados")
    parser.add_argument("--part", choices=["all", "destinations", "pois"], default="all")
    parser.add_argument("--poi-batch-size", type=int, default=20)
    parser.add_argument("--max-memory", default="4G", help="Heap máximo do r5py")
    args = parser.parse_args()
    if args.cell_id and not args.output:
        parser.error("--cell-id exige --output para evitar resultados parciais na pasta final")
    if args.poi_batch_size < 1:
        parser.error("--poi-batch-size deve ser positivo")

    # O r5py lê seu limite de memória da linha de comando quando é importado.
    sys.argv = [sys.argv[0], "--max-memory", args.max_memory]
    city = load_city(args.city)
    source = args.input or ROOT / "data" / "processed" / args.city
    grid = gpd.read_parquet(source / "grid.parquet")
    pois = gpd.read_parquet(source / "pois.parquet")
    if args.cell_id:
        grid = grid.loc[grid.cell_id == args.cell_id]
        if grid.empty:
            raise ValueError(f"Célula não encontrada: {args.cell_id}")

    output = args.output or source
    output.mkdir(parents=True, exist_ok=True)
    network = make_network(city)
    date = city["reference_datetime"]

    if args.part in ("all", "destinations"):
        destinations = load_destinations(args.city)
        result = destination_access(network, grid, destinations, date)
        result.to_parquet(output / "destination_access.parquet", index=False)
        print(f"Destinos: {len(result)} tempos salvos em {output}")

    if args.part in ("all", "pois"):
        result = poi_access(
            network,
            grid,
            pois,
            load_catalog(),
            date,
            city["hex_grid"]["crs"],
            batch_size=args.poi_batch_size,
        )
        result.to_parquet(output / "poi_access.parquet", index=False)
        print(f"POIs: {len(result)} tempos salvos em {output}")


if __name__ == "__main__":
    main()
