"""
WebSocket 연결 관리 모듈
실시간 포트폴리오, 에이전트 로그, 거래 알림 스트리밍
"""
import json
from typing import Dict, List, Set
from fastapi import WebSocket
from loguru import logger


class WebSocketManager:
    """WebSocket 연결 풀 관리자"""

    def __init__(self):
        # 채널별 연결 관리: {"portfolio": [ws1, ws2], "agents": [...]}
        self.connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str):
        """WebSocket 연결 수락 및 채널 등록"""
        await websocket.accept()
        if channel not in self.connections:
            self.connections[channel] = set()
        self.connections[channel].add(websocket)
        logger.info(f"WebSocket 연결: channel={channel}, 총 연결={len(self.connections[channel])}")

    def disconnect(self, websocket: WebSocket, channel: str):
        """WebSocket 연결 해제"""
        if channel in self.connections:
            self.connections[channel].discard(websocket)
        logger.info(f"WebSocket 연결 해제: channel={channel}")

    async def send_to_channel(self, channel: str, data: dict):
        """특정 채널의 모든 클라이언트에게 메시지 전송"""
        if channel not in self.connections:
            return

        disconnected = set()
        for websocket in self.connections[channel].copy():
            try:
                await websocket.send_text(json.dumps(data, default=str))
            except Exception as e:
                logger.warning(f"WebSocket 전송 실패: {e}")
                disconnected.add(websocket)

        # 끊어진 연결 정리
        self.connections[channel] -= disconnected

    async def broadcast(self, data: dict):
        """모든 채널에 브로드캐스트"""
        for channel in list(self.connections.keys()):
            await self.send_to_channel(channel, data)

    def get_connection_count(self, channel: str) -> int:
        """채널별 연결 수 조회"""
        return len(self.connections.get(channel, set()))


# 전역 WebSocket 매니저 인스턴스
ws_manager = WebSocketManager()
