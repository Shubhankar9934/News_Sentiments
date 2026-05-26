"""Reverse-BWB structure geometry (Phase 4a).

Deterministic, pure-function decomposition of the current Reverse-BWB
geometry that the report's "Why Pin Risk / Why Credit Safety / Why
Decision?" panels can reason over.

This module is intentionally side-effect free and never reaches into
the LLM layer. It is consumed by:

* :mod:`app.services.options.service` — to attach
  ``options_intelligence.structure_geometry`` to every report.
* :mod:`app.services.options.position_risk` — to hand off breakevens.
* The new ``reverse_bwb_structure_desk`` — as its primary numeric
  context.

For a Reverse Broken-Wing-Butterfly the trader collects a credit and
maximum loss is inside the body (between the short strikes). Wings
limit loss beyond. We compute relative geometry against the current
spot and 1σ cone over DTE.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StructureGeometry:
    spot: float
    body_strike: float
    wing_width_pct: float
    wing_width_dollars: float
    credit: float
    max_loss: float
    dte: int
    distance_to_body_pct: float
    distance_to_body_sigma: float
    body_exposure_pct: float
    wing_protection_ratio: float
    credit_efficiency: float
    risk_reward: float
    upper_breakeven: float
    lower_breakeven: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "spot": round(self.spot, 4),
            "body_strike": round(self.body_strike, 4),
            "wing_width_pct": round(self.wing_width_pct, 4),
            "wing_width_dollars": round(self.wing_width_dollars, 4),
            "credit": round(self.credit, 4),
            "max_loss": round(self.max_loss, 4),
            "dte": int(self.dte),
            "distance_to_body_pct": round(self.distance_to_body_pct, 4),
            "distance_to_body_sigma": round(self.distance_to_body_sigma, 4),
            "body_exposure_pct": round(self.body_exposure_pct, 4),
            "wing_protection_ratio": round(self.wing_protection_ratio, 4),
            "credit_efficiency": round(self.credit_efficiency, 4),
            "risk_reward": round(self.risk_reward, 4),
            "upper_breakeven": round(self.upper_breakeven, 4),
            "lower_breakeven": round(self.lower_breakeven, 4),
        }


def _horizon_sigma_pct(daily_vol_pct: float, dte: int) -> float:
    if daily_vol_pct <= 0 or dte <= 0:
        return 0.0
    return float(daily_vol_pct) * (float(dte) ** 0.5)


def _normal_cdf(x: float) -> float:
    """Tiny normal CDF helper to avoid scipy dependency at this layer."""

    from math import erf, sqrt

    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def compute_structure_geometry(
    *,
    spot: float,
    body_strike: float,
    wing_width_pct: float,
    credit: float,
    dte: int,
    daily_vol_pct: float,
) -> StructureGeometry | None:
    """Compute the full geometry block.

    Inputs:

    * ``spot``: underlying last close
    * ``body_strike``: short body strike (for symmetric BWB this is the
      midpoint of the short pair; for one-sided it is the short)
    * ``wing_width_pct``: wing distance from body, as % of spot
    * ``credit``: credit collected per share (1.0 = $1 per share)
    * ``dte``: days to expiration
    * ``daily_vol_pct``: daily realized/implied vol as a %

    Returns ``None`` if mandatory inputs are missing or non-physical.
    """

    if spot is None or spot <= 0:
        return None
    if body_strike is None or body_strike <= 0:
        return None
    if wing_width_pct is None or wing_width_pct <= 0:
        return None
    if credit is None or credit < 0:
        return None
    if dte is None or dte <= 0:
        return None

    wing_dollars = spot * (float(wing_width_pct) / 100.0)
    max_loss = max(0.0, wing_dollars - float(credit))

    distance_to_body = abs(spot - body_strike)
    distance_to_body_pct = (distance_to_body / spot) * 100.0
    sigma_pct = _horizon_sigma_pct(daily_vol_pct, dte)
    distance_to_body_sigma = (
        distance_to_body_pct / sigma_pct if sigma_pct > 0 else 0.0
    )

    # Body exposure: probability mass of the terminal price falling
    # within ±0.5 * wing_dollars of the body strike, under a lognormal
    # assumption with zero drift.
    if sigma_pct > 0:
        sigma_log = float(sigma_pct) / 100.0
        # work in log-space around body_strike
        z_hi = (
            (
                (body_strike + wing_dollars * 0.5) / spot
                if spot > 0
                else 1.0
            )
        )
        z_lo = (
            (body_strike - wing_dollars * 0.5) / spot
            if spot > 0
            else 1.0
        )
        from math import log

        if z_hi <= 0 or z_lo <= 0:
            body_exposure = 0.0
        else:
            body_exposure = _normal_cdf(log(z_hi) / sigma_log) - _normal_cdf(
                log(z_lo) / sigma_log
            )
    else:
        body_exposure = 0.0

    body_exposure_pct = max(0.0, min(1.0, body_exposure)) * 100.0

    wing_protection_ratio = (
        wing_width_pct / sigma_pct if sigma_pct > 0 else 0.0
    )

    credit_efficiency = credit / max(wing_dollars, 1e-9)
    risk_reward = credit / max(max_loss, 1e-9)

    upper_breakeven = body_strike + credit
    lower_breakeven = body_strike - credit

    return StructureGeometry(
        spot=float(spot),
        body_strike=float(body_strike),
        wing_width_pct=float(wing_width_pct),
        wing_width_dollars=float(wing_dollars),
        credit=float(credit),
        max_loss=float(max_loss),
        dte=int(dte),
        distance_to_body_pct=float(distance_to_body_pct),
        distance_to_body_sigma=float(distance_to_body_sigma),
        body_exposure_pct=float(body_exposure_pct),
        wing_protection_ratio=float(wing_protection_ratio),
        credit_efficiency=float(credit_efficiency),
        risk_reward=float(risk_reward),
        upper_breakeven=float(upper_breakeven),
        lower_breakeven=float(lower_breakeven),
    )


def derive_geometry_from_options_intelligence(
    options_intel: dict | None,
) -> StructureGeometry | None:
    """Build geometry from the deterministic ``options_intelligence`` block.

    Without a live chain we approximate:

    * ``body_strike`` = midpoint of the body-danger zone (or spot)
    * ``wing_width_pct`` = ``reverse_bwb.suggested_wing_width_pct``
    * ``credit`` = ``wing_width_dollars * 0.45`` (typical mid-RR credit)
    """

    if not options_intel:
        return None

    last_close = options_intel.get("last_close")
    rbwb = options_intel.get("reverse_bwb") or {}
    body_danger = options_intel.get("body_danger") or {}
    daily_vol = options_intel.get("daily_vol_pct")
    dte = rbwb.get("suggested_dte")
    wing_pct = rbwb.get("suggested_wing_width_pct")

    if last_close is None or wing_pct is None or dte is None:
        return None

    body_strike = (
        (
            float(body_danger.get("short_body_lo", last_close))
            + float(body_danger.get("short_body_hi", last_close))
        )
        / 2.0
        if body_danger
        else float(last_close)
    )
    wing_dollars = float(last_close) * (float(wing_pct) / 100.0)
    credit = round(wing_dollars * 0.45, 2)

    return compute_structure_geometry(
        spot=float(last_close),
        body_strike=float(body_strike),
        wing_width_pct=float(wing_pct),
        credit=float(credit),
        dte=int(dte),
        daily_vol_pct=float(daily_vol or 0.0),
    )
