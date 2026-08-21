import os
import feedparser
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# WEBHOOK URLS (Read from Environment / GitHub Secrets)
# ---------------------------------------------------------------------------
WEBHOOKS = {
    "tech": os.environ.get("WEBHOOK_TECH", ""),
    "sports": os.environ.get("WEBHOOK_SPORTS", ""),
    "esports": os.environ.get("WEBHOOK_ESPORTS", ""),
    "aviation": os.environ.get("WEBHOOK_AVIATION", ""),
    "research": os.environ.get("WEBHOOK_RESEARCH", ""),
    "space": os.environ.get("WEBHOOK_SPACE", ""),
}

# ---------------------------------------------------------------------------
# CONFIGURATION: DIRECT RSS FEEDS & KEYWORD ARRAYS
# ---------------------------------------------------------------------------
CONFIG = {
    "tech": {
        "urls": [
            "https://www.apple.com/newsroom/rss-feed.rss",
            "https://nvidianews.nvidia.com/rss",
            "https://ir.amd.com/rss/pressreleases.xml",
            "https://newsroom.intel.com/feed/",
            "https://frame.work/blog.rss",
            "https://news.google.com/rss/search?q=site:press.asus.com",
            "https://news.google.com/rss/search?q=site:press.razer.com",
            "https://news.google.com/rss/search?q=site:news.lenovo.com",
            "https://news.google.com/rss/search?q=site:delltechnologies.com",
            "https://news.google.com/rss/search?q=site:msi.com",
        ],
        "keywords": [
            "macbook", "core ultra", "ryzen", "geforce", "rtx", "snapdragon",
            "zephyrus", "legion", "thinkpad", "rog", "blade", "alienware", "xps"
        ],
        "color": 3447003,  # Blue
        "prefix": "💻 Tech",
    },
    "esports": {
        "urls": [
            "https://www.hltv.org/rss/news",
            "https://www.vlr.gg/rss",
            "https://dotesports.com/feed",
            "https://lolesports.com/en-US/rss",
        ],
        "keywords": [
            "rlcs", "vct", "worlds", "msi", "major", "grand slam",
            "ewc", "enc", "champions", "finals"
        ],
        "color": 10181046,  # Purple
        "prefix": "🎮 Esports",
    },
    "research": {
        "urls": [
            "https://news.mit.edu/rss/feed",
            "https://news.stanford.edu/feed/",
            "https://news.berkeley.edu/feed/",
        ],
        "keywords": [],  # No keyword filtering: pulls all university news
        "color": 15844367,  # Gold
        "prefix": "🔬 Research",
    },
}


# ---------------------------------------------------------------------------
# CORE RSS PARSER & KEYWORD FILTER
# ---------------------------------------------------------------------------
def process_category(cat_name):
    print(f"Processing {cat_name.capitalize()}...")
    cat = CONFIG[cat_name]
    embeds = []
    seen_links = set()

    for url in cat["urls"]:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title = entry.title
                summary = entry.get("summary", "")
                link = entry.link

                if link in seen_links:
                    continue

                text_to_check = f"{title} {summary}".lower()

                keywords = cat.get("keywords", [])
                if not keywords or any(kw in text_to_check for kw in keywords):
                    seen_links.add(link)
                    clean_summary = summary[:200] + "..." if summary else "No summary available."
                    embeds.append({
                        "title": f"{cat['prefix']}: {title}",
                        "url": link,
                        "description": clean_summary,
                        "color": cat["color"],
                    })
        except Exception as e:
            print(f"Error fetching {url}: {e}")

    return embeds[:3]


# ---------------------------------------------------------------------------
# SPACE & ROCKET LAUNCH ENGINE (RocketLaunch.live API)
# ---------------------------------------------------------------------------
def fetch_space_updates():
    print("Processing Rocket Launches (RocketLaunch.live)...")
    url = "https://fwd.rocketlaunch.live/json/launches"
    embeds = []

    try:
        res = requests.get(url, timeout=10).json()
        launches = res.get("result", [])

        for launch in launches[:5]:
            provider = launch.get("provider", {}).get("name", "Unknown Provider")
            vehicle = launch.get("vehicle", {}).get("name", "Rocket")
            mission = launch.get("name", "Mission")
            location = launch.get("pad", {}).get("location", {}).get("name", "Launch Site")
            status_text = launch.get("status", {}).get("text", "Scheduled")
            date_str = launch.get("date_str", "TBD")

            # Extract video livestream link if available
            media = launch.get("media", [])
            stream_url = None
            if media and len(media) > 0:
                stream_url = media[0].get("media_url")

            desc = f"**Provider:** {provider}\n**Vehicle:** {vehicle}\n**Pad Location:** {location}\n**Launch Time:** {date_str}\n**Status:** {status_text}"
            if stream_url:
                desc += f"\n\n📺 **[Watch Livestream Here]({stream_url})**"

            embeds.append({
                "title": f"🚀 Rocket Launch: {provider} - {mission}",
                "description": desc,
                "color": 15105570,  # Orange/Red Rocket Color
            })
    except Exception as e:
        print(f"Error fetching rocket launches: {e}")

    return embeds[:2]  # Return top 2 upcoming/active launches


