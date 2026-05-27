# Binance Small-Cap Futures CLI

这个工具用于合约小币的本地研究、模拟和受保护下单。默认不会真实下单。

It is a research and execution-assist tool, not a trading signal or investment recommendation.

## Safety Model

- `scan`、`simulate`、`plan` 都只读取公开行情数据。
- `order` 默认也是 dry-run，只打印将要发送的订单。
- 真实下单必须同时满足：
  - 设置环境变量 `BINANCE_FAPI_KEY` 和 `BINANCE_FAPI_SECRET`
  - 传入 `--live`
  - 传入确认短语 `--confirm-live I_UNDERSTAND_THIS_CAN_PLACE_REAL_FUTURES_ORDERS`
  - 明确选择 `--entry-only` 或 `--place-stops-now`
- API key 不要写进仓库。建议先使用 Binance Futures Testnet 和最小名义金额测试。

## Commands

扫描 24h 涨幅、成交额和交易笔数满足条件的 USDT 永续小币，并补充资金费率与 OI：

```bash
python3 tools/binance_smallcap_cli.py scan --limit 10
```

跳过 Funding / OI，加快扫描：

```bash
python3 tools/binance_smallcap_cli.py scan --limit 10 --no-enrich
```

对一个标的同时跑“阶梯提前挂空”和“冲高回落确认”模拟：

```bash
python3 tools/binance_smallcap_cli.py simulate PLAYUSDT --strategy both
```

先自动扫描，再对前 5 个候选做模拟：

```bash
python3 tools/binance_smallcap_cli.py simulate --auto --auto-limit 5
```

生成阶梯空单计划。默认以最新价为锚点，每层 20 USDT 名义金额：

```bash
python3 tools/binance_smallcap_cli.py plan PLAYUSDT --notional 20
```

只做下单 dry-run，查看完整 Binance Futures 订单 payload：

```bash
python3 tools/binance_smallcap_cli.py order PLAYUSDT --notional 20
```

使用 Futures Testnet 做真实测试单：

```bash
export BINANCE_FAPI_KEY="..."
export BINANCE_FAPI_SECRET="..."

python3 tools/binance_smallcap_cli.py --testnet order PLAYUSDT \
  --notional 20 \
  --live \
  --entry-only \
  --confirm-live I_UNDERSTAND_THIS_CAN_PLACE_REAL_FUTURES_ORDERS
```

## Strategy Logic

`ladder`：

- 以回放起点价或当前价为锚点。
- 每隔 `--step-pct` 生成一层做空价。
- K 线最高价触达某层时，模拟以该层价格开空。
- 止损价 = 实际开空价 × `(1 + --stop-pct)`。

`pullback`：

- 价格先触达某层，只记为提醒。
- 触发后持续记录该层之后的最高价。
- 当收盘价低于 `触发后最高价 × (1 - --confirm-pct)` 时，模拟回落确认开空。
- 止损价仍按实际开空价计算。

模拟结果中的 `MAX_LOSS` 是简化估算：

```text
阶梯层数 × 单层账户仓位 × (单层止损百分比 + 滑点/费用缓冲)
```

## Order Mapping

工具的订单计划使用 Binance USD-M Futures 常见参数：

- 开空：`SELL LIMIT`，`timeInForce=GTC`
- 止损：`BUY STOP_MARKET`
- 单向持仓模式：止损带 `reduceOnly=true`
- Hedge Mode：使用 `positionSide=SHORT`，不发送 `reduceOnly`

`--place-stops-now` 会在发送 entry 订单后立刻发送对应 stop 订单。实际账户是否接受这种顺序，取决于账户持仓模式、交易所风控和当时状态；生产化之前需要加成交监听、补单、撤单和状态校验。

## Important Parameters

- `--min-pct`：扫描时的最小 24h 涨幅，默认 `12`
- `--min-quote-volume`：最小 24h USDT 成交额，默认 `20000000`
- `--min-trades`：最小 24h 成交笔数，默认 `20000`
- `--step-pct`：阶梯间距，默认 `15`
- `--layers`：阶梯层数，默认 `5`
- `--confirm-pct`：冲高回落确认幅度，默认 `7`
- `--unit-account-pct`：模拟里每层占账户百分比，默认 `1`
- `--stop-pct`：单层止损上浮，默认 `15`
- `--friction-pct`：滑点和费用缓冲，默认 `0.4`
- `--notional`：真实订单计划里每层名义金额，默认 `20`

## References

- Binance USD-M Futures `New Order`: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order
- Binance USD-M Futures `Exchange Information`: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information
- Binance USD-M Futures `24hr Ticker`: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/24hr-Ticker-Price-Change-Statistics
- Binance USD-M Futures `Klines`: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Kline-Candlestick-Data
- Binance USD-M Futures `Funding Rate History`: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History
- Binance USD-M Futures `Open Interest Statistics`: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics
