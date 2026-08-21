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
# Helper & Deduplication Functions
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


def clean_description(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ").strip()
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text)


def is_published_today(entry):
    """Strictly verifies if an RSS entry was published today (UTC)."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pub_date = entry.get("published_parsed") or entry.get("updated_parsed")
    if pub_date:
        entry_date = datetime(*pub_date[:6], tzinfo=timezone.utc).strftime(
            "%Y-%m-%d"
        )
        return entry_date == today_str
    return False


def send_discord_webhooks(webhook_url, payloads, bot_name, seen_urls):
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
                print(
                    f"[{bot_name}] Webhook error: {response.status_code} - {response.text}"
                )
        except Exception as e:
            print(f"[{bot_name}] Error sending webhook: {e}")


# ---------------------------------------------------------------------------
# 1. Tech Bot (Consumer Hardware Drops Only - Published Today)
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
        "macbook",
        "core ultra",
        "ryzen",
        "radeon",
        "snapdragon",
        "geforce rtx",
        "geforce gtx",
        "rtx",
        "razer blade",
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
        "acer predator",
        "swift",
        "nitro",
        "framework",
        "laptop",
        "robot",
        "robotics",
    ]

    exclude_terms = [
        "geforce now",
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
        "leaders",
        "survey",
        "daas",
        "truscale",
        "certification",
        "calm tech",
        "sustainability",
        "partner",
        "red dot",
        "award",
        "awards",
        "deep dive",
        "repairable",
        "services",
        "growth",
        "ecosystem",
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
                if not is_published_today(entry):
                    continue

                raw_title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                if is_consumer_hardware(raw_title, summary):
                    cleaned_title = html.unescape(raw_title)
                    cleaned_summary = clean_description(summary)
                    matches.append({
                        "title": f"💻 Tech: {cleaned_title}",
                        "description": (
                            cleaned_summary[:280] + "..."
                            if len(cleaned_summary) > 280
                            else cleaned_summary
                        ),
                        "url": entry.get("link", ""),
                        "color": 3447003,
                    })
        except Exception as e:
            print(f"[TechBot] Error parsing {url}: {e}")
    return matches


# ---------------------------------------------------------------------------
# 2. Sports Bot (ESPN Scoreboard API - Today's Completed Playoff Games)
# ---------------------------------------------------------------------------
def fetch_sports_updates():
    matches = []
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")

    leagues = [
        ("basketball", "nba"),
        ("hockey", "nhl"),
        ("baseball", "mlb"),
        ("football", "nfl"),
    ]

    for sport, league in leagues:
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={today_str}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for event in data.get("events", []):
                    season_type = event.get("season", {}).get("type", 0)
                    is_playoff = season_type == 3 or "playoff" in event.get(
                        "name", ""
                    ).lower()

                    status = (
                        event.get("status", {})
                        .get("type", {})
                        .get("state", "")
                    )

                    if is_playoff and status == "post":
                        competitors = event["competitions"][0]["competitors"]
                        team_a = competitors[0]["team"]["displayName"]
                        score_a = competitors[0]["score"]
                        team_b = competitors[1]["team"]["displayName"]
                        score_b = competitors[1]["score"]

                        game_id = event.get("id")
                        game_link = (
                            event.get("links", [{}])[0].get("href", "")
                            or f"https://espn.com/game?gameId={game_id}"
                        )

                        matches.append({
                            "title": (
                                f"⚽ Score: {team_a} {score_a} - {score_b}"
                                f" {team_b}"
                            ),
                            "description": (
                                f"Playoff Result | {league.upper()} Final Score"
                            ),
                            "url": game_link,
                            "color": 15105570,
                        })
        except Exception as e:
            print(f"[SportsBot] Error fetching {league} scores: {e}")

    return matches


# ---------------------------------------------------------------------------
# 3. Esports Bot (Match Scores - CS, Valorant, LoL, Rocket League)
# ---------------------------------------------------------------------------
ESPORTS_RESULT_FEEDS = [
    "https://www.hltv.org/rss/results",   # Counter-Strike
    "https://vlr.gg/vlr.xml",             # Valorant
    "https://lolesports.com/en-US/rss",   # League of Legends
    "https://www.octane.gg/feed.xml",     # Rocket League
]

def fetch_esports_updates():
    matches = []
    allowed_tournaments = [
        # Rocket League
        "rocket league major", "rlcs major", "rocket league world championship", "rlcs worlds",
        # Valorant
        "valorant masters", "valorant champions", "vct masters", "vct champions",
        # League of Legends
        "first stand", "mid-season invitational", "msi", "league of legends world championship", "lol worlds",
        # Counter-Strike
        "valve major", "intel grand slam",
        # Multi-Title Events
        "esports world cup", "ewc", "esports nations cup", "enc"
    ]

    for url in ESPORTS_RESULT_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if not is_published_today(entry):
                    continue

                raw_title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                text = f"{raw_title} {summary}".lower()

                # Score line verification (e.g. "Team A (2) vs (0) Team B", "Team A 2 - 0 Team B")
                has_score_pattern = (
                    re.search(r"\(\d+\)\s*vs\s*\(\d+\)", raw_title, re.IGNORECASE) or 
                    re.search(r"\b\d+\s*-\s*\d+\b", raw_title) or
                    " vs " in raw_title.lower()
                )

                if any(re.search(r"\b" + re.escape(term) + r"\b", text) for term in allowed_tournaments) or has_score_pattern:
                    cleaned_title = html.unescape(raw_title)
                    cleaned_summary = clean_description(summary)

                    matches.append({
                        "title": f"🎮 Match Result: {cleaned_title}",
                        "description": (
                            cleaned_summary[:280]
                            if cleaned_summary
                            else "Match complete."
                        ),
                        "url": entry.get("link", ""),
                        "color": 10181046,
                    })
        except Exception as e:
            print(f"[EsportsBot] Error parsing {url}: {e}")

    return matches


# ---------------------------------------------------------------------------
# 4. Aviation Bot (Airfleets New Deliveries Scraper)
# ---------------------------------------------------------------------------
def fetch_aviation_updates():
    url = "https://www.airfleets.net/divers/delivery.htm"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    today_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    matches = []
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 4:
                    text_content = " ".join(
                        [c.get_text(strip=True) for c in cols]
                    )
                    if (
                        today_str in text_content
                        and "delivery" not in text_content.lower()
                    ):
                        matches.append({
                            "title": "✈️ Aviation: New Plane Delivery",
                            "description": (
                                f"Latest delivery: {text_content[:250]}"
                            ),
                            "url": f"{url}#{hash(text_content)}",
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
    "https://news.berkeley.edu/feed/",
]


def fetch_research_updates():
    matches = []
    for url in UNI_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if not is_published_today(entry):
                    continue

                matches.append({
                    "title": (
                        f"🔬 Research: {html.unescape(entry.get('title', ''))}"
                    ),
                    "description": clean_description(
                        entry.get("summary", "")
                    )[:280],
                    "url": entry.get("link", ""),
                    "color": 15844367,
                })
        except Exception as e:
            print(f"[ResearchBot] Error: {e}")
    return matches


# ---------------------------------------------------------------------------
# 6. Space Bot (Rocket Launch API - Today's Launches Only)
# ---------------------------------------------------------------------------
def fetch_space_updates():
    matches = []
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        resp = requests.get(
            "https://fwd.rocketlaunch.live/json/launches/next/1", timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            launches = data.get("result", [])
            if launches:
                launch = launches[0]
                launch_date = launch.get("date_str", "")

                if today_str in launch_date or "today" in launch_date.lower():
                    name = launch.get("name", "Rocket Launch")
                    provider = launch.get("provider", {}).get("name", "")
                    vehicle = launch.get("vehicle", {}).get("name", "")
                    desc = (
                        f"Launch: {name} | Provider: {provider} | Vehicle:"
                        f" {vehicle}"
                    )
                    matches.append({
                        "title": f"🚀 Space: {name}",
                        "description": desc[:280],
                        "url": (
                            "https://www.rocketlaunch.live#"
                            f"{launch.get('id', name)}"
                        ),
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

    send_discord_webhooks(
        WEBHOOKS["tech"], process_tech_feeds(), "TechBot", seen_urls
    )
    send_discord_webhooks(
        WEBHOOKS["sports"], fetch_sports_updates(), "SportsBot", seen_urls
    )
    send_discord_webhooks(
        WEBHOOKS["esports"], fetch_esports_updates(), "EsportsBot", seen_urls
    )
    send_discord_webhooks(
        WEBHOOKS["aviation"], fetch_aviation_updates(), "AeroBot", seen_urls
    )
    send_discord_webhooks(
        WEBHOOKS["research"], fetch_research_updates(), "ResearchBot", seen_urls
    )
    send_discord_webhooks(
        WEBHOOKS["space"], fetch_space_updates(), "SpaceBot", seen_urls
    )
