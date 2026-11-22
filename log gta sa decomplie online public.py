#!/usr/bin/env python3
"""
decompilati.onl kuzatuvchi -> Discord webhook

- Loyiha RSS feedini tekshiradi va yangi hisobotlarni Discord'ga yuboradi
- Sahifada "Private repository" yozuvi yo'qolsa (repo public bo'lsa), alohida ogohlantirish yuboradi

O'rnatish:  pip install requests
Ishga tushirish:  python decompilati_monitor.py
"""

import html
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

# ============ SOZLAMALAR ============
WEBHOOK_URL = "https://discord.com/api/webhooks/1511316715064135700/q2lPuGyFBPHFaHo4KemmLrek-KAEjxgzRaXD-hsVX3MSYLxFiqA8m9zX0_ToG41URRPl"

PROJECT_URL = "https://decompilati.onl/projects/grand-theft-auto-san-andreas-compact-exe"
FEED_URL = PROJECT_URL + "/feed.xml"

CHECK_INTERVAL = 300  # soniya (300 = 5 daqiqa)
STATE_FILE = Path("seen_state.json")
# Agar sahifa login talab qilsa, brauzerdan cookie'ni nusxalab shu yerga qo'ying:
# masalan: COOKIES = {"session": "abcdef..."}
COOKIES = {}
# ====================================

HEADERS = {"User-Agent": "Mozilla/5.0 (decompilati-monitor)"}


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"seen": [], "was_private": None}


def save_state(state):
    state["seen"] = state["seen"][-500:]  # fayl katta bo'lib ketmasin
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def clean(text):
    text = re.sub(r"<[^>]+>", "\n", text or "")
    text = html.unescape(text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def send_discord(title, description, url=None, color=0x5865F2):
    embed = {"title": title[:256], "description": description[:4000], "color": color}
    if url:
        embed["url"] = url
    try:
        r = requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=20)
        if r.status_code == 429:  # rate limit
            time.sleep(float(r.json().get("retry_after", 2)))
            requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=20)
        elif r.status_code >= 300:
            print(f"Discord xato: {r.status_code} {r.text[:200]}")
    except requests.RequestException as e:
        print(f"Discord'ga yuborib bo'lmadi: {e}")


def fetch_feed():
    r = requests.get(FEED_URL, headers=HEADERS, cookies=COOKIES, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = []
    for it in root.iter("item"):
        items.append({
            "guid": (it.findtext("guid") or it.findtext("link") or "").strip(),
            "title": (it.findtext("title") or "").strip(),
            "link": (it.findtext("link") or "").strip(),
            "date": (it.findtext("pubDate") or "").strip(),
            "desc": clean(it.findtext("description")),
        })
    return items


def check_feed(state):
    items = fetch_feed()
    seen = set(state["seen"])

    # Birinchi ishga tushirishda eskilarini yubormaymiz, faqat eslab qolamiz
    if not state["seen"]:
        state["seen"] = [i["guid"] for i in items]
        print(f"Birinchi ishga tushish: {len(items)} ta eski yozuv eslab qolindi.")
        send_discord("Kuzatuv boshlandi",
                     f"decompilati.onl GTA SA kuzatilmoqda. Hozir {len(items)} ta yozuv bor.",
                     PROJECT_URL, 0x57F287)
        return

    new_items = [i for i in items if i["guid"] and i["guid"] not in seen]
    for item in reversed(new_items):  # eskisidan yangisiga
        send_discord(item["title"], f"{item['desc']}\n\n{item['date']}", item["link"])
        state["seen"].append(item["guid"])
        print("Yangi:", item["title"])
        time.sleep(1)


def check_private(state):
    r = requests.get(PROJECT_URL, headers=HEADERS, cookies=COOKIES, timeout=30)
    if r.status_code != 200:
        print(f"Sahifa statusi {r.status_code}, repo holati tekshirilmadi.")
        return
    page = r.text
    # Sahifa to'g'ri yuklanganini tekshiramiz (xato sahifada yolg'on signal bermaslik uchun)
    if "objdiff" not in page and "Functions" not in page and "FUNCTIONS" not in page:
        print("Sahifa kutilgandek emas (login kerak bo'lishi mumkin), o'tkazib yuborildi.")
        return

    is_private = "Private repository" in page
    if state["was_private"] is True and not is_private:
        send_discord("REPO PUBLIC BO'LDI!",
                     "Sahifada 'Private repository' yozuvi yo'qoldi. Tekshirib ko'ring:",
                     PROJECT_URL, 0xED4245)
        print("Repo public bo'ldi!")
    state["was_private"] = is_private


def main():
    if "PASTE_YOUR" in WEBHOOK_URL:
        raise SystemExit("WEBHOOK_URL ni to'ldiring!")
    state = load_state()
    while True:
        try:
            check_feed(state)
        except Exception as e:
            print(f"Feed xatosi: {e}")
        try:
            check_private(state)
        except Exception as e:
            print(f"Sahifa xatosi: {e}")
        save_state(state)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
