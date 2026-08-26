from __future__ import annotations

from app.connectors.contracts import FederatedConnector
from app.connectors.postgres import PostgresFederatedConnector


_CONNECTORS: dict[str, FederatedConnector] = {
    "postgresql": PostgresFederatedConnector(),
}


def get_federated_connector(connector_type: str) -> FederatedConnector:
    try:
        return _CONNECTORS[connector_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported connector type: {connector_type}") from exc
