import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import time
import sqlite3
import logging
import sys
import os

# Путь к базе данных (должен совпадать с render.yaml)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'currency_data.db')

def setup_logger():
    """Настраивает логгер для Render"""
    logger = logging.getLogger('currency_parser')
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()

def connect_db_with_retry(retries=3, delay=1):
    """Подключается к БД с повторными попытками при блокировке"""
    for attempt in range(retries):
        try:
            conn = sqlite3.connect(
                DB_PATH,
                timeout=15  # Увеличенный timeout для Render
            )
            logger.info(f"Успешное подключение к БД (попытка {attempt+1})")
            return conn
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < retries - 1:
                logger.warning(f"БД заблокирована, повторная попытка через {delay} сек...")
                time.sleep(delay)
            else:
                logger.error(f"Критическая ошибка подключения: {e}")
                raise
    return None

def init_database():
    """Инициализирует базу данных с защитой от параллельного доступа"""
    if os.path.exists(DB_PATH):
        logger.info(f"База данных уже существует: {DB_PATH}")
        return True

    logger.info(f"Создание новой БД: {DB_PATH}")
    
    try:
        conn = connect_db_with_retry()
        if conn is None:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_time TEXT NOT NULL,
            name_currency TEXT NOT NULL,
            buying_rate REAL NOT NULL,
            selling_rate REAL NOT NULL,
            type_currency TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        
        cursor.execute("""
        INSERT OR IGNORE INTO metadata (key, value)
        VALUES ('db_version', '1.0')
        """)
        
        conn.commit()
        logger.info("Структура БД успешно создана")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Ошибка создания БД: {e}")
        return False
    finally:
        if conn:
            conn.close()

def check_database_initialized():
    """Проверяет инициализацию БД с использованием metadata"""
    if not os.path.exists(DB_PATH):
        logger.error(f"База данных не найдена: {DB_PATH}")
        return False
    
    try:
        conn = connect_db_with_retry()
        if conn is None:
            return False
            
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM metadata WHERE key='db_version'")
        return bool(cursor.fetchone())
    except sqlite3.Error as e:
        logger.error(f"Ошибка проверки БД: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_moscow_time():
    """Возвращает текущее время в Москве в формате ГГГГ-ММ-ДД ЧЧ:ММ"""
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz).strftime('%Y-%m-%d %H:%M')

def fetch_currency_data(url, max_retries=3):
    """Получает данные с сайта с повторными попытками при ошибках"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for attempt in range(max_retries):
        try:
            logger.info(f"Попытка {attempt+1}/{max_retries}: запрос к {url}")
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            logger.info("Данные успешно получены")
            return response.text
        except Exception as e:
            logger.warning(f"Ошибка запроса ({attempt+1}/{max_retries}): {str(e)[:100]}")
            if attempt < max_retries - 1:
                time.sleep(2)
    return None

def parse_currency_data():
    """Основная функция парсинга данных"""
    formatted_datetime = get_moscow_time()
    logger.info(f"Начало парсинга: {formatted_datetime}")
    
    url = 'https://myfin.by/currency/minsk'
    html_content = fetch_currency_data(url)
    
    if not html_content:
        logger.error("Не удалось получить данные с сайта")
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Упрощенный и более надежный парсинг
    currencies = []
    
    # Парсинг лучших курсов
    best_rates = []
    for span in soup.select('span.accent'):
        best_rates.append(span.text.strip())
    
    if len(best_rates) >= 6:
        currencies.append({
            "date_time": formatted_datetime,
            "bank_name": "Лучший курс",
            "rates": [
                {"currency": "USD", "buy": best_rates[1], "sell": best_rates[0]},
                {"currency": "EUR", "buy": best_rates[3], "sell": best_rates[2]},
                {"currency": "RUB 100", "buy": best_rates[5], "sell": best_rates[4]}
            ]
        })

    # Парсинг БелВЭБ
    belveb_row = None
    for row in soup.select('tr.currencies-courses__row-main'):
        if 'belveb' in row.get_text().lower():
            belveb_row = row
            break

    if belveb_row:
        cells = belveb_row.select('td.currencies-courses__currency-cell span')
        if len(cells) >= 6:
            currencies.append({
                "date_time": formatted_datetime,
                "bank_name": "БелВЭБ",
                "rates": [
                    {"currency": "USD", "buy": cells[1].text.strip(), "sell": cells[0].text.strip()},
                    {"currency": "EUR", "buy": cells[3].text.strip(), "sell": cells[2].text.strip()},
                    {"currency": "RUB 100", "buy": cells[5].text.strip(), "sell": cells[4].text.strip()}
                ]
            })

    logger.info(f"Собрано банков: {len(currencies)}")
    return currencies

def save_to_database(data):
    """Сохраняет данные в базу данных с защитой от блокировок"""
    if not data:
        logger.warning("Нет данных для сохранения")
        return 0

    try:
        conn = connect_db_with_retry()
        if conn is None:
            return 0
            
        cursor = conn.cursor()
        inserted_rows = 0
        
        for bank in data:
            for rate in bank["rates"]:
                try:
                    buy = float(rate["buy"].replace(',', '.'))
                    sell = float(rate["sell"].replace(',', '.'))
                except ValueError:
                    logger.warning(f"Ошибка преобразования курса: {rate}")
                    continue
                    
                cursor.execute("""
                INSERT INTO exchange_rates 
                (date_time, name_currency, buying_rate, selling_rate, type_currency) 
                VALUES (?, ?, ?, ?, ?)
                """, (
                    bank["date_time"],
                    rate["currency"],
                    buy,
                    sell,
                    bank["bank_name"]
                ))
                inserted_rows += 1
        
        conn.commit()
        logger.info(f"Сохранено записей: {inserted_rows}")
        return inserted_rows
        
    except sqlite3.Error as e:
        logger.error(f"Ошибка сохранения в БД: {e}")
        return 0
    finally:
        if conn:
            conn.close()

def main():
    """Основная функция для парсинга и сохранения"""
    logger.info("Запуск парсера валютных курсов")
    logger.info(f"Используется БД: {DB_PATH}")
    
    # Проверка и инициализация БД
    if not os.path.exists(DB_PATH):
        logger.info("Первоначальная инициализация БД")
        if not init_database():
            logger.error("Не удалось инициализировать базу данных")
            return
    elif not check_database_initialized():
        logger.error("Проблемы с структурой БД")
        return
    
    # Парсинг данных
    start_time = time.time()
    currency_data = parse_currency_data()
    parse_duration = time.time() - start_time
    
    # Сохранение данных
    if currency_data:
        save_start = time.time()
        saved_count = save_to_database(currency_data)
        save_duration = time.time() - save_start
        logger.info(f"Сохранено {saved_count} записей за {save_duration:.2f} сек")
    else:
        logger.warning("Нет данных для сохранения")
    
    logger.info(f"Общее время работы: {time.time() - start_time:.2f} сек")

if __name__ == "__main__":
    main()