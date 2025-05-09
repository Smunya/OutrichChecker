import os
import sys
# Додаємо кореневу папку у шлях імпорту, щоб pytest бачив модуль
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import types  # для створення простих «фейкових» об'єктів у тестах
from bs4 import BeautifulSoup
from unittest.mock import patch, Mock

import seo_checks  # Імпортуємо модуль, який тестуємо

# ------------------------ ТЕСТИ ДЛЯ check_robots_txt ------------------------

@pytest.mark.parametrize("status_code, expected", [
    (200, True),
    (404, True),
    (500, True),
])
def test_check_robots_txt_status_codes(status_code, expected):
    # Перевірка, як функція обробляє різні статус-коди відповіді на robots.txt
    with patch('requests.get') as mock_get:
        mock_resp = Mock()
        mock_resp.status_code = status_code
        mock_resp.text = "User-agent: *\nDisallow:"
        mock_get.return_value.__enter__.return_value = mock_resp

        result = seo_checks.check_robots_txt("http://example.com")
        assert result == expected

def test_check_robots_txt_disallow():
    # Перевірка, коли robots.txt забороняє доступ
    with patch('requests.get') as mock_get:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "User-agent: *\nDisallow: /"
        mock_get.return_value.__enter__.return_value = mock_resp

        result = seo_checks.check_robots_txt("http://example.com/page")
        assert result is False

def test_check_robots_txt_allow_specific_user_agent():
    # Перевірка для специфічного user-agent, який дозволено
    with patch('requests.get') as mock_get:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "User-agent: Googlebot\nDisallow:"
        mock_get.return_value.__enter__.return_value = mock_resp

        result = seo_checks.check_robots_txt("http://example.com/page", user_agent="Googlebot")
        assert result is True

def test_check_robots_txt_disallow_specific_user_agent():
    # Перевірка для специфічного user-agent, якому заборонено
    with patch('requests.get') as mock_get:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "User-agent: Googlebot\nDisallow: /"
        mock_get.return_value.__enter__.return_value = mock_resp

        result = seo_checks.check_robots_txt("http://example.com/page", user_agent="Googlebot")
        assert result is False

def test_check_robots_txt_network_error():
    # Перевірка, що при винятку (наприклад, проблеми з мережею) повертається True
    with patch('requests.get', side_effect=Exception("Connection error")):
        result = seo_checks.check_robots_txt("http://example.com")
        assert result is True

def test_check_robots_txt_none_url():
    # Перевірка, що передача None не викликає помилку і функція повертає True
    with patch('requests.get', side_effect=Exception("Invalid URL")):
        result = seo_checks.check_robots_txt(None)
        assert result is True

def test_check_robots_txt_invalid_url():
    # Перевірка роботи з невалідним URL
    with patch('requests.get', side_effect=Exception("Invalid URL format")):
        result = seo_checks.check_robots_txt("not-a-valid-url")
        assert result is True

def test_check_robots_txt_verify_ssl_false():
    # Перевірка, що параметр verify_ssl передається у запит
    with patch('requests.get') as mock_get:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "User-agent: *\nDisallow:"
        mock_get.return_value.__enter__.return_value = mock_resp

        result = seo_checks.check_robots_txt("http://example.com", verify_ssl=False)
        assert result is True
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs["verify"] is False

# ========================== Далі йдуть інші функції ==========================

# ------------------------ ТЕСТИ ДЛЯ check_indexing_directives ------------------------

def test_indexing_directives_x_robots_tag():
    # Перевірка X-Robots-Tag у заголовках
    headers = {"X-Robots-Tag": "noindex, nofollow"}
    html = "<html></html>"
    result = seo_checks.check_indexing_directives("http://example.com", headers, html)
    assert result == {'noindex': True, 'nofollow': True, 'source': 'X-Robots-Tag'}

def test_indexing_directives_meta_googlebot():
    # Перевірка директиви в мета-тегу googlebot
    headers = {}
    html = '<html><head><meta name="googlebot" content="noindex, nofollow"></head></html>'
    result = seo_checks.check_indexing_directives("http://example.com", headers, html)
    assert result == {'noindex': True, 'nofollow': True, 'source': 'Meta Googlebot'}

def test_indexing_directives_meta_robots():
    # Перевірка директиви в мета-тегу robots
    headers = {}
    html = '<html><head><meta name="robots" content="noindex"></head></html>'
    result = seo_checks.check_indexing_directives("http://example.com", headers, html)
    assert result == {'noindex': True, 'nofollow': False, 'source': 'Meta Robots'}

