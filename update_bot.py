import html
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
# Official PR Newsroom RSS Feeds
# ---------------------------------------------------------------------------
TECH_FEEDS = [
    "https://newsroom.apple.com/rss-feed.rss",
    "https://nvidianews.nvidia.com/rss.xml",
    "https://newsroom.intel.com/feed/",
    "https://www.qualcomm.com/news/rss",
    "https://ir.amd.com/rss/news-releases.xml",
    "https://press.razer.com/feed/",
    "https://press.asus.com/feed/",
    "https://news.lenovo.com/feed/",
    "https://www.dell.com/en-us/blog/feed/",
    "https://press.hp.com/us/en/news.rss",
    "https://news.microsoft.com/feed/",
    "https://news.samsung.com/global/feed",
    "https://news.acer.com/rss.xml",
    "https://frame.work/blog.rss",
]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def clean_description(raw_html):
    """Strips raw HTML tags and decodes entities like &#8217; to clean text."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ").strip()
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text)


def send_discord_webhook(webhook_url, payload, bot_name):
    """Sends payload to a Discord webhook."""
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
# Tech Bot Filtering Logic
# ---------------------------------------------------------------------------
def is_consumer_hardware(title, summary):
    """Matches exact consumer hardware brands using word boundaries (\b)."""
    text = html.unescape(f"{title} {summary}").lower()

    # Exact brand terms matched with word boundaries
    hardware_targets = [
        "macbook",
        "core ultra",
        "ryzen",
        "radeon",
        "snapdragon",
        "geforce rtx",
        "geforce gtx",
        "rtx",
        "blade",
        "book",
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
        "robot",
        "robotics",
    ]

    # Strictly excluded content
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
        "driver",
        "drivers",
        "game ready",
        "browser support",
        "patch",
        "update",
        "beta",
        "podcast",
    ]

    if any(term in text for term in exclude_terms):
        return False

    # Word-boundary check ensuring exact phrase matches
    for hw in hardware_targets:
        pattern = r"\b" + re.escape(hw) + r"\b"
        if re.search(pattern, text):
            return True

    return False


def process_tech_feeds(feed_urls):
    """Iterates through newsroom feeds and returns the first matching hardware drop."""
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                raw_title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))

                if is_consumer_hardware(raw_title, summary):
                    cleaned_title = html.unescape(raw_title)
                    cleaned_summary = clean_description(summary)
                    return {
                        "title": f"💻 Tech: {cleaned_title}",
                        "description": (
                            cleaned_summary[:280] + "..."
                            if len(cleaned_summary) > 280
                            else cleaned_summary
                        ),
                        "url": entry.get("link", ""),
                        "color": 3447003,
                    }
        except Exception as e:
            print(f"[TechBot] Error parsing feed {url}: {e}")
    return None


# ---------------------------------------------------------------------------
# Additional Category Handlers
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
# Main Execution Flow
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Tech Bot
    tech_payload = process_tech_feeds(TECH_FEEDS)
    send_discord_webhook(WEBHOOKS["tech"], tech_payload, "TechBot")

    # Sports Bot
    sports_payload = fetch_sports_updates()
    send_discord_webhook(WEBHOOKS["sports"], sports_payload, "SportsBot")

    # Esports Bot
    esports_payload = fetch_esports_updates()
    send_discord_webhook(WEBHOOKS["esports"], esports_payload, "EsportsBot")

    # Aviation Bot
    aviation_payload = fetch_aviation_updates()
    send_discord_webhook(WEBHOOKS["aviation"], aviation_payload, "AeroBot")

    # Research Bot
    research_payload = fetch_research_updates()
    send_discord_webhook(WEBHOOKS["research"], research_payload, "ResearchBot")

    # Space Bot
    space_payload = fetch_space_updates()
    send_discord_webhook(WEBHOOKS["space"], space_payload, "SpaceBot")
