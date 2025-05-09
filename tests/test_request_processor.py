import os
import sys
# Додаємо кореневу папку у шлях імпорту, щоб pytest бачив модулі
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import request_processor
from request_processor import (
    _perform_seo_and_link_checks,
    _process_response
)

# Заглушки для SEO-функцій

def stub_check_robots_txt(url, user_agent, verify_ssl=True):
    return user_agent == '*'

def stub_check_indexing_directives(url, headers, html):
    return {'noindex': False, 'nofollow': False, 'source': 'stub'}

def stub_check_canonical_tag(url, html):
    return url + '/canonical'

def stub_check_links_on_page(html, page_url, a1, u1, a2, u2, a3, u3):
    return {
        'url1_found': 'Так', 'anchor1_match': 'Так', 'url1_rel': None,
        'url2_found': 'Ні', 'anchor2_match': 'Ні', 'url2_rel': None,
        'url3_found': 'Ні', 'anchor3_match': 'Ні', 'url3_rel': None,
        'error': None
    }

@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch):
    # Патчимо всі зовнішні виклики усередині _perform_seo_and_link_checks
    monkeypatch.setattr(request_processor, 'check_robots_txt', stub_check_robots_txt)
    monkeypatch.setattr(request_processor, 'check_indexing_directives', stub_check_indexing_directives)
    monkeypatch.setattr(request_processor, 'check_canonical_tag', stub_check_canonical_tag)
    monkeypatch.setattr(request_processor, 'check_links_on_page', stub_check_links_on_page)

# ------------------ Тести для _perform_seo_and_link_checks ------------------

def test_perform_seo_and_link_checks_success():
    result = _perform_seo_and_link_checks(
        final_url='http://example.com', html_content='<html/>',
        get_headers={'H': 'V'}, anchor1='a1', url1='u1',
        anchor2='a2', url2='u2', anchor3='a3', url3='u3', verify_ssl=False
    )
    assert result['robots_star_allowed'] is True
    assert result['robots_googlebot_allowed'] is False
    assert result['indexing_directives'] == {'noindex': False, 'nofollow': False, 'source': 'stub'}
    assert result['canonical_url'] == 'http://example.com/canonical'
    assert result['url1_found'] == 'Так'
    assert result['anchor1_match'] == 'Так'
    assert result['url2_found'] == 'Ні'
    assert result['link_check_error'] is None


def test_indexing_directives_receives_headers(monkeypatch):
    captured = {}
    def fake_cid(url, headers, html):
        captured['headers'] = headers
        return {}
    monkeypatch.setattr(request_processor, 'check_indexing_directives', fake_cid)
    monkeypatch.setattr(request_processor, 'check_robots_txt', lambda *args, **kwargs: True)
    monkeypatch.setattr(request_processor, 'check_canonical_tag', lambda u, h: None)
    monkeypatch.setattr(request_processor, 'check_links_on_page', lambda *args, **kwargs: {
        'url1_found':'Ні','anchor1_match':'Ні','url1_rel':None,
        'url2_found':'Ні','anchor2_match':'Ні','url2_rel':None,
        'url3_found':'Ні','anchor3_match':'Ні','url3_rel':None,'error':None
    })
    _perform_seo_and_link_checks('url','html',{'X':'Y'},'','','','','','')
    assert captured['headers'] == {'X': 'Y'}


def test_seo_check_exception(monkeypatch):
    def fake_crt(url, ua, verify_ssl):
        raise RuntimeError('robots error')
    monkeypatch.setattr(request_processor, 'check_robots_txt', fake_crt)
    monkeypatch.setattr(request_processor, 'check_indexing_directives', stub_check_indexing_directives)
    monkeypatch.setattr(request_processor, 'check_canonical_tag', stub_check_canonical_tag)
    monkeypatch.setattr(request_processor, 'check_links_on_page', stub_check_links_on_page)
    result = _perform_seo_and_link_checks('u','h',{},'','','','','','')
    assert 'seo_check_error' in result
    assert 'robots error' in result['seo_check_error']


def test_link_check_error_leads_to_link_check_error_field(monkeypatch):
    monkeypatch.setattr(request_processor, 'check_robots_txt', lambda *args, **kwargs: True)
    monkeypatch.setattr(request_processor, 'check_indexing_directives', stub_check_indexing_directives)
    monkeypatch.setattr(request_processor, 'check_canonical_tag', stub_check_canonical_tag)
    def fake_clop(*args, **kwargs):
        return {'error': 'link parse fail'}
    monkeypatch.setattr(request_processor, 'check_links_on_page', fake_clop)
    result = _perform_seo_and_link_checks('u','h',{},'','','','','','')
    assert result['link_check_error'] == 'link parse fail'
    assert result['seo_check_error'] is None


