import os
import sys
# Додаємо кореневу папку у шлях імпорту, щоб pytest бачив модуль
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import types
from unittest.mock import patch, MagicMock
import requests
from urllib.parse import urlparse

# Імпортуємо модуль, який тестуємо
import indexing_checks

# --- ТЕСТИ ДЛЯ clean_url_for_indexing_check ---

def test_clean_url_http_protocol():
    # Перевірка видалення http протоколу з URL
    assert indexing_checks.clean_url_for_indexing_check('http://example.com') == 'example.com'

def test_clean_url_https_protocol():
    # Перевірка видалення https протоколу з URL
    assert indexing_checks.clean_url_for_indexing_check('https://example.com') == 'example.com'

def test_clean_url_www():
    # Перевірка видалення www. з URL
    assert indexing_checks.clean_url_for_indexing_check('www.example.com') == 'example.com'

def test_clean_url_http_www():
    # Перевірка видалення як протоколу, так і www. з URL
    assert indexing_checks.clean_url_for_indexing_check('http://www.example.com') == 'example.com'

def test_clean_url_https_www():
    # Перевірка видалення як https протоколу, так і www. з URL
    assert indexing_checks.clean_url_for_indexing_check('https://www.example.com') == 'example.com'

def test_clean_url_with_path():
    # Перевірка URL з шляхом - повинен зберігатися шлях
    assert indexing_checks.clean_url_for_indexing_check('https://example.com/path/to/page') == 'example.com/path/to/page'

def test_clean_url_with_query_params():
    # Перевірка URL з параметрами запиту - повинні зберігатися параметри
    assert indexing_checks.clean_url_for_indexing_check('http://example.com/path?param=value') == 'example.com/path?param=value'

def test_clean_url_empty_string():
    # Перевірка порожнього рядка
    assert indexing_checks.clean_url_for_indexing_check('') == ''

def test_clean_url_no_protocol():
    # Перевірка URL без протоколу - не повинно змінитися
    assert indexing_checks.clean_url_for_indexing_check('example.com') == 'example.com'

def test_clean_url_multiple_www():
    # Перевірка URL з кількома www - видалення тільки першого www
    assert indexing_checks.clean_url_for_indexing_check('www.www.example.com') == 'www.example.com'

# --- ТЕСТИ ДЛЯ format_search_query ---

def test_format_search_query_simple_url():
    # Перевірка форматування простого URL без параметрів
    assert indexing_checks.format_search_query('https://example.com') == 'site:example.com'

def test_format_search_query_with_path():
    # Перевірка форматування URL з шляхом - без слешу в кінці
    assert indexing_checks.format_search_query('https://example.com/path') == 'site:example.com/path'

def test_format_search_query_with_trailing_slash():
    # Перевірка форматування URL з завершальним слешем
    assert indexing_checks.format_search_query('https://example.com/path/') == 'site:example.com/path/'

def test_format_search_query_with_query_params():
    # Перевірка форматування URL з параметрами запиту
    result = indexing_checks.format_search_query('https://example.com/path?param=value')
    assert result == 'site:example.com/path/ inurl:param=value'

def test_format_search_query_with_multiple_params():
    # Перевірка форматування URL з кількома параметрами запиту
    result = indexing_checks.format_search_query('https://example.com/path?param1=value1&param2=value2')
    assert result == 'site:example.com/path/ inurl:param1=value1 inurl:param2=value2'

def test_format_search_query_with_www():
    # Перевірка форматування URL з www
    assert indexing_checks.format_search_query('https://www.example.com') == 'site:example.com'

def test_format_search_query_with_no_path():
    # Перевірка форматування URL без шляху
    assert indexing_checks.format_search_query('https://example.com') == 'site:example.com'

def test_format_search_query_with_root_path():
    # Перевірка форматування URL з кореневим шляхом
    assert indexing_checks.format_search_query('https://example.com/') == 'site:example.com/'

def test_format_search_query_with_non_key_value_params():
    # Перевірка форматування URL з параметрами без структури ключ=значення
    result = indexing_checks.format_search_query('https://example.com/path?12345')
    assert result == 'site:example.com/path/ inurl:12345'

def test_format_search_query_with_double_slash():
    # Перевірка форматування URL з подвійним слешем
    result = indexing_checks.format_search_query('https://example.com/path//')
    assert result == 'site:example.com/path//'

# --- ТЕСТИ ДЛЯ check_google_indexing ---

@pytest.fixture
def mock_valueserp_indexed_response():
    # Фікстура для імітації відповіді API, коли URL проіндексований
    return {
        "organic_results": [
            {"title": "Example Page", "link": "https://example.com"}
        ],
        "search_information": {
            "total_results": 1
        }
    }

