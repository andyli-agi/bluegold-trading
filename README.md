# BlueGold Trading

Automated trade execution — fetch target allocations from [BlueGold](https://bluegold.ai) and rebalance your brokerage account.

## How It Works

1. **Trigger** fires (fixed daily schedule)
2. **Fetch** target portfolio weights from the BlueGold API
3. **Compare** target weights against your current brokerage positions
4. **Execute** sell-then-buy orders to rebalance (or dry-run to preview)

## Supported Brokerages

- **Alpaca** (stocks, paper + live trading)
- More coming — the broker interface is designed to be extended (see [Adding a Broker](#adding-a-broker))

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your credentials:

```yaml
strategy:
  name: galaxy
  api_url: http://localhost:3000/api/strategies/galaxy/live
  api_access_key: "bg_live_YOUR_KEY_HERE"

broker:
  type: alpaca
  api_key: "APCA-API-KEY-ID"
  api_secret: "APCA-API-SECRET-KEY"
  paper: true

trigger:
  type: scheduled
  time: "16:05"
  timezone: America/New_York

trading:
  min_order_value: 1.0
  max_position_drift: 0.02
  dry_run: true
```

### 3. Run

```bash
# Preview what orders would be placed (no real trades)
bluegold-trading dry-run

# Execute a one-shot rebalance
bluegold-trading run

# Show current positions vs target allocations
bluegold-trading status

# Start a continuous loop (scheduled)
bluegold-trading start
```

## CLI Reference

| Command                    | Description                                     |
| -------------------------- | ----------------------------------------------- |
| `bluegold-trading run`     | One-shot: fetch allocations and rebalance       |
| `bluegold-trading dry-run` | Same as `run` but logs orders without executing |
| `bluegold-trading status`  | Display current vs target weights with drift    |
| `bluegold-trading start`   | Run continuously with the configured trigger    |

Global options: `--config PATH` (default `config.yaml`), `--verbose` / `-v`.

## Configuration

| Section    | Key                      | Description                                         |
| ---------- | ------------------------ | --------------------------------------------------- |
| `strategy` | `name`                   | Strategy identifier (e.g. `galaxy`)                 |
|            | `api_url`                | Full URL to the live allocation endpoint            |
|            | `api_access_key`         | Your BlueGold API access key                        |
| `broker`   | `type`                   | Brokerage adapter (`alpaca`)                        |
|            | `api_key` / `api_secret` | Brokerage API credentials                           |
|            | `paper`                  | `true` for paper trading, `false` for live          |
| `trigger`  | `type`                   | `scheduled` (cron)                                  |
|            | `time`                   | Execution time in HH:MM 24h format (scheduled only) |
|            | `timezone`               | IANA timezone (e.g. `America/New_York`)             |
| `trading`  | `min_order_value`        | Skip orders below this dollar amount                |
|            | `max_position_drift`     | Only rebalance if weight diff exceeds this (0-1)    |
|            | `dry_run`                | `true` to log orders without executing              |

## Adding a Broker

Create a new file in `bluegold_trading/brokers/` that implements the `Broker` interface:

```python
from bluegold_trading.brokers.base import Broker

class MyBroker(Broker):
    async def get_account(self) -> Account: ...
    async def get_positions(self) -> list[Position]: ...
    async def submit_order(self, order: Order) -> OrderResult: ...
    async def close_position(self, symbol: str) -> OrderResult: ...
```

Then register it in `bluegold_trading/core/engine.py` inside `_create_broker()`.

## Project Structure

```
bluegold_trading/
  cli.py              # Click CLI entry point
  config.py           # YAML config loading + Pydantic validation
  core/
    models.py         # Data models (Account, Position, Order, etc.)
    engine.py         # TradingEngine — rebalance pipeline
  brokers/
    base.py           # Abstract Broker interface
    alpaca.py         # Alpaca implementation (alpaca-py SDK)
  signals/
    base.py           # Abstract AllocationSource interface
    bluegold_api.py   # BlueGold live allocation fetcher
  triggers/
    base.py           # Abstract Trigger interface
    scheduled.py      # APScheduler cron trigger
```

## License

MIT
