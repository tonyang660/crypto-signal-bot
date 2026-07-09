# Repository Cleanup Plan

## Objective

Clean and document the repository without changing trading behavior.

The cleanup is intentionally phased so that source-control hygiene is separated from architecture refactoring and strategy changes.

## Step 0 — Security remediation

This is the highest-priority task.

The public repository currently tracks a `.env` file containing Bitget credential fields and Discord webhook URLs.

Required actions:

1. Revoke and rotate the Bitget API credentials.
2. Delete and recreate both exposed Discord webhooks.
3. Update GitHub Actions secrets with the new values.
4. Remove `.env` from the repository working tree.
5. Purge the leaked file/secret values from Git history using `git filter-repo` or BFG Repo-Cleaner.
6. Force-push the rewritten repository history.
7. Confirm the old credentials and webhooks no longer work.

Deleting the current `.env` alone is insufficient because old commits can retain the values.

Do not reuse the exposed values.

## Phase 1 — Behavior-neutral repository hygiene

### Remove tracked generated files

Stop tracking:

- `**/__pycache__/`
- `*.pyc`
- `logs/`
- runtime JSON state under `data/`
- `backtest/results/`
- nested generated backtest results
- downloaded backtest CSV datasets

Preserve empty directories only when needed through `.gitkeep`.

### Add safe environment template

Add `.env.example` with variable names and safe defaults only.

Never place real keys, secrets, passphrases, or webhook tokens in the template.

### Correct ignore rules

Do not ignore the entire `backtest/` directory.

Ignore its generated data and results while continuing to version-control Python backtest source.

### Normalize text encoding

Convert repository configuration/text files to UTF-8:

- `.gitignore`
- `requirements.txt`

### Classify root utility scripts

Proposed status:

| File | Proposed classification |
|---|---|
| `analytics.py` | analytics CLI |
| `analyze_logs.py` | diagnostics/legacy analytics; compare with `analytics.py` |
| `check_signals.py` | operations CLI |
| `check_volume.py` | diagnostics |
| `remove_signals.py` | operations CLI |
| `quick_backtest.py` | obsolete/broken until missing dependency is resolved |

Do not delete scripts until their behavior and callers are checked.

## Phase 2 — Documentation organization

Move implementation notes under `docs/`.

Suggested structure:

```text
docs/
├── ARCHITECTURE.md
├── CLEANUP_PLAN.md
├── strategy/
│   ├── adaptive-stops.md
│   ├── cooldown-penalty.md
│   ├── dynamic-risk.md
│   ├── fast-rally.md
│   ├── partial-protection.md
│   └── scoring-philosophy.md
├── backtesting/
│   ├── implementation.md
│   └── optimization.md
└── deployment/
    └── custom-ami.md
```

Update `README.md` so it acts as the repository entry point rather than containing every implementation detail.

The README should explain:

1. What the bot does.
2. Paper/live execution status.
3. Core architecture.
4. Quick start.
5. Environment configuration.
6. Production workflow.
7. State persistence.
8. Backtesting.
9. Documentation links.
10. Risk disclaimer.

## Phase 3 — Establish real tests

The current `backtest/test_*.py` files appear primarily to be loader/debug scripts rather than a structured unit-test suite.

Create:

```text
tests/
├── analysis/
├── strategy/
├── risk/
├── tracking/
└── backtest/
```

Highest-priority characterization tests:

1. TP1/TP2/TP3 lifecycle.
2. Stop loss before any TP.
3. TP1 followed by stop/trailing exit.
4. TP1 + TP2 followed by stop/trailing exit.
5. Full TP1 + TP2 + TP3 completion.
6. Fee and spread application.
7. Position-size calculation.
8. Daily and weekly loss limits.
9. Correlation/exposure limits.
10. Signal state save/load round trip.

These tests should freeze current behavior before large refactors.

## Phase 4 — Separate tracking concepts

The current analytics can count TP1/TP2/TP3 exit legs as separate trades.

Introduce explicit terminology:

- `position`
- `exit_leg`
- `tp_hit`
- `stop_exit`

Recommended performance fields:

```json
{
  "positions_closed": 0,
  "exit_legs_closed": 0,
  "winning_positions": 0,
  "losing_positions": 0,
  "winning_exit_legs": 0,
  "losing_exit_legs": 0,
  "position_win_rate": 0,
  "exit_leg_win_rate": 0,
  "tp1_hits": 0,
  "tp2_hits": 0,
  "tp3_hits": 0,
  "stop_exits": 0
}
```

Do this as a separate behavioral/data-model change after repository hygiene and characterization tests.

## Phase 5 — Refactor oversized modules

Refactor in dependency-safe order.

### 1. `signal_tracker.py`

Current responsibilities include:

- portfolio/margin availability;
- signal creation;
- price updates;
- TP detection;
- near-TP reversal logic;
- trailing stop calculation;
- stop-loss handling;
- PnL/fees/spread;
- manual close;
- adaptive stops;
- JSON persistence.

Potential future split:

```text
src/tracking/
├── signal_tracker.py
├── position_state.py
├── exit_engine.py
├── execution_costs.py
└── signal_repository.py
```

Keep `SignalTracker` as a facade initially so callers do not all change at once.

### 2. `main.py`

Move detailed signal construction/update behavior into services after `SignalTracker` has stable boundaries.

Possible target:

```text
src/services/
├── market_scanner.py
├── signal_service.py
└── position_monitor.py
```

`src/main.py` should eventually become application bootstrap/orchestration.

### 3. `backtest/engine.py`

Split only after production strategy behavior has characterization tests.

The backtest engine must reuse or clearly mirror production strategy components to avoid production/backtest drift.

## Phase 6 — Dashboard and improved analytics

Only after position-level logging is corrected:

- equity curve;
- daily PnL;
- drawdown;
- rolling 7-day/14-day PnL;
- rolling profit factor;
- position-level win rate;
- TP conversion funnel;
- PnL by symbol;
- PnL by regime;
- PnL by session.

## Recommended first pull request

Title:

`chore: clean repository structure and document current architecture`

Scope:

- remove leaked `.env` from the current tree after credentials are rotated;
- add `.env.example`;
- fix `.gitignore`;
- remove generated Python caches from tracking;
- stop tracking generated logs/runtime state/backtest outputs/data;
- normalize text files to UTF-8;
- add `docs/ARCHITECTURE.md`;
- add `docs/CLEANUP_PLAN.md`;
- reorganize existing Markdown notes under `docs/`;
- update README documentation links;
- no strategy logic changes.

This PR should remain behavior-neutral.
