"""
거래소 연결 모듈 (ccxt 기반)
Binance, Upbit, Bybit 등 다양한 거래소를 통일된 인터페이스로 제공
"""
import asyncio
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

        import uuid
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
        """페이퍼트레이딩 지정가 주문 시뮬레이션 (즉시 체결 가정)"""
        # 단순화: 지정가도 즉시 체결로 처리
        return await self._paper_market_order(symbol, side, amount)

    # ──────────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────────

    def get_paper_balance_summary(self) -> Dict:
        """페이퍼트레이딩 잔고 요약"""
        return dict(self._paper_balance)

    @property
    def is_connected(self) -> bool:
        return self._exchange is not None
