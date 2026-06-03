# BTC Dao System

`dao-system` compresses the existing BTC macro dashboard, tactical BTC structure, and MSTR/mNAV reflexivity into one state machine.

Run it after the macro report:

```bash
python3 btc-macro-system/run.py
python3 dao-system/scripts/build_dao.py
open dao-system/index.html
```

The model has three axes:

- `天 / Macro liquidity`: reads `btc-macro-system/outputs/latest.json`.
- `地 / Market structure`: reads BTC technicals plus `dao-system/data/market-structure.json`.
- `人 / Treasury reflexivity`: reads the local mSTR/mNAV SQLite DB when available, then falls back to a CSV or `data/mnav-snapshot.json` for GitHub Pages.

Outputs:

- `dao-system/data/dao-latest.json`
- `dao-system/data/mnav-snapshot.json`
- `dao-system/index.html`

It is a regime and action-gating tool, not a price prediction or investment recommendation.