def test_verify_ssl_forwarded(monkeypatch):
    calls = []
    def fake_crt(url, ua, verify_ssl):
        calls.append((ua, verify_ssl))
        return True
    monkeypatch.setattr(request_processor, 'check_robots_txt', fake_crt)
    monkeypatch.setattr(request_processor, 'check_indexing_directives', stub_check_indexing_directives)
    monkeypatch.setattr(request_processor, 'check_canonical_tag', stub_check_canonical_tag)
    monkeypatch.setattr(request_processor, 'check_links_on_page', stub_check_links_on_page)
    _perform_seo_and_link_checks('u','h',{},'','','','','','', verify_ssl=True)
    assert calls[0] == ('*', True)
    assert calls[1] == ('Googlebot', True)

# ------------------ Тести для _process_response ------------------

def test_process_response_no_redirect(monkeypatch):
    class DummyResp:
        status_code = 200
        url = 'http://example.com'
        history = []
    monkeypatch.setattr(request_processor, 'normalize_url', lambda u: u)
    resp = DummyResp()
    chain, final, final_code, orig_code = _process_response(resp, 'http://example.com', ssl_disabled=False)
    assert chain == []
    assert final == 'http://example.com'
    assert final_code == 200
    assert orig_code == 200


def test_process_response_with_redirects(monkeypatch):
    class DummyResp:
        pass
    r1 = DummyResp(); r1.status_code = 301; r1.url = 'http://example.com/a'
    r2 = DummyResp(); r2.status_code = 302; r2.url = 'http://example.com/b'
    resp = DummyResp(); resp.status_code = 200; resp.url = 'http://example.com/c'; resp.history = [r1, r2]
    monkeypatch.setattr(request_processor, 'normalize_url', lambda u: u)
    chain, final, final_code, orig_code = _process_response(resp, 'http://example.com/start', ssl_disabled=True)
    assert chain == [
        {'url': 'http://example.com/a', 'status_code': 301},
        {'url': 'http://example.com/b', 'status_code': 302}
    ]
    assert final == 'http://example.com/c'
    assert final_code == 200
    assert orig_code == 200


# ------------------ Тести для check_status_code_requests ------------------

def test_empty_url_skipped():
    # Рядок з відсутнім URL має бути пропущений з помилкою
    rows = [
        {"Url": None, "Анкор-1": "a1", "Урл-1": "u1", "Анкор-2": None, "Урл-2": None, "Анкор-3": None, "Урл-3": None}
    ]
    results = request_processor.check_status_code_requests(rows)
    assert len(results) == 1
    assert results[0]["error"] == "URL порожній"


def test_successful_status_and_seo(monkeypatch):
    # Успішний HEAD без редиректів і GET з отриманням контенту
    class HeadResp:
        status_code = 200
        url = 'http://example.com'
        history = []
    class GetResp:
        def __init__(self):
            self.status_code = 200
            self.content = b'<html></html>'
            self.headers = {'H': 'V'}
        def raise_for_status(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    # Патчимо HEAD, GET, detect_encoding та SEO-функцію
    monkeypatch.setattr(request_processor.requests, 'head', lambda url, allow_redirects, timeout, headers, verify: HeadResp())
    monkeypatch.setattr(request_processor.requests, 'get', lambda url, timeout, headers, verify: GetResp())
    monkeypatch.setattr(request_processor, 'detect_encoding', lambda b: 'utf-8')
    monkeypatch.setattr(request_processor, '_perform_seo_and_link_checks', lambda final_url, html, get_headers, a1,u1,a2,u2,a3,u3, verify_ssl: {
        'robots_star_allowed': True,
        'robots_googlebot_allowed': True,
        'indexing_directives': {'noindex': False, 'nofollow': False, 'source': 'stub'},
        'canonical_url': 'http://example.com/canonical',
        'url1_found': 'Так', 'anchor1_match': 'Так', 'url1_rel': None,
        'url2_found': 'Ні', 'anchor2_match': 'Ні', 'url2_rel': None,
        'url3_found': 'Ні', 'anchor3_match': 'Ні', 'url3_rel': None,
        'error': None
    })

    rows = [{"Url": "http://example.com", "Анкор-1": "a1", "Урл-1": "u1",
             "Анкор-2": None, "Урл-2": None, "Анкор-3": None, "Урл-3": None}]
    results = request_processor.check_status_code_requests(rows)

    r = results[0]
    assert r['status_code'] == 200
    assert r['final_status_code'] == 200
    assert r['robots_star_allowed'] is True
    assert r['seo_check_error'] is None
    assert r['url1_found'] == 'Так'


def test_head_request_exception_non_ssl(monkeypatch):
    # HEAD кине RequestException без SSL-помилки
    monkeypatch.setattr(request_processor.requests, 'head', lambda *args, **kwargs: (_ for _ in ()).throw(request_processor.requests.exceptions.RequestException('conn fail')))
    monkeypatch.setattr(request_processor, 'is_ssl_error', lambda e: False)

    rows = [{"Url": "http://example.com", "Анкор-1": None, "Урл-1": None, "Анкор-2": None, "Урл-2": None, "Анкор-3": None, "Урл-3": None}]
    results = request_processor.check_status_code_requests(rows)

    r = results[0]
    # При помилці HEAD і не-SSL, final_status_code має бути 0, error містить повідомлення
    assert r['final_status_code'] == 0
    assert r['error'] == 'conn fail'
