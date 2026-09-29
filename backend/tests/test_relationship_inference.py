from __future__ import annotations

import unittest

import pandas as pd

from app.services.relational import infer_relationships


class RelationshipInferenceTests(unittest.TestCase):
    def test_generic_shared_columns_do_not_create_relationships(self) -> None:
        relationships = infer_relationships({
            "Customers": pd.DataFrame({"status": ["active", "inactive"]}),
            "Orders": pd.DataFrame({"status": ["active", "inactive", "active"]}),
        })

        self.assertEqual(relationships, [])

    def test_shared_measurement_columns_do_not_create_relationships(self) -> None:
        relationships = infer_relationships({
            "January": pd.DataFrame({"amount": [10, 20], "region": ["North", "South"]}),
            "February": pd.DataFrame({"amount": [10, 20], "region": ["North", "South"]}),
        })

        self.assertEqual(relationships, [])

    def test_explicit_key_with_no_matching_values_needs_review(self) -> None:
        relationships = infer_relationships({
            "Customers": pd.DataFrame({"CustomerID (PK)": [1, 2]}),
            "Orders": pd.DataFrame({"CustomerID (FK)": [98, 99]}),
        })

        self.assertEqual(len(relationships), 1)
        relationship = relationships[0]
        self.assertFalse(relationship["active"])
        self.assertEqual(relationship["recommendation"], "needs_review")
        self.assertEqual(relationship["evidence"]["child_match_ratio"], 0.0)
        self.assertEqual(relationship["evidence"]["orphan_count"], 2)

    def test_numeric_identifier_representations_match_safely(self) -> None:
        relationships = infer_relationships({
            "Orders": pd.DataFrame({"customer_id": ["1.0", "2.0", "3.0", None]}),
            "Customers": pd.DataFrame({"customer_id": [1, 2, 3]}),
        })

        self.assertEqual(len(relationships), 1)
        relationship = relationships[0]
        self.assertFalse(relationship["active"])
        self.assertEqual(relationship["recommendation"], "recommended")
        self.assertEqual(relationship["evidence"]["child_match_ratio"], 1.0)
        self.assertEqual(relationship["evidence"]["null_count"], 1)

    def test_non_unique_parent_does_not_create_name_match_relationship(self) -> None:
        relationships = infer_relationships({
            "Customers": pd.DataFrame({"customer_id": [1, 1, 2]}),
            "Orders": pd.DataFrame({"customer_id": [1, 2, 2]}),
        })

        self.assertEqual(relationships, [])


if __name__ == "__main__":
    unittest.main()
