# Small-Cap Futures Agent Harness

This harness turns the existing Binance small-cap scanner into a sustainable agent loop. It keeps market collection, thesis rules, notification decisions, and iteration evidence separate so each layer can improve without rewriting the whole system.

## Loop

1. Observe: `update_smallcap_system.py` fetches public Binance USD-M Futures market data.
2. Classify: `harness/config.json` defines symbol theses, zones, thresholds, and event gates.
3. Decide: `run_agent_harness.py` converts the latest snapshot into `NOTIFY` or `DONT_NOTIFY` decisions.
4. Log: the runner writes `data/harness_state.json` and appends `data/harness_decisions.jsonl`.
5. Learn: forward outcomes from the base scanner plus harness decisions can be reviewed to tune thresholds and gates.
6. Validate: `validate_harness.py` checks structural integrity before changing the loop.

## Commands

Use the existing snapshot without network calls:

```bash
python3 smallcap-futures-system/scripts/run_agent_harness.py --no-update --dry-run
```

Run a full public-data update and write harness state:

```bash
python3 smallcap-futures-system/scripts/run_agent_harness.py --raw
```

Show the latest harness state:

```bash
python3 smallcap-futures-system/scripts/run_agent_harness.py --show
```

Validate the harness:

```bash
python3 smallcap-futures-system/scripts/validate_harness.py
```

Show the base system summary:

```bash
python3 smallcap-futures-system/scripts/update_smallcap_system.py --show
```

## Guardrails

- Public Binance Futures data only.
- No API keys.
- No order placement.
- Every notification must include context and a risk note.
- Output is research workflow evidence, not financial advice.

## Iteration Rules

- Change `harness/config.json` first when the thesis, zone, or threshold changes.
- Change `run_agent_harness.py` only when the decision logic needs a new reusable classifier.
- Run `validate_harness.py` after each rule change.
- Compare `data/harness_decisions.jsonl` with `data/forward_outcomes.jsonl` before promoting a rule from experimental to stable.
