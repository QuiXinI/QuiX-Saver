import os
import shutil
import sqlite3
import sys
import tempfile

try:
    import win32crypt
except ImportError:
    print("Ошибка: нет win32crypt (pywin32). Установи через 'pip install pywin32' и запускай снова.")
    sys.exit(1)

def get_chrome_cookies_db_path():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("Не найдена переменная окружения LOCALAPPDATA")
    # Собираем путь по частям, чтобы не было проблем с "\" в строке
    path = os.path.join(
        local_app_data,
        "Google", "Chrome", "User Data", "Default", "Network", "Cookies"
    )
    if not os.path.exists(path):
        raise FileNotFoundError(f"Не найден файл куки по пути: {path}")
    return path

def copy_db_to_temp(src_path):
    """
    Чтобы Chrome не ругался на лок (он может блокировать файл), копируем базу в temp.
    """
    tmp_dir = tempfile.mkdtemp(prefix="chrome_cookies_")
    dst_path = os.path.join(tmp_dir, "Cookies_copy.db")
    shutil.copy2(src_path, dst_path)
    return dst_path

def decrypt_cookie(encrypted_value):
    """
    Расшифровываем через Win DPAPI (win32crypt).
    Если что пошло не так — возвращаем пустую строку.
    """
    try:
        decrypted = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1]
        return decrypted.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def chrome_ts_to_unix(ts):
    """
    Хром хранит timestamp в микросекундах от 1601-01-01.
    Переводим в UNIX (секунды от 1970-01-01).
    """
    if ts == 0:
        return 0
    return int(ts / 1_000_000 - 11644473600)

def export_to_netscape(db_path, output_path):
    """
    Открываем копию файла, читаем таблицу cookies и пилим строки в формате Netscape:
    <домен>\t<флаг_поддоменов>\t<путь>\t<secure>\t<expires>\t<имя>\t<значение>\n
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT host_key, name, path, expires_utc, is_secure, is_httponly, encrypted_value
        FROM cookies
    """)

    header = (
        "# Netscape HTTP Cookie File\n"
        "# Сгенерировано автоматически, не бейте кукишник!\n\n"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        for host_key, name, path_, expires_utc, is_secure, is_httponly, encrypted_value in cursor.fetchall():
            include_subdomains = "TRUE" if host_key.startswith('.') else "FALSE"
            value = decrypt_cookie(encrypted_value)
            expiry = chrome_ts_to_unix(expires_utc)
            secure_flag = "TRUE" if is_secure else "FALSE"
            # В формате Netscape нет отдельного поля для HttpOnly, поэтому просто пропускаем is_httponly.
            line = f"{host_key}\t{include_subdomains}\t{path_}\t{secure_flag}\t{expiry}\t{name}\t{value}\n"
            f.write(line)

    conn.close()

def main():
    try:
        src = get_chrome_cookies_db_path()
    except Exception as e:
        print("Не удалось найти базу куки Chrome:", e)
        sys.exit(1)

    tmp_db = copy_db_to_temp(src)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "cookies.txt")

    try:
        export_to_netscape(tmp_db, output_file)
        print(f"[OK] cookies.txt сохранён сюда: {output_file}")
    except Exception as e:
        print("Что-то пошло не так при экспорте:", e)
    finally:
        try:
            os.remove(tmp_db)
        except OSError:
            pass

if __name__ == "__main__":
    main()
