"""Tests for garmin_mcp.tools.body."""

from datetime import date
from unittest.mock import MagicMock, patch

from garmin_mcp.tools.body import get_body_composition, get_weight_trend


# --- get_weight_trend ---

class TestGetWeightTrend:

    @patch("garmin_mcp.tools.body.date")
    def test_returns_weight_entries(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 30)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_weigh_ins.return_value = {
            "dailyWeightSummaries": [
                {"calendarDate": "2025-01-29", "weight": 80000, "bmi": 24.5},
                {"calendarDate": "2025-01-30", "weight": 79500, "bmi": 24.3},
            ]
        }

        result = get_weight_trend(api, days=30)

        assert len(result["entries"]) == 2
        assert result["entries"][0]["weight_kg"] == 80.0
        assert result["entries"][1]["weight_kg"] == 79.5

    @patch("garmin_mcp.tools.body.date")
    def test_converts_grams_to_kg(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 30)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_weigh_ins.return_value = {
            "dailyWeightSummaries": [{"calendarDate": "2025-01-30", "weight": 75000}]
        }

        result = get_weight_trend(api, days=30)

        assert result["entries"][0]["weight_kg"] == 75.0

    @patch("garmin_mcp.tools.body.date")
    def test_includes_lbs_conversion(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 30)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_weigh_ins.return_value = {
            "dailyWeightSummaries": [{"calendarDate": "2025-01-30", "weight": 100000}]
        }

        result = get_weight_trend(api, days=30)

        assert result["entries"][0]["weight_lbs"] == pytest_approx_220()

    @patch("garmin_mcp.tools.body.date")
    def test_summary_stats_calculated(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 30)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_weigh_ins.return_value = {
            "dailyWeightSummaries": [
                {"calendarDate": "2025-01-28", "weight": 82000},
                {"calendarDate": "2025-01-29", "weight": 81000},
                {"calendarDate": "2025-01-30", "weight": 80000},
            ]
        }

        result = get_weight_trend(api, days=30)
        summary = result["summary"]

        assert summary["latest_kg"] == 80.0
        assert summary["min_kg"] == 80.0
        assert summary["max_kg"] == 82.0
        assert summary["change_kg"] == -2.0

    @patch("garmin_mcp.tools.body.date")
    def test_returns_empty_on_api_exception(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 30)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_weigh_ins.side_effect = Exception("API error")

        result = get_weight_trend(api, days=30)

        assert result["entries"] == []
        assert result["summary"] is None

    @patch("garmin_mcp.tools.body.date")
    def test_days_requested_in_response(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 30)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_weigh_ins.return_value = {"dailyWeightSummaries": []}

        result = get_weight_trend(api, days=14)

        assert result["days_requested"] == 14


def pytest_approx_220():
    """100kg in lbs is 220.5."""
    return 220.5


# --- get_body_composition ---

class TestGetBodyComposition:

    @patch("garmin_mcp.tools.body.date")
    def test_returns_composition_entries(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 30)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_body_composition.return_value = {
            "totalAverage": {
                "weight": 80000,
                "bmi": 24.5,
                "bodyFat": 18.5,
                "muscleMass": 62000,
            },
            "dateWeightList": [
                {
                    "calendarDate": "2025-01-30",
                    "weight": 80000,
                    "bmi": 24.5,
                    "bodyFat": 18.5,
                    "bodyWater": 60.0,
                    "boneMass": 3000,
                    "muscleMass": 62000,
                    "visceralFat": 8,
                    "metabolicAge": 32,
                }
            ],
        }

        result = get_body_composition(api, days=30)

        assert len(result["entries"]) == 1
        entry = result["entries"][0]
        assert entry["weight_kg"] == 80.0
        assert entry["body_fat_pct"] == 18.5
        assert entry["muscle_mass_kg"] == 62.0
        assert entry["bone_mass_kg"] == 3.0
        assert entry["visceral_fat"] == 8
        assert entry["metabolic_age"] == 32

    @patch("garmin_mcp.tools.body.date")
    def test_period_average_included(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 30)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_body_composition.return_value = {
            "totalAverage": {
                "weight": 80000,
                "bmi": 24.5,
                "bodyFat": 18.0,
                "muscleMass": 63000,
            },
            "dateWeightList": [],
        }

        result = get_body_composition(api, days=30)

        assert result["period_average"]["weight_kg"] == 80.0
        assert result["period_average"]["body_fat_pct"] == 18.0
        assert result["period_average"]["muscle_mass_kg"] == 63.0

    @patch("garmin_mcp.tools.body.date")
    def test_returns_empty_on_api_exception(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 30)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_body_composition.side_effect = Exception("API error")

        result = get_body_composition(api, days=30)

        assert result["entries"] == []

    @patch("garmin_mcp.tools.body.date")
    def test_handles_none_response(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 30)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_body_composition.return_value = None

        result = get_body_composition(api, days=30)

        assert result["entries"] == []

    @patch("garmin_mcp.tools.body.date")
    def test_days_requested_in_response(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 30)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_body_composition.return_value = {"totalAverage": {}, "dateWeightList": []}

        result = get_body_composition(api, days=7)

        assert result["days_requested"] == 7
