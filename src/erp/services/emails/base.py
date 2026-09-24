from abc import ABC, abstractmethod

from .schemas import EmailMessage


class BaseEmailProvider(ABC):
    @abstractmethod
    async def send_email(self, message: EmailMessage) -> str:
        """
        Sends a single email message asynchronously.

        :param message: Validated EmailMessage payload
        :return: Provider-assigned Message ID or Tracking ID
        :raises EmailSendError: If email delivery fails
        """
        pass

    @abstractmethod
    async def send_bulk(self, messages: list[EmailMessage]) -> list[str]:
        """
        Sends multiple email messages.

        :param messages: List of EmailMessage payloads
        :return: List of Message IDs
        """
        pass
