import requests
import warnings
import pandas as pd
from urllib.parse import unquote

from utils import normalize_url, detect_encoding, is_ssl_error
from seo_checks import check_robots_txt, check_indexing_directives, check_canonical_tag, check_links_on_page
from indexing_checks import check_google_indexing

# --- НОВА ДОПОМІЖНА ФУНКЦІЯ для SEO та перевірки посилань ---
def _perform_seo_and_link_checks(final_url, html_content, get_headers, anchor1, url1, anchor2, url2, anchor3, url3, verify_ssl=True):
    """Виконує перевірки robots.txt, директив індексації, canonical та посилань на сторінці."""
    print(f"   ├── Виконуємо SEO та перевірку посилань для: {final_url} (SSL Verify: {verify_ssl})")
    seo_results = {
        "robots_star_allowed": None,
        "robots_googlebot_allowed": None,
        "indexing_directives": None,
        "canonical_url": None,
        "seo_check_error": None,
        # Результати перевірки посилань
        "url1_found": "Н/Д", "anchor1_match": "Н/Д", "url1_rel": None,
        "url2_found": "Н/Д", "anchor2_match": "Н/Д", "url2_rel": None,
        "url3_found": "Н/Д", "anchor3_match": "Н/Д", "url3_rel": None,
        "link_check_error": None
    }
    try:
        # а. Перевірка robots.txt
        seo_results["robots_star_allowed"] = check_robots_txt(final_url, '*', verify_ssl=verify_ssl)
        seo_results["robots_googlebot_allowed"] = check_robots_txt(final_url, 'Googlebot', verify_ssl=verify_ssl)

        # b. Перевірка Meta Robots / X-Robots-Tag
        seo_results["indexing_directives"] = check_indexing_directives(final_url, get_headers, html_content)

        # c. Перевірка Canonical
        seo_results["canonical_url"] = check_canonical_tag(final_url, html_content)

        # d. Перевірка посилань та анкорів
        link_check_results = check_links_on_page(html_content, final_url, anchor1, url1, anchor2, url2, anchor3, url3)
        # Оновлюємо seo_results полями з link_check_results
        seo_results.update(link_check_results)
        if "error" in link_check_results and link_check_results["error"]:
             seo_results["link_check_error"] = link_check_results["error"]
             # Усуваємо поле 'error' з link_check_results, щоб воно не перезаписало інші помилки
             del seo_results["error"]

    except Exception as seo_e:
        error_msg = f"Помилка під час SEO/Link перевірок: {seo_e}"
        print(f"   │   └── ⚠️ {error_msg}")
        seo_results["seo_check_error"] = error_msg # Записуємо як помилку SEO/Link

    return seo_results
# --- КІНЕЦЬ НОВОЇ ДОПОМІЖНОЇ ФУНКЦІЇ ---


def _process_response(response, url, ssl_disabled=False):
    """Допоміжна функція для обробки відповіді requests та витягування інформації про редиректи.
       Повертає нормалізований final_url.
    """
    redirect_chain = []
    status_code = response.status_code
    # Нормалізуємо початковий URL перед тим, як він потенційно стане final_url
    final_url = normalize_url(url)
    final_status_code = status_code
    ssl_status_text = "(SSL вимкнено)" if ssl_disabled else ""

    if response.history:
        # Нормалізуємо URL на кожному кроці редиректу
        redirect_chain = [{
            "url": normalize_url(resp.url),
            "status_code": resp.status_code
        } for resp in response.history]

        print(f"   Ланцюжок редиректів {ssl_status_text}:")
        # Виводимо нормалізовані URL редиректів
        [print(f"   {i+1}. {resp['url']} → {resp['status_code']}") for i, resp in enumerate(redirect_chain)]

        # Фінальний URL після редиректів - нормалізуємо його
        final_url = normalize_url(response.url)
        final_status_code = response.status_code
        print(f"   Фінальний URL {ssl_status_text}: {final_url} → {final_status_code}")
    else:
        # Якщо редиректів не було, final_url вже нормалізований на початку
        print(f"   Статус-код {ssl_status_text}: {status_code} (без редиректів)")

    return redirect_chain, final_url, final_status_code, status_code

