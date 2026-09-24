from pydantic import BaseModel, EmailStr, Field


class EmailAttachment(BaseModel):
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


class EmailMessage(BaseModel):
    subject: str
    recipients: list[EmailStr] = Field(..., min_length=1)
    body_text: str
    body_html: str | None = None
    sender: EmailStr | None = None
    cc: list[EmailStr] = Field(default_factory=list)
    bcc: list[EmailStr] = Field(default_factory=list)
    reply_to: EmailStr | None = None
    attachments: list[EmailAttachment] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)