@pytest.fixture
def mock_valueserp_not_indexed_response():
    # Фікстура для імітації відповіді API, коли URL не проіндексований
    return {
        "organic_results": [],
        "search_information": {
            "total_results": 0,
            "original_query_yields_zero_results": True
        }
    }

def test_check_google_indexing_indexed(monkeypatch, mock_valueserp_indexed_response):
    # Перевірка поведінки функції, коли URL проіндексований
    mock_response = MagicMock()
    mock_response.json.return_value = mock_valueserp_indexed_response
    mock_response.raise_for_status = MagicMock()
    
    def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr(requests, 'get', mock_get)
    
    result, query = indexing_checks.check_google_indexing('https://example.com', 'test_api_key')
    assert result is True
    assert query == 'site:example.com'

def test_check_google_indexing_not_indexed(monkeypatch, mock_valueserp_not_indexed_response):
    # Перевірка поведінки функції, коли URL не проіндексований
    mock_response = MagicMock()
    mock_response.json.return_value = mock_valueserp_not_indexed_response
    mock_response.raise_for_status = MagicMock()
    
    def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr(requests, 'get', mock_get)
    
    result, query = indexing_checks.check_google_indexing('https://example.com', 'test_api_key')
    assert result is False
    assert query == 'site:example.com'

def test_check_google_indexing_no_search_information(monkeypatch):
    # Перевірка поведінки функції, коли у відповіді немає інформації про результати пошуку
    mock_response = MagicMock()
    mock_response.json.return_value = {"organic_results": []}
    mock_response.raise_for_status = MagicMock()
    
    def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr(requests, 'get', mock_get)
    
    result, query = indexing_checks.check_google_indexing('https://example.com', 'test_api_key')
    assert result is False
    assert query == 'site:example.com'

def test_check_google_indexing_http_error(monkeypatch):
    # Перевірка обробки HTTP помилок
    def mock_get(*args, **kwargs):
        raise requests.exceptions.HTTPError("HTTP Error")
    
    monkeypatch.setattr(requests, 'get', mock_get)
    
    result, query = indexing_checks.check_google_indexing('https://example.com', 'test_api_key')
    assert result is False
    assert query == 'site:example.com'

def test_check_google_indexing_connection_error(monkeypatch):
    # Перевірка обробки помилок з'єднання
    def mock_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Connection Error")
    
    monkeypatch.setattr(requests, 'get', mock_get)
    
    result, query = indexing_checks.check_google_indexing('https://example.com', 'test_api_key')
    assert result is False
    assert query == 'site:example.com'

def test_check_google_indexing_timeout_error(monkeypatch):
    # Перевірка обробки помилок тайм-ауту
    def mock_get(*args, **kwargs):
        raise requests.exceptions.Timeout("Timeout Error")
    
    monkeypatch.setattr(requests, 'get', mock_get)
    
    result, query = indexing_checks.check_google_indexing('https://example.com', 'test_api_key')
    assert result is False
    assert query == 'site:example.com'

def test_check_google_indexing_general_request_exception(monkeypatch):
    # Перевірка обробки загальних помилок запиту
    def mock_get(*args, **kwargs):
        raise requests.exceptions.RequestException("General Error")
    
    monkeypatch.setattr(requests, 'get', mock_get)
    
    result, query = indexing_checks.check_google_indexing('https://example.com', 'test_api_key')
    assert result is False
    assert query == 'site:example.com'

def test_check_google_indexing_unexpected_response_format(monkeypatch):
    # Перевірка обробки неочікуваного формату відповіді
    mock_response = MagicMock()
    mock_response.json.return_value = {"unexpected_key": "unexpected_value"}
    mock_response.raise_for_status = MagicMock()
    
    def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr(requests, 'get', mock_get)
    
    result, query = indexing_checks.check_google_indexing('https://example.com', 'test_api_key')
    assert result is False
    assert query == 'site:example.com'

def test_check_google_indexing_json_decode_error(monkeypatch):
    # Перевірка обробки помилок декодування JSON
    mock_response = MagicMock()
    mock_response.json.side_effect = ValueError("JSON decode error")
    mock_response.raise_for_status = MagicMock()
    
    def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr(requests, 'get', mock_get)
    
    result, query = indexing_checks.check_google_indexing('https://example.com', 'test_api_key')
    assert result is False
    assert query == 'site:example.com'

# Параметризовані тести

@pytest.mark.parametrize("input_url,expected_output", [
    ('http://example.com', 'example.com'),
    ('https://www.example.com', 'example.com'),
    ('www.example.com', 'example.com'),
    ('example.com', 'example.com'),
    ('https://www.example.com/path?param=value', 'example.com/path?param=value'),
])
def test_clean_url_parametrized(input_url, expected_output):
    # Параметризований тест для функції clean_url_for_indexing_check
    assert indexing_checks.clean_url_for_indexing_check(input_url) == expected_output

