"""Testes do catálogo ampliado e do filtro de confiança Overture."""

import unittest
from unittest.mock import patch

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from src.config import ROOT, load_catalog, load_overture_options
from src.pois import load_pois


class OvertureTests(unittest.TestCase):
    def test_catalog_and_options(self):
        catalog = load_catalog()
        self.assertEqual(len(catalog), 33)
        self.assertEqual(
            sum(item.get("priority") == "secondary" for item in catalog.values()),
            23,
        )
        self.assertEqual(load_overture_options()["min_confidence"], 0.0)

    def test_low_confidence_and_closed_places(self):
        # Confiança mede existência; uma padaria pouco confiável ainda pode
        # ser selecionada quando o limiar é zero.
        source = gpd.GeoDataFrame(
            [
                {"id": "low", "confidence": 0.1, "operating_status": None},
                {"id": "high", "confidence": 0.9, "operating_status": None},
                {"id": "missing", "confidence": None, "operating_status": None},
                {"id": "zero", "confidence": 0.0, "operating_status": None},
                {"id": "closed", "confidence": 0.9,
                 "operating_status": "permanently_closed"},
            ],
            geometry=[Point(-50, -25)] * 5,
            crs="EPSG:4326",
        )
        source["taxonomy"] = [{"primary": "bakery", "hierarchy": ["bakery"]}] * 5
        source["basic_category"] = ["bakery"] * 5
        source["names"] = [{"primary": "Padaria"}] * 5
        city = {"id": "test", "overture_file": "unused.parquet"}
        catalog = {"bakery": load_catalog()["bakery"]}

        with patch("src.pois.gpd.read_parquet", return_value=source), patch(
            "src.pois.load_overture_options",
            return_value={"min_confidence": 0.0, "include_missing_confidence": True},
        ):
            pois = load_pois(city, catalog)
        self.assertEqual(set(pois.poi_id), {"low:bakery", "high:bakery", "missing:bakery"})
        self.assertTrue(pd.isna(pois.loc[pois.poi_id == "missing:bakery", "confidence"]).all())

        with patch("src.pois.gpd.read_parquet", return_value=source), patch(
            "src.pois.load_overture_options",
            return_value={"min_confidence": 0.5, "include_missing_confidence": False},
        ):
            pois = load_pois(city, catalog)
        self.assertEqual(pois.poi_id.tolist(), ["high:bakery"])

    def test_processed_data_covers_catalog(self):
        catalog = set(load_catalog())
        for city in ("ponta_grossa", "curitiba"):
            with self.subTest(city=city):
                folder = ROOT / "data" / "processed" / city
                grid = pd.read_parquet(folder / "grid.parquet")
                pois = pd.read_parquet(folder / "pois.parquet")
                access = pd.read_parquet(folder / "poi_access.parquet")
                self.assertEqual(set(pois.poi_type), catalog)
                self.assertIn("confidence", pois.columns)
                self.assertEqual(len(access), len(grid) * len(catalog))
                self.assertFalse(access.duplicated(["cell_id", "poi_type"]).any())
                self.assertTrue({"nearest_poi_id", "nearest_poi_name"}.issubset(access.columns))
                self.assertTrue(access.loc[access.nearest_walk_minutes.notna(), "nearest_poi_id"].notna().all())


if __name__ == "__main__":
    unittest.main()
