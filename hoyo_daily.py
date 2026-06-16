#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HoYo daily — автономный скрипт: ежедневный чек-ин HoYoLab + активация промокодов
для Genshin Impact, Honkai: Star Rail, Zenless Zone Zero. Без Obsidian.

Настройки:
  config.json — поведение (какие игры, чек-ин/коды вкл-выкл, когда слать уведомления).
  .env        — секреты (вебхуки/токены, при желании сами куки).
  cookies.txt — куки (или переменная окружения HOYO_COOKIES).

Уведомления умные: шлются в Discord/Telegram ТОЛЬКО при событии
(применён новый код / протухли куки) — настраивается в config.json.

Запуск: python3 hoyo_daily.py
"""

import os
import sys
import json
import asyncio
import urllib.request
import urllib.parse
import datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "state.json"
CODES_API = "https://hoyo-codes.seria.moe/codes?game={}"

# ключ -> (атрибут genshin.Game, ключ API кодов, метка)
GAME_DEFS = {
    "genshin":  ("GENSHIN",  "genshin", "Genshin"),
    "starrail": ("STARRAIL", "hkrpg",   "HSR"),
    "zzz":      ("ZZZ",      "nap",     "ZZZ"),
}

DEFAULT_CONFIG = {
    "games": ["genshin", "starrail", "zzz"],
    "checkin": True,
    "redeem_codes": True,
    "notify": {"on_new_code": True, "on_cookie_error": True, "on_nothing": False},
}

_lines = []
EVENTS = {"new_codes": [], "cookie_error": []}


def log(m):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {m}", flush=True)
    _lines.append(m)


def load_env():
    f = HERE / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    f = HERE / "config.json"
    if f.exists():
        try:
            user = json.loads(f.read_text(encoding="utf-8"))
            for k, v in user.items():
                if k == "notify" and isinstance(v, dict):
                    cfg["notify"].update(v)
                else:
                    cfg[k] = v
        except Exception as e:  # noqa: BLE001
            log(f"config.json — ошибка чтения ({e}), беру значения по умолчанию")
    return cfg


def get_cookies() -> dict:
    raw = os.getenv("HOYO_COOKIES")
    cf = os.getenv("HOYO_COOKIES_FILE") or str(HERE / "cookies.txt")
    if not raw and os.path.exists(cf):
        raw = Path(cf).read_text(encoding="utf-8")
    if not raw:
        log("ОШИБКА: не найдены куки (cookies.txt / env HOYO_COOKIES)")
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


async def do_checkin(client, genshin, active):
    G = genshin.Game
    log("Чек-ин:")
    for attr, _, label in active:
        g = getattr(G, attr, None)
        if g is None:
            continue
        try:
            await client.claim_daily_reward(game=g, reward=False)
            log(f"  {label}: ок")
        except genshin.AlreadyClaimed:
            log(f"  {label}: уже получено сегодня")
        except genshin.InvalidCookies as e:
            log(f"  {label}: 🔴 плохие куки hoyolab — {e}")
            EVENTS["cookie_error"].append("hoyolab (ltoken_v2/ltuid_v2)")
        except Exception as e:  # noqa: BLE001
            log(f"  {label}: ошибка — {e}")


async def do_redeem(client, genshin, active):
    G = genshin.Game
    state = load_state()
    log("Промокоды:")
    for attr, api, label in active:
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
                EVENTS["new_codes"].append(f"{label}: {code} — {rew}")
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
                    log(f"  {label}: 🔴 плохие куки hoyoverse — стоп")
                    EVENTS["cookie_error"].append("hoyoverse (cookie_token_v2/account_mid_v2)")
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


def _post(url, data, headers):
    urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=15)


def send_discord(text):
    url = os.getenv("DISCORD_WEBHOOK", "")
    if not url:
        return
    try:
        _post(url, json.dumps({"content": text[:1900]}).encode("utf-8"), {"Content-Type": "application/json"})
    except Exception as e:  # noqa: BLE001
        print("discord error:", e)


def send_telegram(text):
    tok = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if not tok or not chat:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text[:3900]}).encode("utf-8")
        _post(f"https://api.telegram.org/bot{tok}/sendMessage", data,
              {"Content-Type": "application/x-www-form-urlencoded"})
    except Exception as e:  # noqa: BLE001
        print("telegram error:", e)


def notify(cfg):
    n = cfg["notify"]
    trigger = ((EVENTS["cookie_error"] and n.get("on_cookie_error", True))
               or (EVENTS["new_codes"] and n.get("on_new_code", True))
               or n.get("on_nothing", False))
    if not trigger:
        return
    parts = [f"🎮 HoYo daily — {dt.date.today().isoformat()}"]
    if EVENTS["cookie_error"]:
        parts.append("⚠️ Протухли куки: " + ", ".join(sorted(set(EVENTS["cookie_error"]))) + " — обнови.")
    if EVENTS["new_codes"]:
        parts.append("✅ Новые коды:\n" + "\n".join(EVENTS["new_codes"]))
    if not EVENTS["cookie_error"] and not EVENTS["new_codes"]:
        parts.append("Прогон без событий (чек-ин/коды отработали).")
    msg = "\n".join(parts)
    send_discord(msg)
    send_telegram(msg)


async def main():
    load_env()
    cfg = load_config()
    try:
        import genshin
    except ImportError:
        log("ОШИБКА: установи библиотеку: pip install genshin")
        sys.exit(1)
    active = [GAME_DEFS[k] for k in cfg.get("games", []) if k in GAME_DEFS]
    if not active:
        log("В config.json не выбрано ни одной игры (поле games).")
        sys.exit(1)
    client = genshin.Client(get_cookies())
    log("=== HoYo daily ===")
    if cfg.get("checkin", True):
        await do_checkin(client, genshin, active)
    if cfg.get("redeem_codes", True):
        await do_redeem(client, genshin, active)
    log("Готово.")
    notify(cfg)


if __name__ == "__main__":
    asyncio.run(main())
