"""Decision Sensitivity Analysis (Phase 11).

Pure read-side helper. Composes four sub-blocks the report panel renders
to explain not just WHY the decision was made, but also what it depends
on and what would change it:

    1. ``key_drivers``         — weighted attribution of decision drivers
    2. ``assumptions``         — critical assumptions the decision rests on
    3. ``triggers``            — what would flip the decision (ENTER / AVOID)
    4. ``analyst_disagreement``— assessment-team stance split + main conflict

Every value is derived from data already present on the report
(``options_intelligence``, ``deliberation_layer``, ``summary``) — no
LLM calls happen here. Failure-isolated by the assembler ``_safe``
wrapper, so a partial input still produces a renderable block.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.dashboard.schemas import (
    AnalystDisagreementExplain,
    AnalystStanceRow,
    DecisionAssumption,
    DecisionKeyDriver,
    DecisionSensitivityExplain,
    DecisionTrigger,
    ReverseBwbSummary,
)

# ---------------------------------------------------------------------------
# Generic helpers.
# ---------------------------------------------------------------------------


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


_RISK_ORDER = {"Low": 0, "Medium": 1, "High": 2}


# ---------------------------------------------------------------------------
# 1. Key Drivers — weighted attribution of WHY the current decision holds.
# ---------------------------------------------------------------------------

# Magnitude weights for each driver derived directly from the existing
# Credit Safety component decomposition. Each |delta| approximates how
# much the driver pushed the score away from the move-stability anchor
# (10.0). Body placement is added on top using structure-geometry.


def _driver_label_pretty(slot: str) -> str:
    return {
        "pin_risk_impact": "Pin Risk",
        "event_risk_impact": "Event Risk",
        "volatility_impact": "Volatility Regime",
        "structure_placement_impact": "Body Placement",
        "liquidity_impact": "Liquidity",
    }.get(slot, slot.replace("_", " ").title())


def _direction_for_decision(delta: float, decision: str) -> str:
    """Map a Credit-Safety delta to a decision-aligned direction.

    - Decision ``Avoid``/``Wait``: negative deltas (deductions) *support*
      the cautious decision, because they explain why the card is not
      Enter-ready.
    - Decision ``Enter``: a near-zero or positive delta supports Enter
      (no major deduction); a meaningful negative delta opposes it
      (means the decision was Enter *despite* this drag).
    """

    if decision == "Enter":
        if delta > -0.05:
            return "supports"
        return "opposes"
    # Wait / Avoid
    if delta < -0.05:
        return "supports"
    if delta > 0.1:
        return "opposes"
    return "neutral"


def _collect_raw_drivers(
    *, summary: ReverseBwbSummary, options_intel: dict[str, Any]
) -> list[tuple[str, float, float, str]]:
    """Return ``(slot, magnitude, delta, detail)`` quadruples.

    Magnitude is non-negative; delta keeps its sign so direction can be
    derived. ``detail`` is a short trader-friendly hint.
    """

    raw: list[tuple[str, float, float, str]] = []

    pin = _safe_dict(options_intel.get("pin_risk"))
    event = _safe_dict(options_intel.get("event_risk"))
    body = _safe_dict(options_intel.get("body_danger"))
    cs = _safe_dict(options_intel.get("credit_safety"))
    cs_components = _safe_dict(cs.get("components"))

    pin_pen = float(cs_components.get("pin_risk") or 0.0)
    body_pen = float(cs_components.get("body_danger") or 0.0)
    event_pen = float(cs_components.get("event_risk") or 0.0)
    vol_pen = float(cs_components.get("vol_regime") or 0.0)

    pin_label = pin.get("label") or summary.pin_risk
    event_label = event.get("label") or summary.event_risk
    raw.append(
        (
            "pin_risk_impact",
            abs(pin_pen),
            -abs(pin_pen),
            f"Pin risk {pin_label} (gamma magnet at "
            f"{_to_float(pin.get('nearest_round')) or 0.0:.2f}).",
        )
    )
    raw.append(
        (
            "event_risk_impact",
            abs(event_pen),
            -abs(event_pen),
            f"Event risk {event_label} (catalysts within horizon).",
        )
    )
    raw.append(
        (
            "volatility_impact",
            abs(vol_pen),
            -abs(vol_pen),
            f"IV quality {summary.iv_quality}; vol regime weighed "
            f"{vol_pen:.2f} on credit safety.",
        )
    )
    raw.append(
        (
            "structure_placement_impact",
            abs(body_pen),
            -abs(body_pen),
            (
                f"Spot {_to_float(options_intel.get('last_close')) or 0.0:.2f} vs "
                f"body {_to_float(body.get('short_body_lo')) or 0.0:.2f}"
                f"–{_to_float(body.get('short_body_hi')) or 0.0:.2f}."
            ),
        )
    )

    liquidity_pen = 0.0
    liq = summary.liquidity
    if liq == "Poor":
        liquidity_pen = 0.6
    elif liq == "Average":
        liquidity_pen = 0.25
    raw.append(
        (
            "liquidity_impact",
            liquidity_pen,
            -liquidity_pen,
            f"Liquidity {liq}; execution drag included in card.",
        )
    )

    return raw


def build_key_drivers(
    *, summary: ReverseBwbSummary, options_intel: dict[str, Any]
) -> list[DecisionKeyDriver]:
    raw = _collect_raw_drivers(summary=summary, options_intel=options_intel)
    total_mag = sum(mag for _, mag, _, _ in raw)
    if total_mag <= 0.0:
        # No deductions worth attributing → return a single neutral row
        # so the panel still has a place to render an "all-clear" state.
        return [
            DecisionKeyDriver(
                label="No dominant risk drivers",
                weight_pct=100.0,
                direction="neutral",
                detail=(
                    "Credit safety components are roughly balanced; "
                    "no single lens dominates the decision."
                ),
            )
        ]

    rows: list[DecisionKeyDriver] = []
    decision = summary.decision
    for slot, mag, delta, detail in raw:
        pct = round(100.0 * mag / total_mag, 1)
        if pct < 1.0:
            continue
        rows.append(
            DecisionKeyDriver(
                label=_driver_label_pretty(slot),
                weight_pct=pct,
                direction=_direction_for_decision(delta, decision),  # type: ignore[arg-type]
                detail=detail,
            )
        )

    rows.sort(key=lambda r: r.weight_pct, reverse=True)
    # Renormalise after dropping <1% rows so the visible bars still sum to 100.
    visible_total = sum(r.weight_pct for r in rows)
    if visible_total > 0 and abs(visible_total - 100.0) > 0.2:
        scale = 100.0 / visible_total
        rebalanced: list[DecisionKeyDriver] = []
        for row in rows:
            rebalanced.append(
                DecisionKeyDriver(
                    label=row.label,
                    weight_pct=round(row.weight_pct * scale, 1),
                    direction=row.direction,
                    detail=row.detail,
                )
            )
        rows = rebalanced
    return rows


# ---------------------------------------------------------------------------
# 2. Assumptions Tracker — what the decision quietly depends on.
# ---------------------------------------------------------------------------


def build_assumptions(
    *,
    summary: ReverseBwbSummary,
    options_intel: dict[str, Any],
    deliberation_layer: dict[str, Any] | None,
    report: dict[str, Any],
) -> list[DecisionAssumption]:
    out: list[DecisionAssumption] = []

    event = _safe_dict(options_intel.get("event_risk"))
    event_label = event.get("label") or summary.event_risk
    event_drivers = [
        str(d).lower() for d in (event.get("drivers") or []) if isinstance(d, str)
    ]

    # Volatility stability assumption — high IV / wide range = fragile.
    iv_intel = _safe_dict(_safe_dict(report.get("options_intelligence")).get("iv_intel"))
    iv30 = _to_float(iv_intel.get("iv30"))
    rv20 = _to_float(iv_intel.get("rv20"))
    vol_regime = iv_intel.get("vol_regime")
    vol_fragility = "medium"
    vol_basis = "Implied vol holds near current level."
    if iv30 is not None and rv20 is not None and iv30 - rv20 > 5.0:
        vol_fragility = "high"
        vol_basis = (
            f"IV30={iv30:.1f} sits >5pts above RV20={rv20:.1f} — "
            "vol can collapse quickly."
        )
    elif vol_regime in {"low", "compressed"}:
        vol_fragility = "low"
        vol_basis = f"Vol regime tagged '{vol_regime}'; range stable."
    out.append(
        DecisionAssumption(
            label="IV remains near current level",
            basis=vol_basis,
            fragility=vol_fragility,  # type: ignore[arg-type]
        )
    )

    # Macro stability assumption — fragile when macro_transmission flagged a shock.
    macro_shock: str | None = None
    if deliberation_layer:
        explain_block = _safe_dict(report.get("explainability"))
        macro_block = _safe_dict(explain_block.get("macro_transmission"))
        macro_shock = macro_block.get("primary_shock") if isinstance(macro_block, dict) else None
    macro_fragility = "high" if macro_shock else "low"
    macro_basis = (
        f"Live macro shock '{macro_shock}' is already feeding the chain — "
        "follow-through risk is elevated."
        if macro_shock
        else "No active macro shock detected in the transmission chain."
    )
    out.append(
        DecisionAssumption(
            label="No major macro shock",
            basis=macro_basis,
            fragility=macro_fragility,  # type: ignore[arg-type]
        )
    )

    # Earnings / event window — fragile when event_risk drivers mention earnings.
    has_earnings = any("earning" in d for d in event_drivers)
    has_catalyst = any(
        kw in d for d in event_drivers for kw in ("fomc", "cpi", "fda", "guide")
    )
    if has_earnings or has_catalyst or event_label == "High":
        kw = "earnings" if has_earnings else ("catalyst" if has_catalyst else "event")
        out.append(
            DecisionAssumption(
                label="No surprise on the upcoming event",
                basis=(
                    f"Event risk tagged {event_label} with {kw} flagged in drivers; "
                    "a surprise re-prices the structure immediately."
                ),
                fragility="high",
            )
        )
    else:
        out.append(
            DecisionAssumption(
                label="No earnings or catalyst surprise inside horizon",
                basis="No catalyst flagged on the event-risk drivers list.",
                fragility="low",
            )
        )

    # Pin-risk drift — fragile if pin risk is borderline (Medium with proximity).
    pin = _safe_dict(options_intel.get("pin_risk"))
    pin_dist = _to_float(pin.get("distance_pct"))
    pin_label = pin.get("label") or summary.pin_risk
    if pin_label == "High" or (pin_dist is not None and pin_dist <= 0.3):
        out.append(
            DecisionAssumption(
                label="Round-number pin does not migrate",
                basis=(
                    f"Pin risk {pin_label}; nearest round "
                    f"{_to_float(pin.get('nearest_round')) or 0.0:.2f} is "
                    f"{(pin_dist or 0.0):.2f}% away."
                ),
                fragility="high",
            )
        )

    # Sector-specific assumption (energy → oil stability).
    ticker = (report.get("ticker") or "").upper()
    energy_tickers = {"XLE", "USO", "BNO", "CVX", "XOM", "OXY", "OIH"}
    if ticker in energy_tickers:
        out.append(
            DecisionAssumption(
                label="Oil benchmarks remain stable",
                basis=f"{ticker} is energy-linked; WTI shocks propagate immediately.",
                fragility="high" if macro_shock and "oil" in macro_shock else "medium",
            )
        )

    return out


# ---------------------------------------------------------------------------
# 3. Decision Triggers — what would flip the decision.
# ---------------------------------------------------------------------------


def _flip_targets(decision: str) -> list[str]:
    if decision == "Wait":
        return ["Enter", "Avoid"]
    if decision == "Avoid":
        return ["Enter", "Wait"]
    if decision == "Enter":
        return ["Wait", "Avoid"]
    return []


def _conditions_to_enter(
    *, summary: ReverseBwbSummary, options_intel: dict[str, Any]
) -> list[str]:
    conditions: list[str] = []
    geometry = _safe_dict(options_intel.get("structure_geometry"))
    body = _safe_dict(options_intel.get("body_danger"))
    cs = _safe_dict(options_intel.get("credit_safety"))
    cs_score = _to_float(cs.get("score")) or summary.credit_safety_score

    upper_be = _to_float(geometry.get("upper_breakeven"))
    lower_be = _to_float(geometry.get("lower_breakeven"))
    last_close = _to_float(options_intel.get("last_close"))

    if upper_be is not None and last_close is not None and last_close < upper_be:
        conditions.append(f"Spot trades above {upper_be:.2f} (upper breakeven)")
    elif lower_be is not None and last_close is not None and last_close > lower_be:
        conditions.append(f"Spot trades below {lower_be:.2f} (lower breakeven)")

    if summary.pin_risk != "Low":
        conditions.append(f"Pin Risk falls from {summary.pin_risk} to Low")
    if summary.event_risk != "Low":
        conditions.append(f"Event Risk falls from {summary.event_risk} to Low")
    if cs_score < 7.0:
        conditions.append(f"Credit Safety rises above 7.0 (currently {cs_score:.1f})")
    if summary.liquidity == "Poor":
        conditions.append("Liquidity improves to at least Average")
    if summary.iv_quality == "Poor":
        conditions.append("IV Quality improves to at least Average")

    body_lo = _to_float(body.get("short_body_lo"))
    body_hi = _to_float(body.get("short_body_hi"))
    if body_lo is not None and body_hi is not None and last_close is not None:
        if body_lo <= last_close <= body_hi:
            conditions.append(
                f"Spot exits the body zone {body_lo:.2f}–{body_hi:.2f}"
            )
    return conditions


def _conditions_to_avoid(
    *, summary: ReverseBwbSummary, options_intel: dict[str, Any]
) -> list[str]:
    conditions: list[str] = []
    body = _safe_dict(options_intel.get("body_danger"))
    cs_score = summary.credit_safety_score

    body_lo = _to_float(body.get("short_body_lo"))
    body_hi = _to_float(body.get("short_body_hi"))
    last_close = _to_float(options_intel.get("last_close"))
    if (
        body_lo is not None
        and body_hi is not None
        and last_close is not None
        and not (body_lo <= last_close <= body_hi)
    ):
        conditions.append(f"Spot enters body zone {body_lo:.2f}–{body_hi:.2f}")

    if summary.pin_risk != "High":
        conditions.append(f"Pin Risk rises to High (currently {summary.pin_risk})")
    if summary.event_risk != "High":
        conditions.append(f"Event Risk rises to High (currently {summary.event_risk})")

    iv_intel = _safe_dict(_safe_dict(options_intel.get("iv_intel")))
    iv30 = _to_float(iv_intel.get("iv30"))
    if iv30 is not None:
        threshold = max(iv30 * 1.25, iv30 + 5.0)
        conditions.append(
            f"IV30 spikes above {threshold:.1f} (currently {iv30:.1f})"
        )
    else:
        conditions.append("Realised volatility expands sharply (vol regime → high)")

    if cs_score >= 4.0:
        conditions.append(
            f"Credit Safety drops below 4.0 (currently {cs_score:.1f})"
        )

    if summary.liquidity != "Poor":
        conditions.append("Liquidity deteriorates to Poor")

    return conditions


def _conditions_to_wait(
    *, summary: ReverseBwbSummary, options_intel: dict[str, Any]
) -> list[str]:
    """Used when current decision is Enter or Avoid to describe the gray zone."""

    conditions: list[str] = []
    cs_score = summary.credit_safety_score

    if summary.decision == "Enter":
        if summary.pin_risk == "Low":
            conditions.append("Pin Risk drifts up to Medium")
        if summary.event_risk == "Low":
            conditions.append("Event Risk rises to Medium")
        if cs_score >= 7.0:
            conditions.append(
                f"Credit Safety eases between 4.0–7.0 (currently {cs_score:.1f})"
            )
    else:  # Avoid → Wait
        if summary.pin_risk == "High":
            conditions.append("Pin Risk eases from High to Medium")
        if summary.event_risk == "High":
            conditions.append("Event Risk eases from High to Medium")
        if cs_score < 4.0:
            conditions.append(
                f"Credit Safety recovers above 4.0 (currently {cs_score:.1f})"
            )
    return conditions


def build_triggers(
    *, summary: ReverseBwbSummary, options_intel: dict[str, Any]
) -> list[DecisionTrigger]:
    triggers: list[DecisionTrigger] = []
    targets = _flip_targets(summary.decision)
    for target in targets:
        if target == "Enter":
            conditions = _conditions_to_enter(
                summary=summary, options_intel=options_intel
            )
        elif target == "Avoid":
            conditions = _conditions_to_avoid(
                summary=summary, options_intel=options_intel
            )
        else:  # Wait
            conditions = _conditions_to_wait(
                summary=summary, options_intel=options_intel
            )
        # Keep at most 5 conditions per branch so the panel stays scannable.
        if conditions:
            triggers.append(
                DecisionTrigger(
                    target_decision=target,  # type: ignore[arg-type]
                    conditions=conditions[:5],
                )
            )
    return triggers


# ---------------------------------------------------------------------------
# 4. Analyst Disagreement Summary — assessment-team stance split.
# ---------------------------------------------------------------------------


_BULLISH_OUTLOOKS = {"Bullish"}
_BEARISH_OUTLOOKS = {"Bearish"}


def _classify_stance(opinion: dict[str, Any]) -> str:
    """Bullish / Bearish / Neutral from one member's card."""

    today = opinion.get("today_outlook")
    nxt = opinion.get("next_3d_outlook")
    bull_signals = 0
    bear_signals = 0
    if today in _BULLISH_OUTLOOKS:
        bull_signals += 1
    if today in _BEARISH_OUTLOOKS:
        bear_signals += 1
    if nxt in _BULLISH_OUTLOOKS:
        bull_signals += 1
    if nxt in _BEARISH_OUTLOOKS:
        bear_signals += 1

    chance_up = opinion.get("chance_up_2_3_pct")
    chance_dn = opinion.get("chance_down_2_3_pct")
    if chance_up == "High" and chance_dn != "High":
        bull_signals += 1
    if chance_dn == "High" and chance_up != "High":
        bear_signals += 1

    if bull_signals > bear_signals:
        return "Bullish"
    if bear_signals > bull_signals:
        return "Bearish"
    return "Neutral"


