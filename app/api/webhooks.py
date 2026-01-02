"""
WhatsApp Webhook Handler for Mahavihara.

Gupshup calls this endpoint when a user sends a message.

CRITICAL: Process inline, not in background tasks!
Cloud Run can kill the container after response is sent.
"""

from fastapi import APIRouter, Request, HTTPException, Query
from typing import Optional

from app.config import settings
from app.services.whatsapp import WhatsAppService, parse_gupshup_webhook
from app.agent.router import process_message

router = APIRouter()


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Main webhook for incoming WhatsApp messages.

    Called by Gupshup when user sends a message.

    Flow:
    1. Parse incoming payload
    2. Process message through agent
    3. Send response back to user
    4. Return 200 OK to Gupshup

    IMPORTANT: We process inline (not background) because
    Cloud Run may kill container after HTTP response.
    """
    try:
        # Parse raw payload
        payload = await request.json()

        # Log for debugging (remove in production)
        print(f"Webhook received: {payload.get('type', 'unknown')}")

        # Parse Gupshup format
        message_data = parse_gupshup_webhook(payload)

        if not message_data:
            # Not a user message (could be delivery receipt, etc.)
            return {"status": "ignored", "reason": "not a user message"}

        print(f"Message from {message_data['phone_number']}: {message_data.get('text', '[image]')[:50]}")

        # Process message through agent
        response = await process_message(
            phone_number=message_data["phone_number"],
            message_text=message_data.get("text"),
            image_url=message_data.get("image_url"),
            whatsapp_message_id=message_data.get("message_id")
        )

        # Send response back to user
        if response:
            await WhatsAppService.send_message(
                phone_number=message_data["phone_number"],
                message=response
            )

        return {"status": "ok"}

    except Exception as e:
        print(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()

        # Still return 200 to prevent Gupshup retries
        # Log the error for debugging
        return {"status": "error", "message": str(e)}


@router.get("/webhook/whatsapp")
async def whatsapp_webhook_verify(
    request: Request,
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge")
):
    """
    Webhook verification endpoint.

    Meta/Gupshup calls this to verify webhook ownership.
    Must return the challenge string if token matches.
    """
    print(f"Webhook verification: mode={hub_mode}, token={hub_verify_token}")

    if hub_mode == "subscribe" and hub_verify_token == settings.WEBHOOK_VERIFY_TOKEN:
        print("Webhook verified!")
        return int(hub_challenge) if hub_challenge else "OK"

    print("Webhook verification failed")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/test")
async def test_webhook(request: Request):
    """
    Test endpoint for local development.

    Send test messages without going through Gupshup.

    Example:
        curl -X POST http://localhost:8000/api/webhook/test \
             -H "Content-Type: application/json" \
             -d '{"phone": "919999999999", "message": "Hi"}'
    """
    data = await request.json()

    phone = data.get("phone", "919999999999")
    message = data.get("message", "Hi")
    image_url = data.get("image_url")

    print(f"Test message: {phone} -> {message}")

    response = await process_message(
        phone_number=phone,
        message_text=message,
        image_url=image_url
    )

    return {
        "status": "ok",
        "input": {"phone": phone, "message": message},
        "response": response
    }