def check_status_code_requests(rows_data, valueserp_api_key=None):
    """Перевіряє статус-коди URL, редиректи та виконує SEO та перевірки посилань."""
    print("\n\n🔍 ПЕРЕВІРКА СТАТУС-КОДІВ URL, SEO-ПАРАМЕТРІВ ТА ПОСИЛАНЬ...\n")

    results = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.184 Safari/537.36'}

    for i, row_info in enumerate(rows_data, 1):
        url = row_info.get("Url")
        anchor1 = row_info.get("Анкор-1")
        url1 = row_info.get("Урл-1")
        anchor2 = row_info.get("Анкор-2")
        url2 = row_info.get("Урл-2")
        anchor3 = row_info.get("Анкор-3")
        url3 = row_info.get("Урл-3")

        # Ініціалізація результатів для поточного URL
        current_result = {
            "url": url, "status_code": 0, "redirect_chain": [],
            "final_url": url, "final_status_code": 0, "error": None,
            "ssl_disabled": False, "robots_star_allowed": None,
            "robots_googlebot_allowed": None, "indexing_directives": None,
            "canonical_url": None, "seo_check_error": None,
            # Поля для результатів перевірки посилань
            "url1_found": "Н/Д", "anchor1_match": "Н/Д", "url1_rel": None,
            "url2_found": "Н/Д", "anchor2_match": "Н/Д", "url2_rel": None,
            "url3_found": "Н/Д", "anchor3_match": "Н/Д", "url3_rel": None,
            "link_check_error": None,
            # Поле для результату перевірки індексації в Google
            "google_indexing": None
        }

        # Зберігаємо початкові дані для оновлення таблиці
        current_result.update(row_info)

        if not url or pd.isna(url):
            print(f"{i}. URL порожній, пропускаємо")
            current_result["error"] = "URL порожній"
            results.append(current_result)
            continue

        print(f"{i}. Перевіряємо: {url}")
        ssl_verify = True # Починаємо з увімкненим SSL

        try:
            # 1. Перша спроба запиту (з SSL або без, залежно від попередніх помилок)
            response = requests.head(url, allow_redirects=True, timeout=10, headers=headers, verify=ssl_verify)
            redirect_chain, final_url, final_status_code, status_code = _process_response(response, url)
            current_result.update({
                "status_code": status_code, "redirect_chain": redirect_chain,
                "final_url": final_url, "final_status_code": final_status_code,
                "error": None, "ssl_disabled": not ssl_verify
            })

            # 2. Якщо фінальний статус 200, виконуємо SEO та перевірку посилань
            if final_status_code == 200:
                try:
                    # Робимо GET запит для отримання контенту
                    with requests.get(final_url, timeout=15, headers=headers, verify=ssl_verify) as response_get:
                        response_get.raise_for_status()
                        html_content_bytes = response_get.content
                        encoding = detect_encoding(html_content_bytes)
                        html_content = html_content_bytes.decode(encoding, errors='replace')
                        get_headers = response_get.headers

                        # Викликаємо нову функцію для SEO та перевірки посилань
                        seo_link_results = _perform_seo_and_link_checks(
                            final_url, html_content, get_headers,
                            anchor1, url1, anchor2, url2, anchor3, url3, verify_ssl=ssl_verify
                        )
                        current_result.update(seo_link_results)

                        # 3. Перевірка індексації в Google
                        if valueserp_api_key:
                            # Використовуємо фінальний URL для перевірки індексації
                            print(f"   ├── Перевіряємо індексацію в Google для: {final_url}")
                            try:
                                is_indexed, search_query = check_google_indexing(final_url, valueserp_api_key)
                                current_result["google_indexing"] = "Так" if is_indexed else "Ні"
                                print(f"   │   ├── Пошуковий запит: {search_query}")
                                print(f"   │   └── {'✅ URL проіндексований' if is_indexed else '❌ URL не проіндексований'}")
                            except Exception as index_e:
                                error_msg = f"Помилка при перевірці індексації: {str(index_e)}"
                                print(f"   │   └── ⚠️ {error_msg}")
                                current_result["google_indexing"] = "Помилка"
                        else:
                            print(f"   │   └── ℹ️ Пропускаємо перевірку індексації (API ключ не вказано)")

                except requests.exceptions.RequestException as get_e:
                    error_msg = f"Помилка GET-запиту {'(SSL вимкнено)' if not ssl_verify else ''}: {get_e}"
                    print(f"   └── ⚠️ {error_msg}")
                    # Записуємо помилку і в seo_check_error і в link_check_error, оскільки GET провалився для обох
                    current_result["seo_check_error"] = error_msg
                    current_result["link_check_error"] = error_msg
                except Exception as general_e: # Загальна помилка під час обробки GET відповіді
                    error_msg = f"Загальна помилка обробки контенту {'(SSL вимкнено)' if not ssl_verify else ''}: {general_e}"
                    print(f"   └── ⚠️ {error_msg}")
                    current_result["seo_check_error"] = error_msg
                    current_result["link_check_error"] = error_msg

        except requests.exceptions.RequestException as e:
            error_text = str(e)
            current_result["status_code"] = 0 # Встановлюємо тут, бо запит HEAD не вдався
            current_result["final_status_code"] = 0

            # Перевірка на SSL помилку ТІЛЬКИ при першій спробі (коли ssl_verify=True)
            if ssl_verify and is_ssl_error(error_text):
                print(f"   ⚠️ Виявлено помилку SSL: {error_text}")
                print(f"   🔄 Повторюємо запит з вимкненою перевіркою SSL...")
                ssl_verify = False # Вимикаємо SSL для наступної спроби
                current_result["ssl_disabled"] = True # Відмічаємо, що SSL вимкнено

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        # Повторюємо HEAD запит без SSL
                        response_nossl = requests.head(url, allow_redirects=True, timeout=10, headers=headers, verify=ssl_verify)
                        redirect_chain, final_url, final_status_code, status_code = _process_response(response_nossl, url, ssl_disabled=True)
                        current_result.update({
                            "status_code": status_code, "redirect_chain": redirect_chain,
                            "final_url": final_url, "final_status_code": final_status_code,
                            "error": "SSL вимкнено: " + error_text # Зберігаємо початкову помилку SSL
                        })

                        # Якщо фінальний статус 200 після SSL retry, виконуємо SEO та перевірку посилань
                        if final_status_code == 200:
                            try:
                                # Робимо GET запит без SSL
                                with requests.get(final_url, timeout=15, headers=headers, verify=ssl_verify) as response_get_nossl:
                                    response_get_nossl.raise_for_status()
                                    html_content_bytes = response_get_nossl.content
                                    encoding = detect_encoding(html_content_bytes)
                                    html_content = html_content_bytes.decode(encoding, errors='replace')
                                    get_headers = response_get_nossl.headers

                                    # Викликаємо нову функцію для SEO та перевірки посилань
                                    seo_link_results = _perform_seo_and_link_checks(
                                        final_url, html_content, get_headers,
                                        anchor1, url1, anchor2, url2, anchor3, url3, verify_ssl=ssl_verify
                                    )
                                    current_result.update(seo_link_results)

                                    # Перевірка індексації в Google
                                    if valueserp_api_key:
                                        print(f"   ├── Перевіряємо індексацію в Google для: {final_url} (SSL вимкнено)")
                                        try:
                                            is_indexed, search_query = check_google_indexing(final_url, valueserp_api_key)
                                            current_result["google_indexing"] = "Так" if is_indexed else "Ні"
                                            print(f"   │   ├── Пошуковий запит: {search_query}")
                                            print(f"   │   └── {'✅ URL проіндексований' if is_indexed else '❌ URL не проіндексований'}")
                                        except Exception as index_e:
                                            error_msg = f"Помилка при перевірці індексації: {str(index_e)}"
                                            print(f"   │   └── ⚠️ {error_msg}")
                                            current_result["google_indexing"] = "Помилка"
                                    else:
                                        print(f"   │   └── ℹ️ Пропускаємо перевірку індексації (API ключ не вказано)")

                            except requests.exceptions.RequestException as get_e:
                                error_msg = f"Помилка GET-запиту (SSL вимкнено): {get_e}"
                                print(f"   └── ⚠️ {error_msg}")
                                current_result["seo_check_error"] = error_msg
                                current_result["link_check_error"] = error_msg
                            except Exception as general_e:
                                error_msg = f"Загальна помилка обробки контенту (SSL вимкнено): {general_e}"
                                print(f"   └── ⚠️ {error_msg}")
                                current_result["seo_check_error"] = error_msg
                                current_result["link_check_error"] = error_msg

                    except requests.exceptions.RequestException as e2:
                        # Помилка навіть з вимкненим SSL
                        final_error = f"Помилка HEAD і з вимкненим SSL: {str(e2)}"
                        current_result["error"] = final_error # Перезаписуємо помилку
                        current_result["status_code"] = 0 # Статус невідомий
                        current_result["final_status_code"] = 0
                        print(f"   ❌ {final_error}")

            else: # Якщо помилка не SSL, або це вже друга спроба (з вимкненим SSL)
                current_result["error"] = error_text # Зберігаємо поточну помилку
                print(f"   ❌ Помилка HEAD: {current_result['error']}")
                # status_code та final_status_code вже встановлені на 0 на початку блоку except

        results.append(current_result)
        print("---")

    # Статистика перевірок
    stats = {
        "всього": len(results),
        "успішні_200_з_перевірками": sum(1 for r in results if r["final_status_code"] == 200 and not r.get("seo_check_error") and not r.get("link_check_error")),
        "помилки_seo_link": sum(1 for r in results if r["final_status_code"] == 200 and (r.get("seo_check_error") or r.get("link_check_error"))),
        # Змінено логіку підрахунку помилок запиту - це помилки HEAD/GET, які НЕ призвели до статусу 200
        "помилки_запиту": sum(1 for r in results if r.get("error") and r["final_status_code"] != 200),
        "ssl_вимкнено": sum(1 for r in results if r["ssl_disabled"]),
        "інші_коди": sum(1 for r in results if r["final_status_code"] not in [0, 200] and not r["error"]), # Коди, які не 0 або 200 і без помилок запиту
        "проіндексовані": sum(1 for r in results if r.get("google_indexing") == "Так"),
        "не_проіндексовані": sum(1 for r in results if r.get("google_indexing") == "Ні"),
        "помилки_індексації": sum(1 for r in results if r.get("google_indexing") == "Помилка")
    }

    # Оновлюємо вивід статистики
    print(f"\n📊 РЕЗУЛЬТАТИ ПЕРЕВІРКИ {stats['всього']} URL:")
    print(f"✅ Успішні запити (200) з SEO та перевіркою посилань: {stats['успішні_200_з_перевірками']}")
    print(f"⚠️ Успішні запити (200) з помилками SEO/посилань: {stats['помилки_seo_link']}")
    print(f"❌ Помилки запиту: {stats['помилки_запиту']}")
    print(f"🔄 Запити з вимкненим SSL: {stats['ssl_вимкнено']}")
    print(f"ℹ️ Інші статус-коди: {stats['інші_коди']}")
    
    # Додаємо статистику індексації
    if valueserp_api_key:
        print(f"\n📊 РЕЗУЛЬТАТИ ПЕРЕВІРКИ ІНДЕКСАЦІЇ В GOOGLE:")
        print(f"✅ Проіндексовані URL: {stats['проіндексовані']}")
        print(f"❌ Не проіндексовані URL: {stats['не_проіндексовані']}")
        print(f"⚠️ Помилки перевірки індексації: {stats['помилки_індексації']}")
        print(f"ℹ️ Не перевірялися (немає 200 статусу): {stats['всього'] - stats['проіндексовані'] - stats['не_проіндексовані'] - stats['помилки_індексації']}")

    return results 