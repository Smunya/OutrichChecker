import os
import sys
# Додаємо кореневу папку у шлях імпорту, щоб pytest бачив модуль gsheet_utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import pandas as pd
import gspread
import re
import ast

import gsheet_utils
from gsheet_utils import (
    check_sheet_structure,
    update_sheet_with_results,
    handle_header_error,
    handle_missing_data_error,
    display_sheet_validation_results
)

# Стуби для Google auth та gspread
class DummyWS:
    def __init__(self, id, title, data):
        self.id = id
        self.title = title
        self._data = data
    def get_all_values(self):
        return self._data

class DummySheet:
    def __init__(self, worksheets):
        self._worksheets = worksheets
    def worksheets(self):
        return self._worksheets
    def get_worksheet(self, idx):
        return self._worksheets[0]

class DummyClient:
    def __init__(self, sheet):
        self._sheet = sheet
    def open_by_key(self, key):
        return self._sheet

@pytest.fixture(autouse=True)
def patch_google(monkeypatch):
    # Прибираємо реальну аутентифікацію
    monkeypatch.setattr(gsheet_utils.auth, 'authenticate_user', lambda: None)
    # Повертаємо фіктивні креденшали
    monkeypatch.setattr(gsheet_utils, 'default', lambda: (None, None))

# ---------- Тести для check_sheet_structure ----------

def test_invalid_sheet_url(monkeypatch):
    monkeypatch.setattr(gsheet_utils, 'extract_sheet_params', lambda url: None)
    result = check_sheet_structure('not a sheet url')
    assert result['success'] is False
    assert 'Неправильний формат URL' in result['error']

def test_empty_sheet(monkeypatch):
    monkeypatch.setattr(gsheet_utils, 'extract_sheet_params', lambda url: ('sheet_id', 123))
    ws = DummyWS(123, 'Sheet1', [])
    sheet = DummySheet([ws])
    monkeypatch.setattr(gsheet_utils.gspread, 'authorize', lambda creds: DummyClient(sheet))

    result = check_sheet_structure('https://docs.google.com/spreadsheets/d/sheet_id/edit#gid=123')
    assert result['success'] is False
    assert result['error'] == 'Таблиця порожня'

def test_missing_mandatory_headers(monkeypatch):
    monkeypatch.setattr(gsheet_utils, 'extract_sheet_params', lambda url: ('sid', 0))
    data = [['Анкор-1', 'Url'], ['a1', 'http://example.com']]
    ws = DummyWS(0, 'Sheet', data)
    sheet = DummySheet([ws])
    monkeypatch.setattr(gsheet_utils.gspread, 'authorize', lambda creds: DummyClient(sheet))

    result = check_sheet_structure('https://docs.google.com/...')
    assert result['success'] is False
    assert "Відсутні обов'язкові заголовки" in result['error']
    assert 'Урл-1' in result['error']
    assert result['actual_headers'] == ['Анкор-1', 'Url']

def test_wrong_order_before_url(monkeypatch):
    monkeypatch.setattr(gsheet_utils, 'extract_sheet_params', lambda url: ('sid', 0))
    data = [['Урл-1', 'Анкор-1', 'Url'], ['u1', 'a1', 'http://example.com']]
    ws = DummyWS(0, 'Sheet', data)
    sheet = DummySheet([ws])
    monkeypatch.setattr(gsheet_utils.gspread, 'authorize', lambda creds: DummyClient(sheet))

    result = check_sheet_structure('...')
    assert result['success'] is False
    assert 'Неправильний порядок' in result['error']
    assert result['actual_headers'] == ['Урл-1', 'Анкор-1', 'Url']

def test_success_with_extra_columns(monkeypatch):
    monkeypatch.setattr(gsheet_utils, 'extract_sheet_params', lambda url: ('sid', 0))
    headers = ['Анкор-1', 'Урл-1', 'Url', 'Extra']
    data = [headers, ['a1', 'u1', 'http://ex.com', 'x']]
    ws = DummyWS(0, 'Sheet', data)
    sheet = DummySheet([ws])
    monkeypatch.setattr(gsheet_utils.gspread, 'authorize', lambda creds: DummyClient(sheet))

    result = check_sheet_structure('...')
    assert result['success'] is True
    assert result['message'] == 'Таблиця має правильну структуру.'
    assert result['data'] == data
    assert result['worksheet'] is ws

