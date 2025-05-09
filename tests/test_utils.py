import os
import sys
# Додаємо кореневу папку у шлях імпорту, щоб pytest бачив модуль
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import types  # для створення простих «фейкових» об'єктів у тестах
import utils  # Імпортуємо модуль, який тестуємо

# ------------------------ ТЕСТИ ДЛЯ normalize_text ------------------------

def test_normalize_text_basic():
    # Перевірка базової нормалізації тексту з діакритикою та пробілами
    assert utils.normalize_text("Café  del   Mar") == "cafe del mar"

def test_normalize_text_uppercase():
    # Перевірка перетворення на нижній регістр
    assert utils.normalize_text("HELLO") == "hello"

def test_normalize_text_combined_chars():
    # Перевірка видалення комбінованих діакритичних символів
    assert utils.normalize_text("Ångström") == "angstrom"

def test_normalize_text_empty_string():
    # Перевірка обробки порожнього рядка
    assert utils.normalize_text("") == ""

def test_normalize_text_none():
    # Перевірка обробки None як вхідного значення
    assert utils.normalize_text(None) == ""

def test_normalize_text_whitespace():
    # Перевірка видалення зайвих пробілів
    assert utils.normalize_text("  this   is  spaced ") == "this is spaced"

def test_normalize_text_numeric():
    # Перевірка числового вводу
    assert utils.normalize_text(12345) == "12345"

def test_normalize_text_symbols():
    # Перевірка обробки символів
    assert utils.normalize_text("!@# Café $$$") == "!@# cafe $$$"

@pytest.mark.parametrize("input_text,expected", [
    ("Résumé", "resume"),
    ("mañana", "manana"),
    ("naïve", "naive"),
    (" coöperate ", "cooperate"),
    ("  Über cool ", "uber cool")
])
def test_normalize_text_parametrized(input_text, expected):
    # Параметризований тест нормалізації тексту з діакритикою та пробілами
    assert utils.normalize_text(input_text) == expected

# ------------------------ ТЕСТИ ДЛЯ normalize_url ------------------------

def test_normalize_url_with_path():
    # Перевірка URL, який вже має шлях
    assert utils.normalize_url("https://example.com/page") == "https://example.com/page"

def test_normalize_url_root():
    # Перевірка додавання слешу до кореневого URL
    assert utils.normalize_url("https://example.com") == "https://example.com/"

def test_normalize_url_with_query():
    # Перевірка збереження параметрів запиту
    assert utils.normalize_url("https://example.com?x=1") == "https://example.com/?x=1"

def test_normalize_url_with_fragment():
    # Перевірка збереження фрагментів URL
    assert utils.normalize_url("https://example.com#top") == "https://example.com/#top"

def test_normalize_url_empty():
    # Перевірка обробки порожнього URL
    assert utils.normalize_url("") == ""

def test_normalize_url_none():
    # Перевірка обробки None
    assert utils.normalize_url(None) == None

def test_normalize_url_invalid():
    # Перевірка некоректного URL
    assert utils.normalize_url("not a url") == "not a url"

# ------------------------ ТЕСТИ ДЛЯ extract_sheet_params ------------------------

def test_extract_sheet_params_valid():
    # Перевірка витягування sheet_id і gid з правильного URL
    url = "https://docs.google.com/spreadsheets/d/abc12345678/edit#gid=789"
    assert utils.extract_sheet_params(url) == ("abc12345678", 789)

def test_extract_sheet_params_gid_in_query():
    # Перевірка, коли gid знаходиться в query, а не в fragment
    url = "https://docs.google.com/spreadsheets/d/xyz987654321/view?gid=456"
    assert utils.extract_sheet_params(url) == ("xyz987654321", 456)

def test_extract_sheet_params_gid_missing():
    # Перевірка коли gid відсутній
    url = "https://docs.google.com/spreadsheets/d/sheetID/view"
    assert utils.extract_sheet_params(url) == ("sheetID", 0)

