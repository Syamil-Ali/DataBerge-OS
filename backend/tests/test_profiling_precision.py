from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from app.services.profiling import bivariate_analysis


class ProfilingPrecisionTests(unittest.TestCase):
    def test_bivariate_p_values_are_not_rounded_before_storage(self) -> None:
        fake_stats = SimpleNamespace(
            pearsonr=lambda left, right: (0.25, 1.23456789e-8),
            chi2_contingency=lambda table: (12.0, 2.34567891e-9, 1, None),
            f_oneway=lambda *groups: (8.0, 3.45678912e-10),
        )
        frame = pd.DataFrame({
            "x": [1, 2, 3, 4],
            "y": [2, 3, 4, 5],
            "group": ["a", "a", "b", "b"],
            "segment": ["x", "y", "x", "y"],
        })

        with patch("app.services.profiling.stats", fake_stats):
            result = bivariate_analysis(frame, ["x", "y"], ["group", "segment"])

        self.assertEqual(result["numeric_numeric"][0]["p_value"], 1.23456789e-8)
        self.assertEqual(result["categorical_categorical"][0]["p_value"], 2.34567891e-9)
        self.assertEqual(result["numeric_categorical"][0]["p_value"], 3.45678912e-10)


if __name__ == "__main__":
    unittest.main()