@pytest.mark.parametrize("input_url,expected_output", [
    ('https://example.com', 'site:example.com'),
    ('https://example.com/path', 'site:example.com/path'),
    ('https://example.com/path?param=value', 'site:example.com/path/ inurl:param=value'),
    ('https://example.com/path?param1=value1&param2=value2', 'site:example.com/path/ inurl:param1=value1 inurl:param2=value2'),
    ('https://example.com/path?123', 'site:example.com/path/ inurl:123'),
])
def test_format_search_query_parametrized(input_url, expected_output):
    # Параметризований тест для функції format_search_query
    assert indexing_checks.format_search_query(input_url) == expected_output

# ========================== ІНТЕГРАЦІЙНІ ТЕСТИ ==========================

def test_integration_clean_and_format_simple_url():
    # Інтеграційний тест для перевірки взаємодії функцій clean_url_for_indexing_check та format_search_query
    # на простому URL
    url = 'https://example.com'
    cleaned_url = indexing_checks.clean_url_for_indexing_check(url)
    assert cleaned_url == 'example.com'
    
    search_query = indexing_checks.format_search_query(url)
    assert search_query == 'site:example.com'

def test_integration_clean_and_format_complex_url():
    # Інтеграційний тест для перевірки взаємодії функцій clean_url_for_indexing_check та format_search_query
    # на складному URL з параметрами
    url = 'https://www.example.com/path/to/page?param1=value1&param2=value2'
    cleaned_url = indexing_checks.clean_url_for_indexing_check(url)
    assert cleaned_url == 'example.com/path/to/page?param1=value1&param2=value2'
    
    search_query = indexing_checks.format_search_query(url)
    assert search_query == 'site:example.com/path/to/page/ inurl:param1=value1 inurl:param2=value2'

def test_integration_format_and_check_indexed(monkeypatch, mock_valueserp_indexed_response):
    # Інтеграційний тест для перевірки взаємодії функцій format_search_query та check_google_indexing
    # коли URL проіндексований
    url = 'https://example.com/page'
    
    # Імітація HTTP запиту
    mock_response = MagicMock()
    mock_response.json.return_value = mock_valueserp_indexed_response
    mock_response.raise_for_status = MagicMock()
    
    def mock_get(*args, **kwargs):
        # Виправлено очікування запиту - без слешу в кінці
        expected_query = 'site:example.com/page'
        actual_query = kwargs['params']['q']
        assert actual_query == expected_query
        return mock_response
    
    monkeypatch.setattr(requests, 'get', mock_get)
    
    # Перевіряємо результат
    result, query = indexing_checks.check_google_indexing(url, 'test_api_key')
    assert result is True
    assert query == 'site:example.com/page'

def test_integration_format_and_check_not_indexed(monkeypatch, mock_valueserp_not_indexed_response):
    # Коригуємо очікуваний запит - без слешу в кінці
    url = 'https://example.com/not-indexed'
    
    mock_response = MagicMock()
    mock_response.json.return_value = mock_valueserp_not_indexed_response
    mock_response.raise_for_status = MagicMock()
    
    def mock_get(*args, **kwargs):
        expected_query = 'site:example.com/not-indexed'
        actual_query = kwargs['params']['q']
        assert actual_query == expected_query
        return mock_response
    
    monkeypatch.setattr(requests, 'get', mock_get)
    
    result, query = indexing_checks.check_google_indexing(url, 'test_api_key')
    assert result is False
    assert query == 'site:example.com/not-indexed'

def test_integration_full_pipeline(monkeypatch, mock_valueserp_indexed_response):
    # Інтеграційний тест для перевірки повного робочого циклу - від очищення URL до перевірки індексації
    url = 'https://www.example.com/products?category=electronics&brand=sony'
    
    # Перевіряємо очищення URL
    cleaned_url = indexing_checks.clean_url_for_indexing_check(url)
    assert cleaned_url == 'example.com/products?category=electronics&brand=sony'
    
    # Перевіряємо форматування пошукового запиту
    search_query = indexing_checks.format_search_query(url)
    assert search_query == 'site:example.com/products/ inurl:category=electronics inurl:brand=sony'
    
    # Імітація HTTP запиту
    mock_response = MagicMock()
    mock_response.json.return_value = mock_valueserp_indexed_response
    mock_response.raise_for_status = MagicMock()
    
    def mock_get(*args, **kwargs):
        # Перевіряємо, що до API передається правильно сформований запит
        actual_query = kwargs['params']['q']
        assert actual_query == search_query
        return mock_response
    
    monkeypatch.setattr(requests, 'get', mock_get)
    
    # Перевіряємо результат повного циклу
    result, query = indexing_checks.check_google_indexing(url, 'test_api_key')
    assert result is True
    assert query == search_query