def test_missing_data_cells(monkeypatch):
    monkeypatch.setattr(gsheet_utils, 'extract_sheet_params', lambda url: ('sid', 0))
    headers = ['Анкор-1', 'Урл-1', 'Url']
    data = [headers, ['', 'u1', 'http://ex.com']]
    ws = DummyWS(0, 'Sheet', data)
    sheet = DummySheet([ws])
    monkeypatch.setattr(gsheet_utils.gspread, 'authorize', lambda creds: DummyClient(sheet))

    result = check_sheet_structure('...')
    assert result['success'] is False
    assert "Відсутні дані в обов'язкових стовпцях" in result['error']

# ---------- Тести для update_sheet_with_results ----------

class StubWorksheet:
    def __init__(self, sheet_data):
        self.sheet_data = sheet_data
        self.updated_ranges = []
        self.batches = []

    def get_all_values(self):
        return [list(r) for r in self.sheet_data]

    def update(self, values, range_name):
        self.sheet_data[0] = list(values[0])
        self.updated_ranges.append(range_name)

    def batch_update(self, batch):
        for upd in batch:
            cell, val = upd['range'], upd['values'][0][0]
            m = re.match(r"([A-Z]+)(\d+)", cell)
            col_letters, row_str = m.groups()
            row = int(row_str) - 1
            col = sum((ord(c) - ord('A') + 1) * (26 ** i)
                      for i, c in enumerate(reversed(col_letters))) - 1
            while row >= len(self.sheet_data):
                self.sheet_data.append([])
            row_data = self.sheet_data[row]
            if col >= len(row_data):
                row_data.extend([''] * (col + 1 - len(row_data)))
            row_data[col] = val
        self.batches.append(batch)

def test_empty_table_for_update(capsys):
    ws = StubWorksheet(sheet_data=[])
    update_sheet_with_results(ws, results=[{"url": "http://example.com"}])
    captured = capsys.readouterr()
    assert "⚠️ Помилка: Не вдалося прочитати заголовки" in captured.out
    assert ws.updated_ranges == []
    assert ws.batches == []

def test_missing_url_column_update(capsys):
    headers = ["Анкор-1", "Урл-1", "Extra"]
    data = [headers, ["a1", "u1", "x"]]
    ws = StubWorksheet(sheet_data=data)
    update_sheet_with_results(ws, results=[{"url": "u1"}])
    captured = capsys.readouterr()
    assert "⚠️ Помилка: Стовпець 'Url' не знайдено" in captured.out
    assert ws.updated_ranges == []
    assert ws.batches == []

def test_successful_update_with_new_headers():
    headers = ["Анкор-1", "Урл-1", "Url"]
    row = ["a1", "u1", "http://ex.com"]
    ws = StubWorksheet(sheet_data=[headers.copy(), row.copy()])

    results = [{
        "url": "http://ex.com",
        "status_code": 200,
        "redirect_chain": [],
        "robots_star_allowed": True,
        "robots_googlebot_allowed": True,
        "indexing_directives": None,
        "canonical_url": None,
        "url1_found": "Так",
        "anchor1_match": "Так",
        "url1_rel": "nofollow"
    }]

    update_sheet_with_results(ws, results)

    expected_new = [
        "Status Code", "Final Redirect URL", "Final Status Code",
        "Robots.txt", "Meta Robots/X-Robots-Tag", "Canonical",
        "Урл-1 наявність", "Анкор-1 співпадає", "Урл-1 rel"
    ]
    for h in expected_new:
        assert h in ws.sheet_data[0]

    assert len(ws.updated_ranges) == 1
    total_updates = sum(len(batch) for batch in ws.batches)
    assert total_updates == 1
    first_batch = ws.batches[0]
    mapping = {upd['range']: upd['values'][0][0] for upd in first_batch}
    assert mapping == {"D2": "200"}

# ---------- Тести для handle_header_error ----------

