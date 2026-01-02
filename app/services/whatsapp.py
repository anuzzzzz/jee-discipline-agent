"""
WhatsApp Service - Gupshup integration for Mahavihara.

Handles:
- Sending text messages
- Sending template messages (for >24hr window)
- Sending button messages
- Parsing incoming webhooks
- 24-hour session window tracking
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import httpx
from app.config import settings


class WhatsAppService:
    """
    WhatsApp Business API client via Gupshup.

    IMPORTANT: WhatsApp has a 24-hour messaging window.
    - Within 24 hours of user's last message: Send any text
    - After 24 hours: MUST use pre-approved template messages
    """

    BASE_URL = "https://api.gupshup.io/wa/api/v1"

    # Pre-registered template names (register these in Gupshup dashboard)
    # You'll need to create these templates and get them approved by Meta
    TEMPLATES = {
        "daily_nudge": "daily_streak_reminder",
        "streak_warning": "streak_break_warning",
        "comeback": "comeback_reminder",
        "milestone": "milestone_celebration",
    }

    @classmethod
    async def send_message(
        cls,
        phone_number: str,
        message: str,
        user_last_message_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Send a free-form WhatsApp message.

        Args:
            phone_number: User's phone (with country code, e.g., "919876543210")
            message: Text message to send
            user_last_message_at: When user last messaged us (for 24hr check)

        Returns:
            Gupshup API response

        Raises:
            ValueError: If outside 24-hour window (use template instead)
        """
        # Check 24-hour window if we have the timestamp
        if user_last_message_at:
            hours_since = (datetime.utcnow() - user_last_message_at).total_seconds() / 3600
            if hours_since > 24:
                raise ValueError(
                    f"Cannot send free-form message. {hours_since:.1f} hours since last user message. "
                    "Use send_template_message() instead."
                )

        # Check if Gupshup is configured
        if not settings.GUPSHUP_API_KEY:
            print(f"⚠️ Gupshup not configured. Would send to {phone_number}: {message[:50]}...")
            return {"status": "mock", "message": "Gupshup not configured"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{cls.BASE_URL}/msg",
                headers={
                    "apikey": settings.GUPSHUP_API_KEY,
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "channel": "whatsapp",
                    "source": settings.WHATSAPP_PHONE_NUMBER,
                    "destination": phone_number,
                    "message": json.dumps({
                        "type": "text",
                        "text": message
                    }),
                    "src.name": settings.WHATSAPP_APP_NAME
                },
                timeout=30.0
            )

            result = response.json()

            if response.status_code == 200:
                print(f"✅ Message sent to {phone_number}")
            else:
                print(f"❌ Failed to send message: {result}")

            return result

    @classmethod
    async def send_template_message(
        cls,
        phone_number: str,
        template_key: str,
        variables: List[str]
    ) -> Dict[str, Any]:
        """
        Send a pre-approved HSM template message.

        Use this for proactive messages when >24 hours since last user message.
        Templates must be registered and approved in Gupshup/Meta dashboard.

        Args:
            phone_number: User's phone number
            template_key: Key from TEMPLATES dict (e.g., "daily_nudge")
            variables: List of variable values to fill template placeholders

        Example:
            await send_template_message(
                "919876543210",
                "daily_nudge",
                ["Rahul", "5"]  # {{1}}=name, {{2}}=streak_count
            )
        """
        template_name = cls.TEMPLATES.get(template_key)
        if not template_name:
            raise ValueError(f"Unknown template key: {template_key}")

        if not settings.GUPSHUP_API_KEY:
            print(f"⚠️ Gupshup not configured. Would send template '{template_key}' to {phone_number}")
            return {"status": "mock", "message": "Gupshup not configured"}

        if not settings.GUPSHUP_NAMESPACE:
            raise ValueError("GUPSHUP_NAMESPACE not configured. Required for template messages.")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{cls.BASE_URL}/msg",
                headers={
                    "apikey": settings.GUPSHUP_API_KEY,
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "channel": "whatsapp",
                    "source": settings.WHATSAPP_PHONE_NUMBER,
                    "destination": phone_number,
                    "src.name": settings.WHATSAPP_APP_NAME,
                    "message": json.dumps({
                        "type": "template",
                        "template": {
                            "name": template_name,
                            "namespace": settings.GUPSHUP_NAMESPACE,
                            "language": {
                                "code": "en",
                                "policy": "deterministic"
                            },
                            "components": [{
                                "type": "body",
                                "parameters": [
                                    {"type": "text", "text": var}
                                    for var in variables
                                ]
                            }]
                        }
                    })
                },
                timeout=30.0
            )

            result = response.json()

            if response.status_code == 200:
                print(f"✅ Template '{template_key}' sent to {phone_number}")
            else:
                print(f"❌ Failed to send template: {result}")

            return result

    @classmethod
    async def send_button_message(
        cls,
        phone_number: str,
        body: str,
        buttons: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Send an interactive button message.

        Args:
            phone_number: User's phone number
            body: Message text
            buttons: List of button dicts [{"id": "btn1", "title": "Option 1"}, ...]
                     Max 3 buttons allowed by WhatsApp.

        Example:
            await send_button_message(
                "919876543210",
                "Ready to practice?",
                [
                    {"id": "go", "title": "GO"},
                    {"id": "later", "title": "Later"},
                    {"id": "stats", "title": "Stats"}
                ]
            )
        """
        if len(buttons) > 3:
            buttons = buttons[:3]
            print("⚠️ Truncated buttons to 3 (WhatsApp limit)")

        if not settings.GUPSHUP_API_KEY:
            print(f"⚠️ Gupshup not configured. Would send buttons to {phone_number}")
            return {"status": "mock", "message": "Gupshup not configured"}

        message = {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": btn["id"],
                                "title": btn["title"][:20]  # Max 20 chars
                            }
                        }
                        for btn in buttons
                    ]
                }
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{cls.BASE_URL}/msg",
                headers={
                    "apikey": settings.GUPSHUP_API_KEY,
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "channel": "whatsapp",
                    "source": settings.WHATSAPP_PHONE_NUMBER,
                    "destination": phone_number,
                    "message": json.dumps(message),
                    "src.name": settings.WHATSAPP_APP_NAME
                },
                timeout=30.0
            )

            return response.json()

    @classmethod
    async def send_image(
        cls,
        phone_number: str,
        image_url: str,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an image message.

        Useful for sending question images or solution diagrams.
        """
        if not settings.GUPSHUP_API_KEY:
            print(f"⚠️ Gupshup not configured. Would send image to {phone_number}")
            return {"status": "mock", "message": "Gupshup not configured"}

        message: Dict[str, Any] = {
            "type": "image",
            "originalUrl": image_url,
            "previewUrl": image_url,
        }

        if caption:
            message["caption"] = caption

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{cls.BASE_URL}/msg",
                headers={
                    "apikey": settings.GUPSHUP_API_KEY,
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "channel": "whatsapp",
                    "source": settings.WHATSAPP_PHONE_NUMBER,
                    "destination": phone_number,
                    "message": json.dumps(message),
                    "src.name": settings.WHATSAPP_APP_NAME
                },
                timeout=30.0
            )

            return response.json()


