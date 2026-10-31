from __future__ import annotations

from uuid import UUID

import httpx

from app.core.config import Settings
from app.modules.transport.contracts import FareQuery, FareResult
from app.modules.transport.providers.amadeus import AmadeusFareProvider
from app.modules.transport.providers.base import FareProvider, TransportProviderError
from app.modules.transport.providers.flyai import CliExecutor, FlyAITrainFareProvider
from app.modules.transport.service import TransportService


class ModeFareProvider:
    def __init__(self, providers: dict[str, FareProvider]) -> None:
        self.providers = providers

    def search_fares(self, query: FareQuery, *, request_id: UUID) -> FareResult:
        provider = self.providers.get(query.mode)
        if provider is None:
            raise TransportProviderError("unconfigured")
        return provider.search_fares(query, request_id=request_id)


def create_transport_service(
    settings: Settings,
    *,
    amadeus_client: httpx.Client | None = None,
    flyai_executor: CliExecutor | None = None,
) -> TransportService:
    """Build transport providers only from explicit, complete server configuration."""

    providers: dict[str, FareProvider] = {}
    if settings.transport_amadeus_configured:
        client_id = settings.transport_amadeus_client_id
        client_secret = settings.transport_amadeus_client_secret
        if client_id is None or client_secret is None:
            raise ValueError("Amadeus provider is configured without complete credentials.")
        providers["flight"] = AmadeusFareProvider(
            environment=settings.transport_amadeus_env,
            client_id=client_id,
            client_secret=client_secret,
            timeout_seconds=settings.transport_amadeus_timeout_seconds,
            max_response_bytes=settings.transport_amadeus_max_response_bytes,
            client=amadeus_client,
        )
    if settings.transport_flyai_configured:
        key = settings.transport_flyai_api_key
        assert key is not None
        providers["rail"] = FlyAITrainFareProvider(
            api_key=key,
            node_path=settings.transport_flyai_node_path,
            timeout_seconds=settings.transport_flyai_timeout_seconds,
            max_response_bytes=settings.transport_flyai_max_response_bytes,
            executor=flyai_executor,
        )
    return TransportService(fare_provider=ModeFareProvider(providers) if providers else None)
