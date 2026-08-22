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


# ---------------------------------------------------------------------------
# Heartbeat & Deduplication Functions
# ---------------------------------------------------------------------------
def send_general_heartbeat():
    """Sends a heartbeat notification every time GitHub Actions executes."""
    webhook_url = WEBHOOKS["general"]
    if not webhook_url:
        print("[GeneralBot] No WEBHOOK_GENERAL configured. Skipping heartbeat.")
        return

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    payload = {
        "username": "GeneralBot",
        "embeds": [{
            "title": "⚙️ Workflow Execution Heartbeat",
            "description": f"GitHub Actions successfully triggered and executed at `{now_utc}`.",
            "color": 3447003,
        }]
    }
    headers = {"Content-Type": "application/json"}
    try:
        requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        print("[GeneralBot] Heartbeat sent successfully.")
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


def is_published_today(entry):
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
                    f"[{bot_name}] Webhook error: {response.status_code} -"
                    f" {response.text}"
                )
        except Exception as e:
            print(f"[{bot_name}] Error sending webhook: {e}")


# ---------------------------------------------------------------------------
# 1. Tech Bot
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
# 2. Sports Bot (ESPN Scoreboard API - Playoffs & F1 Races/Sprints)
# ---------------------------------------------------------------------------
def fetch_sports_updates():
    matches = []
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")

    # Standard Team Sports (NBA, NHL, MLB, NFL)
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

    # Formula 1 Handling (Races & Sprints)
    f1_url = f"https://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard?dates={today_str}"
    try:
        f1_resp = requests.get(f1_url, timeout=10)
        if f1_resp.status_code == 200:
            f1_data = f1_resp.json()
            for event in f1_data.get("events", []):
                event_name = event.get("name", "Grand Prix")
                for comp in event.get("competitions", []):
                    comp_type = comp.get("type", {}).get("text", "").lower()
                    status = (
                        comp.get("status", {}).get("type", {}).get("state", "")
                    )

                    # Only process completed Main Races or Sprint Races
                    if status == "post" and (
                        "race" in comp_type or "sprint" in comp_type
                    ):
                        session_title = (
                            "Sprint Race"
                            if "sprint" in comp_type
                            else "Grand Prix"
                        )
                        competitors = comp.get("competitors", [])

                        # Sort drivers by final placement
                        drivers = sorted(
                            competitors,
                            key=lambda x: int(x.get("order", 99)),
                        )

                        if len(drivers) >= 3:
                            p1 = drivers[0].get("athlete", {}).get("displayName", "P1")
                            p2 = drivers[1].get("athlete", {}).get("displayName", "P2")
                            p3 = drivers[2].get("athlete", {}).get("displayName", "P3")

                            f1_link = (
                                event.get("links", [{}])[0].get("href", "")
                                or "https://espn.com/f1/"
                            )

                            matches.append({
                                "title": (
                                    f"🏎️ F1 {session_title}: 1. {p1} | 2."
                                    f" {p2} | 3. {p3}"
                                ),
                                "description": (
                                    f"{event_name}"
                                ),
                                "url": f1_link,
                                "color": 15105570,
                            })
    except Exception as e:
        print(f"[SportsBot] Error fetching F1 scores: {e}")

    return matches


# ---------------------------------------------------------------------------
# 3. Esports Bot
# ---------------------------------------------------------------------------
def fetch_esports_updates():
    matches = []
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    wikis = ["counterstrike", "valorant", "leagueoflegends", "rocketleague"]

    for wiki in wikis:
        api_url = f"https://liquipedia.net/{wiki}/api.php"

        params = {
            "action": "cargoquery",
            "tables": "Matches",
            "fields": (
                "opponent1, opponent2, opponent1score, opponent2score, tournament,"
                " matchgroup, date, page"
            ),
            "where": f"date LIKE '{today_str}%' AND finished = 1",
            "order_by": "date DESC",
            "limit": "50",
            "format": "json",
        }

        try:
            resp = requests.get(
                api_url, params=params, headers=LIQUIPEDIA_HEADERS, timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("cargoquery", [])

                for entry in results:
                    item = entry.get("title", {})
                    page_path = item.get("page", "").lower()
                    tournament_name = item.get("tournament", "").lower()

                    clean_context = f"{page_path} {tournament_name}".replace(
                        "_", " "
                    )

                    is_cs_major = wiki == "counterstrike" and (
                        "major" in clean_context
                        or "pgl" in clean_context
                        or "blast" in clean_context
                    )
                    is_grand_slam = (
                        wiki == "counterstrike"
                        and "grand slam" in clean_context
                    )
                    is_rlcs = wiki == "rocketleague" and (
                        "rlcs" in clean_context
                        or "championship" in clean_context
                    )
                    is_vct = wiki == "valorant" and (
                        "vct" in clean_context
                        or "masters" in clean_context
                        or "champions" in clean_context
                    )
                    is_lol = wiki == "leagueoflegends" and (
                        "worlds" in clean_context
                        or "msi" in clean_context
                        or "first stand" in clean_context
                    )
                    is_ewc_enc = (
                        "esports world cup" in clean_context
                        or "ewc" in clean_context
                        or "nations cup" in clean_context
                        or "enc" in clean_context
                    )

                    if (
                        is_cs_major
                        or is_grand_slam
                        or is_rlcs
                        or is_vct
                        or is_lol
                        or is_ewc_enc
                    ):
                        team_a = item.get("opponent1", "Team A")
                        score_a = item.get("opponent1score", "0")
                        team_b = item.get("opponent2", "Team B")
                        score_b = item.get("opponent2score", "0")

                        stage = item.get("matchgroup", "Playoffs").replace(
                            "_", " "
                        )
                        tournament = item.get("tournament", "Tournament")

                        page_clean = item.get("page", "")
                        match_url = f"https://liquipedia.net/{wiki}/{page_clean}#{team_a}-{team_b}"

                        matches.append({
                            "title": (
                                f"🎮 {team_a.lower()} {score_a} - {score_b}"
                                f" {team_b.lower()}"
                            ),
                            "description": (
                                f"{stage.lower()}\n{tournament.lower()}"
                            ),
                            "url": match_url,
                            "color": 10181046,
                        })
        except Exception as e:
            print(
                f"[EsportsBot] Error querying Liquipedia Cargo for {wiki}: {e}"
            )

    return matches


# ---------------------------------------------------------------------------
# 4. Aviation Bot
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
# 5. Research Bot
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
# 6. Space Bot
# ---------------------------------------------------------------------------
def fetch_space_updates():
    matches = []
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        resp = requests.get(
            "https://fwd.rocketlaunch.live/json/launches", timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            launches = data.get("result", [])
            for launch in launches:
                launch_date = launch.get("date_str", "")
                win_open = launch.get("win_open", "")

                is_today_launch = (
                    today_str in launch_date
                    or (win_open and win_open.startswith(today_str))
                    or "today" in launch_date.lower()
                )

                if is_today_launch:
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
    # Send execution heartbeat
    send_general_heartbeat()

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
