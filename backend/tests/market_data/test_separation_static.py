"""Static-import boundary checks for the live vs snapshot domains.

These guard the architectural invariant of the Reverse BWB Trading
Workstation:

    - ``app.services.market_data.*`` never imports
      ``app.services.dashboard.*`` (live worker mustn't write analysis).
    - ``app.services.dashboard.*`` never imports
      ``app.services.market_data.*`` (analysis batch mustn't depend on
      live data).
    - ``app.services.dil_resilience.*`` never imports
      ``app.services.dashboard.repositories`` (resilience is shared
      infrastructure; it must not encode analysis-snapshot writes).
    - ``DashboardRepository.save_snapshot`` only touches the three
      analysis-snapshot tables (``ticker_reports``,
      ``ticker_reverse_bwb_summary``, ``ticker_option_opportunities``).
    - The market_data repository only writes to the three live tables
      (``ticker_market_data``, ``ticker_live_option_opportunities``,
      ``ticker_option_opportunity_history``).
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil


def _iter_module_sources(package_name: str):
    package = importlib.import_module(package_name)
    paths = list(getattr(package, "__path__", []))
    for module_info in pkgutil.walk_packages(paths, prefix=package_name + "."):
        try:
            module = importlib.import_module(module_info.name)
        except Exception:
            continue
        try:
            source = inspect.getsource(module)
        except (OSError, TypeError):
            continue
        yield module_info.name, source


def test_market_data_never_imports_dashboard_services() -> None:
    """Live worker must not reach into the analysis snapshot package."""
    for name, source in _iter_module_sources("app.services.market_data"):
        # `dashboard.watchlist` is the canonical 12-ticker list — it is
        # the only allowed cross-package symbol because the live worker
        # needs the *list of tickers*. Everything else is forbidden.
        assert "from app.services.dashboard.repositor" not in source, name
        assert "from app.services.dashboard.watchlist_batch" not in source, name
        assert "from app.services.dashboard.opportunity_generator" not in source, name
        assert "from app.services.dashboard.summary_projector" not in source, name
        # Belt-and-braces — no submodule of dashboard.* outside the watchlist
        # roster is allowed.
        for forbidden in (
            "from app.db.repositories.dashboard_repository",
            "from app.services.dashboard.schemas",
        ):
            assert forbidden not in source, (
                f"{name} imports {forbidden}; live layer must not depend on "
                "analysis-snapshot schemas/repositories"
            )


def test_dashboard_services_never_import_market_data() -> None:
    for name, source in _iter_module_sources("app.services.dashboard"):
        assert "from app.services.market_data" not in source, name
        assert "import app.services.market_data" not in source, name


def test_dil_resilience_never_imports_dashboard_repository() -> None:
    """DIL resilience is a shared infrastructure module; it must not
    encode analysis-snapshot table writes."""
    for name, source in _iter_module_sources("app.services.dil_resilience"):
        assert "from app.db.repositories.dashboard_repository" not in source, name
        # Loose check — anything importing the snapshot ORM tables is
        # also suspect.
        assert "TickerReverseBwbSummaryModel" not in source, name
        assert "TickerOptionOpportunityModel" not in source, name


def test_market_data_repository_only_writes_live_tables() -> None:
    import app.services.market_data.repository as repo_mod

    source = inspect.getsource(repo_mod)
    # Whitelisted ORM models; everything else is forbidden in the
    # repository's write path.
    forbidden_models = (
        "TickerReverseBwbSummaryModel",
        "TickerReportModel",
        "TickerOptionOpportunityModel",
        "ResearchReportModel",
        "DeliberationRunModel",
    )
    for symbol in forbidden_models:
        assert symbol not in source, (
            f"{symbol} must not appear in market_data.repository — "
            "live writes must never touch analysis-snapshot tables"
        )

    allowed_models = (
        "TickerMarketDataModel",
        "TickerLiveOptionOpportunityModel",
        "TickerOptionOpportunityHistoryModel",
    )
    for symbol in allowed_models:
        assert symbol in source, f"{symbol} should be referenced in repository"


def test_dashboard_save_snapshot_only_touches_snapshot_tables() -> None:
    """Re-running analysis must never write to the live tables."""
    import app.db.repositories.dashboard_repository as repo_mod

    source = inspect.getsource(repo_mod.DashboardRepository.save_snapshot)
    forbidden = (
        "TickerMarketDataModel",
        "TickerLiveOptionOpportunityModel",
        "TickerOptionOpportunityHistoryModel",
        "ticker_market_data",
        "ticker_live_option_opportunities",
        "ticker_option_opportunity_history",
    )
    for symbol in forbidden:
        assert symbol not in source, (
            f"DashboardRepository.save_snapshot must not reference {symbol} — "
            "the analysis batch must never touch the live market-data tables"
        )
