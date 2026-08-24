from datetime import datetime, timedelta, timezone
import html
import os
import re
from bs4 import BeautifulSoup
import feedparser
import requests
import json
import time

# ---------------------------------------------------------------------------
# Environment Variables & Configurations
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

SCRAPER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# General Bot & Utility Logic
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


def is_recent(entry):
    now = datetime.now(timezone.utc)
    pub_date = entry.get("published_parsed") or entry.get("updated_parsed")
    if pub_date:
        entry_dt = datetime(*pub_date[:6], tzinfo=timezone.utc)
        return (now - entry_dt) <= timedelta(hours=72)
    return True


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
                if not is_recent(entry):
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
# 2. Sports Bot (No Title Emojis + Clean League Description)
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
                                        "description": league_display_name,
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
                                    "description": league_display_name,
                                    "url": game_link,
                                    "color": 15105570,
                                })
            except Exception as e:
                print(f"[SportsBot] Error fetching {league}: {e}")

    return matches


import time

# ---------------------------------------------------------------------------
# 3. Esports Bot (Liquipedia DOM Scorebox Engine via RecentChanges)
# ---------------------------------------------------------------------------
def fetch_esports_updates():
    matches = []
    wikis = ["counterstrike", "valorant", "leagueoflegends", "rocketleague"]

    for wiki in wikis:
        api_url = f"https://liquipedia.net/{wiki}/api.php"

        # 1. Fetch recently updated tournament pages
        params_rc = {
            "action": "query",
            "list": "recentchanges",
            "rcnamespace": "0",
            "rclimit": "20",
            "format": "json"
        }

        try:
            time.sleep(2.5)  # Enforce Liquipedia 2-second rate limit
            resp = requests.get(api_url, params=params_rc, headers=LIQUIPEDIA_HEADERS, timeout=10)
            
            if resp.status_code == 200:
                rc_data = resp.json()
                changes = rc_data.get("query", {}).get("recentchanges", [])

                page_titles = set()
                for c in changes:
                    title = c.get("title", "")
                    # Filter out user pages, modules, or templates
                    if not any(title.startswith(p) for p in ["User:", "Template:", "Module:", "Liquipedia:", "User talk:"]):
                        page_titles.add(title)

                # 2. Parse Wikitext for the active updated tournament pages
                for page_title in list(page_titles)[:3]:
                    time.sleep(2.5)
                    parse_params = {
                        "action": "parse",
                        "page": page_title,
                        "prop": "text",
                        "format": "json"
                    }

                    p_resp = requests.get(api_url, params=parse_params, headers=LIQUIPEDIA_HEADERS, timeout=10)
                    if p_resp.status_code == 200:
                        p_data = p_resp.json()
                        raw_html = p_data.get("parse", {}).get("text", {}).get("*", "")

                        if not raw_html:
                            continue

                        soup = BeautifulSoup(raw_html, "html.parser")
                        # Target all bracket game cells and score boxes
                        match_cells = soup.find_all(["div", "tr"], class_=re.compile("brkts-matchbox|match-row|wikitable"))

                        for cell in match_cells:
                            t1_elem = cell.find(class_=re.compile("team-left|team-1|brkts-opponent-entry-left|brkts-matchbox-opponent-name"))
                            t2_elem = cell.find(class_=re.compile("team-right|team-2|brkts-opponent-entry-right|brkts-matchbox-opponent-name"))
                            score_elem = cell.find(class_=re.compile("versus|score|brkts-matchbox-score"))

                            if t1_elem and t2_elem and score_elem:
                                t1 = t1_elem.get_text(strip=True).lower()
                                t2 = t2_elem.get_text(strip=True).lower()
                                score = score_elem.get_text(strip=True).replace(":", " - ").replace("(", "").replace(")", "")

                                # Skip unplayed matches ("vs") or blank entries
                                if "vs" in score.lower() or not t1 or not t2:
                                    continue

                                match_url = f"https://liquipedia.net/{wiki}/{page_title.replace(' ', '_')}#{t1}-{t2}-{score}"

                                matches.append({
                                    "title": f"🎮 {t1} {score} {t2}",
                                    "description": f"{page_title}\nFinal Score",
                                    "url": match_url,
                                    "color": 10181046,
                                })
        except Exception as e:
            print(f"[EsportsBot] Error parsing Liquipedia for {wiki}: {e}")

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
                if not is_recent(entry):
                    continue

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
# 6. Space Bot (24-Hour Strict Launch Window + Human Web Links)
# ---------------------------------------------------------------------------
def fetch_space_updates():
    matches = []
    url = "https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=10"
    now_utc = datetime.now(timezone.utc)

    try:
        resp = requests.get(url, headers=SCRAPER_HEADERS, timeout=25)
        if resp.status_code == 200:
            data = resp.json()
            launches = data.get("results", [])

            for launch in launches:
                name = launch.get("name", "Space Launch")
                net_str = launch.get("net", "")

                if net_str:
                    # Parse ISO timestamp and calculate time until launch
                    launch_dt = datetime.fromisoformat(
                        net_str.replace("Z", "+00:00")
                    )
                    time_diff = launch_dt - now_utc

                    # Strict Filter: Only launches within the next 24 hours (or past 2 hours)
                    if timedelta(hours=-2) <= time_diff <= timedelta(hours=24):
                        mission = launch.get("mission", {}) or {}
                        desc = mission.get(
                            "description", "Scheduled orbital rocket launch."
                        )

                        # Clean web link instead of raw API URL
                        launch_slug = launch.get("slug", "")
                        web_url = (
                            f"https://nextspaceflight.com/launches/details/{launch.get('id')}"
                            if launch.get("id")
                            else "https://nextspaceflight.com/"
                        )

                        matches.append({
                            "title": f"🚀 Space: {name}",
                            "description": (
                                f"NET Launch:"
                                f" {launch_dt.strftime('%b %d, %H:%M UTC')}\n{desc[:250]}"
                            ),
                            "url": web_url,
                            "color": 9807270,
                        })
    except Exception as e:
        print(f"[SpaceBot] Error querying Launch Library API: {e}")

    return matches

