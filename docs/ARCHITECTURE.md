# Current Architecture

## Purpose

This document describes the current structure of `crypto-signal-bot` before repository cleanup and behavioral refactoring.

The goal is to preserve current behavior while making responsibilities and dependencies explicit.

## Runtime flow

The current production entry point is:

`src/main.py`

At a high level, `SignalBot` coordinates:

1. Loading configuration.
2. Fetching and managing market data.
3. Calculating technical indicators.
4. Detecting market regime and structure.
5. Evaluating long and short entries.
6. Scoring candidate signals.
7. Calculating stop-loss and take-profit levels.
8. Applying position sizing and risk controls.
9. Creating and updating tracked signals.
10. Publishing Discord notifications.
11. Logging trade and daily performance data.

This makes `src/main.py` an orchestration layer, but it currently contains substantial execution and signal-management logic in addition to orchestration.

## Source packages

### `src/core`

Infrastructure and configuration.

- `config.py` — environment-backed configuration and strategy constants.
- `bitget_client.py` — Bitget exchange/API access.
- `data_manager.py` — market-data retrieval and management.

### `src/analysis`

Market measurements and classification.

- `indicators.py` — technical indicator calculations.
- `market_structure.py` — support, resistance, structure, and related market context.
- `regime_detector.py` — market-regime classification.

### `src/strategy`

Signal-generation logic.

- `entry_logic.py` — entry-condition evaluation.
- `signal_scorer.py` — candidate signal scoring.
- `stop_tp_calculator.py` — stop-loss and TP1/TP2/TP3 calculations.

### `src/risk`

Risk and exposure controls.

- `position_sizer.py` — position-size calculations.
- `risk_manager.py` — strategy and account risk checks.

### `src/tracking`

Signal lifecycle and performance persistence.

- `signal_tracker.py` — active signal lifecycle, partial TP handling, stop handling, trailing/adaptive stop logic, state persistence, and manual closure.
- `performance_logger.py` — trade logging, aggregate statistics, daily reports, and weekly reports.

`signal_tracker.py` currently has the broadest concentration of responsibilities and is a major future refactor boundary.

### `src/notifications`

Discord presentation and status notifications.

- `discord_notifier.py` — signal and performance notifications.
- `active_positions_notifier.py` — rolling active-position summary.

## Production orchestration

`src/main.py` depends on nearly every source package.

Current dependency direction is approximately:

```text
src/main.py
├── core
│   ├── config
│   └── data_manager
├── analysis
│   ├── indicators
│   ├── market_structure
│   └── regime_detector
├── strategy
│   ├── entry_logic
│   ├── signal_scorer
│   └── stop_tp_calculator
├── risk
│   ├── position_sizer
│   └── risk_manager
├── tracking
│   ├── signal_tracker
│   └── performance_logger
└── notifications
    ├── discord_notifier
    └── active_positions_notifier
```

The package boundaries are generally sensible. The main cleanup problem is not the package names; it is responsibility concentration inside several large modules and generated artifacts mixed with source control.

## Backtesting

The `backtest/` directory contains:

- backtest configuration;
- historical-data loaders;
- Binance data import/download utilities;
- the backtest engine;
- walk-forward tooling;
- multi-year runners;
- diagnostics;
- data-validation scripts;
- test-like loader/debug scripts;
- large downloaded CSV datasets;
- many generated result files.

The largest module is `backtest/engine.py`, which is currently over 1,200 lines.

The repository also contains `quick_backtest.py` at the root. It imports `backtest.data_fetcher.HistoricalDataFetcher`, but no matching `backtest/data_fetcher.py` implementation exists in the current repository. Treat `quick_backtest.py` as a broken or obsolete utility until its intended dependency is identified.

## Persistent state

Current runtime state is stored under `data/`, including active signals, signal history, trade history, and performance data.

These are runtime artifacts, not source code. They should not be treated as canonical application source.

The existing production workflow synchronizes state with S3 before and after bot execution.

## GitHub Actions

The primary trading workflow:

1. Checks out the repository.
2. Configures AWS credentials from GitHub Actions secrets.
3. Installs Python dependencies.
4. Downloads persistent state from S3.
5. Injects Bitget and Discord configuration through GitHub Actions secrets.
6. Runs `python -m src.main --single-run`.
7. Uploads updated state to S3.
8. Uploads diagnostic artifacts.

This means the committed `.env` is not required by the GitHub Actions production workflow.

## Known repository-structure issues

1. A `.env` containing credentials/webhook values is tracked in a public repository.
2. Generated `__pycache__` files are tracked.
3. Historical datasets occupy most of the repository size.
4. Generated backtest results are tracked alongside backtest source.
5. Root-level utility scripts have mixed status: operational, diagnostic, analytical, and obsolete.
6. Root-level implementation notes are not organized into a documentation hierarchy.
7. `quick_backtest.py` references a missing module.
8. `.gitignore` ignores the entire `backtest/` directory even though backtest source code is intentionally version-controlled.
9. `.gitignore` and `requirements.txt` are stored as UTF-16 text in the inspected ZIP, which is unusual for Python repository configuration files.
10. Runtime and analytics terminology currently uses `trade` for TP1/TP2/TP3 exit legs in some metrics, which can misrepresent position-level trade frequency and win rate.

## Refactor boundaries to preserve for now

Do not change strategy behavior during the first cleanup pass.

Specifically, avoid modifying:

- entry conditions;
- regime thresholds;
- scoring weights;
- position sizing;
- dynamic risk;
- TP1/TP2/TP3 behavior;
- adaptive stop behavior;
- cooldown logic;
- partial-protection logic;
- spread/fee simulation.

The first cleanup should make the repository safer and easier to understand before changing these systems.
