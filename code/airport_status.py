import requests
import schedule
import time
import logging
from twilio.rest import Client
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("airport_status.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)
# ──────────────────────────────────────────────────────────────────────────────

# ─── CONFIG ───────────────────────────────────────────────────────────────────
AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
TWILIO_ACCOUNT_SID    = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN     = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM  = os.getenv("TWILIO_WHATSAPP_FROM")
YOUR_WHATSAPP_NUMBERS = os.getenv("YOUR_WHATSAPP_NUMBERS", "").split(",")

AIRPORT_CODE = "SHJ"  # Sharjah International Airport
# ──────────────────────────────────────────────────────────────────────────────

def get_airport_status():
    """Fetch flight stats for SHJ from AviationStack."""
    logger.info(f"Fetching flight data from AviationStack for airport: {AIRPORT_CODE}")
    url = "http://api.aviationstack.com/v1/flights"
    params = {
        "access_key": AVIATIONSTACK_API_KEY,
        "arr_iata": AIRPORT_CODE,
        "arr_scheduled": datetime.now().strftime("%Y-%m-%d")
    }

    response = requests.get(url, params=params)
    data = response.json()

    if "data" not in data:
        logger.error("AviationStack response missing 'data' field. Response: %s", data)
        return None, "Could not fetch flight data."

    flights = data["data"]
    total = len(flights)
    delayed = sum(1 for f in flights if f.get("arrival", {}).get("delay") and f["arrival"]["delay"] > 0)
    cancelled = sum(1 for f in flights if f.get("flight_status") == "cancelled")
    unknown = sum(1 for f in flights if f.get("flight_status") == "unknown")
    none = sum(1 for f in flights if f.get("flight_status") is None)
    on_time = total - delayed - cancelled - unknown - none

    avg_delay = 0
    delayed_flights = [f["arrival"]["delay"] for f in flights if f.get("arrival", {}).get("delay") and f["arrival"]["delay"] > 0]
    if delayed_flights:
        avg_delay = round(sum(delayed_flights) / len(delayed_flights))

    summary = {
        "total": total,
        "on_time": on_time,
        "delayed": delayed,
        "cancelled": cancelled,
        "unknown": unknown,
        "none": none,
        "avg_delay_min": avg_delay
    }

    logger.info(
        "Flight data fetched — Total: %d | On time: %d | Delayed: %d | Cancelled: %d | Unknown: %d | No status: %d | Avg delay: %d min",
        total, on_time, delayed, cancelled, unknown, none, avg_delay
    )
    return summary, None


def build_message(stats):
    """Build a clean WhatsApp message from flight stats."""
    now = datetime.now().strftime("%d %b %Y, %H:%M")
    msg = (
        f"✈️ *Sharjah Airport (SHJ) Status*\n"
        f"🕐 {now}\n\n"
        f"📊 *Arrivals Overview:*\n"
        f"  ✅ On time:   {stats['on_time']} flights\n"
        f"  ⏳ Delayed:   {stats['delayed']} flights\n"
        f"  ❌ Cancelled: {stats['cancelled']} flights\n"
        f"  ❓ Unknown:   {stats['unknown']} flights\n"
        f"  🚫 No Status: {stats['none']} flights\n"
    )
    return msg


def send_whatsapp(message):
    """Send a WhatsApp message via Twilio to all configured numbers."""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    for number in YOUR_WHATSAPP_NUMBERS:
        try:
            client.messages.create(
                body=message,
                from_=TWILIO_WHATSAPP_FROM,
                to=number
            )
            logger.info("WhatsApp message sent successfully to %s", number)
        except Exception as e:
            logger.error("Failed to send WhatsApp message to %s: %s", number, e)


def check_and_notify():
    """Main job: fetch status and send WhatsApp notification."""
    logger.info("Running scheduled check for %s airport status...", AIRPORT_CODE)
    stats, error = get_airport_status()

    if error:
        logger.error("Could not retrieve airport status: %s", error)
        return

    message = build_message(stats)
    send_whatsapp(message)
    logger.info("Notification cycle completed.")


# ─── SCHEDULE ─────────────────────────────────────────────────────────────────
schedule.every(12).hours.do(check_and_notify)

logger.info("SHJ Airport Bot started. Notifications scheduled every 12 hours.")
check_and_notify()

logger.info("Bot is running. Press Ctrl+C to stop.")
while True:
    schedule.run_pending()
    time.sleep(60)