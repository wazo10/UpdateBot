from datetime import datetime, timedelta, timezone
import html
import os
import re
import time
from bs4 import BeautifulSoup
import feedparser
import requests

# ---------------------------------------------------------------------------
# Discord Webhook Environment Variables
# ---------------------------------------------------------------------------
WEBHOOKS = {
    "general": os.getenv("WEBHOOK_GENERAL"),
    "tech": os.getenv("WEBHOOK_TECH"),
    "sports": os.getenv("WEBHOOK_SPORTS"),
    "esports": os.getenv("WEBHOOK_ESPORTS"),
    "aviation": os.getenv("WEBHOOK_AVIATION"),
    "research": os.getenv("WEBHOOK_RESEARCH"),
    "space": os.getenv("WEBHOOK_SPACE"),
}

SEEN_FILE = "seen_posts.txt"

LIQUIPEDIA_HEADERS = {
    "User-Agent": (
        "MultiBotAutomation/1.0 (https://github.com/wazo10; bot@example.com)"
    ),
    "Accept-Encoding": "gzip",
}

SCRAPER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Helper & Deduplication Functions
# ---------------------------------------------------------------------------
def send_general_heartbeat():
    webhook_url = WEBHOOKS["general"]
    message_id = os.getenv("WEBHOOK_MESSAGE_ID")

    if not webhook_url:
        print("[GeneralBot] No WEBHOOK_GENERAL configured. Skipping heartbeat.")
        return

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    payload = {
        "username": "GeneralBot",
        "embeds": [{
            "title": "⚙️ Workflow Live Status",
            "description": (
                "GitHub Actions execution active.\n"
                f"**Last Run Timestamp:** `{now_utc}`"
            ),
            "color": 3447003,
        }],
    }
    headers = {"Content-Type": "application/json"}

    try:
        if message_id:
            edit_url = f"{webhook_url}/messages/{message_id}"
            resp = requests.patch(
                edit_url, json=payload, headers=headers, timeout=10
            )
            if resp.status_code == 200:
                print("[GeneralBot] Live status updated successfully.")
            else:
                print(f"[GeneralBot] Status update error: {resp.status_code}")
        else:
            requests.post(webhook_url, json=payload, headers=headers, timeout=10)
            print("[GeneralBot] Heartbeat posted successfully.")
    except Exception as e:
        print(f"[GeneralBot] Error sending heartbeat: {e}")


def load_seen_urls():
    current_year = datetime.now(timezone.utc).strftime("%Y")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    valid_urls = set()
    updated_lines = []

    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if "|" in line:
                    entry_date, url = line.split("|", 1)
                    entry_year = entry_date.split("-")[0]
                    if entry_year == current_year:
                        valid_urls.add(url)
                        updated_lines.append(f"{entry_date}|{url}\n")
                else:
                    valid_urls.add(line)
                    updated_lines.append(f"{today_str}|{line}\n")

        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            f.writelines(updated_lines)

    return valid_urls


def save_seen_url(url):
    if url:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with open(SEEN_FILE, "a", encoding="utf-8") as f:
            f.write(f"{today_str}|{url}\n")


def clean_description(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ").strip()
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text)


def is_within_72_hours(entry):
    now = datetime.now(timezone.utc)
    pub_date = entry.get("published_parsed") or entry.get("updated_parsed")
    if pub_date:
        entry_dt = datetime(*pub_date[:6], tzinfo=timezone.utc)
        return (now - timedelta(hours=36)) <= entry_dt <= (now + timedelta(hours=36))
    return True


def send_discord_webhooks(webhook_url, payloads, bot_name, seen_urls, save_to_seen=True):
    if not webhook_url:
        print(f"[{bot_name}] No webhook URL configured. Skipping.")
        return

    if not payloads:
        print(f"[{bot_name}] No new filtered items to send.")
        return

    headers = {"Content-Type": "application/json"}
    for payload in payloads:
        url = payload.get("url")
        # If save_to_seen is True, enforce deduplication check
        if save_to_seen and url in seen_urls:
            continue

        data = {"username": bot_name, "embeds": [payload]}
        try:
            response = requests.post(webhook_url, json=data, headers=headers)
            if response.status_code in [200, 204]:
                print(f"[{bot_name}] Sent update: {payload.get('title')}")
                if save_to_seen:
                    save_seen_url(url)
                    seen_urls.add(url)
            else:
                print(
                    f"[{bot_name}] Webhook error: {response.status_code} -"
                    f" {response.text}"
                )
        except Exception as e:
            print(f"[{bot_name}] Error sending webhook: {e}")


