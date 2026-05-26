"""Compose the deterministic options-intelligence block for a single ticker run."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

import structlog

from app.core.config import Settings
from app.services.options.body_danger import body_danger_zone
from app.services.options.credit_safety import credit_safety_score
from app.services.options.event_risk import event_risk_score
from app.services.options.expected_range import expected_range
from app.services.options.pin_risk import pin_risk
from app.services.options.position_risk import compute_position_risk
from app.services.options.probability import move_probabilities
from app.services.options.reverse_bwb import reverse_bwb_suitability
from app.services.options.schemas import (
    BodyDanger,
    CreditSafety,
    CreditSafetyComponents,
    EventRisk,
    ExpectedRange,
    MoveProbabilities,
    OptionsIntelligence,
    PinRisk,
    PositionRiskBlock,
    ReverseBwb,
    StructureGeometryBlock,
)
from app.services.options.structure_geometry import compute_structure_geometry

log = structlog.get_logger(__name__)


class _BarLike(Protocol):
    close: float


def _daily_vol_pct_from_bars(bars: Iterable[Any], window: int = 20) -> float:
    """Average absolute daily % move over the last ``window`` bars.

    Matches the deterministic measure already used by ``get_volatility_regime``
    so the panel never disagrees with the regime label shown elsewhere.
    """
    bars_list = list(bars)
    if len(bars_list) < 2:
        return 1.5
    recent = bars_list[-min(window, len(bars_list)) :]
    moves: list[float] = []
    for i in range(1, len(recent)):
        prev = recent[i - 1]
        curr = recent[i]
        if prev.close:
            moves.append(abs(curr.close - prev.close) / prev.close * 100.0)
    if not moves:
        return 1.5
    return sum(moves) / len(moves)


def _data_quality_penalty(articles_analyzed: int | None, data_mode: str | None) -> float:
    penalty = 0.0
    if data_mode and data_mode != "real":
        penalty += 0.15
    if isinstance(articles_analyzed, int) and articles_analyzed < 10:
        penalty += 0.1
    return min(penalty, 0.3)


class OptionsIntelligenceService:
    """Pure orchestration — no I/O, runs after ``_pipeline_meta`` is attached."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def compute(
        self,
        *,
        last_close: float | None,
        bars: Iterable[Any],
        volatility_regime: str | None,
        key_events: list[dict[str, Any]] | None,
        horizon_days: int | None = None,
        articles_analyzed: int | None = None,
        data_mode: str | None = None,
        live_iv_pct: float | None = None,
    ) -> OptionsIntelligence | None:
        """Compute the full block. Returns ``None`` if mandatory inputs are missing."""
        if not last_close or last_close <= 0:
            log.info("options.skip", reason="no_last_close")
            return None

        horizon = int(horizon_days or self._settings.options_default_horizon_days)
        horizon = max(1, horizon)

        if isinstance(live_iv_pct, (int, float)) and live_iv_pct > 0:
            # IV is annualized — convert to a daily % equivalent by /sqrt(252)
            daily_vol_pct = float(live_iv_pct) / (252 ** 0.5)
            source: str = "live_iv"
        else:
            daily_vol_pct = _daily_vol_pct_from_bars(bars)
            source = "realized_vol"

        penalty = _data_quality_penalty(articles_analyzed, data_mode)
        er = expected_range(
            last_close=last_close,
            daily_vol_pct=daily_vol_pct,
            horizon_days=horizon,
            z=1.0,
            data_quality_penalty=penalty,
        )
        mp = move_probabilities(last_close, daily_vol_pct, horizon)
        pr = pin_risk(last_close, daily_vol_pct, horizon)
        bd = body_danger_zone(last_close, daily_vol_pct, horizon)
        ev = event_risk_score(key_events)
        cs = credit_safety_score(
            prob_block=mp["p_in_range_1sigma"],
            pin_risk=float(pr["score"]),
            body_danger=0.5 if bd["label"] == "Medium" else 0.85 if bd["label"] == "High" else 0.15,
            event_risk=float(ev["score"]),
            vol_regime=volatility_regime,
            weights=self._settings.options_credit_safety_weights or None,
        )
        bw = reverse_bwb_suitability(
            credit_safety_score=float(cs["score"]),
            expected_range_sigma_pct=float(er["sigma_pct"]),
            vol_regime=volatility_regime,
            event_risk_score=float(ev["score"]),
        )

        # Structure geometry (Phase 4a) — deterministic decomposition of
        # the current Reverse-BWB structure. Approximated when no live
        # chain is available.
        body_center = (float(bd["short_body_lo"]) + float(bd["short_body_hi"])) / 2.0
        geometry = compute_structure_geometry(
            spot=float(last_close),
            body_strike=float(body_center),
            wing_width_pct=float(bw["suggested_wing_width_pct"]),
            credit=round(
                float(last_close)
                * (float(bw["suggested_wing_width_pct"]) / 100.0)
                * 0.45,
                2,
            ),
            dte=int(bw["suggested_dte"]),
            daily_vol_pct=float(daily_vol_pct),
        )

        # Position risk (Phase 5) — closed-form lognormal PoP / PoT / EV
        # mirrored into options_intelligence.position_risk. Card values
        # are unchanged; this is a parallel derivative block.
        position_risk_block = None
        if geometry is not None:
            position_risk_dict = compute_position_risk(
                spot=geometry.spot,
                body_strike=geometry.body_strike,
                wing_width_pct=geometry.wing_width_pct,
                credit=geometry.credit,
                sigma_pct=float(er["sigma_pct"]),
                dte=geometry.dte,
            )
            if position_risk_dict is not None:
                position_risk_block = PositionRiskBlock(**position_risk_dict)

        try:
            return OptionsIntelligence(
                source=source,  # type: ignore[arg-type]
                horizon_days=horizon,
                last_close=float(last_close),
                daily_vol_pct=round(float(daily_vol_pct), 4),
                expected_range=ExpectedRange(**er),
                move_probabilities=MoveProbabilities(**mp),
                pin_risk=PinRisk(
                    score=float(pr["score"]),
                    label=pr["label"],  # type: ignore[arg-type]
                    nearest_round=float(pr["nearest_round"]),
                    distance_pct=float(pr["distance_pct"]),
                ),
                body_danger=BodyDanger(
                    short_body_lo=float(bd["short_body_lo"]),
                    short_body_hi=float(bd["short_body_hi"]),
                    distance_pct=float(bd["distance_pct"]),
                    label=bd["label"],  # type: ignore[arg-type]
                ),
                event_risk=EventRisk(
                    score=float(ev["score"]),
                    label=ev["label"],  # type: ignore[arg-type]
                    drivers=list(ev.get("drivers") or []),
                ),
                credit_safety=CreditSafety(
                    score=float(cs["score"]),
                    label=cs["label"],  # type: ignore[arg-type]
                    components=CreditSafetyComponents(**cs["components"]),  # type: ignore[arg-type]
                ),
                reverse_bwb=ReverseBwb(
                    score=float(bw["score"]),
                    label=bw["label"],  # type: ignore[arg-type]
                    suggested_wing_width_pct=float(bw["suggested_wing_width_pct"]),
                    suggested_dte=int(bw["suggested_dte"]),
                    rationale=str(bw["rationale"]),
                ),
                structure_geometry=(
                    StructureGeometryBlock(**geometry.as_dict())
                    if geometry is not None
                    else None
                ),
                position_risk=position_risk_block,
            )
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("options.assemble_failed", error=str(exc))
            return None
