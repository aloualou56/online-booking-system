"""
Custom email backend using Resend API.
"""
import logging
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings
import resend

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """Email backend that uses Resend API for sending emails."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        resend.api_key = settings.RESEND_API_KEY

    def send_messages(self, email_messages):
        """
        Send one or more EmailMessage objects and return the number of email
        messages sent.
        """
        if not email_messages:
            return 0

        num_sent = 0
        for message in email_messages:
            try:
                # Get sender email
                from_email = message.from_email or settings.DEFAULT_FROM_EMAIL

                # Get recipients
                to_emails = message.to

                # Prepare email data
                params = {
                    "from": from_email,
                    "to": to_emails,
                    "subject": message.subject,
                }

                body_text = message.body or ""
                body_html = ""

                # EmailMultiAlternatives stores html in alternatives, not content_subtype.
                alternatives = getattr(message, "alternatives", None) or []
                for alt in alternatives:
                    if isinstance(alt, (list, tuple)) and len(alt) >= 2 and alt[1] == "text/html":
                        body_html = alt[0] or ""
                        break

                # For EmailMessage with html subtype, body itself is html.
                if message.content_subtype == 'html' and body_text:
                    body_html = body_text

                # Resend requires at least one non-empty body field.
                if body_html:
                    params["html"] = body_html
                if body_text:
                    params["text"] = body_text

                if not body_html and not body_text:
                    logger.warning("Skipping email without body content: subject=%s to=%s", message.subject, to_emails)
                    continue

                # Add CC and BCC if present
                if message.cc:
                    params["cc"] = message.cc
                if message.bcc:
                    params["bcc"] = message.bcc

                # Add reply-to if present
                if message.reply_to:
                    params["reply_to"] = message.reply_to

                # Send via Resend
                resend.Emails.send(params)
                num_sent += 1

            except Exception as e:
                logger.exception(f"Failed to send email via Resend: {e}")
                if not self.fail_silently:
                    raise

        return num_sent
