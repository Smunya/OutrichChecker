# Встановлення необхідних бібліотек тільки якщо вони відсутні
import sys

# Імпорти для роботи програми
import pandas
import gspread
import requests
import importlib.util

# Імпорти для Colab
from google.colab import auth
from google.auth import default
from IPython.utils.io import capture_output
from IPython.display import clear_output

# Імпорт основних функцій з модулів
from gsheet_utils import check_sheet_structure, display_sheet_validation_results, update_sheet_with_results
from request_processor import check_status_code_requests

#
# 6. ГОЛОВНА ФУНКЦІЯ
#
def main(google_sheet, valueserp_api_key=None):
    """Головна функція, що запускає перевірку та виводить результати."""
    # Авторизуємося в Google через Colab
    try:
        print("Авторизуємося в Google (Colab)...")
        auth.authenticate_user()
        print("Авторизація в Google пройшла успішно.")
    except Exception as auth_e:
        print(f"Помилка авторизації в Google: {auth_e}", file=sys.stderr)
        return # Зупиняємо виконання, якщо авторизація не вдалась

    # Перевірка наявності API ключа для ValueSerp
    if not valueserp_api_key:
        print("⚠️ Попередження: API ключ ValueSerp не вказано. Перевірка індексації в Google буде пропущена.")

    # Перевірка структури таблиці (викликає gspread.authorize всередині)
    result = check_sheet_structure(google_sheet)
    display_sheet_validation_results(result)

    if result["success"]:
        data = result["data"]
        headers = data[0]
        rows = data[1:]

        # Знаходимо індекси потрібних стовпців
        try:
            idx_url = headers.index("Url")
            idx_anchor1 = headers.index("Анкор-1")
            idx_url1 = headers.index("Урл-1")
            # Додаємо обробку можливої відсутності Анкор-2/Урл-2 та Анкор-3/Урл-3
            idx_anchor2 = headers.index("Анкор-2") if "Анкор-2" in headers else -1
            idx_url2 = headers.index("Урл-2") if "Урл-2" in headers else -1
            idx_anchor3 = headers.index("Анкор-3") if "Анкор-3" in headers else -1
            idx_url3 = headers.index("Урл-3") if "Урл-3" in headers else -1
        except ValueError as e:
            print(f"Помилка: Не знайдено обов'язковий стовпець ('Анкор-1', 'Урл-1', 'Url', або опціональні 'Анкор-2/3', 'Урл-2/3') у заголовках: {e}")
            return

        # Формуємо список словників для передачі в check_status_code_requests
        rows_to_check = []
        for row_idx, row in enumerate(rows, 2): # Починаємо нумерацію рядків з 2 для повідомлень
            # Перевіряємо, чи рядок достатньо довгий для зчитування *обов'язкових* полів
            min_required_len = max(idx_anchor1, idx_url1, idx_url) + 1
            if len(row) < min_required_len:
                 print(f"Попередження: Рядок {row_idx}: Пропускаємо короткий рядок (менше {min_required_len} стовпців): {row}")
                 continue

            row_data = {
                "Анкор-1": row[idx_anchor1],
                "Урл-1": row[idx_url1],
                # Додаємо Анкор/Урл 2 і 3 з перевіркою індексу та довжини рядка
                "Анкор-2": row[idx_anchor2] if idx_anchor2 != -1 and idx_anchor2 < len(row) else None,
                "Урл-2": row[idx_url2] if idx_url2 != -1 and idx_url2 < len(row) else None,
                "Анкор-3": row[idx_anchor3] if idx_anchor3 != -1 and idx_anchor3 < len(row) else None,
                "Урл-3": row[idx_url3] if idx_url3 != -1 and idx_url3 < len(row) else None,
                "Url": row[idx_url]
            }
            # Додаємо тільки якщо є URL для перевірки
            if row_data["Url"]:
                rows_to_check.append(row_data)
            else:
                 print(f"Попередження: Рядок {row_idx}: Порожній 'Url', пропускаємо.")

        if not rows_to_check:
            print("Не знайдено жодного URL для перевірки в таблиці.")
            return

        check_results = check_status_code_requests(rows_to_check, valueserp_api_key)

        update_sheet_with_results(result["worksheet"], check_results)

# Перевірка Google таблиці
google_sheet = "" # @param {"type":"string"}

# Запуск головної функції
if __name__ == "__main__":
    # Перевіряємо, чи передано аргументи командного рядка
    if len(sys.argv) > 1:
        google_sheet = sys.argv[1]
        
        # Перевіряємо, чи передано API ключ ValueSerp
        valueserp_api_key = sys.argv[2] if len(sys.argv) > 2 else None
        
        main(google_sheet, valueserp_api_key)
    else:
        # Якщо аргументи не передані, використовуємо значення за замовчуванням
        main(google_sheet)
