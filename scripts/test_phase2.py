"""Testes locais da interpretação validada e da pontuação."""

import json
import unittest

import numpy as np
import pandas as pd
from pydantic import ValidationError

from src.config import load_catalog, load_destinations
from src.data import load_data
from src.llm import interpret_query
from src.schemas import QueryCriteria
from src.scoring import explain, score_cells, score_minutes, DESTINATION_CURVE, POI_CURVE


class FakeProvider:
    """Substitui o Gemini sem acesso à rede nos testes determinísticos."""

    def __init__(self, *answers):
        self.answers = iter(answers)
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return json.dumps(next(self.answers))


class PhaseTwoTests(unittest.TestCase):
    def test_curves_and_missing_route(self):
        self.assertEqual(
            score_minutes([0, 5, 10, 20, 30, np.nan], POI_CURVE).tolist(),
            [100, 100, 80, 50, 0, 0],
        )
        self.assertEqual(
            score_minutes([0, 15, 30, 45, 60, np.nan], DESTINATION_CURVE).tolist(),
            [100, 100, 80, 50, 0, 0],
        )

    def test_weighted_score_and_explanation(self):
        criteria = QueryCriteria.model_validate(
            {
                "city_id": "ponta_grossa",
                "destinations": [{"destination_id": "unicesumar_pg", "weight": 5}],
                "poi_preferences": [{"poi_type": "pharmacy", "weight": 3}],
            }
        )
        grid = pd.DataFrame({"cell_id": ["a", "b"]})
        pois = pd.DataFrame(
            {"cell_id": ["a", "b"], "poi_type": ["pharmacy"] * 2,
             "nearest_walk_minutes": [10, np.nan]}
        )
        destinations = pd.DataFrame(
            {"cell_id": ["a", "b"], "destination_id": ["unicesumar_pg"] * 2,
             "best_minutes": [15, 60]}
        )
        scores = score_cells(criteria, grid, pois, destinations)
        self.assertEqual(scores.score.tolist(), [92.5, 0])
        self.assertIn("Unicesumar", explain(
            criteria, load_destinations("ponta_grossa"), load_catalog()
        ))

    def test_required_unicesumar_query_with_precomputed_data(self):
        provider = FakeProvider({
            "city_id": "ponta_grossa",
            "destinations": [{"destination_id": "unicesumar_pg", "weight": 5}],
            "poi_preferences": [
                {"poi_type": "pharmacy", "weight": 4},
                {"poi_type": "hospital", "weight": 3},
            ],
        })
        criteria = interpret_query(
            "Vou estudar na Unicesumar e quero morar perto de serviços de saúde.",
            "ponta_grossa", provider,
        )
        grid, pois, destinations = load_data("ponta_grossa")
        scores = score_cells(criteria, grid, pois, destinations)
        self.assertEqual(criteria.destinations[0].destination_id, "unicesumar_pg")
        self.assertTrue((scores.score >= 0).all() and (scores.score <= 100).all())
        self.assertEqual(len(scores), len(grid))

    def test_required_utfpr_query(self):
        provider = FakeProvider({
            "city_id": "ponta_grossa",
            "destinations": [{"destination_id": "utfpr_pg", "weight": 5}],
            "poi_preferences": [
                {"poi_type": "supermarket", "weight": 4},
                {"poi_type": "gym", "weight": 3},
            ],
        })
        criteria = interpret_query(
            "Vou estudar na UTFPR. Quero mercado perto e faço academia.",
            "ponta_grossa", provider,
        )
        self.assertEqual(criteria.destinations[0].destination_id, "utfpr_pg")
        self.assertEqual({p.poi_type for p in criteria.poi_preferences}, {"supermarket", "gym"})

    def test_broad_arts_query_gets_complementary_places(self):
        provider = FakeProvider({
            "city_id": "ponta_grossa",
            "destinations": [],
            "poi_preferences": [{"poi_type": "museum", "weight": 5}],
        })
        criteria = interpret_query("Quero acesso a locais artísticos", "ponta_grossa", provider)
        weights = {item.poi_type: item.weight for item in criteria.poi_preferences}
        self.assertEqual(weights, {
            "museum": 5, "art_gallery": 4, "cultural_center": 4,
            "theater": 3, "library": 2, "bookstore": 1, "movie_theater": 1,
        })
        self.assertIn("livraria e cinema", provider.prompts[0])

    def test_specific_museum_request_stays_specific(self):
        provider = FakeProvider({
            "city_id": "ponta_grossa",
            "destinations": [],
            "poi_preferences": [{"poi_type": "museum", "weight": 5}],
        })
        criteria = interpret_query("Quero apenas museus por perto", "ponta_grossa", provider)
        self.assertEqual([item.poi_type for item in criteria.poi_preferences], ["museum"])

    def test_only_arts_still_expands_broad_theme(self):
        provider = FakeProvider({
            "city_id": "ponta_grossa",
            "destinations": [],
            "poi_preferences": [{"poi_type": "museum", "weight": 5}],
        })
        criteria = interpret_query("Quero apenas arte por perto", "ponta_grossa", provider)
        self.assertIn("art_gallery", {item.poi_type for item in criteria.poi_preferences})

    def test_arts_query_respects_explicit_exclusion(self):
        provider = FakeProvider({
            "city_id": "ponta_grossa",
            "destinations": [],
            "poi_preferences": [{"poi_type": "art_gallery", "weight": 5}],
        })
        criteria = interpret_query("Quero arte, mas sem cinema", "ponta_grossa", provider)
        self.assertNotIn("movie_theater", {item.poi_type for item in criteria.poi_preferences})

    def test_bad_choice_retries_only_once(self):
        invalid = {
            "city_id": "ponta_grossa",
            "destinations": [{"destination_id": "inventado", "weight": 5}],
            "poi_preferences": [],
        }
        valid = {
            "city_id": "ponta_grossa",
            "destinations": [{"destination_id": "utfpr_pg", "weight": 5}],
            "poi_preferences": [],
        }
        provider = FakeProvider(invalid, valid)
        criteria = interpret_query("Vou estudar na UTFPR", "ponta_grossa", provider)
        self.assertEqual(criteria.destinations[0].destination_id, "utfpr_pg")
        self.assertEqual(len(provider.prompts), 2)

    def test_invalid_weight_and_extra_fields(self):
        with self.assertRaises(ValidationError):
            QueryCriteria.model_validate({
                "city_id": "ponta_grossa", "destinations": [],
                "poi_preferences": [{"poi_type": "gym", "weight": 6}],
            })
        with self.assertRaises(ValidationError):
            QueryCriteria.model_validate({
                "city_id": "ponta_grossa", "destinations": [],
                "poi_preferences": [{"poi_type": "gym", "weight": 5, "latitude": 0}],
            })


if __name__ == "__main__":
    unittest.main()
