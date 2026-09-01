import requests
import json
import os

from config import CINEMA_ID, MOVIE_ID, ONLY_WEEKEND, ONLY_IMAX, SEEN_FILE

BARK_KEY = os.environ.get("BARK_KEY", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer": f"https://m.maoyan.com/cinema/{CINEMA_ID}",
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


def fetch_cinema_detail():
    """
    这是猫眼移动端一个较老但仍在使用的接口，返回该影院近期的排片信息。
    如果这一步报错或者返回空数据，把打印出来的原始内容发给Claude，
    根据实际返回结构调整下面的解析部分。
    """
    url = f"https://m.maoyan.com/ajax/cinemaDetail?cinemaId={CINEMA_ID}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def parse_shows(data):
    """
    从cinemaDetail的返回结果里，挑出目标电影(MOVIE_ID)的场次列表。
    真实字段名可能和这里假设的不完全一样，第一次跑很可能需要调整，
    调整时把 print(json.dumps(data, ...)) 那行打印出来的内容发给Claude。
    """
    shows = []

    cinema_data = data.get("cinemaData", {})
    if not cinema_data:
        print("cinemaData是空的，可能是cinemaId不对，或者接口结构变了。原始返回：")
        print(json.dumps(data, ensure_ascii=False)[:2000])
        return shows

    # 猫眼这个接口一般会把场次按"电影"分组，movieId是关键筛选条件
    movie_list = cinema_data.get("movieList", []) or cinema_data.get("movies", [])

    for movie in movie_list:
        if str(movie.get("movieId")) != str(MOVIE_ID):
            continue

        for show in movie.get("shows", []) or movie.get("showList", []):
            seq_no = str(show.get("seqNo") or show.get("showId") or show.get("id"))
            hall = show.get("hallName", show.get("hall", ""))
            date = show.get("showDate", show.get("date", ""))
            time_ = show.get("showTime", show.get("time", ""))
            is_imax = "IMAX" in hall.upper()
            shows.append({
                "id": seq_no,
                "date": date,
                "time": time_,
                "hall": hall,
                "is_imax": is_imax,
            })

    if not movie_list:
        print("movieList是空的，原始cinemaData结构：")
        print(json.dumps(cinema_data, ensure_ascii=False)[:2000])

    return shows


def main():
    seen = load_seen()
    data = fetch_cinema_detail()
    shows = parse_shows(data)

    new_count = 0
    for s in shows:
        if s["id"] in seen:
            continue
        if ONLY_IMAX and not s["is_imax"]:
            continue

        push("新场次上线", f'{s["date"]} {s["time"]} {s["hall"]}')
        seen.add(s["id"])
        new_count += 1

    save_seen(seen)
    print(f"本次检查完成，新增 {new_count} 个场次通知，共发现 {len(shows)} 个场次。")


if __name__ == "__main__":
    main()
