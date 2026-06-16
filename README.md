# HoYo daily — чек-ин + промокоды (автономно)

Один скрипт, который раз в день делает для **Genshin / Honkai: Star Rail / Zenless Zone Zero**:
- забирает ежедневные награды HoYoLab (чек-ин);
- находит новые промокоды ([hoyo-codes.seria.moe](https://hoyo-codes.seria.moe)) и активирует их.

Работает где угодно с Python, без внешних зависимостей кроме библиотеки `genshin`. Уже погашенные коды помнит в `state.json`.

## Установка (5 минут)

```bash
# 1) положить папку hoyo-daily на машину (Linux/Windows/Mac с Python 3.10+)
cd hoyo-daily
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip install -r requirements.txt

# 2) куки: скопируй шаблон и впиши свои значения (см. ниже)
cp cookies.example.txt cookies.txt

# 3) проверить
.venv/bin/python hoyo_daily.py
```

## Куки (откуда брать)
Залогинься на hoyolab.com, открой DevTools (F12) → Application/Storage → Cookies. Впиши в `cookies.txt`:
- `ltoken_v2`, `ltuid_v2` — с домена **hoyolab.com** (для чек-ина)
- `cookie_token_v2`, `account_mid_v2` — с домена **account.hoyoverse.com** (для промокодов; именно этот домен!)

UID игр указывать не нужно. Куки живут несколько месяцев; когда чек-ин/коды начнут писать «🔴 плохие куки» — впиши свежие.

## Настройки (опционально) — `config.json`
По умолчанию включено всё для 3 игр. Чтобы выбрать, **что именно отслеживать и применять**, — `cp config.example.json config.json` и правь.

**По каждой игре отдельно** (рекомендую): для каждой игры свои тумблеры `checkin` (чек-ин) и `codes` (промокоды):
```json
{
  "games": {
    "genshin":  { "checkin": true,  "codes": true  },
    "starrail": { "checkin": true,  "codes": false },   // HSR: только чек-ин
    "zzz":      { "checkin": false, "codes": true  }     // ZZZ: только коды
  }
}
```
Чтобы игру **вообще не трогать** — убери её из `games` (или поставь `"zzz": false`).

**Простой вид** (то же для всех): список игр + глобальные тумблеры:
```json
{ "games": ["genshin", "zzz"], "checkin": true, "redeem_codes": false }
```

Уведомления — блок `notify`:
```json
"notify": { "on_new_code": true, "on_cookie_error": true, "on_nothing": false }
```

## Уведомления (опционально) — `.env`
Умные: по умолчанию приходят **только при событии** — применён новый код или протухли куки (то, ради чего стоит вмешаться). `cp .env.example .env` и заполни нужное:
- **Discord** — `DISCORD_WEBHOOK` (вебхук канала).
- **Telegram** — `TELEGRAM_BOT_TOKEN` (от @BotFather) + `TELEGRAM_CHAT_ID`.

Можно оба сразу, можно ни одного (тогда просто лог). Когда слать — настраивается в `config.json → notify`.

## Автозапуск раз в день

**Linux (cron), 09:00:**
```
0 9 * * * cd /ПУТЬ/hoyo-daily && .venv/bin/python hoyo_daily.py >> hoyo_daily.log 2>&1
```

**Windows (Планировщик заданий):** действие — `.venv\Scripts\python.exe`, аргумент `hoyo_daily.py`, рабочая папка — папка скрипта, триггер — ежедневно.

## Заметки
- `state.json` создаётся сам — не удаляй (список уже применённых кодов).
- Региональные и истёкшие коды помечаются и больше не дёргаются.
- Между активациями пауза 6 сек (анти-кулдаун). Много кодов → добьются за пару прогонов.
