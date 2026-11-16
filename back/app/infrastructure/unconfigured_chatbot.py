"""Replace through dependency injection once the external contract is known."""
from app.domain.interfaces.chatbot_provider import ChatbotUnavailable


class UnconfiguredChatbot:
    available = False

    async def health(self) -> bool:
        return False

    async def answer(self, question: str, conversation_id: str | None):
        raise ChatbotUnavailable()
