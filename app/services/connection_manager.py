import asyncio
from typing import Set
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.active.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self.active.discard(ws)

    async def broadcast(self, message: str):
        async with self._lock:
            for ws in list(self.active):
                await ws.send_text(f"Response: {message}")