def test_indexing_directives_empty():
    # Коли директиви відсутні повністю
    headers = {}
    html = '<html><head></head><body></body></html>'
    result = seo_checks.check_indexing_directives("http://example.com", headers, html)
    assert result == {'noindex': False, 'nofollow': False, 'source': None}

def test_indexing_directives_invalid_html():
    # Некоректний HTML не повинен викликати помилку
    headers = {}
    html = '<html><head><meta name="robots" content="nofollow"></body>'
    result = seo_checks.check_indexing_directives("http://example.com", headers, html)
    assert result == {'noindex': False, 'nofollow': True, 'source': 'Meta Robots'}

def test_indexing_directives_mixed_case_header():
    # Перевірка, що заголовки не чутливі до регістру
    headers = {"x-robots-tag": "NOINDEX"}
    html = ""
    result = seo_checks.check_indexing_directives("http://example.com", headers, html)
    assert result['noindex'] is True
    assert result['source'] == "X-Robots-Tag"

# ------------------------ ТЕСТИ ДЛЯ check_canonical_tag ------------------------

def test_canonical_tag_match():
    # Перевірка, коли canonical співпадає з поточним URL
    html = '<html><head><link rel="canonical" href="http://example.com/page"/></head></html>'
    result = seo_checks.check_canonical_tag("http://example.com/page", html)
    assert result == "http://example.com/page"

def test_canonical_tag_differs():
    # Перевірка, коли canonical відрізняється
    html = '<html><head><link rel="canonical" href="http://example.com/other"/></head></html>'
    result = seo_checks.check_canonical_tag("http://example.com/page", html)
    assert result == "http://example.com/other"

def test_canonical_tag_relative_url():
    # Перевірка, коли canonical є відносним шляхом
    html = '<html><head><link rel="canonical" href="/relative"/></head></html>'
    result = seo_checks.check_canonical_tag("http://example.com/page", html)
    assert result == "http://example.com/relative"

def test_canonical_tag_missing():
    # Перевірка, коли canonical тег відсутній
    html = '<html><head></head><body></body></html>'
    result = seo_checks.check_canonical_tag("http://example.com/page", html)
    assert result is None

def test_canonical_tag_invalid_html():
    # Перевірка, коли HTML пошкоджений
    html = '<html><head><link rel="canonical" href="http://example.com"></head><body>'
    result = seo_checks.check_canonical_tag("http://example.com/page", html)
    assert result == "http://example.com/"

# ------------------------ ТЕСТИ ДЛЯ check_links_on_page ------------------------

def test_links_on_page_exact_match():
    # Перевірка точного співпадіння URL і анкору
    html = '<a href="https://example.com/page1">Anchor 1</a>'
    result = seo_checks.check_links_on_page(html, "https://example.com", "Anchor 1", "https://example.com/page1", None, None, None, None)
    assert result['url1_found'] == "Так"
    assert result['anchor1_match'] == "Так"

def test_links_on_page_url_match_only():
    # URL знайдено, але анкор не співпадає
    html = '<a href="https://example.com/page1">Wrong Anchor</a>'
    result = seo_checks.check_links_on_page(html, "https://example.com", "Anchor 1", "https://example.com/page1", None, None, None, None)
    assert result['url1_found'] == "Так"
    assert result['anchor1_match'] == "Ні"

def test_links_on_page_not_found():
    # Посилання повністю відсутнє
    html = '<a href="https://example.com/other">Other</a>'
    result = seo_checks.check_links_on_page(html, "https://example.com", "Anchor 1", "https://example.com/page1", None, None, None, None)
    assert result['url1_found'] == "Ні"
    assert result['anchor1_match'] == "Ні"

def test_links_on_page_with_rel():
    # Посилання з rel="nofollow"
    html = '<a href="https://example.com/page1" rel="nofollow">Anchor 1</a>'
    result = seo_checks.check_links_on_page(html, "https://example.com", "Anchor 1", "https://example.com/page1", None, None, None, None)
    assert result['url1_rel'] == "nofollow"

def test_links_on_page_multiple():
    # Перевірка трьох пар одночасно
    html = '''
    <a href="https://example.com/page1">Anchor 1</a>
    <a href="https://example.com/page2">Anchor 2</a>
    <a href="https://example.com/page3" rel="sponsored">Anchor 3</a>
    '''
    result = seo_checks.check_links_on_page(
        html, "https://example.com",
        "Anchor 1", "https://example.com/page1",
        "Anchor 2", "https://example.com/page2",
        "Anchor 3", "https://example.com/page3"
    )
    assert result['url1_found'] == "Так"
    assert result['anchor1_match'] == "Так"
    assert result['url2_found'] == "Так"
    assert result['anchor2_match'] == "Так"
    assert result['url3_found'] == "Так"
    assert result['anchor3_match'] == "Так"
    assert result['url3_rel'] == "sponsored"

