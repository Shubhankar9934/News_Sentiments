"""Live options-chain adapter for implied-vol upgrade (gated by OPTIONS_USE_LIVE_IV).

Two providers are supported via ``OPTIONS_CHAIN_PROVIDER``:
- ``polygon`` (default): Polygon Options snapshot endpoint
- ``tradier``: Tradier Brokerage API

Every method swallows provider errors and returns ``None``. The caller
(``OptionsIntelligenceService``) treats ``None`` as "no live IV, fall back
to realized vol" so the pipeline never crashes when the chain is down.
"""

from __future__ import annotations

from typing import Any

import aiohttp
import structlog
from aiohttp import ClientTimeout

from app.core.config import Settings

log = structlog.get_logger(__name__)


class OptionsChainService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def fetch_atm_iv_pct(self, ticker: str, target_dte: int = 7) -> float | None:
        """Return the annualized ATM IV (in percent) closest to ``target_dte``.

        ``None`` is returned for any failure path. Callers must degrade
        gracefully — there is no exception surface here by design.
        """
        if not self._settings.options_use_live_iv:
            return None

        provider = (self._settings.options_chain_provider or "polygon").strip().lower()
        try:
            if provider == "polygon":
                return await self._fetch_polygon(ticker, target_dte)
            if provider == "tradier":
                return await self._fetch_tradier(ticker, target_dte)
            log.warning("options_chain.unknown_provider", provider=provider)
            return None
        except Exception as exc:  # pragma: no cover - resilient by design
            log.warning("options_chain.failed", provider=provider, error=str(exc))
            return None

    async def _fetch_polygon(self, ticker: str, target_dte: int) -> float | None:
        api_key = (
            self._settings.polygon_options_api_key.strip()
            or self._settings.polygon_api_key.strip()
        )
        if not api_key:
            return None
        url = f"https://api.polygon.io/v3/snapshot/options/{ticker.upper()}"
        params = {"limit": 250, "apiKey": api_key}
        async with aiohttp.ClientSession(timeout=ClientTimeout(total=15)) as session:
            async with session.get(url, params=params) as resp:
                if resp.status >= 400:
                    log.info("options_chain.polygon_status", status=resp.status)
                    return None
                data = await resp.json()

        contracts = data.get("results") or []
        candidate_iv = _pick_atm_iv_from_polygon(contracts, target_dte)
        if candidate_iv is None:
            return None
        return round(candidate_iv * 100.0, 3)  # polygon returns IV as decimal fraction

    async def _fetch_tradier(self, ticker: str, target_dte: int) -> float | None:
        token = self._settings.tradier_api_key.strip()
        if not token:
            return None
        base = self._settings.tradier_base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        async with aiohttp.ClientSession(timeout=ClientTimeout(total=15)) as session:
            async with session.get(
                f"{base}/markets/options/expirations",
                params={"symbol": ticker.upper(), "includeAllRoots": "true"},
                headers=headers,
            ) as resp:
                if resp.status >= 400:
                    return None
                exp_data = await resp.json()
            expirations = (
                exp_data.get("expirations", {}).get("date")
                if isinstance(exp_data, dict)
                else None
            )
            if not expirations:
                return None
            chosen = _closest_expiration(expirations, target_dte)
            if not chosen:
                return None

            async with session.get(
                f"{base}/markets/options/chains",
                params={"symbol": ticker.upper(), "expiration": chosen, "greeks": "true"},
                headers=headers,
            ) as resp:
                if resp.status >= 400:
                    return None
                chain = await resp.json()

        options = (chain.get("options", {}) or {}).get("option") or []
        iv = _atm_iv_from_tradier(options)
        if iv is None:
            return None
        return round(iv * 100.0, 3)


def _pick_atm_iv_from_polygon(contracts: list[dict[str, Any]], target_dte: int) -> float | None:
    """Find the ATM call (or put) closest to ``target_dte`` and return its IV."""
    best: tuple[float, float] | None = None  # (distance, iv)
    for c in contracts:
        details = c.get("details") or {}
        underlying = c.get("underlying_asset") or {}
        last_quote = c.get("last_quote") or {}
        iv = c.get("implied_volatility")
        if iv is None:
            iv = (c.get("greeks") or {}).get("implied_volatility")
        if iv is None or iv <= 0:
            continue
        strike = details.get("strike_price")
        spot = underlying.get("price") or last_quote.get("price")
        dte = c.get("days_to_expiration") or details.get("days_to_expiration")
        if not (strike and spot and dte is not None):
            continue
        try:
            distance = (
                abs(float(strike) - float(spot)) / float(spot)
                + abs(int(dte) - int(target_dte)) * 0.01
            )
        except (TypeError, ValueError):
            continue
        if best is None or distance < best[0]:
            best = (distance, float(iv))
    return best[1] if best else None


def _closest_expiration(expirations: list[str], target_dte: int) -> str | None:
    from datetime import UTC, datetime

    today = datetime.now(UTC).date()
    best: tuple[int, str] | None = None
    for exp in expirations:
        try:
            d = datetime.strptime(exp, "%Y-%m-%d").date()
        except ValueError:
            continue
        diff = abs((d - today).days - target_dte)
        if best is None or diff < best[0]:
            best = (diff, exp)
    return best[1] if best else None


def _atm_iv_from_tradier(options: list[dict[str, Any]]) -> float | None:
    best: tuple[float, float] | None = None
    for o in options:
        greeks = o.get("greeks") or {}
        iv = greeks.get("mid_iv") or greeks.get("smv_vol") or greeks.get("ask_iv")
        if iv is None or iv <= 0:
            continue
        strike = o.get("strike")
        underlying = o.get("underlying")
        spot = None
        if isinstance(underlying, dict):
            spot = underlying.get("last") or underlying.get("price")
        if strike is None or spot is None:
            continue
        try:
            distance = abs(float(strike) - float(spot)) / float(spot)
        except (TypeError, ValueError):
            continue
        if best is None or distance < best[0]:
            best = (distance, float(iv))
    return best[1] if best else None
