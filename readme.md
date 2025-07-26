# Windows Quick Start Guide to localhost same bot

**Other OSs:** ***[Windows](readme.md)*** | [Linux](readmes/readme_eng_linux.md)

**Languages:** ***[English](readme.md)*** | [Русский](readmes/readme_ru_win.md)

---

## Clone repo

**Copy-paste into Powershell or CMD**, change `C:\Code\QuiX-Saver` to prefered directory or remove completely:

```powershell
git clone https://github.com/QuiXinI/QuiX-Saver.git C:\Code\QuiX-Saver
```

## Create `.env`

```powershell
cd C:\Code\QuiX-Saver
New-Item .env -Type File
```

*(or inside of Windows Explorer)*

---

## Getting API keys

1. Go to [my.telegram.org](https://my.telegram.org/apps) and authorise.
2. Copy `API_ID` и `API_HASH` into `.env`.
3. Go to [@BotFather](https://t.me/BotFather), create new bot and copy `BOT_TOKEN` into `.env`.

Example of `.env`:

```ini
API_ID=12345678
API_HASH=abcdefghijklmnopqrstuvwx12456789
BOT_TOKEN=1234567890:Aabcdefghijklmopqrtuvwxyz1234567890
```

> **WARNING:** no spaces between data and `=`!

---

## Installing dependencies

Install Python 3.10+ (tested on 3.10–3.14b01).

```powershell
cd C:\Code\QuiX-Saver
python -m venv venv
venv\Scripts\Activate.ps1   # or Activate.bat
pip install -r requirements.txt
```

If asked `[Y/n]`, press `y` + `Enter`.

---

## Running bot

```powershell
cd C:\Code\QuiX-Saver
venv\Scripts\Activate.ps1
python main.py
```

Don't close this window - it will terminate bot.
To manually terminate bot, press `Ctrl+C`.

---

## Broadcast notifications (optional)

There are `notify.py` and `mass_sent.txt` in the same directory.

1. Into `mass_sent.txt` type anything, you want to broadcast to your users.
2. Stop bot (`Ctrl+C`).
3. Run:

```powershell
venv\Scripts\Activate.ps1
python notify.py
```

4. After it stops (eventually) run:

```powershell
python main.py
```

