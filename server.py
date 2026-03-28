import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve .env next to this file so keys load even if cwd is not the project root (e.g. uvicorn from elsewhere)
_PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(_PROJECT_ROOT / ".env")

from fastapi import BackgroundTasks, FastAPI, Form
from twilio.rest import Client

from agent import run_agent

app = FastAPI(title="WhatsApp Agent Webhook Server")

_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
ALLOWED_USERS: list[str] = os.getenv("ALLOWED_USERS", "").split(",") if os.getenv("ALLOWED_USERS") else []

twilio_client: Client | None
if _account_sid and _auth_token:
    twilio_client = Client(_account_sid, _auth_token)
else:
    twilio_client = None


def _normalize_whatsapp_addr(value: str) -> str:
    v = value.strip().lower()
    if v.startswith("whatsapp:"):
        v = v[9:]
    return v


def process_and_notify(url: str, user_number: str):
    """Background worker: Runs the agent and sends the WhatsApp reply."""
    print(f"\n[Background Worker] ⏳ Processing requested URL for {user_number}...")

    # 1. Run the agent (auto-approved: no stdin / no interactive prompts)
    result = run_agent(url, auto_approve=True)

    # 2. Format the message for WhatsApp
    if result and "error" not in result.title.lower():
        # Using WhatsApp's markdown (*bold*, _italics_)
        message_body = f"*{result.title}*\n_{result.category}_\n\n"
        for point in result.key_points:
            message_body += f"• {point}\n"
    else:
        message_body = "⚠️ Sorry, the agent encountered an error and could not summarize that URL."

    # 3. Send the message back via Twilio
    print(f"\n[System Log] 📱 Sending WhatsApp reply to {user_number}...")
    if twilio_client is None:
        print(
            "[System Log] ❌ Twilio is not configured: set TWILIO_ACCOUNT_SID and "
            f"TWILIO_AUTH_TOKEN in {_PROJECT_ROOT / '.env'} (or your environment), then restart."
        )
        return
    if not twilio_number:
        print("[System Log] ❌ TWILIO_WHATSAPP_NUMBER is not set; cannot send WhatsApp replies.")
        return
    if _normalize_whatsapp_addr(twilio_number) == _normalize_whatsapp_addr(user_number):
        print(
            "[System Log] ❌ From and To are the same (Twilio error 63031). "
            "TWILIO_WHATSAPP_NUMBER must be your Twilio WhatsApp *sender* "
            "not your personal WhatsApp number. "
            "https://www.twilio.com/docs/errors/63031"
        )
        return
    try:
        twilio_client.messages.create(
            body=message_body,
            from_=twilio_number,
            to=user_number,
        )
        print("[System Log] ✅ Message sent successfully!")
    except Exception as e:
        print(f"[System Log] ❌ Failed to send Twilio message: {e}")


@app.post("/webhook/whatsapp")
@app.post("/webhook/whatsapp/")
def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    body: str = Form(..., alias="Body", description="The URL to summarize."),
    # BKM: We MUST capture the sender's phone number to reply to them!
    sender: str = Form(..., alias="From", description="The WhatsApp number of the sender."),
):
# --- SECURITY GATE: Whitelist Check ---
    if sender not in ALLOWED_USERS:
        print(f"[Security] 🚫 Blocked unauthorized access from: {sender}")
        # BKM: We still return 200 OK so Meta doesn't think our server is broken and retry the webhook.
        return {"message": "Unauthorized user ignored."}

    # If they pass the gate, queue the agent
    background_tasks.add_task(process_and_notify, body, sender)
    return {"message": "Processing URL..."}



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
