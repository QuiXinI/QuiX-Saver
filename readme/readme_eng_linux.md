# Linux Quick Start Guide to localhost same bot

**Other OSs:** [Windows](./readme.md) | ***[Linux](./readme_eng_linux.md)***

**Languages:** ***[English](./readme_eng_linux.md)*** | [Русский](./readme_ru_linux.md)

---

## Clone repo

**Copy-paste into terminal**, replace `~/QuiX-Saver` with your preferred directory or remove the path:

```bash
git clone https://github.com/QuiXinI/QuiX-Saver.git ~/QuiX-Saver
```

## Create `.env`

```bash
cd ~/QuiX-Saver
touch .env
```

---

## Getting API keys

1. Go to [my.telegram.org](https://my.telegram.org/apps) and log in.
2. Copy `API_ID` and `API_HASH` into the `.env` file.
3. Open [@BotFather](https://t.me/BotFather), create a new bot, copy `BOT_TOKEN`, and add it to `.env`.

Example `.env`:

```ini
API_ID=12345678
API_HASH=abcdefghijklmnopqrstuvwx12456789
BOT_TOKEN=1234567890:Aabcdefghijklmopqrtuvwxyz1234567890
```

> **Note:** no spaces around `=`!

---

## Installing dependencies

**Debian / Ubuntu:**

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
cd ~/QuiX-Saver
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Arch Linux:**

```bash
sudo pacman -Syu python python-virtualenv
cd ~/QuiX-Saver
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If prompted `[Y/n]`, choose `y` and press `Enter`.

---

## Running bot

```bash
cd ~/QuiX-Saver
source venv/bin/activate
python main.py
```

Keep the terminal open or the bot will stop.\
To stop manually, press `Ctrl+C`.

---

## Broadcast notifications (optional)

The folder contains `notify.py` and `mass_sent.txt`.

1. Write your broadcast message in `mass_sent.txt`.
2. Stop the bot (`Ctrl+C`).
3. Run:

```bash
source venv/bin/activate
python notify.py
```

4. Start the bot again:

```bash
python main.py
```

