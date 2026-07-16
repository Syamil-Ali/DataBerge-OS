from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

from app.api.opendosm import ConnectRequest
from app.services import opendosm


class OpenDOSMTests(unittest.TestCase):
    def test_data_catalogue_uses_the_current_official_api_route(self) -> None:
        self.assertEqual(opendosm.BASE_URL, "https://api.data.gov.my/data-catalogue")

    def test_parse_catalogue_page_extracts_all_nested_entries(self) -> None:
        payload = {
            "props": {
                "pageProps": {
                    "collection": {
                        "Demography": {
                            "Population": [
                                {
                                    "id": "population_malaysia",
                                    "title": "Population Table: Malaysia",
                                    "description": "National population.",
                                },
                                {
                                    "id": "population_state",
                                    "title": "Population Table: States",
                                    "description": "State population.",
                                },
                            ]
                        }
                    }
                }
            }
        }
        html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'

        result = opendosm._parse_catalogue_page(html)

        self.assertEqual([item["id"] for item in result], ["population_malaysia", "population_state"])
        self.assertEqual(result[0]["category"], "Demography: Population")

    @patch("app.services.opendosm.requests.get")
    def test_fetch_dataset_omits_limit_by_default(self, get: Mock) -> None:
        get.return_value.json.return_value = [{"year": 2024}, {"year": 2025}]

        result = opendosm.fetch_dataset("population_malaysia")

        self.assertEqual(len(result), 2)
        get.assert_called_once_with(
            opendosm.BASE_URL,
            params={"id": "population_malaysia"},
            timeout=30,
        )

    @patch("app.services.opendosm.requests.get")
    def test_fetch_dataset_keeps_an_explicit_limit(self, get: Mock) -> None:
        get.return_value.json.return_value = [{"year": 2025}]

        opendosm.fetch_dataset("population_malaysia", limit=1)

        get.assert_called_once_with(
            opendosm.BASE_URL,
            params={"id": "population_malaysia", "limit": 1},
            timeout=30,
        )

    def test_connect_request_is_uncapped_by_default(self) -> None:
        request = ConnectRequest(dataset_id="population_malaysia")

        self.assertIsNone(request.limit)


if __name__ == "__main__":
    unittest.main()
