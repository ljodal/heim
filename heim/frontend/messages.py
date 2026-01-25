"""
A simple set of utils for storing messages in cookies.

NOTE: Does not verify that the cookie has not been tampered with
"""

from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

from fastapi import Depends, Request, Response
from pydantic import BaseModel, TypeAdapter
from starlette.middleware.base import BaseHTTPMiddleware

type Level = Literal["success", "info", "notice", "warning", "error"]
CSS_CLASS_MAPPING = {
    "success": "alert alert-success",
    "info": "alert alert-info",
    "notice": "alert alert-info",
    "warning": "alert alert-warning",
    "error": "alert alert-danger",
}


class Message(BaseModel):
    level: Level
    message: str

    @property
    def css_class(self) -> str:
        return CSS_CLASS_MAPPING[self.level]


COOKIE_TYPE_ADAPTER = TypeAdapter(list[Message])


def get_messages(request: Request) -> list[Message]:
    """
    Consume all the current messages
    """

    messages: list[Message] = request.state.messages
    request.state.messages = []
    return messages


def get_messages_from_cookie(request: Request) -> list[Message]:
    """
    Decode all messages sent in the cookie
    """

    try:
        data = request.cookies.get("messages", None)
        return COOKIE_TYPE_ADAPTER.validate_json(data or "[]")
    except Exception:
        return []


class MessagesMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.messages = get_messages_from_cookie(request)
        response = await call_next(request)
        messages = request.state.messages
        if messages:
            response.set_cookie(
                "messages", COOKIE_TYPE_ADAPTER.dump_json(messages).decode()
            )
        elif "messages" in request.cookies:
            response.delete_cookie("messages")
        return response


class _Messages:
    def __init__(self, request: Request) -> None:
        self.messages = request.state.messages

    def message(self, level: Level, message: str) -> None:
        print(f"Adding message: {message}")
        self.messages.append(Message(level=level, message=message))

    def success(self, message: str) -> None:
        self.message("success", message)

    def info(self, message: str) -> None:
        self.message("info", message)

    def notice(self, message: str) -> None:
        self.message("notice", message)

    def warning(self, message: str) -> None:
        self.message("warning", message)

    def error(self, message: str) -> None:
        self.message("error", message)


Messages = Annotated[_Messages, Depends(_Messages)]
