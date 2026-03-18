"""
스캐너 설정에 따라 고점수 종목 자동 매수 (RiskManager → Execution 파이프라인)
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from agents.market_analyzer import MarketSignal
from agents.risk_manager import RejectedSignal
from agents.strategy_agent import TradingSignal
from core.database import AsyncSessionLocal
from models.system_condition import SystemCondition
from services.pick_scanner import SymbolPickResult, analyze_symbol_df, _groups_from_config
from services.pick_scanner_config import load_pick_scanner_config


async def _fetch_df(exchange, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
    try:
        limit = min(max(50, limit), 1000)
        raw = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not raw:
            return None
        df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"])
        return df
    except Exception as e:
        logger.warning(f"{symbol} OHLCV 조회 실패: {e}")
        return None


async def run_pick_scan(
    exchange,
    cfg: Optional[Dict[str, Any]] = None,
) -> List[SymbolPickResult]:
    """
    설정의 심볼 목록에 대해 백테스트 스코어 산출.
    """
    cfg = cfg or load_pick_scanner_config()
    symbols = cfg.get("symbols") or []
    timeframe = cfg.get("timeframe") or "1d"
    candle_limit = int(cfg.get("candle_limit") or 200)
    template_key = cfg.get("template_key") or "rsi_reversal"
    condition_id = cfg.get("condition_id")

    condition_row = None
    if condition_id:
        async with AsyncSessionLocal() as session:
            condition_row = await session.get(SystemCondition, int(condition_id))
            if not condition_row:
                logger.warning(f"condition_id={condition_id} 없음, 템플릿 사용")

    buy_g, sell_g, label = _groups_from_config(template_key, condition_row)

    results: List[SymbolPickResult] = []
    for symbol in symbols:
        df = await _fetch_df(exchange, symbol, timeframe, candle_limit)
        if df is None:
            continue
        results.append(analyze_symbol_df(symbol, df, buy_g, sell_g, label))
    results.sort(key=lambda x: x.score, reverse=True)
    return results


async def execute_pick_auto_buy(force: bool = False) -> Dict[str, Any]:
    """
    auto_buy_enabled 이고 조건 충족 시 시장가 매수 시도.
    force=True: 스케줄 없이 수동 실행 시 auto_buy_enabled 무시.

    Returns: { attempted, bought, details: [...] }
    """
    from main import exchange, risk_manager_agent, portfolio_agent

    cfg = load_pick_scanner_config()
    out: Dict[str, Any] = {
        "attempted": False,
        "bought": 0,
        "skipped_reason": None,
        "details": [],
    }

    if not force and not cfg.get("auto_buy_enabled"):
        out["skipped_reason"] = "auto_buy_enabled=false"
        return out

    if exchange is None or not exchange.is_connected:
        out["skipped_reason"] = "exchange_not_ready"
        return out
    if risk_manager_agent is None or portfolio_agent is None:
        out["skipped_reason"] = "agents_not_ready"
        return out

    out["attempted"] = True
    min_score = float(cfg.get("min_score") or 60)
    require_live = bool(cfg.get("require_live_buy_signal", True))
    max_buys = int(cfg.get("max_auto_buys_per_scan") or 2)

    picks = await run_pick_scan(exchange, cfg)
    balance = portfolio_agent.portfolio.cash_usd

    bought = 0
    for p in picks:
        if bought >= max_buys:
            break
        if p.score < min_score:
            continue
        if require_live and not p.live_buy_signal:
            out["details"].append(
                {"symbol": p.symbol, "action": "skip", "reason": "live_buy_signal=false"}
            )
            continue
        if p.symbol in risk_manager_agent.open_positions:
            out["details"].append(
                {"symbol": p.symbol, "action": "skip", "reason": "already_in_position"}
            )
            continue

        try:
            ticker = await exchange.fetch_ticker(p.symbol)
            price = float(ticker.get("last") or ticker.get("close") or 0)
        except Exception as e:
            out["details"].append({"symbol": p.symbol, "action": "error", "reason": str(e)})
            continue

        if price <= 0:
            out["details"].append({"symbol": p.symbol, "action": "skip", "reason": "no_price"})
            continue

        conf = min(0.99, max(0.5, 0.45 + p.score / 180.0))
        ms = MarketSignal(
            symbol=p.symbol,
            exchange="binance",
            direction="BULLISH",
            confidence=conf,
            indicators={"pick_score": p.score, "pick_detail": p.score_detail},
            price=price,
            volume_24h=float(ticker.get("quoteVolume") or 0),
            timestamp=datetime.utcnow(),
        )
        ts = TradingSignal(
            symbol=p.symbol,
            exchange="binance",
            action="BUY",
            strategy_name="pick_scanner",
            confidence=conf,
            reasoning=f"[PickScanner] 점수 {p.score}: {p.score_detail}",
            market_signal=ms,
            indicators={"template": p.template_key},
        )

        res = await risk_manager_agent.evaluate_signal(ts, balance)
        if isinstance(res, RejectedSignal):
            out["details"].append(
                {
                    "symbol": p.symbol,
                    "action": "rejected",
                    "reason": res.reason,
                    "score": p.score,
                }
            )
        else:
            bought += 1
            balance = portfolio_agent.portfolio.cash_usd
            out["details"].append(
                {
                    "symbol": p.symbol,
                    "action": "approved",
                    "score": p.score,
                }
            )

    out["bought"] = bought
    logger.info(f"PickScanner 자동매수 완료: 승인 {bought}건")
    return out
