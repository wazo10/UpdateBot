import os
import re
from bs4 import BeautifulSoup
import feedparser
import requests

# ---------------------------------------------------------------------------
# Discord Webhook Environment Variables
# ---------------------------------------------------------------------------
WEBHOOKS = {
    "tech": os.getenv("WEBHOOK_TECH"),
    "sports": os.getenv("WEBHOOK_SPORTS"),
    "esports": os.getenv("WEBHOOK_ESPORTS"),
    "aviation": os.getenv("WEBHOOK_AVIATION"),
    "research": os.getenv("WEBHOOK_RESEARCH"),
    "space": os.getenv("WEBHOOK_SPACE"),
}


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def clean_description(raw_html):
    """Strips raw HTML tags (<p>, <a>) leaving clean text."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ").strip()
    return re.sub(r"\s+", " ", text)


def send_discord_webhook(webhook_url, payload, bot_name):
    """Sends a payload to a Discord webhook if a valid URL exists."""
    if not webhook_url:
        print(f"[{bot_name}] No webhook URL configured. Skipping.")
        return

    if not payload:
        print(f"[{bot_name}] No new filtered items to send.")
        return

    headers = {"Content-Type": "application/json"}
    data = {"username": bot_name, "embeds": [payload]}

    try:
        response = requests.post(webhook_url, json=data, headers=headers)
        if response.status_code in [200, 204]:
            print(f"[{bot_name}] Successfully sent update to Discord.")
        else:
            print(
                f"[{bot_name}] Failed to send webhook: {response.status_code} - {response.text}"
            )
    except Exception as e:
        print(f"[{bot_name}] Error sending webhook: {e}")


# ---------------------------------------------------------------------------
# Tech Bot Logic
# ---------------------------------------------------------------------------
def is_consumer_hardware(title, summary):
    """Filters strictly for consumer hardware terms while blocking financials/reviews."""
    text = f"{title} {summary}".lower()

    # Your complete list of hardware target keywords
    hardware_targets = [
        "macbook",
        "core ultra",
        "ryzen",
        "radeon",
        "snapdragon",
        "geforce",
        "rtx",
        "blade",
        "titan",
        "stealth",
        "raider",
        "crosshair",
        "cyborg",
        "vector",
        "pulse",
        "katana",
        "prestige",
        "rog",
        "zephyrus",
        "strix",
        "tuf",
        "zenbook",
        "vivobook",
        "proart",
        "legion",
        "loq",
        "thinkpad",
        "yoga",
        "alienware",
        "xps",
        "inspiron",
        "latitude",
        "omen",
        "omnibook",
        "victus",
        "envy",
        "surface",
        "galaxy book",
        "predator",
        "swift",
        "nitro",
        "framework",
        "laptop",
    ]

    # Explicit exclusions (financials, stocks, reviews, previews)
    exclude_terms = [
        "stock offering",
        "public offering",
        "shares",
        "sec filing",
        "earnings",
        "quarterly",
        "financial",
        "review",
        "reviews",
        "hands-on",
        "opinion",
        "preview",
    ]

    # Block financial and review noise
    if any(term in text for term in exclude_terms):
        return False

    # Match if any targeted hardware brand/term is present
    return any(hw in text for hw in hardware_targets)


def process_tech_feed(feed_url):
    """Parses an RSS feed and returns the first matching consumer hardware item."""
    feed = feedparser.parse(feed_url)
    for entry in feed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", entry.get("description", ""))

        if is_consumer_hardware(title, summary):
            cleaned_summary = clean_description(summary)
            return {
                "title": f"💻 Tech: {title}",
                "description": (
                    cleaned_summary[:280] + "..."
                    if len(cleaned_summary) > 280
                    else cleaned_summary
                ),
                "url": entry.get("link", ""),
                "color": 3447003,
            }
    return None


# ---------------------------------------------------------------------------
# Placeholders for Other Categories (Use your existing logic if added)
# ---------------------------------------------------------------------------
def fetch_sports_updates():
    return None


def fetch_esports_updates():
    return None


def fetch_aviation_updates():
    return None


def fetch_research_updates():
    return None


def fetch_space_updates():
    return None


# ---------------------------------------------------------------------------
# Main Runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Example RSS feed source for tech updates (e.g., Verge / Ars Technica / Framework)
    TECH_RSS_URL = "https://www.theverge.com/rss/index.xml"

    # Process & Send Updates
    tech_payload = process_tech_feed(TECH_RSS_URL)
    send_discord_webhook(WEBHOOKS["tech"], tech_payload, "TechBot")

    send_discord_webhook(
        WEBHOOKS["sports"], fetch_sports_updates(), "SportsBot"
    )
    send_discord_webhook(
        WEBHOOKS["esports"], fetch_esports_updates(), "EsportsBot"
    )
    send_discord_webhook(
        WEBHOOKS["aviation"], fetch_aviation_updates(), "AeroBot"
    )
    send_discord_webhook(
        WEBHOOKS["research"], fetch_research_updates(), "ResearchBot"
    )
    send_discord_webhook(
        WEBHOOKS["space"], fetch_space_updates(), "SpaceBot"
    )
