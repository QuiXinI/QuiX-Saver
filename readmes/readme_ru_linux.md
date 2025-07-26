# Быстрый старт на Linux для локального хостинга личной копии бота

**Другие системы:** [Windows](./readme_ru_win.md) | ***[Linux](./readme_ru_linux.md)***

**Языки:** [English](./readme_eng_linux.md) | ***[Русский](./readme_ru_linux.md)***

---

## Клонирование репозитория

**Скопируйте в терминал**, замените `~/QuiX-Saver` на нужную папку или уберите путь:

```bash
git clone https://github.com/QuiXinI/QuiX-Saver.git ~/QuiX-Saver
```

## Создание `.env`

```bash
cd ~/QuiX-Saver
touch .env
```

---

## Получение ключей API

1. Перейдите на [my.telegram.org](https://my.telegram.org/apps) и авторизуйтесь.
2. Скопируйте `API_ID` и `API_HASH` в файл `.env`.
3. Откройте [@BotFather](https://t.me/BotFather), создайте бота и вставьте `BOT_TOKEN` в `.env`.

Пример `.env`:

```ini
API_ID=12345678
API_HASH=abcdefghijklmnopqrstuvwx12456789
BOT_TOKEN=1234567890:Aabcdefghijklmopqrtuvwxyz1234567890
```

> **Важно:** не используйте пробелы вокруг `=`!

---

## Установка зависимостей

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

Нажмите `y` и `Enter`, если система спросит `[Y/n]`.

---

## Запуск бота

```bash
cd ~/QuiX-Saver
source venv/bin/activate
python main.py
```

Не закрывайте терминал, иначе бот остановится.\
Для остановки: `Ctrl+C`.

---

## Рассылка уведомлений (опционально)

В директории лежат `notify.py` и `mass_sent.txt`.

1. Напишите текст рассылки в `mass_sent.txt`.
2. Прервите бота (`Ctrl+C`).
3. Выполните:

```bash
source venv/bin/activate
python notify.py
```

4. Запустите бота снова:

```bash
python main.py
```