# ---------------------------------------------------------------------------
# 1. Tech Bot (Strict Consumer Hardware Filtering)
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
    
    # Strict Hardware Product Terms
    hardware_targets = [
        "macbook",
        "core ultra",
        "ryzen",
        "radeon",
        "snapdragon",
        "geforce rtx",
        "geforce gtx",
        "rtx 50",
        "rtx 40",
        "razer blade",
        "rog zephyrus",
        "rog strix",
        "tuf gaming",
        "thinkpad",
        "alienware",
        "xps 13",
        "xps 14",
        "xps 16",
        "framework laptop",
        "gaming laptop",
    ]

    # Exclude IT, Enterprise, Security, and Firmware Blog Spam
    exclude_terms = [
        "firmware",
        "cybersecurity",
        "endpoint resilience",
        "security threat",
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
        "patch",
        "update",
        "beta",
        "podcast",
        "survey",
        "daas",
        "truscale",
        "certification",
        "sustainability",
        "partner",
        "award",
        "awards",
        "repairable",
        "services",
        "growth",
        "cloud",
        "datacenter",
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
                if not is_within_72_hours(entry):
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
# 2. Sports Bot (Title Scores + League & Game Type Line 2)
# ---------------------------------------------------------------------------
def fetch_sports_updates():
    matches = []
    now_utc = datetime.now(timezone.utc)
    dates_to_check = [
        (now_utc - timedelta(days=1)).strftime("%Y%m%d"),
        now_utc.strftime("%Y%m%d"),
        (now_utc + timedelta(days=1)).strftime("%Y%m%d"),
    ]

    espn_endpoints = [
        ("basketball", "nba"),
        ("hockey", "nhl"),
        ("baseball", "mlb"),
        ("football", "nfl"),
        ("racing", "f1"),
        ("soccer", "ger.1"),
        ("soccer", "eng.1"),
        ("soccer", "esp.1"),
        ("soccer", "ita.1"),
        ("soccer", "fra.1"),
        ("soccer", "ger.super_cup"),
        ("soccer", "eng.charity"),
        ("soccer", "esp.super_cup"),
        ("soccer", "ita.super_cup"),
        ("soccer", "uefa.champions"),
        ("soccer", "uefa.super_cup"),
    ]

    # Map ESPN integer season types to clean labels
    SEASON_TYPE_MAP = {
        1: "Preseason",
        2: "Regular Season",
        3: "Playoffs",
        4: "All-Star / Offseason",
    }

    for date_str in dates_to_check:
        for sport, league in espn_endpoints:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={date_str}"
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    league_display_name = data.get("leagues", [{}])[0].get("name", league.upper())

                    for event in data.get("events", []):
                        status = (
                            event.get("status", {})
                            .get("type", {})
                            .get("state", "")
                        )
                        if status == "post":
                            comp = event["competitions"][0]
                            competitors = comp.get("competitors", [])

                            # Extract game type (Playoffs, Regular Season, Preseason, etc.)
                            season_type_id = (
                                event.get("season", {}).get("type")
                                or comp.get("season", {}).get("type")
                            )
                            game_type = SEASON_TYPE_MAP.get(season_type_id, "Regular Season")

                            # Fallback check for special headline notes (e.g., "NBA Finals", "Wild Card Round")
                            notes = comp.get("notes", [])
                            if notes and isinstance(notes, list):
                                headline = notes[0].get("headline", "")
                                if headline and len(headline) < 30:
                                    game_type = headline

                            line_2_desc = f"{league_display_name} • {game_type}"

                            if sport == "racing":
                                drivers = sorted(
                                    competitors,
                                    key=lambda x: int(x.get("order", 99)),
                                )
                                if len(drivers) >= 3:
                                    p1 = drivers[0].get("athlete", {}).get("displayName", "P1")
                                    p2 = drivers[1].get("athlete", {}).get("displayName", "P2")
                                    p3 = drivers[2].get("athlete", {}).get("displayName", "P3")

                                    matches.append({
                                        "title": f"F1: 1. {p1} | 2. {p2} | 3. {p3}",
                                        "description": line_2_desc,
                                        "url": event.get("links", [{}])[0].get("href", "https://espn.com/f1/"),
                                        "color": 15105570,
                                    })
                            elif len(competitors) >= 2:
                                team_a = competitors[0]["team"]["displayName"]
                                score_a = competitors[0].get("score", "0")
                                team_b = competitors[1]["team"]["displayName"]
                                score_b = competitors[1].get("score", "0")

                                game_id = event.get("id")
                                game_link = (
                                    event.get("links", [{}])[0].get("href", "")
                                    or f"https://espn.com/game?gameId={game_id}"
                                )

                                matches.append({
                                    "title": f"{team_a} {score_a} - {score_b} {team_b}",
                                    "description": line_2_desc,
                                    "url": game_link,
                                    "color": 15105570,
                                })
            except Exception as e:
                print(f"[SportsBot] Error fetching {league}: {e}")

    return matches


# ---------------------------------------------------------------------------
# 3. Esports Bot (Liquipedia Match Ticker HTML DOM Parser)
# ---------------------------------------------------------------------------
def fetch_esports_updates():
    matches = []
    wikis = ["counterstrike", "valorant", "leagueoflegends", "rocketleague"]

    for wiki in wikis:
        # Fetch rendered HTML directly from main Liquipedia page for active match scores
        url = f"https://liquipedia.net/{wiki}/Main_Page"

        try:
            time.sleep(2.5)  # Enforce Liquipedia rate limit
            resp = requests.get(url, headers=LIQUIPEDIA_HEADERS, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Target all active and completed match rows
                match_rows = soup.find_all(["tr", "div"], class_=re.compile("match-filler|match-row|infobox_matches_content|brkts-matchbox"))

                for row in match_rows:
                    t1_elem = row.find(class_=re.compile("team-left|team-1|brkts-opponent-entry-left"))
                    t2_elem = row.find(class_=re.compile("team-right|team-2|brkts-opponent-entry-right"))
                    score_elem = row.find(class_=re.compile("versus|score|brkts-matchbox-score"))

                    if t1_elem and t2_elem and score_elem:
                        t1 = t1_elem.get_text(strip=True).lower()
                        t2 = t2_elem.get_text(strip=True).lower()
                        score = score_elem.get_text(strip=True).replace(":", " - ").replace("(", "").replace(")", "")

                        # Exclude unplayed games ("vs")
                        if "vs" in score.lower() or not t1 or not t2:
                            continue

                        link_elem = row.find("a", href=True)
                        match_url = (
                            f"https://liquipedia.net{link_elem['href']}"
                            if link_elem
                            else f"https://liquipedia.net/{wiki}/Main_Page#{t1}-{t2}"
                        )

                        matches.append({
                            "title": f"🎮 {t1} {score} {t2}",
                            "description": f"Liquipedia {wiki.capitalize()} Match Result",
                            "url": match_url,
                            "color": 10181046,
                        })
        except Exception as e:
            print(f"[EsportsBot] Error parsing Liquipedia Main_Page for {wiki}: {e}")

    return matches


# ---------------------------------------------------------------------------
# 4. Aviation Bot
# ---------------------------------------------------------------------------
def fetch_aviation_updates():
    url = "https://www.airfleets.net/divers/delivery.htm"
    now_utc = datetime.now(timezone.utc)
    dates_to_check = [
        (now_utc - timedelta(days=1)).strftime("%d/%m/%Y"),
        now_utc.strftime("%d/%m/%Y"),
        (now_utc + timedelta(days=1)).strftime("%d/%m/%Y"),
    ]
    matches = []

    try:
        resp = requests.get(url, headers=SCRAPER_HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 4:
                    text_content = " ".join(
                        [c.get_text(strip=True) for c in cols]
                    )
                    if any(d in text_content for d in dates_to_check) and (
                        "delivery" not in text_content.lower()
                    ):
                        matches.append({
                            "title": "✈️ Aviation: New Plane Delivery",
                            "description": f"Latest delivery: {text_content[:250]}",
                            "url": f"{url}#{hash(text_content)}",
                            "color": 3066993,
                        })
                        break
    except Exception as e:
        print(f"[AeroBot] Error: {e}")
    return matches


# ---------------------------------------------------------------------------
# 5. Research Bot (All Engineering Feeds: Columbia, UIUC, MIT, Stanford, Cal)
# ---------------------------------------------------------------------------
UNI_FEEDS = [
    ("Columbia Engineering", "https://engineering.columbia.edu/news/rss.xml"),
    ("UIUC Engineering", "https://news.illinois.edu/feed/category/16834/rss.xml"),
    ("MIT Engineering", "https://news.mit.edu/rss/school/engineering"),
    ("Stanford Engineering", "https://engineering.stanford.edu/news/rss.xml"),
    ("UC Berkeley Engineering", "https://engineering.berkeley.edu/feed/"),
]


def fetch_research_updates():
    matches = []
    for school_name, url in UNI_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if not is_within_72_hours(entry):
                    continue

                raw_title = html.unescape(entry.get("title", ""))
                summary = clean_description(entry.get("summary", ""))

                matches.append({
                    "title": f"🔬 {school_name}: {raw_title}",
                    "description": (
                        summary[:280] + "..." if len(summary) > 280 else summary
                    ),
                    "url": entry.get("link", ""),
                    "color": 15844367,
                })
        except Exception as e:
            print(f"[ResearchBot] Error parsing {school_name} feed ({url}): {e}")

    return matches


# ---------------------------------------------------------------------------
# 6. Space Bot (RocketLaunch.Live API + Safe Timestamp & Countdown)
# ---------------------------------------------------------------------------
def fetch_space_updates():
    matches = []
    url = "https://fdo.rocketlaunch.live/json/launches/next/5"
    now_utc = datetime.now(timezone.utc)

    try:
        resp = requests.get(url, headers=SCRAPER_HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            launches = data.get("result", [])

            for launch in launches:
                name = launch.get("name", "Space Launch")
                sort_date = launch.get("sort_date")

                if sort_date:
                    try:
                        # Safely cast sort_date to float before passing to fromtimestamp
                        ts = float(sort_date)
                        launch_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    except (ValueError, TypeError):
                        continue

                    diff = launch_dt - now_utc
                    total_seconds = int(diff.total_seconds())

                    # Format human-readable countdown string safely using integers
                    if total_seconds > 0:
                        days, remainder = divmod(total_seconds, 86400)
                        hours, remainder = divmod(remainder, 3600)
                        minutes = remainder // 60

                        parts = []
                        if days > 0:
                            parts.append(f"{days}d")
                        if hours > 0:
                            parts.append(f"{hours}h")
                        parts.append(f"{minutes}m")

                        countdown_str = f"In {' '.join(parts)}"
                    else:
                        countdown_str = "Launching Now / Recently Launched"

                    formatted_time = launch_dt.strftime("%b %d, %Y @ %H:%M UTC")

                    desc = (
                        launch.get("launch_description")
                        or launch.get("quicktext")
                        or "Scheduled orbital rocket launch."
                    )

                    # Direct working canonical slug link
                    slug = launch.get("slug", "")
                    web_url = (
                        f"https://www.rocketlaunch.live/launch/{slug}"
                        if slug
                        else "https://www.rocketlaunch.live/"
                    )

                    matches.append({
                        "title": f"🚀 Space: {name}",
                        "description": (
                            f"**Time Until Launch:** `{countdown_str}`\n"
                            f"**Scheduled:** `{formatted_time}`\n\n"
                            f"{desc[:250]}"
                        ),
                        "url": web_url,
                        "color": 9807270,
                    })
    except Exception as e:
        print(f"[SpaceBot] Error querying RocketLaunch.Live API: {e}")

    return matches


# ---------------------------------------------------------------------------
# Main Execution Loop
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    send_general_heartbeat()

    seen_urls = load_seen_urls()

# Standard bots write to seen_posts.txt
    send_discord_webhooks(WEBHOOKS["tech"], process_tech_feeds(), "TechBot", seen_urls)
    send_discord_webhooks(WEBHOOKS["sports"], fetch_sports_updates(), "SportsBot", seen_urls)
    send_discord_webhooks(WEBHOOKS["aviation"], fetch_aviation_updates(), "AeroBot", seen_urls)
    send_discord_webhooks(WEBHOOKS["research"], fetch_research_updates(), "ResearchBot", seen_urls)

    # SpaceBot bypasses seen_posts.txt to keep launch countdowns updating live
    send_discord_webhooks(WEBHOOKS["space"], fetch_space_updates(), "SpaceBot", seen_urls, save_to_seen=False)
