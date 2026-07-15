from __future__ import annotations

import unittest

import pandas as pd

from app.services.data_engineering import build_data_engineering_contract
from data_berge_core.skills.engineering import EngineeringSkill


def population_profile() -> dict:
    return {
        "row_count": 3,
        "column_count": 5,
        "metadata": {
            "described_columns": 5,
            "duplicate_rows": 0,
            "missing_cells": 0,
        },
        "columns": [
            {
                "name": "age",
                "semantic_type": "text",
                "description": "[Categorical] Five-year age groups.",
                "unique_count": 3,
                "missing_pct": 0,
            },
            {
                "name": "sex",
                "semantic_type": "categorical",
                "description": "[Categorical] Sex grouping.",
                "unique_count": 1,
                "missing_pct": 0,
            },
            {
                "name": "date",
                "semantic_type": "categorical",
                "description": "[Date] Annual date with MM-DD fixed at 01-01.",
                "unique_count": 1,
                "missing_pct": 0,
            },
            {
                "name": "ethnicity",
                "semantic_type": "categorical",
                "description": "[Categorical] Citizen and non-citizen resident groups.",
                "unique_count": 1,
                "missing_pct": 0,
            },
            {
                "name": "population",
                "semantic_type": "numeric",
                "description": "[Float] Thousands of people.",
                "unique_count": 3,
                "missing_pct": 0,
            },
        ],
    }


class DataEngineeringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.df = pd.DataFrame({
            "age": ["overall", "0-4", "5-9"],
            "sex": ["both", "both", "both"],
            "date": ["1970-01-01", "1970-01-01", "1970-01-01"],
            "ethnicity": ["overall", "overall", "overall"],
            "population": [10881.8, 1702.4, 1690.3],
        })

    def test_semantic_descriptions_do_not_trigger_substring_role_errors(self) -> None:
        profile = population_profile()
        contract = build_data_engineering_contract(self.df, profile)

        self.assertEqual(contract["version"], 2)
        self.assertEqual(contract["semantic_roles"]["time"], ["date"])
        self.assertEqual(contract["semantic_roles"]["measure"], ["population"])
        self.assertEqual(contract["semantic_roles"]["category"], ["age", "sex", "ethnicity"])
        self.assertEqual(contract["semantic_roles"]["identifier"], [])

    def test_parseable_annual_date_is_preparation_advice_not_quality_failure(self) -> None:
        profile = population_profile()
        contract = build_data_engineering_contract(self.df, profile)

        date_column = next(column for column in profile["columns"] if column["name"] == "date")
        self.assertEqual(date_column["quality_notes"], [])
        self.assertTrue(date_column["preparation_notes"])
        self.assertEqual(contract["warnings"], [])

        skill = EngineeringSkill.__new__(EngineeringSkill)
        skill._ensure_contract = lambda dataset: contract
        brief = skill.assess_for_report({"profile": profile})

        self.assertEqual(brief["caution_columns"], [])
        self.assertNotIn("quality concerns", " ".join(brief["data_limitations"]))
        self.assertTrue(brief["data_preparation_notes"])


if __name__ == "__main__":
    unittest.main()
