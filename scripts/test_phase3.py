"""Testes da interface e do mapa sem consumir a API do Gemini."""

import json
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.config import ROOT, load_catalog, load_city, load_destinations
from src.data import load_data
from src.map import make_map, score_color, select_scores
from src.schemas import QueryCriteria
from src.scoring import score_cells


ANSWER = {
    "city_id": "ponta_grossa",
    "destinations": [{"destination_id": "utfpr_pg", "weight": 5}],
    "poi_preferences": [
        {"poi_type": "supermarket", "weight": 4},
        {"poi_type": "gym", "weight": 3},
    ],
}


class FakeProvider:
    def __init__(self, answer=ANSWER):
        self.calls = 0
        self.answer = answer

    def generate(self, prompt):
        self.calls += 1
        return json.dumps(self.answer)


class PhaseThreeTests(unittest.TestCase):
    def test_score_colors(self):
        self.assertEqual(score_color(0), [172, 218, 215, 115])
        self.assertEqual(score_color(100), [18, 126, 119, 115])

    def test_map_contains_scores_and_times(self):
        criteria = QueryCriteria.model_validate(ANSWER)
        grid, pois, destinations_access = load_data("ponta_grossa")
        scores = score_cells(criteria, grid, pois, destinations_access)
        deck = make_map(
            scores,
            criteria,
            load_city("ponta_grossa"),
            load_destinations("ponta_grossa"),
            load_catalog(),
        )
        self.assertEqual(len(deck.layers), 2)
        self.assertEqual(len(deck.layers[0].data), len(select_scores(scores)))
        self.assertLess(len(deck.layers[0].data), len(grid))
        self.assertEqual(len(deck.layers[1].data), 1)
        self.assertIn("Pontuação", deck.layers[0].data[0]["tooltip"])
        self.assertIn("UTFPR", deck.layers[0].data[0]["tooltip"])
        self.assertIn("Supermercado", deck.layers[0].data[0]["tooltip"])
        self.assertIn(" · ", deck.layers[0].data[0]["tooltip"])
        self.assertEqual(len(json.loads(deck.to_json())["layers"]), 2)

    def test_initial_screen(self):
        app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "ponta_grossa")
        self.assertIn("Curitiba", app.selectbox[0].options)
        self.assertEqual(len(app.get("deck_gl_json_chart")), 0)

    def test_query_shows_one_map_and_sidebar(self):
        provider = FakeProvider()
        with patch("src.llm.GeminiProvider", return_value=provider):
            app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
            app.text_area[0].set_value(
                "Vou estudar na UTFPR. Quero mercado perto e faço academia."
            )
            app.button[0].click().run(timeout=30)
            # Uma interação posterior com o mapa não deve repetir a chamada à IA.
            app.run(timeout=30)
            app.slider[0].set_value(5).run(timeout=30)
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(len(app.get("deck_gl_json_chart")), 1)
        self.assertEqual(app.session_state["analysis"]["criteria"].city_id, "ponta_grossa")
        self.assertIn("Mobilidade", [item.value for item in app.sidebar.subheader])

    def test_curitiba_uses_precomputed_data(self):
        provider = FakeProvider({
            "city_id": "curitiba",
            "destinations": [{"destination_id": "ufpr_jardim_botanico", "weight": 5}],
            "poi_preferences": [{"poi_type": "museum", "weight": 4}],
        })
        with patch("src.llm.GeminiProvider", return_value=provider):
            app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
            app.selectbox[0].set_value("curitiba")
            app.text_area[0].set_value("Quero morar perto da UFPR e de museus")
            app.button[0].click().run(timeout=30)
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(len(app.get("deck_gl_json_chart")), 1)


if __name__ == "__main__":
    unittest.main()