def test_extract_sheet_params_invalid_url():
    # Перевірка некоректного URL без ID
    url = "https://docs.google.com/view"
    assert utils.extract_sheet_params(url) == (None, None)

def test_extract_sheet_params_non_numeric_gid():
    # Перевірка некоректного gid
    url = "https://docs.google.com/spreadsheets/d/abc123/edit#gid=xyz"
    assert utils.extract_sheet_params(url) == ("abc123", 0)

# ------------------------ ТЕСТИ ДЛЯ is_ssl_error ------------------------

def test_is_ssl_error_certificate():
    # Перевірка тексту, що містить слово "certificate"
    assert utils.is_ssl_error("certificate error")

def test_is_ssl_error_ssl():
    # Перевірка наявності ключового слова ssl
    assert utils.is_ssl_error("SSL handshake failed")

def test_is_ssl_error_unrelated():
    # Перевірка не пов'язаної помилки
    assert not utils.is_ssl_error("connection timeout")

def test_is_ssl_error_case_insensitive():
    # Перевірка регістронезалежності
    assert utils.is_ssl_error("CertIFICATE_VERIFY_FAILED")

# ------------------------ ТЕСТИ ДЛЯ detect_encoding ------------------------

def test_detect_encoding_utf8():
    # Тест для стандартного utf-8 байтового контенту
    text = "Привіт світ".encode("utf-8")
    assert utils.detect_encoding(text) == "utf-8"

def test_detect_encoding_ascii_cyrillic():
    # ascii байти з кирилицею повинні дати windows-1251
    bytes_with_cyrillic = bytes([0xCF, 0xF0, 0xE8])  # частина слова "Прив"
    assert utils.detect_encoding(bytes_with_cyrillic) == "windows-1251"

def test_detect_encoding_unknown():
    # Тест коли chardet не може визначити кодування
    assert utils.detect_encoding(b"") == "utf-8"

# ========================== ІНТЕГРАЦІЙНІ ТЕСТИ ==========================

def test_integration_normalize_text_and_url():
    # Перевірка взаємодії normalize_text та normalize_url для URL з діакритикою у фрагменті
    url = "https://example.com#Café"
    normalized_url = utils.normalize_url(url)
    assert utils.normalize_text(normalized_url) == "https://example.com/#cafe"

def test_integration_extract_and_normalize():
    # Перевірка послідовності витягування ID та нормалізації URL
    url = "https://docs.google.com/spreadsheets/d/TestID/edit#gid=2"
    sheet_id, gid = utils.extract_sheet_params(url)
    normalized = utils.normalize_url(url)
    assert sheet_id == "TestID"
    assert gid == 2
    assert normalized.startswith("https://docs.google.com/")

def test_integration_encoding_and_text():
    # Визначення кодування і далі нормалізація тексту
    text = "Résumé avec naïve touché".encode("utf-8")
    encoding = utils.detect_encoding(text)
    assert encoding == "utf-8"
    decoded = text.decode(encoding)
    assert utils.normalize_text(decoded) == "resume avec naive touche"

def test_integration_error_detection_and_text():
    # Взаємодія is_ssl_error та normalize_text для журналу помилок
    log = "SSL CERTIFICATE_VERIFY_FAILED during fetch"
    assert utils.is_ssl_error(log)
    assert utils.normalize_text(log) == "ssl certificate_verify_failed during fetch"

def test_integration_sheet_url_gid():
    # Повна перевірка URL Google таблиці з нормалізацією та витягом параметрів
    url = "https://docs.google.com/spreadsheets/d/MySheetID/edit?gid=15"
    normalized_url = utils.normalize_url(url)
    sheet_id, gid = utils.extract_sheet_params(normalized_url)
    assert sheet_id == "MySheetID"
    assert gid == 15
    assert normalized_url.endswith("?gid=15")
