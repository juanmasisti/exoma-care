"""Port for the external chatbot. Only the question crosses this boundary."""
from typing import Protocol
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatbotReply:
    answer: str
    conversation_id: str
    kind: str


class ChatbotProvider(Protocol):
    available: bool

    async def answer(self, question: str, conversation_id: str | None) -> ChatbotReply: ...

    async def health(self) -> bool: ...


class ChatbotUnavailable(Exception):
    pass


class ChatbotFailure(Exception):
    pass


class ChatbotRateLimited(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
