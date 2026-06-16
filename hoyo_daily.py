#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HoYo daily — автономный скрипт: ежедневный чек-ин HoYoLab + активация промокодов
для Genshin Impact, Honkai: Star Rail, Zenless Zone Zero.

Не зависит от Obsidian. Нужен только Python + библиотека genshin + твои куки.

Куки (одной строкой или по строкам key=value) в cookies.txt рядом со скриптом
(или в переменной окружения HOYO_COOKIES):
  ltoken_v2 + ltuid_v2            — с домена hoyolab.com            (нужны для чек-ина)
  cookie_token_v2 + account_mid_v2 — с домена account.hoyoverse.com (нужны для кодов)

Запуск:
  python3 hoyo_daily.py
Уже активированные коды запоминаются в state.json (повторно не дёргаются).
Опционально: переменная окружения DISCORD_WEBHOOK — пришлёт итог в Discord.
"""

import os
import sys
import json
import asyncio
import urllib.request
import datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
COOKIE_FILE = os.getenv("HOYO_COOKIES_FILE") or str(HERE / "cookies.txt")
STATE_FILE = HERE / "state.json"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")

CODES_API = "https://hoyo-codes.seria.moe/codes?game={}"
# (атрибут genshin.Game, ключ API кодов, метка)
GAMES = [("GENSHIN", "genshin", "Genshin"), ("STARRAIL", "hkrpg", "HSR"), ("ZZZ", "nap", "ZZZ")]

_lines = []


def log(m):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {m}", flush=True)
    _lines.append(m)


def get_cookies() -> dict:
    raw = os.getenv("HOYO_COOKIES")
    if not raw and os.path.exists(COOKIE_FILE):
        raw = Path(COOKIE_FILE).read_text(encoding="utf-8")
    if not raw:
        log("ОШИБКА: не найдены куки (cookies.txt или env HOYO_COOKIES)")
        sys.exit(1)
    cookies = {}
    for part in raw.replace("\n", ";").split(";"):
        part = part.strip()
        if part.startswith("#") or "=" not in part:
            continue
        k, v = part.split("=", 1)
        if v.strip():
            cookies[k.strip()] = v.strip()
    return cookies


def fetch_codes(api: str):
    req = urllib.request.Request(CODES_API.format(api), headers={"User-Agent": "Mozilla/5.0 (hoyo-daily)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    return [(c["code"], c.get("rewards", "")) for c in data.get("codes", []) if c.get("status") == "OK"]


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_state(s: dict):
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


async def do_checkin(client, genshin):
    G = genshin.Game
    log("Чек-ин:")
    for attr, _, label in GAMES:
        g = getattr(G, attr, None)
        if g is None:
            continue
        try:
            await client.claim_daily_reward(game=g, reward=False)
            log(f"  {label}: ок")
        except genshin.AlreadyClaimed:
            log(f"  {label}: уже получено сегодня")
        except genshin.InvalidCookies as e:
            log(f"  {label}: 🔴 плохие куки hoyolab (ltoken_v2/ltuid_v2) — {e}")
        except Exception as e:  # noqa: BLE001
            log(f"  {label}: ошибка — {e}")


async def do_redeem(client, genshin):
    G = genshin.Game
    state = load_state()
    log("Промокоды:")
    for attr, api, label in GAMES:
        g = getattr(G, attr, None)
        if g is None:
            continue
        try:
            items = await asyncio.to_thread(fetch_codes, api)
        except Exception as e:  # noqa: BLE001
            log(f"  {label}: не удалось получить коды — {e}")
            continue
        done = set(state.get(api, []))
        new = [(c, r) for c, r in items if c not in done]
        if not new:
            log(f"  {label}: новых кодов нет")
            continue
        for code, rew in new:
            try:
                await client.redeem_code(code, game=g)
                log(f"  {label}: ✅ {code}  ({rew})")
                done.add(code)
            except genshin.RedemptionClaimed:
                log(f"  {label}: уже был активирован {code}")
                done.add(code)
            except genshin.RedemptionInvalid:
                log(f"  {label}: невалиден/истёк {code}")
                done.add(code)
            except genshin.RedemptionCooldown:
                log(f"  {label}: кулдаун — остальное в следующий раз")
                break
            except Exception as e:  # noqa: BLE001
                m = str(e)
                if "cookie_token" in m or "-1071" in m or "log in to your account" in m:
                    log(f"  {label}: 🔴 плохие куки hoyoverse (cookie_token_v2/account_mid_v2) — стоп")
                    save_state(state)
                    return
                if "-2008" in m or "not eligible" in m:
                    log(f"  {label}: регион не подходит, пропуск {code}")
                    done.add(code)
                else:
                    log(f"  {label}: {code} — {e} (повтор позже)")
            await asyncio.sleep(6)
        state[api] = sorted(done)
    save_state(state)


def notify_discord():
    if not DISCORD_WEBHOOK:
        return
    try:
        text = "**HoYo daily " + dt.date.today().isoformat() + "**\n" + "\n".join(_lines)
        body = json.dumps({"content": text[:1900]}).encode("utf-8")
        req = urllib.request.Request(DISCORD_WEBHOOK, data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:  # noqa: BLE001
        print("discord webhook error:", e)


async def main():
    try:
        import genshin
    except ImportError:
        log("ОШИБКА: установи библиотеку: pip install genshin")
        sys.exit(1)
    client = genshin.Client(get_cookies())
    log("=== HoYo daily ===")
    await do_checkin(client, genshin)
    await do_redeem(client, genshin)
    log("Готово.")
    notify_discord()


if __name__ == "__main__":
    asyncio.run(main())
