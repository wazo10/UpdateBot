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

SEEN_FILE = "seen_posts.txt"

# ---------------------------------------------------------------------------
# Deduplication Tracking
# ---------------------------------------------------------------------------
def load_seen_urls():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen_url(url):
    if url:
        with open(SEEN_FILE, "a", encoding="utf-8") as f:
            f.write(f"{url}\n")

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

def send_discord_webhooks(webhook_url, payloads, bot_name, seen_urls):
    """Sends all valid payloads to a Discord webhook and updates seen history."""
    if not webhook_url:
        print(f"[{bot_name}] No webhook URL configured. Skipping.")
        return

    if not payloads:
        print(f"[{bot_name}] No new filtered items to send.")
        return

    headers = {"Content-Type": "application/json"}
    for payload in payloads:
        url = payload.get("url")
        if url in seen_urls:
            continue

        data = {"username": bot_name, "embeds": [payload]}
        try:
            response = requests.post(webhook_url, json=data, headers=headers)
            if response.status_code in [200, 204]:
                print(f"[{bot_name}] Sent update: {payload.get('title')}")
                save_seen_url(url)
                seen_urls.add(url)
            else:
                print(f"[{bot_name}] Webhook error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[{bot_name}] Error sending webhook: {e}")

# ---------------------------------------------------------------------------
# 1. Tech Bot (Consumer Hardware Drops Only - Multi-Feed)
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
    matches = []
    for url in TECH_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                raw_title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                if is_consumer_hardware(raw_title, summary):
                    cleaned_title = html.unescape(raw_title)
                    cleaned_summary = clean_description(summary)
                    matches.append({
                        "title": f"💻 Tech: {cleaned_title}",
                        "description": cleaned_summary[:280] + "..." if len(cleaned_summary) > 280 else cleaned_summary,
                        "url": entry.get("link", ""),
                        "color": 3447003,
                    })
        except Exception as e:
            print(f"[TechBot] Error parsing {url}: {e}")
    return matches

# ---------------------------------------------------------------------------
# 2. Sports Bot (Today's Playoff Games)
# ---------------------------------------------------------------------------
def fetch_sports_updates():
    feed_url = "https://www.espn.com/espn/rss/news"
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    matches = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
            if "playoff" in text or "playoffs" in text:
                pub_date = entry.get("published_parsed")
                if pub_date:
                    entry_date = datetime(*pub_date[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d")
                    if entry_date != today_str:
                        continue
                matches.append({
                    "title": f"⚽ Sports: {html.unescape(entry.get('title', ''))}",
                    "description": clean_description(entry.get("summary", ""))[:280],
                    "url": entry.get("link", ""),
                    "color": 15105570,
                })
    except Exception as e:
        print(f"[SportsBot] Error: {e}")
    return matches

# ---------------------------------------------------------------------------
# 3. Esports Bot (RL, VAL, LoL, CS, EWC, ENC Specific Tournaments)
# ---------------------------------------------------------------------------
ESPORTS_FEEDS = [
    "https://dotesports.com/feed",
    "https://www.hltv.org/rss/news"
]

def fetch_esports_updates():
    allowed_terms = [
        "rocket league major", "rlcs major", "rocket league world championship",
        "valorant masters", "valorant champions",
        "first stand", "mid-season invitational", "msi", "league of legends world championship", "lol worlds",
        "valve major", "intel grand slam",
        "esports world cup", "ewc", "esports nations cup", "enc"
    ]
    matches = []
    for url in ESPORTS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                if any(re.search(r"\b" + re.escape(term) + r"\b", text) for term in allowed_terms):
                    matches.append({
                        "title": f"🎮 Esports: {html.unescape(entry.get('title', ''))}",
                        "description": clean_description(entry.get("summary", ""))[:280],
                        "url": entry.get("link", ""),
                        "color": 10181046,
                    })
        except Exception as e:
            print(f"[EsportsBot] Error: {e}")
    return matches

# ---------------------------------------------------------------------------
# 4. Aviation Bot (Airfleets New Deliveries Scraper)
# ---------------------------------------------------------------------------
def fetch_aviation_updates():
    url = "https://www.airfleets.net/divers/delivery.htm"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    matches = []
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 4:
                    text_content = " ".join([c.get_text(strip=True) for c in cols])
                    if text_content and "delivery" not in text_content.lower():
                        matches.append({
                            "title": "✈️ Aviation: New Plane Delivery",
                            "description": f"Latest delivery: {text_content[:250]}",
                            "url": f"{url}#{hash(text_content)}",  # Unique anchor per delivery entry
                            "color": 3066993,
                        })
                        break
    except Exception as e:
        print(f"[AeroBot] Error: {e}")
    return matches

# ---------------------------------------------------------------------------
# 5. Research Bot (University Feeds - Published Today Only)
# ---------------------------------------------------------------------------
UNI_FEEDS = [
    "https://news.stanford.edu/feed/",
    "https://news.mit.edu/rss/feed",
    "https://news.berkeley.edu/feed/"
]

def fetch_research_updates():
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    matches = []
    for url in UNI_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                pub_date = entry.get("published_parsed")
                if pub_date:
                    entry_date = datetime(*pub_date[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d")
                    if entry_date == today_str:
                        matches.append({
                            "title": f"🔬 Research: {html.unescape(entry.get('title', ''))}",
                            "description": clean_description(entry.get("summary", ""))[:280],
                            "url": entry.get("link", ""),
                            "color": 15844367,
                        })
        except Exception as e:
            print(f"[ResearchBot] Error: {e}")
    return matches

# ---------------------------------------------------------------------------
# 6. Space Bot (Rocket Launch API)
# ---------------------------------------------------------------------------
def fetch_space_updates():
    matches = []
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
                matches.append({
                    "title": f"🚀 Space: {name}",
                    "description": desc[:280],
                    "url": f"https://www.rocketlaunch.live#{launch.get('id', name)}",
                    "color": 9807270,
                })
    except Exception as e:
        print(f"[SpaceBot] Error: {e}")
    return matches

# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    seen_urls = load_seen_urls()

    send_discord_webhooks(WEBHOOKS["tech"], process_tech_feeds(), "TechBot", seen_urls)
    send_discord_webhooks(WEBHOOKS["sports"], fetch_sports_updates(), "SportsBot", seen_urls)
    send_discord_webhooks(WEBHOOKS["esports"], fetch_esports_updates(), "EsportsBot", seen_urls)
    send_discord_webhooks(WEBHOOKS["aviation"], fetch_aviation_updates(), "AeroBot", seen_urls)
    send_discord_webhooks(WEBHOOKS["research"], fetch_research_updates(), "ResearchBot", seen_urls)
    send_discord_webhooks(WEBHOOKS["space"], fetch_space_updates(), "SpaceBot", seen_urls)
