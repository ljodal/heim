"""
Minimal async SignalR Core client for Easee streaming.

This is a lightweight implementation of the SignalR Core protocol using
websockets. It supports only the JSON protocol and WebSocket transport.

Protocol spec: https://github.com/dotnet/aspnetcore/blob/main/src/SignalR/docs/specs/HubProtocol.md
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog
from websockets import ConnectionClosed
from websockets.asyncio.client import ClientConnection, connect

logger = structlog.get_logger()

# SignalR message terminator
RECORD_SEPARATOR = "\x1e"

# Message types
TYPE_INVOCATION = 1
TYPE_STREAM_ITEM = 2
TYPE_COMPLETION = 3
TYPE_PING = 6
TYPE_CLOSE = 7


@dataclass
class SignalRMessage:
    """A parsed SignalR message."""

    type: int
    target: str | None = None
    arguments: list[Any] = field(default_factory=list)
    invocation_id: str | None = None
    error: str | None = None
    result: Any = None


class SignalRClient:
    """
    Async SignalR Core client.

    Usage:
        async with SignalRClient(hub_url, access_token) as client:
            await client.send("SubscribeWithCurrentState", charger_id, True)
            async for message in client.messages():
                if message.target == "ProductUpdate":
                    handle_update(message.arguments)
    """

    def __init__(
        self,
        hub_url: str,
        access_token: str,
        *,
        ping_interval: float = 15.0,
        reconnect_delay: float = 5.0,
    ) -> None:
        self.hub_url = hub_url.rstrip("/")
        self.access_token = access_token
        self.ping_interval = ping_interval
        self.reconnect_delay = reconnect_delay

        self._ws: ClientConnection | None = None
        self._invocation_id = 0
        self._ping_task: asyncio.Task[None] | None = None
        self._handlers: dict[str, Callable[..., Awaitable[None]]] = {}

    async def connect(self) -> None:
        """Establish connection to the SignalR hub."""
        # Step 1: Negotiate to get connection token
        connection_token = await self._negotiate()

        # Step 2: Connect WebSocket
        ws_url = f"{self.hub_url.replace('https://', 'wss://').replace('http://', 'ws://')}?id={connection_token}"
        self._ws = await connect(
            ws_url,
            additional_headers={"Authorization": f"Bearer {self.access_token}"},
        )

        # Step 3: Send handshake
        await self._send_raw({"protocol": "json", "version": 1})

        # Step 4: Receive handshake response
        response = await self._recv_raw()
        if response.get("error"):
            raise ConnectionError(f"Handshake failed: {response['error']}")

        logger.info("SignalR connected", hub=self.hub_url)

        # Start ping task
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def close(self) -> None:
        """Close the connection."""
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send(self, target: str, *arguments: Any) -> None:
        """Send an invocation message (fire-and-forget, no response expected)."""
        if not self._ws:
            raise ConnectionError("Not connected")

        # For fire-and-forget, we don't include invocationId
        message = {
            "type": TYPE_INVOCATION,
            "target": target,
            "arguments": list(arguments),
        }
        await self._send_raw(message)
        logger.debug("Sent invocation", target=target, arguments=arguments)

    async def invoke(self, target: str, *arguments: Any) -> Any:
        """Send an invocation and wait for completion response."""
        if not self._ws:
            raise ConnectionError("Not connected")

        self._invocation_id += 1
        invocation_id = str(self._invocation_id)

        message = {
            "type": TYPE_INVOCATION,
            "invocationId": invocation_id,
            "target": target,
            "arguments": list(arguments),
        }
        await self._send_raw(message)

        # Wait for completion
        async for msg in self.messages():
            if msg.type == TYPE_COMPLETION and msg.invocation_id == invocation_id:
                if msg.error:
                    raise Exception(msg.error)
                return msg.result

        raise ConnectionError("Connection closed before receiving response")

    def on(self, target: str, handler: Callable[..., Awaitable[None]]) -> None:
        """Register a handler for a specific target method."""
        self._handlers[target] = handler

    async def messages(self) -> AsyncIterator[SignalRMessage]:
        """Iterate over incoming messages."""
        if not self._ws:
            raise ConnectionError("Not connected")

        buffer = ""
        async for data in self._ws:
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            buffer += data

            # Split on record separator
            while RECORD_SEPARATOR in buffer:
                raw_message, buffer = buffer.split(RECORD_SEPARATOR, 1)
                if not raw_message:
                    continue

                try:
                    parsed = json.loads(raw_message)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON message", raw=raw_message)
                    continue

                message = self._parse_message(parsed)

                # Handle pings automatically
                if message.type == TYPE_PING:
                    continue

                # Handle close
                if message.type == TYPE_CLOSE:
                    logger.info("Server requested close", error=message.error)
                    return

                # Call registered handler if exists
                if message.target and message.target in self._handlers:
                    try:
                        await self._handlers[message.target](*message.arguments)
                    except Exception:
                        logger.exception("Handler error", target=message.target)

                yield message

    async def run_forever(self) -> None:
        """Process messages forever, calling registered handlers."""
        async for _ in self.messages():
            pass  # Handlers are called in messages()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator["SignalRClient"]:
        """Context manager for auto-reconnect."""
        while True:
            try:
                await self.connect()
                yield self
                return
            except ConnectionClosed:
                logger.warning(
                    "Connection lost, reconnecting...", delay=self.reconnect_delay
                )
                await asyncio.sleep(self.reconnect_delay)
            except Exception:
                logger.exception("Connection error, reconnecting...")
                await asyncio.sleep(self.reconnect_delay)
            finally:
                await self.close()

    async def __aenter__(self) -> "SignalRClient":
        await self.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def _negotiate(self) -> str:
        """Negotiate connection and return connection token."""
        negotiate_url = f"{self.hub_url}/negotiate?negotiateVersion=1"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                negotiate_url,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        # v1 returns connectionToken, v0 returns connectionId
        token: str = data.get("connectionToken") or data["connectionId"]
        return token

    async def _send_raw(self, message: dict[str, Any]) -> None:
        """Send a raw message with record separator."""
        if not self._ws:
            raise ConnectionError("Not connected")
        await self._ws.send(json.dumps(message) + RECORD_SEPARATOR)

    async def _recv_raw(self) -> dict[str, Any]:
        """Receive a single raw message."""
        if not self._ws:
            raise ConnectionError("Not connected")

        buffer = ""
        async for data in self._ws:
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            buffer += data
            if RECORD_SEPARATOR in buffer:
                raw_message = buffer.split(RECORD_SEPARATOR, 1)[0]
                return json.loads(raw_message)  # type: ignore[no-any-return]

        raise ConnectionError("Connection closed during receive")

    async def _ping_loop(self) -> None:
        """Send periodic pings to keep connection alive."""
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                if self._ws:
                    await self._send_raw({"type": TYPE_PING})
        except asyncio.CancelledError:
            pass

    def _parse_message(self, data: dict[str, Any]) -> SignalRMessage:
        """Parse a raw message dict into a SignalRMessage."""
        return SignalRMessage(
            type=data.get("type", 0),
            target=data.get("target"),
            arguments=data.get("arguments", []),
            invocation_id=data.get("invocationId"),
            error=data.get("error"),
            result=data.get("result"),
        )
