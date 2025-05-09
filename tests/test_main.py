import sys
import pytest

import main
from main import main as run_main

# Допоміжний клас для результатів check_sheet_structure
class DummyResult:
    def __init__(self, success, data=None, worksheet=None):
        self.success = success
        self.data = data
        self.worksheet = worksheet

# Тест для main: коли перевірка структури неуспішна, update_sheet_with_results не викликається
def test_main_no_success(monkeypatch, capsys):
    # Імітуємо результат без успіху
    monkeypatch.setattr(main, 'check_sheet_structure', lambda x: {"success": False})
    monkeypatch.setattr(main, 'display_sheet_validation_results', lambda x: None)
    # Захищаємо від небажаного виклику
    monkeypatch.setattr(main, 'update_sheet_with_results', lambda w, r: (_ for _ in ()).throw(Exception("Should not be called")))
    # Імітуємо auth без помилок
    monkeypatch.setattr(main.auth, 'authenticate_user', lambda: None)

    run_main('test_sheet')
    captured = capsys.readouterr()
    assert "Авторизація в Google пройшла успішно" in captured.out

# Тест для main: перевірка успішного флоу з одним рядком
def test_main_success_flow(monkeypatch):
    headers = ["Url", "Анкор-1", "Урл-1"]
    rows = [["http://example.com", "anchor", "http://target.com"]]
    dummy_ws = object()
    dummy_result = {"success": True, "data": [headers] + rows, "worksheet": dummy_ws}

    monkeypatch.setattr(main, 'check_sheet_structure', lambda x: dummy_result)
    monkeypatch.setattr(main, 'display_sheet_validation_results', lambda x: None)
    # Імітуємо, що перевірка URL повертає список результатів
    dummy_check_results = [{"Url": "http://example.com", "status": 200}]
    monkeypatch.setattr(main, 'check_status_code_requests', lambda lst, api_key=None: dummy_check_results)
    update_calls = []
    monkeypatch.setattr(main, 'update_sheet_with_results', lambda ws, res: update_calls.append((ws, res)))
    # Імітуємо auth без помилок
    monkeypatch.setattr(main.auth, 'authenticate_user', lambda: None)

    run_main('test_sheet')
    assert update_calls == [(dummy_ws, dummy_check_results)]

# Тест для main: коли рядок неповний, він пропускається
def test_main_skips_short_rows(monkeypatch, capsys):
    headers = ["Url", "Анкор-1", "Урл-1"]
    # Додаємо короткий рядок без третьої колонки
    rows = [["http://example.com", "anchor"]]
    dummy_ws = object()
    dummy_result = {"success": True, "data": [headers] + rows, "worksheet": dummy_ws}

    monkeypatch.setattr(main, 'check_sheet_structure', lambda x: dummy_result)
    monkeypatch.setattr(main, 'display_sheet_validation_results', lambda x: None)
    monkeypatch.setattr(main, 'check_status_code_requests', lambda lst, api_key=None: [])
    monkeypatch.setattr(main, 'update_sheet_with_results', lambda ws, res: None)
    # Імітуємо auth без помилок
    monkeypatch.setattr(main.auth, 'authenticate_user', lambda: None)

    run_main('test_sheet')
    captured = capsys.readouterr()
    # Має бути попередження про пропуск короткого рядка
    assert "Пропускаємо короткий рядок" in captured.out
