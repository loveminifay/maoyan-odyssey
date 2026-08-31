import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests


TARGET_URL = (
    "https://co.maoyan.com/mtrade/cinema/cinema"
    "?cinemaId=37534"
    "&movieId=1545360"
    "&date=2026-09-01"
    "&merCode=1000488"
)

STATE_FILE = Path("seen_showtimes.json")
BARK_KEY = os.environ.get("BARK_KEY")


def send_bark(title, message):
    if not BARK_KEY:
        print("BARK_KEY 未设置")
        return

    url = f"https://api.day.app/{BARK_KEY}"

    response = requests.post(
        url,
        json={
            "title": title,
            "body": message,
            "group": "奥德赛前滩雷达",
            "level": "active",
        },
        timeout=20,
    )

    print("Bark:", response.status_code)
    print(response.text)


def load_state():
    if not STATE_FILE.exists():
        return set()

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data)
    except Exception:
        return set()


def save_state(items):
    STATE_FILE.write_text(
        json.dumps(sorted(items), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def install_playwright():
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "playwright", "requests"],
        check=True,
    )

    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
    )


def get_page_text():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={"width": 1280, "height": 2000},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0 Safari/537.36"
            ),
        )

        page.goto(
            TARGET_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(8000)

        text = page.locator("body").inner_text()

        browser.close()

        return text


def extract_showtimes(text):
    """
    从猫眼页面当前实际显示的文字中提取时间。

    第一版重点：
    - 识别 HH:MM
    - 保留包含 IMAX 的上下文
    - 自动去重

    后续可以进一步精确到：
    日期 / 厅 / IMAX激光 / 语言 / 价格
    """

    lines = [x.strip() for x in text.splitlines() if x.strip()]

    results = set()

    for i, line in enumerate(lines):
        times = re.findall(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b", line)

        if not times:
            continue

        context_start = max(0, i - 3)
        context_end = min(len(lines), i + 4)

        context = " ".join(lines[context_start:context_end])

        # 当前页面如果明确出现 IMAX，则优先记录
        is_imax = "IMAX" in context.upper()

        for t in times:
            if is_imax:
                results.add(f"IMAX|{t}")
            else:
                results.add(f"OTHER|{t}")

    return results


def main():
    print("开始检查猫眼页面")
    print(TARGET_URL)

    install_playwright()

    text = get_page_text()

    print("页面文字长度:", len(text))

    if not text:
        raise RuntimeError("猫眼页面没有读取到内容")

    current = extract_showtimes(text)

    print("当前发现的场次:")
    for item in sorted(current):
        print(item)

    if not current:
        print("没有识别到场次，本次不通知")
        return

    previous = load_state()

    # 第一次运行：
    # 只记录当前场次，不把已经存在的场次全部当成“新开票”
    if not previous:
        save_state(current)
        print("第一次运行，已建立场次记录，不发送通知")
        return

    new_items = current - previous

    if not new_items:
        print("没有新场次，不发送通知")
        return

    for item in sorted(new_items):
        kind, time = item.split("|", 1)

        if kind == "IMAX":
            title = "🚨《奥德赛》IMAX 新场次"
        else:
            title = "🎬《奥德赛》新场次"

        message = (
            "上海前滩 MOViE MOViE\n\n"
            f"⏰ 新增场次：{time}\n"
            f"🎥 类型：{kind}\n\n"
            "猫眼购票页面：\n"
            f"{TARGET_URL}"
        )

        send_bark(title, message)

    save_state(current)


if __name__ == "__main__":
    main()