# ---------------------------------------------------------------------------
# AVIATION SCRAPER (Airfleets Delivery Log)
# ---------------------------------------------------------------------------
def fetch_aviation_updates():
    print("Processing Aviation (Airfleets)...")
    url = "https://www.airfleets.net/divers/delivery.htm"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    embeds = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        rows = soup.select("table.tabcadre tr")[1:6]  # Top 5 delivery rows
        for row in rows:
            cols = [col.get_text(strip=True) for col in row.select("td")]
            if len(cols) >= 4:
                date_str = cols[0]
                airline = cols[1]
                plane_type = cols[2]
                msn = cols[3]

                embeds.append({
                    "title": f"✈️ Aircraft Delivery: {airline} ({plane_type})",
                    "url": url,
                    "description": f"**Date:** {date_str}\n**Airline:** {airline}\n**Aircraft:** {plane_type}\n**MSN:** {msn}",
                    "color": 1752220,  # Teal
                })
    except Exception as e:
        print(f"Error scraping Airfleets: {e}")

    return embeds[:3]


# ---------------------------------------------------------------------------
# EXPANDED SPORTS ENGINE (Pro, College, Soccer, F1, Global)
# ---------------------------------------------------------------------------
def fetch_sports_updates():
    print("Processing Sports...")
    endpoints = {
        # Pro US Leagues
        "NBA": "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        "NFL": "http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        "NHL": "http://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
        "MLB": "http://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
        # College Sports
        "NCAA Football": "http://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
        "NCAA Hoops": "http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard",
        "NCAA Baseball": "http://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/scoreboard",
        "NCAA Hockey": "http://site.api.espn.com/apis/site/v2/sports/hockey/mens-college-hockey/scoreboard",
        # Soccer Leagues & Cups
        "EPL": "http://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
        "UCL": "http://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard",
        "La Liga": "http://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard",
        "Serie A": "http://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard",
        "MLS": "http://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard",
        # Formula 1 & Racing
        "F1": "http://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard",
    }

    embeds = []
    for league, url in endpoints.items():
        try:
            res = requests.get(url, timeout=10).json()
            for event in res.get("events", [])[:2]:
                status = event["status"]["type"]["state"]
                detail = event["status"]["type"]["shortDetail"]

                if status in ["in", "post"]:
                    competitions = event["competitions"][0]

                    if league == "F1":
                        race_name = event.get("name", "F1 Grand Prix")
                        embeds.append({
                            "title": f"🏎️ [F1] {race_name}",
                            "description": f"**Status:** {detail}",
                            "color": 15158332 if status == "post" else 3066993,
                        })
                        continue

                    comp = competitions.get("competitors", [])
                    if len(comp) >= 2:
                        t1, s1 = comp[0]["team"]["shortDisplayName"], comp[0].get("score", "0")
                        t2, s2 = comp[1]["team"]["shortDisplayName"], comp[1].get("score", "0")

                        embeds.append({
                            "title": f"🏆 [{league}] {t2} vs {t1}",
                            "description": f"**Score:** {t2} `{s2}` - `{s1}` {t1}\n**Status:** {detail}",
                            "color": 15158332 if status == "post" else 3066993,
                        })
        except Exception as e:
            print(f"Error fetching {league}: {e}")

    return embeds


# ---------------------------------------------------------------------------
# DISCORD WEBHOOK SENDER
# ---------------------------------------------------------------------------
def send_discord_webhook(webhook_url, embeds, username="UpdateBot"):
    if not webhook_url or not embeds:
        return
    for i in range(0, len(embeds), 10):
        payload = {"username": username, "embeds": embeds[i: i + 10]}
        try:
            requests.post(webhook_url, json=payload, timeout=10)
        except Exception as e:
            print(f"Webhook error ({username}): {e}")


# ---------------------------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    send_discord_webhook(WEBHOOKS["tech"], process_category("tech"), "TechBot")
    send_discord_webhook(WEBHOOKS["sports"], fetch_sports_updates(), "SportsBot")
    send_discord_webhook(WEBHOOKS["esports"], process_category("esports"), "EsportsBot")
    send_discord_webhook(WEBHOOKS["aviation"], fetch_aviation_updates(), "AeroBot")
    send_discord_webhook(WEBHOOKS["research"], process_category("research"), "ResearchBot")
    send_discord_webhook(WEBHOOKS["space"], fetch_space_updates(), "SpaceBot")
