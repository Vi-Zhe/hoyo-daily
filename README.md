# HoYo daily — чек-ин + промокоды (автономно)

Один скрипт, который раз в день делает для **Genshin / Honkai: Star Rail / Zenless Zone Zero**:
- забирает ежедневные награды HoYoLab (чек-ин);
- находит новые промокоды ([hoyo-codes.seria.moe](https://hoyo-codes.seria.moe)) и активирует их.

Не нужен Obsidian/сервер автора — работает где угодно с Python. Уже погашенные коды помнит в `state.json`.

## Установка (5 минут)

```bash
# 1) положить папку hoyo-daily на машину (Linux/Windows/Mac с Python 3.10+)
cd hoyo-daily
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip install -r requirements.txt

# 2) скопировать шаблон и вписать свои куки:
#    cp cookies.example.txt cookies.txt   (затем впиши значения, см. ниже)

# 3) проверить
.venv/bin/python hoyo_daily.py
```

## Куки (откуда брать)
Залогинься на hoyolab.com, открой DevTools (F12) → Application/Storage → Cookies. Впиши в `cookies.txt`:
- `ltoken_v2`, `ltuid_v2` — с домена **hoyolab.com** (для чек-ина)
- `cookie_token_v2`, `account_mid_v2` — с домена **account.hoyoverse.com** (для промокодов; именно этот домен!)

UID игр указывать не нужно — берутся из аккаунта. Куки живут несколько месяцев; когда чек-ин/коды начнут писать «🔴 плохие куки» — впиши свежие.

## Автозапуск раз в день

**Linux (cron), 09:00:**
```
0 9 * * * cd /ПУТЬ/hoyo-daily && .venv/bin/python hoyo_daily.py >> hoyo_daily.log 2>&1
```

**Windows (Планировщик заданий):** действие — запуск `.venv\Scripts\python.exe` с аргументом `hoyo_daily.py`, рабочая папка — папка скрипта, триггер — ежедневно.

## Опционально: уведомления в Discord
Создай в канале вебхук и задай переменную окружения перед запуском:
```
DISCORD_WEBHOOK=https://discord.com/api/webhooks/.... 
```
Скрипт пришлёт итог прогона (что зачекинилось, какие коды применились, протухли ли куки). Без неё всё пишется только в лог.

## Заметки
- Файл `state.json` создаётся сам — не удаляй (в нём список уже применённых кодов).
- Региональные коды (не для твоего региона) и истёкшие помечаются и больше не дёргаются.
- Между активациями пауза 6 сек (анти-кулдаун HoYo). Если кодов много — добьются за пару прогонов.