LIQUIPEDIA_HEADERS = {
    "User-Agent": (
        "MultiBotAutomation/1.0 (https://github.com/wazo10; bot@example.com)"
    ),
    "Accept-Encoding": "gzip",
}

def debug_liquipedia():
    print("=== 1. DEBUGGING CARGO MATCH2 TABLE ===")
    api_url = "https://liquipedia.net/counterstrike/api.php"
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Raw Query on Match2
    params_cargo = {
        "action": "cargoquery",
        "tables": "Match2",
        "fields": "match2id, opponent1, opponent2, opponent1score, opponent2score, tournament, page, winner, date",
        "limit": "5",
        "format": "json"
    }

    try:
        r = requests.get(api_url, params=params_cargo, headers=LIQUIPEDIA_HEADERS, timeout=10)
        print("Cargo Raw Response Status:", r.status_code)
        if r.status_code == 200:
            data = r.json()
            print("Cargo Results Count:", len(data.get("cargoquery", [])))
            print("Cargo First 2 Sample Entries:")
            print(json.dumps(data.get("cargoquery", [])[:2], indent=2))
    except Exception as e:
        print("Cargo Query Failed:", e)

    print("\n=== 2. DEBUGGING MATCH2OPPONENT JOIN ===")
    params_join = {
        "action": "cargoquery",
        "tables": "Match2=m, Match2opponent=m2o1, Match2opponent=m2o2",
        "join_on": "m.match2id=m2o1.match2id AND m2o1.match2opponentid='1', m.match2id=m2o2.match2id AND m2o2.match2opponentid='2'",
        "fields": "m.match2id, m.page, m.tournament, m2o1.name=team1, m2o1.score=score1, m2o2.name=team2, m2o2.score=score2",
        "limit": "5",
        "format": "json"
    }

    try:
        r = requests.get(api_url, params=params_join, headers=LIQUIPEDIA_HEADERS, timeout=10)
        print("JOIN Response Status:", r.status_code)
        if r.status_code == 200:
            data = r.json()
            print("JOIN Results Count:", len(data.get("cargoquery", [])))
            print("JOIN First 2 Sample Entries:")
            print(json.dumps(data.get("cargoquery", [])[:2], indent=2))
    except Exception as e:
        print("JOIN Query Failed:", e)

    print("\n=== 3. DEBUGGING RECENT CHANGES API ===")
    params_rc = {
        "action": "query",
        "list": "recentchanges",
        "rcnamespace": "0",
        "rclimit": "10",
        "format": "json"
    }

    try:
        r = requests.get(api_url, params=params_rc, headers=LIQUIPEDIA_HEADERS, timeout=10)
        print("RecentChanges Response Status:", r.status_code)
        if r.status_code == 200:
            data = r.json()
            changes = data.get("query", {}).get("recentchanges", [])
            print("RecentChanges Count:", len(changes))
            for c in changes[:5]:
                print(f" - Title: {c.get('title')}")
    except Exception as e:
        print("RecentChanges Failed:", e)

# ---------------------------------------------------------------------------
# Main Workflow Execution Loop
# ---------------------------------------------------------------------------
if __name__ == "__main__":
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
    debug_liquipedia()
