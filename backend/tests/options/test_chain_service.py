"""OptionsChainService respects the OPTIONS_USE_LIVE_IV flag and degrades silently."""

import asyncio

from app.core.config import Settings
from app.services.market.options_chain import (
    OptionsChainService,
    _atm_iv_from_tradier,
    _closest_expiration,
    _pick_atm_iv_from_polygon,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_returns_none_when_flag_off():
    s = Settings(OPTIONS_USE_LIVE_IV=False)
    svc = OptionsChainService(s)

    async def _go():
        return await svc.fetch_atm_iv_pct("NVDA")

    assert _run(_go()) is None


def test_returns_none_when_polygon_key_missing():
    s = Settings(
        OPTIONS_USE_LIVE_IV=True,
        OPTIONS_CHAIN_PROVIDER="polygon",
        POLYGON_API_KEY="",
        POLYGON_OPTIONS_API_KEY="",
    )
    svc = OptionsChainService(s)

    async def _go():
        return await svc.fetch_atm_iv_pct("NVDA")

    assert _run(_go()) is None


def test_polygon_atm_iv_picks_closest_strike():
    contracts = [
        {
            "details": {"strike_price": 200, "days_to_expiration": 7},
            "underlying_asset": {"price": 220},
            "implied_volatility": 0.41,
        },
        {
            "details": {"strike_price": 220, "days_to_expiration": 7},
            "underlying_asset": {"price": 220},
            "implied_volatility": 0.39,
        },
        {
            "details": {"strike_price": 250, "days_to_expiration": 7},
            "underlying_asset": {"price": 220},
            "implied_volatility": 0.45,
        },
    ]
    iv = _pick_atm_iv_from_polygon(contracts, target_dte=7)
    assert iv == 0.39  # the 220-strike (ATM) wins


def test_closest_expiration_pick():
    # Bias toward "target_dte" days away from "today"
    assert _closest_expiration(["2099-12-31"], target_dte=7) == "2099-12-31"
    assert _closest_expiration([], target_dte=7) is None


def test_tradier_atm_pick():
    options = [
        {
            "strike": 100,
            "underlying": {"last": 110},
            "greeks": {"mid_iv": 0.5},
        },
        {
            "strike": 110,
            "underlying": {"last": 110},
            "greeks": {"mid_iv": 0.42},
        },
    ]
    assert _atm_iv_from_tradier(options) == 0.42