def _pick_revised(round1: dict[str, Any], round3: dict[str, Any]) -> dict[str, Any]:
    if not round3:
        return round1
    merged: dict[str, Any] = {}
    for role, payload in round1.items():
        revision = _safe_dict(round3.get(role))
        rev_opinion = _safe_dict(revision.get("revised_opinion"))
        if rev_opinion and not revision.get("error"):
            merged[role] = rev_opinion
        else:
            merged[role] = payload
    return merged


def _main_conflict_phrase(round2: dict[str, Any]) -> str | None:
    """Mine round-2 critiques for the dominant disagreement theme."""

    enum_buckets: Counter[str] = Counter()
    numeric_buckets: Counter[str] = Counter()
    for crit in round2.values():
        crit_d = _safe_dict(crit)
        for item in crit_d.get("enum_disagreements") or []:
            if isinstance(item, str):
                token = item.split(":")[0].strip().lower().replace(" ", "_")
                if token:
                    enum_buckets[token] += 1
        for item in crit_d.get("numeric_disagreements") or []:
            if isinstance(item, str):
                token = item.split(":")[0].strip().lower().replace(" ", "_")
                if token:
                    numeric_buckets[token] += 1

    parts: list[str] = []
    if enum_buckets:
        top_enum = enum_buckets.most_common(1)[0][0]
        parts.append(top_enum.replace("_", " ").title())
    if numeric_buckets:
        top_num = numeric_buckets.most_common(1)[0][0]
        parts.append(top_num.replace("_", " ").title())
    if not parts:
        return None
    return " vs ".join(dict.fromkeys(parts))  # de-dup, preserve order