def test_handle_header_error_wrong_order(capsys):
    error = "Неправильний порядок. Очікувалось: ['A', 'B'], Отримано: ['B', 'A']"
    result = {}
    handle_header_error(error, result)
    out = capsys.readouterr().out
    assert "Неправильні заголовки стовпців" in out
    assert "Необхідні (по порядку): A, B" in out
    assert "Знайдено: B, A" in out
    assert "Помилка також може бути пов'язана з порядком стовпців перед 'Url'" in out
    assert "Очікувалось: ['A', 'B'], Отримано: ['B', 'A']" in out

def test_handle_header_error_missing_headers(capsys):
    error = "Відсутні обов'язкові заголовки. Очікувалось: ['X'], Отримано: ['Y']"
    result = {"actual_headers": ["Y"]}
    handle_header_error(error, result)
    out = capsys.readouterr().out
    assert "Неправильні заголовки стовпців" in out
    assert "Необхідні (по порядку): X" in out
    assert "Знайдено: Y" in out
    assert f"• {error}" in out

# ---------- Тести для handle_missing_data_error ----------

def test_handle_missing_data_error(capsys):
    missing_data = {"Анкор-1": [2, 4], "Урл-1": [3]}
    error = f"Відсутні дані в обов'язкових стовпцях: {missing_data}"
    handle_missing_data_error(error)
    out_lines = capsys.readouterr().out.splitlines()
    assert out_lines[0] == "• Відсутні дані в обов'язкових стовпцях:"
    assert "  - У стовпці 'Анкор-1' порожні комірки в рядках: 2, 4" in out_lines
    assert "  - У стовпці 'Урл-1' порожні комірки в рядках: 3" in out_lines
    assert out_lines[-1] == "• Заповніть всі обов'язкові поля в зазначених рядках"

# ---------- Тести для display_sheet_validation_results ----------

def test_display_success(capsys):
    result = {"success": True}
    display_sheet_validation_results(result)
    out = capsys.readouterr().out
    assert "🔍 РЕЗУЛЬТАТИ ПЕРЕВІРКИ ТАБЛИЦІ" in out
    assert "✅ УСПІХ! Таблиця має правильну структуру." in out
    assert "• Всі необхідні заголовки стовпців розташовані правильно" in out
    assert "• Всі обов'язкові дані присутні" in out

def test_display_invalid_url(capsys):
    result = {"success": False, "error": "Неправильний формат URL: foo"}
    display_sheet_validation_results(result)
    out = capsys.readouterr().out
    assert "❌ ПОМИЛКА! Виявлено проблеми з таблицею:" in out
    assert "• Неправильний формат URL: foo" in out
    assert "Переконайтеся, що ви скопіювали повний URL Google таблиці" in out
    assert out.strip().endswith("="*50)

def test_display_empty_table(capsys):
    result = {"success": False, "error": "Таблиця порожня"}
    display_sheet_validation_results(result)
    out = capsys.readouterr().out
    assert "• Таблиця порожня" in out
    assert "Перевірте, чи є дані в таблиці" in out
    assert out.strip().endswith("="*50)

def test_display_header_error(monkeypatch, capsys):
    calls = []
    def fake_header_handler(error, result):
        calls.append((error, result))
        print("HANDLED HEADER")
    monkeypatch.setattr(gsheet_utils, "handle_header_error", fake_header_handler)
    result = {"success": False, "error": "Неправильні заголовки стовпців XYZ", "actual_headers": []}
    display_sheet_validation_results(result)
    out = capsys.readouterr().out
    assert "❌ ПОМИЛКА! Виявлено проблеми з таблицею:" in out
    assert "HANDLED HEADER" in out
    assert calls and calls[0][0] == result["error"]

def test_display_missing_data_error(monkeypatch, capsys):
    calls = []
    def fake_missing_handler(error):
        calls.append(error)
        print("HANDLED MISSING DATA")
    monkeypatch.setattr(gsheet_utils, "handle_missing_data_error", fake_missing_handler)
    result = {"success": False, "error": "Відсутні дані в обов'язкових стовпцях: {'A':[1]}"}
    display_sheet_validation_results(result)
    out = capsys.readouterr().out
    assert "❌ ПОМИЛКА! Виявлено проблеми з таблицею:" in out
    assert "HANDLED MISSING DATA" in out
    assert calls and calls[0] == result["error"]
