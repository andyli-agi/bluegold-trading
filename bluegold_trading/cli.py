from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import click
import structlog

from bluegold_trading.config import load_config

if TYPE_CHECKING:
    from bluegold_trading.core.engine import TradingEngine

logger = structlog.get_logger()

DEFAULT_CONFIG = "config.yaml"


def _setup_logging(verbose: bool) -> None:
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            "DEBUG" if verbose else "INFO",
        ),
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
    )


@click.group()
@click.option(
    "--config",
    "config_path",
    default=DEFAULT_CONFIG,
    type=click.Path(),
    help="Path to YAML config file.",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.pass_context
def main(ctx: click.Context, config_path: str, verbose: bool) -> None:
    """BlueGold Trading — automated trade execution."""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["verbose"] = verbose


@main.command()
@click.pass_context
def run(ctx: click.Context) -> None:
    """Fetch latest allocations and rebalance (one-shot)."""
    cfg = load_config(ctx.obj["config_path"])
    from bluegold_trading.core.engine import TradingEngine

    engine = TradingEngine.from_config(cfg)
    result = asyncio.run(engine.rebalance())

    if result.error:
        logger.error("rebalance failed", error=result.error)
        raise SystemExit(1)

    _print_rebalance_result(result, cfg.trading.dry_run)


@main.command(name="dry-run")
@click.pass_context
def dry_run(ctx: click.Context) -> None:
    """Rebalance in dry-run mode (no orders executed)."""
    cfg = load_config(ctx.obj["config_path"])
    cfg.trading.dry_run = True
    from bluegold_trading.core.engine import TradingEngine

    engine = TradingEngine.from_config(cfg)
    result = asyncio.run(engine.rebalance())

    if result.error:
        logger.error("dry-run failed", error=result.error)
        raise SystemExit(1)

    _print_rebalance_result(result, dry_run=True)


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current positions vs target allocations."""
    cfg = load_config(ctx.obj["config_path"])
    from bluegold_trading.core.engine import TradingEngine

    engine = TradingEngine.from_config(cfg)
    asyncio.run(_status(engine))


async def _status(engine: TradingEngine) -> None:
    target = await engine.allocation_source.get_target_allocations()
    account = await engine.broker.get_account()
    positions = await engine.broker.get_positions()

    pos_map: dict[str, float] = {}
    for p in positions:
        pos_map[p.symbol] = (
            p.market_value / account.portfolio_value if account.portfolio_value else 0.0
        )

    all_symbols = sorted(set(target.allocations.keys()) | set(pos_map.keys()))

    click.echo(f"\nStrategy: {target.strategy}  |  Date: {target.evaluation_date}")
    click.echo(
        f"Portfolio value: ${account.portfolio_value:,.2f}  |  Cash: ${account.cash:,.2f}"
    )
    click.echo(f"\n{'Symbol':<8} {'Target':>8} {'Current':>8} {'Drift':>8}")
    click.echo("-" * 36)
    for sym in all_symbols:
        tgt = target.allocations.get(sym, 0.0)
        cur = pos_map.get(sym, 0.0)
        drift = cur - tgt
        click.echo(f"{sym:<8} {tgt:>7.1%} {cur:>7.1%} {drift:>+7.1%}")


@main.command()
@click.pass_context
def start(ctx: click.Context) -> None:
    """Start the trading loop with the configured trigger."""
    cfg = load_config(ctx.obj["config_path"])
    from bluegold_trading.core.engine import TradingEngine
    from bluegold_trading.triggers import create_trigger

    engine = TradingEngine.from_config(cfg)
    trigger = create_trigger(cfg.trigger, engine)
    logger.info("starting trigger loop", trigger_type=cfg.trigger.type)

    try:
        asyncio.run(trigger.start())
    except KeyboardInterrupt:
        logger.info("shutting down")


def _print_rebalance_result(result, dry_run: bool) -> None:
    label = "[DRY RUN] " if dry_run else ""
    click.echo(
        f"\n{label}Rebalance complete — {len(result.orders_planned)} orders planned"
    )

    if result.skipped_symbols:
        click.echo(
            f"Skipped (within drift tolerance): {', '.join(result.skipped_symbols)}"
        )

    for order in result.orders_planned:
        click.echo(
            f"  {order.side.value.upper():<5} {order.symbol:<8} ${order.display_value:>10,.2f}"
        )

    if not dry_run and result.orders_executed:
        click.echo(f"\nExecuted {len(result.orders_executed)} orders:")
        for r in result.orders_executed:
            status = r.status
            if r.error:
                status = f"ERROR: {r.error}"
            click.echo(f"  {r.side.value.upper():<5} {r.symbol:<8} status={status}")