def parse_gupshup_webhook(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse incoming Gupshup webhook payload.

    Gupshup sends various event types. We only care about actual messages.

    Args:
        payload: Raw webhook JSON from Gupshup

    Returns:
        Parsed message dict, or None if not a user message

    Message types handled:
        - text: Regular text message
        - image: Photo (e.g., test paper photo)
        - button: User clicked a button
        - quick_reply: User tapped a quick reply
    """
    try:
        # Check if this is a message event
        event_type = payload.get("type")

        if event_type != "message":
            # Could be: message-event (delivery/read receipts), etc.
            return None

        message_payload = payload.get("payload", {})
        msg_type = message_payload.get("type", "text")

        result: Dict[str, Any] = {
            "message_id": message_payload.get("id"),
            "phone_number": message_payload.get("source"),  # Sender's number
            "timestamp": payload.get("timestamp"),
            "type": msg_type,
            "text": None,
            "image_url": None,
            "button_id": None,
            "button_text": None,
        }

        # Parse based on message type
        if msg_type == "text":
            result["text"] = message_payload.get("payload", {}).get("text", "")

        elif msg_type == "image":
            result["image_url"] = message_payload.get("payload", {}).get("url", "")
            result["text"] = message_payload.get("payload", {}).get("caption", "")

        elif msg_type == "button":
            # User clicked an interactive button
            result["button_id"] = message_payload.get("payload", {}).get("id", "")
            result["button_text"] = message_payload.get("payload", {}).get("title", "")
            result["text"] = result["button_text"]  # Treat as text for processing

        elif msg_type == "quick_reply":
            result["text"] = message_payload.get("payload", {}).get("text", "")

        # Validate we have minimum required fields
        if not result["phone_number"]:
            print(f"⚠️ Missing phone number in webhook: {payload}")
            return None

        return result

    except Exception as e:
        print(f"❌ Error parsing Gupshup webhook: {e}")
        print(f"   Payload: {payload}")
        return None


def can_send_freeform(last_message_at: Optional[datetime]) -> bool:
    """
    Check if we can send a free-form message (within 24-hour window).

    Args:
        last_message_at: When user last sent us a message

    Returns:
        True if within 24-hour window, False otherwise
    """
    if not last_message_at:
        return False

    hours_since = (datetime.utcnow() - last_message_at).total_seconds() / 3600
    return hours_since <= 24


def format_phone_number(phone: str) -> str:
    """
    Normalize phone number format for WhatsApp.

    WhatsApp expects: country code + number, no spaces/dashes
    Examples:
        "+91 98765 43210" -> "919876543210"
        "9876543210" -> "919876543210" (assumes India)
        "91-9876543210" -> "919876543210"
    """
    # Remove common separators
    phone = phone.replace(" ", "").replace("-", "").replace("+", "")

    # If 10 digits, assume Indian number
    if len(phone) == 10 and phone[0] in "6789":
        phone = "91" + phone

    return phone


# ==================== TESTING HELPER ====================

async def test_whatsapp_connection() -> bool:
    """Test WhatsApp configuration (doesn't actually send)."""
    print("Testing WhatsApp configuration...")

    if not settings.GUPSHUP_API_KEY:
        print("  ⚠️ GUPSHUP_API_KEY not set")
        return False

    if not settings.WHATSAPP_PHONE_NUMBER:
        print("  ⚠️ WHATSAPP_PHONE_NUMBER not set")
        return False

    print(f"  ✅ API Key: {settings.GUPSHUP_API_KEY[:10]}...")
    print(f"  ✅ Phone: {settings.WHATSAPP_PHONE_NUMBER}")
    print(f"  ✅ App Name: {settings.WHATSAPP_APP_NAME}")

    return True
