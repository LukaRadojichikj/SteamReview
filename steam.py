# steam.py
import requests
import json
from requests.adapters import HTTPAdapter, Retry
import difflib


STEAM_REVIEWS = "https://store.steampowered.com/appreviews/{}?json=1"

def _session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=3,                
        connect=3,              
        read=3,                
        backoff_factor=0.5,     
        status_forcelist=(500, 502, 503, 504),  
        allowed_methods=frozenset(["GET"])    
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.headers.update({"User-Agent": "steam-reviews-fetcher/1.0"})
    return s

_SESSION = _session()


def _get_appid(title: str, fuzzy: bool = False, cutoff: float = 0.68) -> int:
    resp = _SESSION.get(
        "https://api.steampowered.com/ISteamApps/GetAppList/v2/",
        timeout=10
    )
    resp.raise_for_status()
    app_list = resp.json()
    apps = app_list["applist"]["apps"]

    low = title.lower().strip()
    for app in apps:
        if app["name"].lower() == low:
            return app["appid"]

    if not fuzzy:
        raise ValueError("Game not found (tip: use fuzzy=True)")
    
    names = [a["name"] for a in apps]
    match = difflib.get_close_matches(title, names, n=1, cutoff=cutoff)
    if not match:
        raise ValueError("Game not found (no fuzzy match above cutoff)")
    chosen = match[0]
    for app in apps:
        if app["name"] == chosen:
            return app["appid"]
    raise ValueError("Unexpected: fuzzy match not in list")

def fetch_reviews(game_title: str, count: int = 3, fuzzy: bool = False):
    appid = _get_appid(game_title, fuzzy=fuzzy)
    params = {
        "num_per_page": count,
        "language": "english",
        "filter": "most helpful",
    }
    r = _SESSION.get(STEAM_REVIEWS.format(appid), params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    return [
        {"author": rev["author"]["steamid"], "text": rev["review"],"recommended": bool(rev.get("voted_up", False)),}
        for rev in data.get("reviews", [])
    ]


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.exit("Usage: python steam.py <title> [count] [--fuzzy]")
    game = sys.argv[1]
    count = 3
    use_fuzzy = False
    for arg in sys.argv[2:]:
        if arg == "--fuzzy":
            use_fuzzy = True
        elif arg.isdigit():
            count = int(arg)
    reviews = fetch_reviews(game, count=count, fuzzy=use_fuzzy)
    print(json.dumps(reviews, indent=2, ensure_ascii=False))