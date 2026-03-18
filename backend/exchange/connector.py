"""
거래소 연결 모듈 (ccxt 기반)
Binance, Upbit, Bybit 등 다양한 거래소를 통일된 인터페이스로 제공
"""
import asyncio
import time
import uuid
from typing import Optional, Dict, List, Any
from datetime import datetime
import ccxt.async_support as ccxt
from loguru import logger

from core.config import settings


class ExchangeConnector:
    """
    ccxt 기반 거래소 연결 래퍼
    모든 거래소 API 호출은 이 클래스를 통해서만 수행
    """

    def __init__(self, exchange_id: str = "binance", paper_trading: bool = True):
        self.exchange_id = exchange_id
        self.paper_trading = paper_trading
        self._exchange: Optional[ccxt.Exchange] = None

        # 페이퍼트레이딩용 가상 잔고
        self._paper_balance: Dict[str, float] = {
            "USDT": settings.PAPER_TRADING_BALANCE,
        }
        self._paper_positions: Dict[str, Dict] = {}

    async def initialize(self):
        """거래소 연결 초기화"""
        try:
            exchange_class = getattr(ccxt, self.exchange_id)

            # 거래소별 설정
            exchange_config: Dict[str, Any] = {
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }

            # API 키 설정 (실거래 시)
            if not self.paper_trading:
                if self.exchange_id == "binance":
                    exchange_config["apiKey"] = settings.BINANCE_API_KEY
                    exchange_config["secret"] = settings.BINANCE_SECRET_KEY
                    if settings.BINANCE_TESTNET:
                        exchange_config["options"]["defaultType"] = "future"
                        exchange_config["urls"] = {
                            "api": {
                                "public": "https://testnet.binance.vision/api",
                                "private": "https://testnet.binance.vision/api",
                            }
                        }

            self._exchange = exchange_class(exchange_config)
            await self._exchange.load_markets()
            logger.info(f"거래소 연결 성공: {self.exchange_id} (paper={self.paper_trading})")

        except Exception as e:
            logger.error(f"거래소 연결 실패: {self.exchange_id} - {e}")
            raise

    async def close(self):
        """거래소 연결 종료"""
        if self._exchange:
            await self._exchange.close()
            logger.info(f"거래소 연결 종료: {self.exchange_id}")

    # ──────────────────────────────────────────────
    # 시장 데이터 조회 (공개 API)
    # ──────────────────────────────────────────────

    async def fetch_ticker(self, symbol: str) -> Dict:
        """현재 시세 조회"""
        try:
            ticker = await self._exchange.fetch_ticker(symbol)
            return ticker
        except ccxt.NetworkError as e:
            logger.error(f"네트워크 오류 (fetch_ticker): {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"거래소 오류 (fetch_ticker): {e}")
            raise

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 200,
    ) -> List[List]:
        """
        OHLCV 캔들 데이터 조회
        Returns: [[timestamp, open, high, low, close, volume], ...]
        """
        try:
            ohlcv = await self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            logger.error(f"OHLCV 조회 오류 ({symbol} {timeframe}): {e}")
            raise

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """오더북 조회"""
        try:
            order_book = await self._exchange.fetch_order_book(symbol, limit)
            return order_book
        except Exception as e:
            logger.error(f"오더북 조회 오류 ({symbol}): {e}")
            raise

    # ──────────────────────────────────────────────
    # 계좌/잔고 조회
    # ──────────────────────────────────────────────

    async def fetch_balance(self) -> Dict:
        """계좌 잔고 조회"""
        if self.paper_trading:
            return self._get_paper_balance()

        try:
            balance = await self._exchange.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"잔고 조회 오류: {e}")
            raise

    def _get_paper_balance(self) -> Dict:
        """페이퍼트레이딩 가상 잔고 반환"""
        total = {}
        free = {}
        used = {}

        for currency, amount in self._paper_balance.items():
            total[currency] = amount
            free[currency] = amount
            used[currency] = 0.0

        # 포지션에서 잠긴 자산 계산
        for symbol, position in self._paper_positions.items():
            base = symbol.split("/")[0]
            if base not in total:
                total[base] = 0.0
                free[base] = 0.0
                used[base] = 0.0
            total[base] += position["amount"]
            free[base] += position["amount"]

        return {"total": total, "free": free, "used": used}

    # ──────────────────────────────────────────────
    # 주문 실행
    # ──────────────────────────────────────────────

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> Dict:
        """시장가 주문 실행"""
        if self.paper_trading:
            return await self._paper_market_order(symbol, side, amount)

        try:
            order = await self._exchange.create_market_order(symbol, side, amount)
            logger.info(f"시장가 주문 체결: {side} {amount} {symbol}")
            return order
        except Exception as e:
            logger.error(f"시장가 주문 오류: {e}")
            raise

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> Dict:
        """지정가 주문 실행"""
        if self.paper_trading:
            return await self._paper_limit_order(symbol, side, amount, price)

        try:
            order = await self._exchange.create_limit_order(symbol, side, amount, price)
            logger.info(f"지정가 주문 생성: {side} {amount} {symbol} @ {price}")
            return order
        except Exception as e:
            logger.error(f"지정가 주문 오류: {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """주문 취소"""
        if self.paper_trading:
            return {"id": order_id, "status": "cancelled"}

        try:
            result = await self._exchange.cancel_order(order_id, symbol)
            return result
        except Exception as e:
            logger.error(f"주문 취소 오류: {e}")
            raise

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """미체결 주문 목록"""
        if self.paper_trading:
            return []
        try:
            return await self._exchange.fetch_open_orders(symbol)
        except Exception as e:
            logger.error(f"미체결 주문 조회 오류: {e}")
            raise

    async def fetch_order_by_id(self, order_id: str, symbol: str) -> Dict:
        """주문 단건 조회"""
        if self.paper_trading:
            return {"id": order_id, "symbol": symbol, "status": "unknown"}
        return await self._exchange.fetch_order(order_id, symbol)

    async def fetch_my_trades(
        self, symbol: Optional[str] = None, limit: int = 50
    ) -> List[Dict]:
        """최근 체결 내역 (거래소)"""
        if self.paper_trading:
            return []
        try:
            return await self._exchange.fetch_my_trades(symbol, limit=limit)
        except Exception as e:
            logger.error(f"체결 내역 조회 오류: {e}")
            raise

    def get_market_constraints(self, symbol: str) -> Dict[str, Any]:
        """최소 수량·명목가 등 (주문 UI용)"""
        ex = self._exchange
        if not ex:
            return {}
        try:
            m = ex.market(symbol)
        except Exception:
            return {}
        lim = m.get("limits") or {}
        prec = m.get("precision") or {}
        return {
            "symbol": symbol,
            "base": m.get("base"),
            "quote": m.get("quote"),
            "amount_min": (lim.get("amount") or {}).get("min"),
            "amount_max": (lim.get("amount") or {}).get("max"),
            "cost_min": (lim.get("cost") or {}).get("min"),
            "price_min": (lim.get("price") or {}).get("min"),
            "amount_precision": prec.get("amount"),
            "price_precision": prec.get("price"),
        }

    async def create_orderbook_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        aggressive: bool = False,
    ) -> Dict[str, Any]:
        """
        호가창 기준 지정가 주문 후 체결 대기.

        - aggressive=False (기본 매매): 매수 → 최우선 매수호가(bid), 매도 → 최우선 매도호가(ask) — 유리한 쪽 대기
        - aggressive=True (청산·긴급): 매수 → 매도호가(ask), 매도 → 매수호가(bid) — 상대 호가에 맞춰 빠른 체결
        """
        if self.paper_trading:
            return await self._paper_orderbook_limit(symbol, side, amount, aggressive)

        ex = self._exchange
        ob = await self.fetch_order_book(symbol, limit=25)
        if side == "buy":
            if aggressive:
                if not ob.get("asks"):
                    raise ValueError(f"{symbol}: 매도호가 없음")
                raw_p = float(ob["asks"][0][0])
            else:
                if not ob.get("bids"):
                    raise ValueError(f"{symbol}: 매수호가 없음")
                raw_p = float(ob["bids"][0][0])
        else:
            if aggressive:
                if not ob.get("bids"):
                    raise ValueError(f"{symbol}: 매수호가 없음")
                raw_p = float(ob["bids"][0][0])
            else:
                if not ob.get("asks"):
                    raise ValueError(f"{symbol}: 매도호가 없음")
                raw_p = float(ob["asks"][0][0])

        price = float(ex.price_to_precision(symbol, raw_p))
        amt = float(ex.amount_to_precision(symbol, amount))
        if amt <= 0:
            raise ValueError(f"{symbol}: 주문 수량이 최소 단위 미만입니다.")

        market = ex.market(symbol)
        cost_min = (market.get("limits") or {}).get("cost") or {}
        min_notional = float(cost_min.get("min") or 0)
        if min_notional and amt * price < min_notional * 0.999:
            raise ValueError(
                f"{symbol}: 주문 금액이 최소 명목가({min_notional} USDT) 미만입니다."
            )

        order = await ex.create_limit_order(symbol, side, amt, price)
        oid = str(order["id"])
        max_wait = float(settings.ORDER_FILL_MAX_WAIT_SEC)
        poll = float(settings.ORDER_FILL_POLL_INTERVAL_SEC)
        deadline = time.monotonic() + max_wait
        last: Dict[str, Any] = dict(order)

        while time.monotonic() < deadline:
            await asyncio.sleep(poll)
            last = await ex.fetch_order(oid, symbol)
            filled = float(last.get("filled") or 0)
            st = (last.get("status") or "").lower()
            if st in ("closed", "canceled", "cancelled"):
                break
            if filled >= amt * 0.999:
                break

        filled = float(last.get("filled") or 0)
        st = (last.get("status") or "").lower()
        if st == "open" and filled < amt * 0.999:
            try:
                await ex.cancel_order(oid, symbol)
                last = await ex.fetch_order(oid, symbol)
                filled = float(last.get("filled") or 0)
            except Exception as e:
                logger.warning(f"{symbol} 미체결 취소 중: {e}")

        if filled <= 0:
            raise ValueError(
                f"{symbol} {side} 호가 지정가 미체결 또는 취소 (가격 {price}, 대기 {max_wait:.0f}s)"
            )

        avg = float(last.get("average") or 0) or price
        fee = last.get("fee")
        if not isinstance(fee, dict):
            fee = {"cost": 0.0, "currency": symbol.split("/")[1]}
        elif fee.get("cost") is None:
            fee = {**fee, "cost": 0.0}

        logger.info(
            f"호가 지정가 체결: {side} {filled}/{amt} {symbol} @ ~{avg} ({'공격' if aggressive else '유리'})"
        )
        return {
            "id": last.get("id", oid),
            "symbol": symbol,
            "side": side,
            "type": "limit",
            "amount": amt,
            "filled": filled,
            "price": avg,
            "average": avg,
            "cost": filled * avg,
            "fee": fee if isinstance(fee, dict) else {"cost": 0.0},
            "status": "closed",
        }

    # ──────────────────────────────────────────────
    # 페이퍼트레이딩 시뮬레이션
    # ──────────────────────────────────────────────

    async def _paper_market_order(self, symbol: str, side: str, amount: float) -> Dict:
        """페이퍼트레이딩 시장가 주문 시뮬레이션"""
        ticker = await self.fetch_ticker(symbol)
        price = ticker["last"]
        cost = amount * price
        fee = cost * 0.001  # 0.1% 수수료

        base, quote = symbol.split("/")

        if side == "buy":
            # USDT 차감, 코인 추가
            if self._paper_balance.get("USDT", 0) < cost + fee:
                raise ValueError(f"잔고 부족: 필요={cost + fee:.2f} USDT, 보유={self._paper_balance.get('USDT', 0):.2f} USDT")
            self._paper_balance["USDT"] = self._paper_balance.get("USDT", 0) - cost - fee
            self._paper_balance[base] = self._paper_balance.get(base, 0) + amount

        elif side == "sell":
            # 코인 차감, USDT 추가
            if self._paper_balance.get(base, 0) < amount:
                raise ValueError(f"코인 부족: 필요={amount}, 보유={self._paper_balance.get(base, 0)}")
            self._paper_balance[base] = self._paper_balance.get(base, 0) - amount
            self._paper_balance["USDT"] = self._paper_balance.get("USDT", 0) + cost - fee

        order = {
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "side": side,
            "type": "market",
            "amount": amount,
            "price": price,
            "cost": cost,
            "fee": {"cost": fee, "currency": quote},
            "status": "closed",
            "timestamp": datetime.utcnow().isoformat(),
            "paper": True,
        }

        logger.info(f"[PAPER] 시장가 주문 체결: {side} {amount} {symbol} @ {price:.2f}")
        return order

    async def _paper_limit_order(self, symbol: str, side: str, amount: float, price: float) -> Dict:
        """페이퍼트레이딩 지정가: 지정가로 잔고 반영"""
        base, quote = symbol.split("/")
        cost = amount * price
        fee = cost * 0.001
        if side == "buy":
            if self._paper_balance.get("USDT", 0) < cost + fee:
                raise ValueError(f"잔고 부족: 필요={cost + fee:.2f} USDT")
            self._paper_balance["USDT"] = self._paper_balance.get("USDT", 0) - cost - fee
            self._paper_balance[base] = self._paper_balance.get(base, 0) + amount
        else:
            if self._paper_balance.get(base, 0) < amount:
                raise ValueError(f"코인 부족: {base}")
            self._paper_balance[base] = self._paper_balance.get(base, 0) - amount
            self._paper_balance["USDT"] = self._paper_balance.get("USDT", 0) + cost - fee
        oid = str(uuid.uuid4())
        return {
            "id": oid,
            "symbol": symbol,
            "side": side,
            "type": "limit",
            "amount": amount,
            "filled": amount,
            "price": price,
            "average": price,
            "cost": cost,
            "fee": {"cost": fee, "currency": quote},
            "status": "closed",
        }

    async def _paper_orderbook_limit(
        self, symbol: str, side: str, amount: float, aggressive: bool
    ) -> Dict:
        ob = await self.fetch_order_book(symbol, limit=10)
        if side == "buy":
            raw = float(ob["asks" if aggressive else "bids"][0][0])
        else:
            raw = float(ob["bids" if aggressive else "asks"][0][0])
        return await self._paper_limit_order(symbol, side, amount, raw)

    # ──────────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────────

    def get_paper_balance_summary(self) -> Dict:
        """페이퍼트레이딩 잔고 요약"""
        return dict(self._paper_balance)

    @property
    def is_connected(self) -> bool:
        return self._exchange is not None
