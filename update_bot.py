from datetime import datetime, timedelta, timezone
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

SCRAPER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Helper Functions
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
    """Checks if entry falls within a 72-hour window (-24h to +24h)."""
    now = datetime.now(timezone.utc)
    pub_date = entry.get("published_parsed") or entry.get("updated_parsed")
    if pub_date:
        entry_dt = datetime(*pub_date[:6], tzinfo=timezone.utc)
        return (now - timedelta(hours=36)) <= entry_dt <= (now + timedelta(hours=36))
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
# 2. Sports Bot (72-Hour Sliding Window: Yesterday, Today, Tomorrow)
# ---------------------------------------------------------------------------
def fetch_sports_updates():
    matches = []
    now_utc = datetime.now(timezone.utc)
    dates_to_check = [
        (now_utc - timedelta(days=1)).strftime("%Y%m%d"),
        now_utc.strftime("%Y%m%d"),
        (now_utc + timedelta(days=1)).strftime("%Y%m%d"),
    ]

    espn_playoff_leagues = [
        ("basketball", "nba"),
        ("hockey", "nhl"),
        ("baseball", "mlb"),
        ("football", "nfl"),
        ("basketball", "mens-college-basketball"),
        ("hockey", "mens-college-hockey"),
        ("football", "college-football"),
        ("baseball", "college-baseball"),
        ("soccer", "usa.1"),
    ]

    for date_str in dates_to_check:
        for sport, league in espn_playoff_leagues:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={date_str}"
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    for event in data.get("events", []):
                        season_type = event.get("season", {}).get("type", 0)
                        is_playoff = (
                            season_type == 3
                            or "playoff" in event.get("name", "").lower()
                        )
                        status = (
                            event.get("status", {})
                            .get("type", {})
                            .get("state", "")
                        )

                        if is_playoff and status == "post":
                            competitors = event["competitions"][0][
                                "competitors"
                            ]
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
                                    f"Playoff Result | {league.upper()} Final"
                                    " Score"
                                ),
                                "url": game_link,
                                "color": 15105570,
                            })
            except Exception as e:
                print(f"[SportsBot] Error fetching {league}: {e}")

        # FotMob Soccer Parsing
        fotmob_url = f"https://www.fotmob.com/api/matches?date={date_str}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        try:
            fotmob_resp = requests.get(fotmob_url, headers=headers, timeout=10)
            if fotmob_resp.status_code == 200:
                fotmob_data = fotmob_resp.json()
                leagues = fotmob_data.get("leagues", [])

                for league in leagues:
                    league_name = str(league.get("name", "")).lower()

                    is_cup = any(
                        k in league_name
                        for k in [
                            "supercup",
                            "beckenbauer",
                            "pokal",
                            "cup",
                            "shield",
                            "copa",
                            "trophy",
                        ]
                    )

                    if is_cup:
                        match_list = league.get("matches", []) + league.get(
                            "primaryMatches", []
                        )
                        for match in match_list:
                            status = match.get("status", {})
                            if not isinstance(status, dict):
                                status = {}

                            is_finished = status.get(
                                "finished", False
                            ) or "ft" in str(status.get("reason", "")).lower()
                            if not is_finished:
                                continue

                            home_team = match.get("home", {}).get(
                                "name", "Home"
                            )
                            away_team = match.get("away", {}).get(
                                "name", "Away"
                            )

                            score_str = status.get("scoreStr")
                            if not score_str:
                                home_score = match.get("home", {}).get(
                                    "score", 0
                                )
                                away_score = match.get("away", {}).get(
                                    "score", 0
                                )
                                score_str = f"{home_score} - {away_score}"

                            match_id = match.get("id")
                            match_url = (
                                f"https://www.fotmob.com/matches/{match_id}"
                            )

                            matches.append({
                                "title": (
                                    f"⚽ {home_team} {score_str} {away_team}"
                                ),
                                "description": (
                                    f"{league.get('name')}\nFinal Score"
                                ),
                                "url": match_url,
                                "color": 15105570,
                            })
        except Exception as e:
            print(f"[SportsBot] Error fetching FotMob soccer scores: {e}")

    return matches


