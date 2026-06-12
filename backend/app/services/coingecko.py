"""Async CoinGecko HTTP client.

A thin, well-behaved wrapper over the CoinGecko REST API used to (a) seed the
token catalogue from the top-by-market-cap list and (b) fetch live prices.

Design notes:
  * Uses ``httpx.AsyncClient`` with an explicit timeout.
  * Retries transient failures (network errors, 429, 5xx) with exponential
    backoff; 4xx (other than 429) fail fast.
  * Emits structured logs for observability.
  * Raises :class:`CoinGeckoError` on unrecoverable failures so callers can map
    it to a clean API error rather than leaking ``httpx`` internals.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Status codes worth retrying (transient).
_RETRY_STATUS = {429, 500, 502, 503, 504}


class CoinGeckoError(Exception):
    """Raised when CoinGecko cannot satisfy a request after retries."""


def _headers() -> dict[str, str]:
    headers = {"accept": "application/json"}
    # CoinGecko demo/pro keys use this header; harmless when unset.
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key
    return headers


async def _request(path: str, params: dict[str, Any]) -> Any:
    """Perform a GET with timeout, retries and structured logging."""
    url = f"{settings.coingecko_base}{path}"
    max_attempts = max(1, settings.coingecko_max_retries)
    timeout = httpx.Timeout(settings.coingecko_timeout_sec)

    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout, headers=_headers()) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning(
                    "coingecko_request_error",
                    path=path,
                    attempt=attempt,
                    error=str(exc),
                )
            else:
                if response.status_code == httpx.codes.OK:
                    return response.json()

                if response.status_code in _RETRY_STATUS:
                    last_exc = CoinGeckoError(
                        f"CoinGecko returned {response.status_code}"
                    )
                    logger.warning(
                        "coingecko_retryable_status",
                        path=path,
                        attempt=attempt,
                        status_code=response.status_code,
                    )
                else:
                    # Non-retryable (e.g. 400/404) — fail fast.
                    logger.error(
                        "coingecko_client_error",
                        path=path,
                        status_code=response.status_code,
                        body=response.text[:300],
                    )
                    raise CoinGeckoError(
                        f"CoinGecko request failed: {response.status_code}"
                    )

            if attempt < max_attempts:
                # Exponential backoff: 0.5s, 1s, 2s, ...
                await asyncio.sleep(0.5 * 2 ** (attempt - 1))

    logger.error("coingecko_exhausted_retries", path=path, attempts=max_attempts)
    raise CoinGeckoError(
        f"CoinGecko request to {path} failed after {max_attempts} attempts"
    ) from last_exc


async def get_top_tokens(limit: int | None = None) -> list[dict[str, Any]]:
    """Return the top tokens by market cap.

    Each item contains at least ``id`` (CoinGecko id), ``symbol`` and ``name``.
    Used by the seed script to populate the catalogue.
    """
    count = limit or settings.top_tokens_count
    data = await _request(
        "/coins/markets",
        params={
            "vs_currency": settings.price_vs_currency,
            "order": "market_cap_desc",
            "per_page": min(count, 250),  # CoinGecko per-page cap
            "page": 1,
            "sparkline": "false",
        },
    )
    if not isinstance(data, list):
        raise CoinGeckoError("Unexpected /coins/markets response shape")
    logger.info("coingecko_top_tokens_fetched", count=len(data))
    return data[:count]


async def get_token_price(
    coingecko_id: str, vs_currency: str | None = None
) -> float:
    """Return the current price for a single token.

    Raises :class:`CoinGeckoError` if the token is unknown to CoinGecko.
    """
    currency = vs_currency or settings.price_vs_currency
    data = await _request(
        "/simple/price",
        params={"ids": coingecko_id, "vs_currencies": currency},
    )
    try:
        price = float(data[coingecko_id][currency])
    except (KeyError, TypeError, ValueError) as exc:
        logger.error(
            "coingecko_price_missing",
            coingecko_id=coingecko_id,
            currency=currency,
            payload=data,
        )
        raise CoinGeckoError(
            f"No price for '{coingecko_id}' in '{currency}'"
        ) from exc

    logger.info(
        "coingecko_price_fetched",
        coingecko_id=coingecko_id,
        currency=currency,
        price=price,
    )
    return price