def build_analyst_disagreement(
    *, deliberation_layer: dict[str, Any] | None
) -> AnalystDisagreementExplain | None:
    if not deliberation_layer:
        return None
    assessment_layer = _safe_dict(deliberation_layer.get("assessment_layer"))
    if not assessment_layer:
        return None

    round1 = _safe_dict(assessment_layer.get("round1"))
    round2 = _safe_dict(assessment_layer.get("round2"))
    round3 = _safe_dict(assessment_layer.get("round3"))
    if not round1:
        return None

    used = _pick_revised(round1, round3)

    rows: list[AnalystStanceRow] = []
    stance_counts: Counter[str] = Counter()
    for role_key, opinion in used.items():
        op = _safe_dict(opinion)
        if not op:
            continue
        stance = _classify_stance(op)
        stance_counts[stance] += 1

        risk_view = op.get("risk")
        confidence_view = op.get("confidence")
        # Headline: first reasoning step title or first dynamics bullet
        headline: str | None = None
        steps = op.get("reasoning_steps") or []
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict):
                    title = step.get("title") or ""
                    if title:
                        headline = str(title)[:160]
                        break
        if not headline:
            dyn = op.get("actual_dynamics_summary") or []
            if isinstance(dyn, list) and dyn:
                headline = str(dyn[0])[:160]

        rows.append(
            AnalystStanceRow(
                member=str(op.get("model") or role_key),
                label=str(op.get("assessment_label") or role_key),
                stance=stance,  # type: ignore[arg-type]
                decision_view=None,  # Assessment members don't vote on decision
                risk_view=risk_view if risk_view in _RISK_ORDER else None,
                confidence_view=confidence_view
                if confidence_view in {"Low", "Medium", "High"}
                else None,
                headline=headline,
            )
        )

    distinct = {row.stance for row in rows}
    converged = len(distinct) <= 1
    main_conflict = None if converged else _main_conflict_phrase(round2)

    if not rows:
        return None

    return AnalystDisagreementExplain(
        stances=rows,
        stance_counts={k: int(v) for k, v in stance_counts.items()},
        main_conflict=main_conflict,
        converged=converged,
    )


# ---------------------------------------------------------------------------
# Top-level builder consumed by the assembler.
# ---------------------------------------------------------------------------


def build_decision_sensitivity(
    *,
    ticker: str,  # noqa: ARG001 — kept for signature uniformity with other builders
    report: dict[str, Any],
    deliberation_layer: dict[str, Any] | None,
    summary: ReverseBwbSummary | None,
) -> DecisionSensitivityExplain | None:
    if summary is None:
        return None
    options_intel = _safe_dict(report.get("options_intelligence"))
    if not options_intel:
        return None

    key_drivers = build_key_drivers(summary=summary, options_intel=options_intel)
    assumptions = build_assumptions(
        summary=summary,
        options_intel=options_intel,
        deliberation_layer=deliberation_layer,
        report=report,
    )
    triggers = build_triggers(summary=summary, options_intel=options_intel)
    disagreement = build_analyst_disagreement(
        deliberation_layer=deliberation_layer
    )

    return DecisionSensitivityExplain(
        current_decision=summary.decision,
        key_drivers=key_drivers,
        assumptions=assumptions,
        triggers=triggers,
        analyst_disagreement=disagreement,
    )
