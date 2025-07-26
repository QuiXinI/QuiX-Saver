# Быстрый старт на Windows для локального хостинга личной копии бота

**Другие системы:** ***[Windows](./readme_ru_win.md)*** | [Linux](./readme_ru_linux.md)

**Языки:** [English](./readme.md) | ***[Русский](./readme_ru_win.md)***

---

## Клонирование репозитория

**Скопируйте в Powershell или CMD**, измените `C:\Code\QuiX-Saver` на предпочитаемую директорию или удалите путь:

```powershell
git clone https://github.com/QuiXinI/QuiX-Saver.git C:\Code\QuiX-Saver
```

## Создание `.env`

```powershell
cd C:\Code\QuiX-Saver
New-Item .env -Type File
```

*(или через Проводник Windows)*

---

## Получение ключей API

1. Перейдите на [my.telegram.org](https://my.telegram.org/apps) и авторизуйтесь.
2. Скопируйте `API_ID` и `API_HASH` в файл `.env`.
3. Откройте [@BotFather](https://t.me/BotFather), создайте нового бота и скопируйте `BOT_TOKEN` в `.env`.

Пример `.env`:

```ini
API_ID=12345678
API_HASH=abcdefghijklmnopqrstuvwx12456789
BOT_TOKEN=1234567890:Aabcdefghijklmopqrtuvwxyz1234567890
```

> **Важно:** никаких пробелов вокруг `=`!

---

## Установка зависимостей

Убедитесь, что установлен Python 3.10+ (протестировано на 3.10–3.14b01).

```powershell
cd C:\Code\QuiX-Saver
python -m venv venv
venv\Scripts\Activate.ps1  # либо Activate.bat
pip install -r requirements.txt
```

Если спросят `[Y/n]`, нажмите `y` + `Enter`.

---

## Запуск бота

```powershell
cd C:\Code\QuiX-Saver
venv\Scripts\Activate.ps1
python main.py
```

Не закрывайте окно — иначе бот остановится.
Для принудительной остановки нажмите `Ctrl+C`.

---

## Рассылка уведомлений (опционально)

В папке есть `notify.py` и `mass_sent.txt`.

1. В `mass_sent.txt` напишите сообщение для рассылки.
2. Остановите бота (`Ctrl+C`).
3. Запустите:

```powershell
venv\Scripts\Activate.ps1
python notify.py
```

4. После завершения запустите бота снова:

```powershell
python main.py
```

