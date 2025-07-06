import sqlite3
import pandas as pd
import os
import logging
import sys
from datetime import datetime
import numpy as np
from xlsxwriter.utility import xl_col_to_name
import io

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'currency_data.db')

# Настройка логирования
def setup_logger():
    logger = logging.getLogger('currency_analysis')
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()

def get_all_data(DB_PATH):
    """Получает все данные из БД"""
    conn = None
    try:
        logger.info(f"Подключение к базе данных: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        logger.info("Подключение к базе данных успешно")
        
        query = """
        SELECT 
            date_time,
            name_currency,
            type_currency,
            buying_rate,
            selling_rate
        FROM exchange_rates
        ORDER BY date_time DESC, name_currency
        """
        
        logger.info("Выполнение SQL-запроса для получения всех данных")
        df = pd.read_sql_query(query, conn)
        logger.info(f"Загружено {len(df)} записей из базы данных")
        
        if df.empty:
            logger.warning("Нет данных для анализа")
            return None
        
        return df
    
    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        return None
    finally:
        if conn:
            conn.close()
            logger.info("Соединение с базой данных закрыто")

def prepare_analysis_data(df):
    """Подготавливает данные для анализа, объединяя банковские курсы с лучшими"""
    if df is None or df.empty:
        return None
    
    logger.info("Разделение данных на лучшие курсы и банковские курсы")
    
    # Создаем копии для безопасной работы
    best_df = df[df['type_currency'] == 'Лучший курс'].copy()
    bank_df = df[df['type_currency'] != 'Лучший курс'].copy()
    
    logger.info(f"Найдено: {len(best_df)} записей лучших курсов, {len(bank_df)} банковских записей")
    
    if best_df.empty:
        logger.warning("Нет данных о лучших курсах")
        return None
    
    # Переименовываем колонки для лучших курсов
    best_df = best_df.rename(columns={
        'buying_rate': 'best_buy',
        'selling_rate': 'best_sell'
    })
    
    # Выбираем только нужные колонки для объединения
    best_df = best_df[['date_time', 'name_currency', 'best_buy', 'best_sell']]
    
    logger.info("Объединение банковских данных с лучшими курсами")
    # Объединяем банковские данные с лучшими курсами
    merged_df = pd.merge(
        bank_df,
        best_df,
        on=['date_time', 'name_currency'],
        how='left'
    )
    
    # Удаляем строки, где нет лучшего курса для сравнения
    initial_count = len(merged_df)
    merged_df = merged_df.dropna(subset=['best_buy', 'best_sell'])
    logger.info(f"Удалено {initial_count - len(merged_df)} записей без данных о лучшем курсе")
    
    if merged_df.empty:
        logger.warning("Нет данных для анализа после объединения")
        return None
    
    # Рассчитываем разницу с лучшим курсом (со знаком)
    merged_df['Разница покупки'] = merged_df['buying_rate'] - merged_df['best_buy']
    merged_df['Разница продажи'] = merged_df['selling_rate'] - merged_df['best_sell']
    
    # Рассчитываем абсолютную разницу для форматирования
    merged_df['Абс. разница покупки'] = np.abs(merged_df['Разница покупки'])
    merged_df['Абс. разница продажи'] = np.abs(merged_df['Разница продажи'])
    
    # Форматирование колонок
    merged_df = merged_df.rename(columns={
        'date_time': 'Дата и время',
        'name_currency': 'Валюта',
        'type_currency': 'Наименование',
        'buying_rate': 'Курс покупки',
        'selling_rate': 'Курс продажи',
        'best_buy': 'Лучший курс покупки',
        'best_sell': 'Лучший курс продажи'
    })
    
    # Упорядочиваем колонки
    columns_order = [
        'Дата и время', 'Валюта', 'Наименование', 
        'Курс покупки', 'Лучший курс покупки', 'Разница покупки',
        'Курс продажи', 'Лучший курс продажи', 'Разница продажи'
    ]
    
    return merged_df[columns_order]

def create_excel_bytes(df):
    """Создает Excel в памяти и возвращает bytes"""
    if df.empty:
        logger.warning("Нет данных для создания отчета")
        return None
    
    try:
        # Создаем буфер в памяти
        output = io.BytesIO()
        
        # Создаем Excel writer для работы с буфером
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Записываем данные в Excel
            df.to_excel(writer, sheet_name='Анализ курсов', index=False)
            
            # Получаем объекты для работы с Excel
            workbook = writer.book
            worksheet = writer.sheets['Анализ курсов']
            
            # Форматирование заголовков
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BC',
                'border': 1
            })
            
            # Форматирование чисел
            number_format = workbook.add_format({'num_format': '#,##0.0000'})
            diff_format = workbook.add_format({'num_format': '#,##0.0000'})
            
            # Применяем форматирование заголовков
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Автоширина колонок
            for i, col in enumerate(df.columns):
                max_len = max((
                    df[col].astype(str).map(len).max(),
                    len(col)
                )) + 2
                worksheet.set_column(i, i, max_len)
            
            # Форматирование числовых колонок
            num_cols = ['Курс покупки', 'Лучший курс покупки', 'Курс продажи', 'Лучший курс продажи']
            for col in num_cols:
                if col in df.columns:
                    col_idx = df.columns.get_loc(col)
                    worksheet.set_column(col_idx, col_idx, 15, number_format)
            
            # Форматирование разницы
            diff_cols = ['Разница покупки', 'Разница продажи']
            for col in diff_cols:
                if col in df.columns:
                    col_idx = df.columns.get_loc(col)
                    worksheet.set_column(col_idx, col_idx, 15, diff_format)
            
            # Условное форматирование
            if 'Разница покупки' in df.columns:
                buy_diff_col = df.columns.get_loc('Разница покупки')
                buy_diff_letter = xl_col_to_name(buy_diff_col)
                
                good_format = workbook.add_format({'bg_color': '#7CFC00'})
                warning_format = workbook.add_format({'bg_color': '#FFA07A'})
                
                # Условное форматирование для разницы покупки
                worksheet.conditional_format(
                    1, buy_diff_col,
                    len(df), buy_diff_col,
                    {
                        'type': 'formula',
                        'criteria': f'=ABS({buy_diff_letter}2) <= 0.015',
                        'format': good_format
                    }
                )
                
                worksheet.conditional_format(
                    1, buy_diff_col,
                    len(df), buy_diff_col,
                    {
                        'type': 'formula',
                        'criteria': f'=ABS({buy_diff_letter}2) > 0.015',
                        'format': warning_format
                    }
                )
            
            if 'Разница продажи' in df.columns:
                sell_diff_col = df.columns.get_loc('Разница продажи')
                sell_diff_letter = xl_col_to_name(sell_diff_col)
                
                # Условное форматирование для разницы продажи
                worksheet.conditional_format(
                    1, sell_diff_col,
                    len(df), sell_diff_col,
                    {
                        'type': 'formula',
                        'criteria': f'=ABS({sell_diff_letter}2) <= 0.015',
                        'format': good_format
                    }
                )
                
                worksheet.conditional_format(
                    1, sell_diff_col,
                    len(df), sell_diff_col,
                    {
                        'type': 'formula',
                        'criteria': f'=ABS({sell_diff_letter}2) > 0.015',
                        'format': warning_format
                    }
                )
            
            # Закрепляем заголовки
            worksheet.freeze_panes(1, 0)
            
            # Добавляем пояснение по цветам
            legend_col = len(df.columns)  # Колонка после последней
            legend_col_letter = xl_col_to_name(legend_col)
            
            worksheet.write(f'{legend_col_letter}1', 'Легенда:')
            worksheet.write(f'{legend_col_letter}2', 'Отклонение <= 0.015', good_format)
            worksheet.write(f'{legend_col_letter}3', 'Отклонение > 0.015', warning_format)
        
        # Возвращаем байты из буфера
        output.seek(0)
        return output.getvalue()
    
    except Exception as e:
        logger.error(f"Ошибка при создании Excel: {e}")
        return None

def generate_report():
    """Генерирует отчет в памяти и возвращает байты с Excel файлом"""
    logger.info("Начало генерации отчета в памяти")
    
    try:
        # Путь к базе данных
        
        # Получаем данные
        df = get_all_data(DB_PATH)
        if df is None or df.empty:
            logger.warning("Нет данных в базе")
            return None
            
        # Обрабатываем данные
        processed_df = prepare_analysis_data(df)
        if processed_df is None or processed_df.empty:
            logger.warning("Нет данных для анализа")
            return None
            
        # Создаем отчет в памяти и возвращаем байты
        return create_excel_bytes(processed_df)
            
    except Exception as e:
        logger.error(f"Ошибка генерации отчета: {e}")
        return None