# ========================== ІНТЕГРАЦІЙНІ ТЕСТИ ==========================

# Інтеграційний тест: різні комбінації rel="nofollow", rel="sponsored" і некоректний анкор
def test_links_with_mixed_rel_and_wrong_anchor():
    url = "http://example.com/page"
    html = '''
    <html>
        <body>
            <a href="http://example.com/page1" rel="nofollow">Different Anchor</a>
            <a href="http://example.com/page2" rel="sponsored">Anchor 2</a>
        </body>
    </html>
    '''
    headers = {}

    directives = seo_checks.check_indexing_directives(url, headers, html)
    assert directives['source'] is None

    results = seo_checks.check_links_on_page(
        html, url,
        "Expected Anchor", "http://example.com/page1",
        "Anchor 2", "http://example.com/page2",
        None, None
    )
    assert results['url1_found'] == "Так"
    assert results['anchor1_match'] == "Ні"
    assert results['url1_rel'] == "nofollow"
    assert results['url2_found'] == "Так"
    assert results['anchor2_match'] == "Так"
    assert results['url2_rel'] == "sponsored"

# Інтеграційний тест: rel відсутній, але правильний анкор і url
def test_links_without_rel_but_correct_anchor():
    url = "http://example.com/page"
    html = '''
    <html>
        <body>
            <a href="http://example.com/page1">Correct Anchor</a>
        </body>
    </html>
    '''
    results = seo_checks.check_links_on_page(html, url, "Correct Anchor", "http://example.com/page1", None, None, None, None)
    assert results['url1_found'] == "Так"
    assert results['anchor1_match'] == "Так"
    assert results['url1_rel'] is None

# Інтеграційний тест: повна перевірка сторінки на robots.txt, мета-теги, canonical і посилання
@patch('requests.get')
def test_full_page_analysis(mock_get):
    # Мокаємо robots.txt, який дозволяє доступ
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.text = "User-agent: *\nDisallow:"
    mock_get.return_value.__enter__.return_value = mock_resp

    url = "http://example.com/page"
    html = '''
    <html>
        <head>
            <meta name="robots" content="noindex, nofollow">
            <link rel="canonical" href="http://example.com/page">
        </head>
        <body>
            <a href="http://example.com/page1">Anchor 1</a>
        </body>
    </html>
    '''
    headers = {}

    # Перевірка robots.txt
    is_allowed = seo_checks.check_robots_txt(url)
    assert is_allowed is True

    # Перевірка мета-директив
    directives = seo_checks.check_indexing_directives(url, headers, html)
    assert directives['noindex'] is True
    assert directives['nofollow'] is True

    # Перевірка canonical
    canonical = seo_checks.check_canonical_tag(url, html)
    assert canonical == url

    # Перевірка посилань
    link_results = seo_checks.check_links_on_page(html, url, "Anchor 1", "http://example.com/page1", None, None, None, None)
    assert link_results['url1_found'] == "Так"
    assert link_results['anchor1_match'] == "Так"

# Інтеграційний тест: коли відсутній robots.txt і canonical не збігається
@patch('requests.get')
def test_no_robots_and_different_canonical(mock_get):
    mock_resp = Mock()
    mock_resp.status_code = 404
    mock_get.return_value.__enter__.return_value = mock_resp

    url = "http://example.com/page"
    html = '''
    <html>
        <head>
            <link rel="canonical" href="http://example.com/different">
        </head>
    </html>
    '''
    headers = {"X-Robots-Tag": "index, follow"}

    is_allowed = seo_checks.check_robots_txt(url)
    assert is_allowed is True

    directives = seo_checks.check_indexing_directives(url, headers, html)
    assert directives['noindex'] is False
    assert directives['nofollow'] is False

    canonical = seo_checks.check_canonical_tag(url, html)
    assert canonical == "http://example.com/different"

# Інтеграційний тест: лише мета-тег googlebot і rel="nofollow"
def test_googlebot_meta_and_rel_nofollow():
    url = "http://example.com/page"
    html = '''
    <html>
        <head>
            <meta name="googlebot" content="noindex">
        </head>
        <body>
            <a href="http://example.com/page1" rel="nofollow">Anchor 1</a>
        </body>
    </html>
    '''
    headers = {}

    directives = seo_checks.check_indexing_directives(url, headers, html)
    assert directives['noindex'] is True
    assert directives['nofollow'] is False

    link_results = seo_checks.check_links_on_page(html, url, "Anchor 1", "http://example.com/page1", None, None, None, None)
    assert link_results['url1_rel'] == "nofollow"
