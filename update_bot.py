from datetime import datetime, timezone
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
            print(f"[{bot_name}] Failed to send webhook: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[{bot_name}] Error sending webhook: {e}")

# ---------------------------------------------------------------------------
# 1. Tech Bot (Consumer Hardware Drops Only)
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

def is_consumer_hardware(title, summary):
    text = html.unescape(f"{title} {summary}").lower()
    hardware_targets = [
        "macbook", "core ultra", "ryzen", "radeon", "snapdragon",
        "geforce rtx", "geforce gtx", "rtx", "razer blade", "titan",
        "stealth", "raider", "crosshair", "cyborg", "vector", "pulse",
        "katana", "prestige", "rog", "zephyrus", "strix", "tuf",
        "zenbook", "vivobook", "proart", "legion", "loq", "thinkpad",
        "yoga", "alienware", "xps", "inspiron", "latitude", "omen",
        "omnibook", "victus", "envy", "surface", "galaxy book",
        "acer predator", "swift", "nitro", "framework", "laptop", "robot", "robotics"
    ]
    exclude_terms = [
        "geforce now", "stock offering", "public offering", "shares",
        "sec filing", "earnings", "quarterly", "financial", "review",
        "reviews", "hands-on", "opinion", "preview", "driver", "drivers",
        "game ready", "browser support", "patch", "update", "beta", "podcast"
    ]

    if any(term in text for term in exclude_terms):
        return False

    for hw in hardware_targets:
        if re.search(r"\b" + re.escape(hw) + r"\b", text):
            return True
    return False

def process_tech_feeds():
    for url in TECH_FEEDS:
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
                        "description": cleaned_summary[:280] + "..." if len(cleaned_summary) > 280 else cleaned_summary,
                        "url": entry.get("link", ""),
                        "color": 3447003,
                    }
        except Exception as e:
            print(f"[TechBot] Error parsing {url}: {e}")
    return None

# ---------------------------------------------------------------------------
# 2. Sports Bot (Today's Playoff Games Only)
# ---------------------------------------------------------------------------
def fetch_sports_updates():
    feed_url = "https://www.espn.com/espn/rss/news"
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
            if "playoff" in text or "playoffs" in text:
                # Basic check for today's date if pubDate exists
                pub_date = entry.get("published_parsed")
                if pub_date:
                    entry_date = datetime(*pub_date[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d")
                    if entry_date != today_str:
                        continue
                return {
                    "title": f"⚽ Sports: {html.unescape(entry.get('title', ''))}",
                    "description": clean_description(entry.get("summary", ""))[:280],
                    "url": entry.get("link", ""),
                    "color": 15105570,
                }
    except Exception as e:
        print(f"[SportsBot] Error: {e}")
    return None

# ---------------------------------------------------------------------------
# 3. Esports Bot (RL, VAL, LoL, CS, EWC, ENC Specific Tournaments Only)
# ---------------------------------------------------------------------------
ESPORTS_FEEDS = [
    "https://dotesports.com/feed",
    "https://www.hltv.org/rss/news"
]

def fetch_esports_updates():
    allowed_terms = [
        # Rocket League
        "rocket league major", "rlcs major", "rocket league world championship",
        # Valorant
        "valorant masters", "valorant champions",
        # League of Legends
        "first stand", "mid-season invitational", "msi", "league of legends world championship", "lol worlds",
        # Counter Strike
        "valve major", "intel grand slam",
        # Multi-Title Events
        "esports world cup", "ewc", "esports nations cup", "enc"
    ]
    for url in ESPORTS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                if any(re.search(r"\b" + re.escape(term) + r"\b", text) for term in allowed_terms):
                    return {
                        "title": f"🎮 Esports: {html.unescape(entry.get('title', ''))}",
                        "description": clean_description(entry.get("summary", ""))[:280],
                        "url": entry.get("link", ""),
                        "color": 10181046,
                    }
        except Exception as e:
            print(f"[EsportsBot] Error: {e}")
    return None

# ---------------------------------------------------------------------------
# 4. Aviation Bot (Airfleets New Deliveries Page Scraper)
# ---------------------------------------------------------------------------
def fetch_aviation_updates():
    url = "https://www.airfleets.net/divers/delivery.htm"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Parse main table rows for deliveries
            rows = soup.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 4:
                    text_content = " ".join([c.get_text(strip=True) for c in cols])
                    if text_content and "delivery" not in text_content.lower():
                        return {
                            "title": "✈️ Aviation: New Plane Delivery",
                            "description": f"Latest delivery: {text_content[:250]}",
                            "url": url,
                            "color": 3066993,
                        }
    except Exception as e:
        print(f"[AeroBot] Error: {e}")
    return None

# ---------------------------------------------------------------------------
# 5. Research Bot (University PR Feeds - Published Today Only)
# ---------------------------------------------------------------------------
UNI_FEEDS = [
    "https://news.stanford.edu/feed/",
    "https://news.mit.edu/rss/feed",
    "https://news.berkeley.edu/feed/"
]

def fetch_research_updates():
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for url in UNI_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                pub_date = entry.get("published_parsed")
                if pub_date:
                    entry_date = datetime(*pub_date[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d")
                    if entry_date == today_str:
                        return {
                            "title": f"🔬 Research: {html.unescape(entry.get('title', ''))}",
                            "description": clean_description(entry.get("summary", ""))[:280],
                            "url": entry.get("link", ""),
                            "color": 15844367,
                        }
        except Exception as e:
            print(f"[ResearchBot] Error: {e}")
    return None

# ---------------------------------------------------------------------------
# 6. Space Bot (Rocket Launch API via rocketlaunch.live)
# ---------------------------------------------------------------------------
def fetch_space_updates():
    url = "https://f观察.rocketlaunch.live/json/launches/next/1" # Direct API endpoint for upcoming launches
    try:
        resp = requests.get("https://fwd.rocketlaunch.live/json/launches/next/1", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            launches = data.get("result", [])
            if launches:
                launch = launches[0]
                name = launch.get("name", "Rocket Launch")
                provider = launch.get("provider", {}).get("name", "")
                vehicle = launch.get("vehicle", {}).get("name", "")
                desc = f"Launch: {name} | Provider: {provider} | Vehicle: {vehicle}"
                return {
                    "title": f"🚀 Space: {name}",
                    "description": desc[:280],
                    "url": "https://www.rocketlaunch.live",
                    "color": 9807270,
                }
    except Exception as e:
        print(f"[SpaceBot] Error: {e}")
    return None

# ---------------------------------------------------------------------------
# Main Runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    send_discord_webhook(WEBHOOKS["tech"], process_tech_feeds(), "TechBot")
    send_discord_webhook(WEBHOOKS["sports"], fetch_sports_updates(), "SportsBot")
    send_discord_webhook(WEBHOOKS["esports"], fetch_esports_updates(), "EsportsBot")
    send_discord_webhook(WEBHOOKS["aviation"], fetch_aviation_updates(), "AeroBot")
    send_discord_webhook(WEBHOOKS["research"], fetch_research_updates(), "ResearchBot")
    send_discord_webhook(WEBHOOKS["space"], fetch_space_updates(), "SpaceBot")