# ---------------------------------------------------------------------------
# 3. Esports Bot (Wikitext Parser - Full Ticker Match)
# ---------------------------------------------------------------------------
def fetch_esports_updates():
    matches = []
    wikis = ["counterstrike", "valorant", "leagueoflegends", "rocketleague"]

    for wiki in wikis:
        api_url = f"https://liquipedia.net/{wiki}/api.php"
        params = {
            "action": "parse",
            "page": "Liquipedia:Matches",
            "prop": "text",
            "format": "json",
        }

        try:
            resp = requests.get(
                api_url, params=params, headers=LIQUIPEDIA_HEADERS, timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_html = data.get("parse", {}).get("text", {}).get("*", "")
                if not raw_html:
                    continue

                soup = BeautifulSoup(raw_html, "html.parser")
                rows = soup.find_all(
                    ["tr", "div"],
                    class_=re.compile(
                        "match-filler|match-row|infobox_matches_content|wikitable"
                    ),
                )

                for row in rows:
                    text_content = row.get_text(separator=" ").lower()

                    is_cs_major = wiki == "counterstrike" and (
                        "major" in text_content
                        or "pgl" in text_content
                        or "blast" in text_content
                    )
                    is_grand_slam = (
                        wiki == "counterstrike"
                        and "grand slam" in text_content
                    )
                    is_rlcs = wiki == "rocketleague" and (
                        "rlcs" in text_content
                        or "championship" in text_content
                    )
                    is_vct = wiki == "valorant" and (
                        "vct" in text_content
                        or "masters" in text_content
                        or "champions" in text_content
                    )
                    is_lol = wiki == "leagueoflegends" and (
                        "worlds" in text_content
                        or "msi" in text_content
                        or "first stand" in text_content
                    )
                    is_ewc_enc = (
                        "esports world cup" in text_content
                        or "ewc" in text_content
                        or "nations cup" in text_content
                        or "enc" in text_content
                    )

                    if not (
                        is_cs_major
                        or is_grand_slam
                        or is_rlcs
                        or is_vct
                        or is_lol
                        or is_ewc_enc
                    ):
                        continue

                    team1_elem = row.find(
                        ["td", "div"], class_=re.compile("team-left|team-1")
                    )
                    team2_elem = row.find(
                        ["td", "div"], class_=re.compile("team-right|team-2")
                    )
                    score_elem = row.find(
                        ["td", "div"], class_=re.compile("versus|score")
                    )

                    if team1_elem and team2_elem and score_elem:
                        t1 = team1_elem.get_text(strip=True).lower()
                        t2 = team2_elem.get_text(strip=True).lower()
                        score = (
                            score_elem.get_text(strip=True)
                            .replace(":", " - ")
                            .replace("(", "")
                            .replace(")", "")
                        )

                        if "vs" in score.lower():
                            continue

                        link_elem = row.find("a", href=True)
                        match_url = (
                            f"https://liquipedia.net{link_elem['href']}"
                            if link_elem
                            else (
                                f"https://liquipedia.net/{wiki}/#{t1}-{t2}-{score}"
                            )
                        )

                        matches.append({
                            "title": f"🎮 {t1} {score} {t2}",
                            "description": "Esports World Cup\nFinal Score",
                            "url": match_url,
                            "color": 10181046,
                        })
        except Exception as e:
            print(f"[EsportsBot] Error parsing Wikitext for {wiki}: {e}")

    return matches


# ---------------------------------------------------------------------------
# 4. Aviation Bot (72-Hour Sliding Window)
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
                if not is_within_72_hours(entry):
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
# 6. Space Bot (72-Hour Sliding Window)
# ---------------------------------------------------------------------------
def fetch_space_updates():
    matches = []
    now_utc = datetime.now(timezone.utc)
    dates_to_check = [
        (now_utc - timedelta(days=1)).strftime("%b %d"),
        now_utc.strftime("%b %d"),
        (now_utc + timedelta(days=1)).strftime("%b %d"),
    ]

    url = "https://www.spacelaunchschedule.com/"

    try:
        resp = requests.get(url, headers=SCRAPER_HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            launch_blocks = soup.find_all("div", class_=re.compile("launch-card|card"))

            for block in launch_blocks:
                text = block.get_text(separator=" ")

                if any(d in text for d in dates_to_check):
                    title_elem = block.find(["h2", "h3", "h4", "a"])
                    title = (
                        title_elem.get_text(strip=True)
                        if title_elem
                        else "Rocket Launch"
                    )

                    link_elem = block.find("a", href=True)
                    launch_url = (
                        link_elem["href"]
                        if link_elem and link_elem["href"].startswith("http")
                        else f"https://www.spacelaunchschedule.com#{hash(title)}"
                    )

                    matches.append({
                        "title": f"🚀 Space: {title}",
                        "description": f"Scheduled Space Launch | {title}",
                        "url": launch_url,
                        "color": 9807270,
                    })
    except Exception as e:
        print(f"[SpaceBot] Error scraping space launches: {e}")

    return matches


# ---------------------------------------------------------------------------
# Main Execution Loop
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
