import requests
import re
import logging
from urllib.parse import urlparse, parse_qsl

logger = logging.getLogger(__name__)

def clean_url_for_indexing_check(url):
    """
    Очищає URL від протоколу та www для перевірки індексації.
    
    Args:
        url (str): URL для очищення
        
    Returns:
        str: Очищений URL
    """
    # Видаляємо протокол (http:// або https://)
    cleaned_url = re.sub(r'^https?://', '', url)
    
    # Видаляємо www. якщо присутній
    cleaned_url = re.sub(r'^www\.', '', cleaned_url)
    
    return cleaned_url


def format_search_query(url):
    """
    Форматує пошуковий запит для перевірки індексації URL в Google.
    Для URL з GET-параметрами використовує конструкцію site:domain/path inurl:param1 inurl:param2
    
    Args:
        url (str): URL для перевірки
        
    Returns:
        str: Відформатований пошуковий запит
    """
    # Очищаємо URL від протоколу та www
    cleaned_url = clean_url_for_indexing_check(url)
    
    # Парсимо URL
    parsed_url = urlparse(cleaned_url)
    
    # Отримуємо базовий URL (без параметрів)
    base_url = f"{parsed_url.netloc}{parsed_url.path}"
    
    # Якщо шлях закінчується на /, але це не корінь, або якщо шлях пустий - додаємо /
    if not base_url.endswith('/') and parsed_url.path != "":
        base_url += '/'
    elif base_url.endswith('//'):
        base_url = base_url[:-1]  # Видаляємо подвійні слеші
    
    # Перевіряємо, чи є GET-параметри
    if parsed_url.query:
        # Спочатку пробуємо розбити параметри на пари ключ-значення
        params = parse_qsl(parsed_url.query)
        
        if params:
            # Якщо параметри мають структуру ключ=значення
            inurl_parts = [f"inurl:{key}={value}" for key, value in params]
            query = f"site:{base_url} {' '.join(inurl_parts)}"
        else:
            # Якщо параметри не мають структури ключ=значення (як у вашому прикладі),
            # використовуємо весь query як єдиний параметр для inurl
            query = f"site:{base_url} inurl:{parsed_url.query}"
    else:
        # Якщо параметрів немає, просто використовуємо оператор site:
        query = f"site:{cleaned_url}"
    
    return query


def check_google_indexing(url, api_key):
    """
    Перевіряє індексацію URL в Google за допомогою ValueSerp API.
    
    Args:
        url (str): URL для перевірки (фінальний URL після редиректів)
        api_key (str): API ключ для ValueSerp
        
    Returns:
        tuple: (bool, str) - (True/False - URL проіндексований чи ні, пошуковий запит)
    """
    # Формуємо пошуковий запит
    query = format_search_query(url)
    
    logger.info(f"Перевіряємо індексацію для URL: {url}")
    logger.info(f"Пошуковий запит: {query}")
    
    # Параметри запиту до ValueSerp API
    params = {
        "api_key": api_key,
        "q": query,
        "google_domain": "google.com",
        "gl": "us",
        "hl": "en",
        "num": 1  # Нам потрібен лише факт індексації, тому обмежуємо кількість результатів
    }
    
    try:
        response = requests.get("https://api.valueserp.com/search", params=params)
        response.raise_for_status()
        
        data = response.json()
        
        # Перевіряємо, чи є органічні результати в відповіді
        if "organic_results" in data and len(data["organic_results"]) > 0:
            logger.info(f"URL {url} знайдено в індексі Google")
            return True, query
        else:
            # Перевіряємо, чи є повідомлення про відсутність результатів
            if "search_information" in data and data["search_information"].get("original_query_yields_zero_results", False):
                logger.info(f"URL {url} не знайдено в індексі Google")
                return False, query
                
            # На всяк випадок перевіряємо загальну кількість результатів
            if "search_information" in data and data["search_information"].get("total_results", 0) == 0:
                logger.info(f"URL {url} не знайдено в індексі Google (нуль результатів)")
                return False, query
                
            logger.info(f"URL {url} не знайдено в індексі Google")
            return False, query
            
    except Exception as e:
        logger.error(f"Помилка при перевірці індексації URL {url}: {str(e)}")
        # У випадку помилки вважаємо, що URL не проіндексований
        return False, query 