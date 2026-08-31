import requests
import json
import os
import datetime

from config import CINEMA_ID, MOVIE_ID, ONLY_WEEKEND, ONLY_IMAX, SEEN_FILE

BARK_KEY = os.environ.get("BARK_KEY", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer": f"https://m.maoyan.com/cinema/{CINEMA_ID}?movieId={MOVIE_ID}",
}


def push(title, content):
    if not BARK_KEY:
        print("没配置BARK_KEY，跳过推送:", title, content)
        return
    url = f"https://api.day.app/{BARK_KEY}/{title}/{content}"
    try:
        requests.get(url, timeout=10)
    except Exception as e:
        print("推送失败:", e)


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False)


def fetch_shows():
    url = f"https://m.maoyan.com/showtime/wrap.json?cinemaid={CINEMA_ID}&movieid={MOVIE_ID}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def parse_shows(data):
    shows = []
    try:
        groups = data.get("showList") or data.get("data", {}).get("showList", [])
        for group in groups:
            date = group.get("date", group.get("showDate", ""))
            items = group.get("shows") or group.get("showList") or []
            for show in items:
                show_id = str(show.get("showId") or show.get("id"))
                hall = show.get("hallName", show.get("hall", ""))
                time_ = show.get("showTime", show.get("time", ""))
                is_imax = "IMAX" in hall.upper()
                shows.append({
                    "id": show_id,
                    "date": date,
                    "time": time_,
                    "hall": hall,
                    "is_imax": is_imax,
                })
    except Exception as e:
        print("解析失败，原始数据如下，请把这段发给Claude帮忙调整解析逻辑：")
        print(json.dumps(data, ensure_ascii=False)[:2000])
        raise e
    return shows


def is_weekend(date_str):
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            d = datetime.datetime.strptime(date_str, fmt)
            return d.weekday() >= 5
        except Exception:
            continue
    return True


def main():
    seen = load_seen()
    data = fetch_shows()
    shows = parse_shows(data)

    new_count = 0
    for s in shows:
        if s["id"] in seen:
            continue
        if ONLY_IMAX and not s["is_imax"]:
            continue
        if ONLY_WEEKEND and not is_weekend(s["date"]):
            continue

        push("新场次上线", f'{s["date"]} {s["time"]} {s["hall"]}')
        seen.add(s["id"])
        new_count += 1

    save_seen(seen)
    print(f"本次检查完成，新增 {new_count} 个场次通知，共发现 {len(shows)} 个场次。")


if __name__ == "__main__":
    main()
