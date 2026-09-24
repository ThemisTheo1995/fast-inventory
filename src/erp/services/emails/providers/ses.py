import asyncio
import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ..base import BaseEmailProvider
from ..exceptions import EmailConfigurationError, EmailSendError
from ..schemas import EmailMessage

logger = logging.getLogger(__name__)


def is_transient_aws_error(exception: BaseException) -> bool:
    """Only retry transient network or rate-limiting errors, not permanent client errors."""
    if isinstance(exception, BotoCoreError):
        return True

    if isinstance(exception, ClientError):
        error_code = exception.response.get("Error", {}).get("Code", "")
        transient_codes = {
            "Throttling",
            "ThrottlingException",
            "RequestLimitExceeded",
            "ServiceUnavailable",
            "InternalFailure",
            "InternalError",
        }
        return error_code in transient_codes

    return False


class SESEmailProvider(BaseEmailProvider):
    def __init__(
        self,
        aws_region: str,
        default_sender: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
    ) -> None:
        if not aws_region or not default_sender or not aws_access_key_id or not aws_secret_access_key:
            msg = "AWS region, keys and default sender must be provided."
            raise EmailConfigurationError(msg)

        self.default_sender = default_sender

        client_kwargs = {"region_name": aws_region}
        if aws_access_key_id and aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = aws_access_key_id
            client_kwargs["aws_secret_access_key"] = aws_secret_access_key

        self.client = boto3.client("ses", **client_kwargs)

    def _build_raw_email(self, message: EmailMessage) -> bytes:
        """Constructs a raw MIME email message to support attachments, HTML, and custom headers."""
        msg = MIMEMultipart("mixed")
        msg["Subject"] = message.subject
        msg["From"] = message.sender or self.default_sender
        msg["To"] = ", ".join(message.recipients)

        if message.cc:
            msg["Cc"] = ", ".join(message.cc)
        if message.reply_to:
            msg["Reply-To"] = message.reply_to

        # Body parts
        body_part = MIMEMultipart("alternative")
        text_part = MIMEText(message.body_text, "plain", "utf-8")
        body_part.attach(text_part)

        if message.body_html:
            html_part = MIMEText(message.body_html, "html", "utf-8")
            body_part.attach(html_part)

        msg.attach(body_part)

        # Attachment parts
        for attachment in message.attachments:
            att = MIMEApplication(attachment.content)
            att.add_header("Content-Disposition", "attachment", filename=attachment.filename)
            msg.attach(att)

        return msg.as_string().encode("utf-8")

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(is_transient_aws_error),
    )
    def _send_raw_sync(self, raw_message: bytes, destinations: list[str], tags: list[dict]) -> str:
        kwargs = {"RawMessage": {"Data": raw_message}, "Destinations": destinations}
        if tags:
            kwargs["Tags"] = tags

        response = self.client.send_raw_email(**kwargs)
        return response["MessageId"]

    async def send_email(self, message: EmailMessage) -> str:
        all_destinations = list(set(message.recipients + message.cc + message.bcc))
        raw_msg = self._build_raw_email(message)

        ses_tags = [{"Name": k, "Value": v} for k, v in message.tags.items()]

        try:
            message_id = await asyncio.to_thread(self._send_raw_sync, raw_msg, all_destinations, ses_tags)
            logger.info(f"Email successfully sent via SES. MessageId: {message_id}")

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to send email via SES: {e!s}", exc_info=True)
            msg = f"SES email sending failed: {e!s}"
            raise EmailSendError(msg, original_error=e) from e

        else:
            return message_id

    async def send_bulk(self, messages: list[EmailMessage]) -> list[str]:
        tasks = [self.send_email(msg) for msg in messages]
        return await asyncio.gather(*tasks, return_exceptions=False)
