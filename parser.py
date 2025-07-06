import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import time
import sqlite3
import logging
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'currency_data.db')

def setup_logger():
    """Настраивает логгер для Docker"""
    logger = logging.getLogger('currency_parser')
    logger.setLevel(logging.INFO)
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Только консольный вывод для Docker
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()

def init_database():
    """Инициализирует базу данных, создает таблицу если не существует"""
    try:
        # Создаем директорию если не существует
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем существование таблицы
        cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='exchange_rates'
        """)
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            logger.info("Создание таблицы exchange_rates")
            cursor.execute("""
            CREATE TABLE exchange_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_time TEXT NOT NULL,
                name_currency TEXT NOT NULL,
                buying_rate REAL NOT NULL,
                selling_rate REAL NOT NULL,
                type_currency TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            # Создаем индексы
            cursor.execute("CREATE INDEX idx_datetime ON exchange_rates (date_time)")
            cursor.execute("CREATE INDEX idx_currency ON exchange_rates (name_currency)")
            cursor.execute("CREATE INDEX idx_type ON exchange_rates (type_currency)")
            conn.commit()
            logger.info("Таблица и индексы созданы")
        else:
            logger.info("Таблица exchange_rates уже существует")
            
        return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка инициализации БД: {e}")
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
            response = requests.get(url, headers=headers, timeout=10)
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
    best_rates = soup.find_all('span', class_="accent")
    
    if len(best_rates) < 6:
        logger.warning(f"Найдено недостаточно элементов курсов: {len(best_rates)}")
        return []

    best_courses = {
        "Дата и время": [formatted_datetime] * 3,
        "Наименование валюты": ['USD', 'EUR', 'RUB 100'],
        "Курс продажи": [
            best_rates[0].text.strip(), 
            best_rates[2].text.strip(), 
            best_rates[4].text.strip()
        ],
        "Курс покупки": [
            best_rates[1].text.strip(), 
            best_rates[3].text.strip(), 
            best_rates[5].text.strip()
        ],
        "Название курса": ['Лучший курс'] * 3
    }

    belveb_courses = []
    rows = soup.select('tr.currencies-courses__row-main')
    
    for row in rows:
        bank_name_td = row.select_one('td:first-child')
        if not bank_name_td:
            continue

        bank_text = bank_name_td.get_text().lower()
        if 'belveb.by' in bank_text or 'belveb.svg' in str(bank_name_td):
            currency_cells = row.select('td.currencies-courses__currency-cell span')
            
            if len(currency_cells) >= 6:
                courses = {
                    "Дата и время": [formatted_datetime] * 3,
                    "Наименование валюты": ['USD', 'EUR', 'RUB 100'],
                    "Курс продажи": [
                        currency_cells[0].get_text(strip=True),
                        currency_cells[2].get_text(strip=True),
                        currency_cells[4].get_text(strip=True)
                    ],
                    "Курс покупки": [
                        currency_cells[1].get_text(strip=True),
                        currency_cells[3].get_text(strip=True),
                        currency_cells[5].get_text(strip=True)
                    ],
                    "Название курса": [bank_name_td.get_text(strip=True)] * 3
                }
                belveb_courses.append(courses)

    belveb_courses.append(best_courses)
    logger.info(f"Собрано наборов данных: {len(belveb_courses)}")
    return belveb_courses

def save_to_database(data):
    """Сохраняет данные в базу данных"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        sql = """
        INSERT INTO exchange_rates 
        (date_time, name_currency, buying_rate, selling_rate, type_currency) 
        VALUES (?, ?, ?, ?, ?)
        """
        
        inserted_rows = 0
        
        for bank_data in data:
            for i in range(3):
                try:
                    buying = float(bank_data["Курс покупки"][i].replace(',', '.'))
                    selling = float(bank_data["Курс продажи"][i].replace(',', '.'))
                except ValueError:
                    logger.warning(f"Ошибка преобразования курсов: {bank_data['Курс покупки'][i]}, {bank_data['Курс продажи'][i]}")
                    continue
                    
                values = (
                    bank_data["Дата и время"][i],
                    bank_data["Наименование валюты"][i],
                    buying,
                    selling,
                    bank_data["Название курса"][i]
                )
                cursor.execute(sql, values)
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
    
    # Инициализация базы данных
    if not init_database():
        logger.error("Не удалось инициализировать базу данных")
        return
    
    # Парсинг данных
    currency_data = parse_currency_data()
    
    if currency_data:
        # Сохранение в БД
        saved_count = save_to_database(currency_data)
        if saved_count > 0:
            logger.info("Данные успешно сохранены")
        else:
            logger.warning("Не удалось сохранить данные")
    else:
        logger.warning("Нет данных для сохранения")

if __name__ == "__main__":
    main()