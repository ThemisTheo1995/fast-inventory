import logging
import uuid

from ..base import BaseEmailProvider
from ..schemas import EmailMessage

logger = logging.getLogger(__name__)


class ConsoleEmailProvider(BaseEmailProvider):
    """Prints emails to logs instead of sending them. Useful for local dev and unit testing."""

    async def send_email(self, message: EmailMessage) -> str:
        msg_id = f"console-{uuid.uuid4()}"
        print(
            f"\n--- [MOCK EMAIL SENT] ---\n"
            f"ID: {msg_id}\n"
            f"To: {', '.join(message.recipients)}\n"
            f"Subject: {message.subject}\n"
            f"Body:\n{message.body_text}\n"
            f"Attachments: {len(message.attachments)}\n"
            f"-------------------------"
        )
        return msg_id

    async def send_bulk(self, messages: list[EmailMessage]) -> list[str]:
        return [await self.send_email(msg) for msg in messages]
