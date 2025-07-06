from flask import Flask, send_file, render_template, Response
import io
import logging
import os
from datetime import datetime
from analysis import generate_report  # Импорт функции генерации отчета

app = Flask(__name__)
DB_PATH = '/app/data/currency_data.db'

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('web_app')

@app.before_request
def check_permissions():
    if os.access(DB_PATH, os.W_OK):
        logger.warning("SECURITY WARNING: Application has write access to database!")

@app.route('/')
def index():
    """Главная страница с кнопкой"""
    return render_template('index.html')

@app.route('/download_report')
def download_report():
    """Генерация и скачивание отчета в памяти"""
    logger.info("Запрос на генерацию отчета")
    
    try:
        # Генерируем отчет в памяти (возвращает bytes)
        report_bytes = generate_report()
        
        if not report_bytes:
            logger.error("Не удалось сгенерировать отчет")
            return "Ошибка при генерации отчета", 500
        
        # Создаем поток из байтов
        report_stream = io.BytesIO(report_bytes)
        report_stream.seek(0)
        
        # Формируем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"currency_report_{timestamp}.xlsx"
        
        logger.info(f"Отправка отчета: {filename}")
        return send_file(
            report_stream,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logger.error(f"Ошибка при обработке запроса: {str(e)}")
        return "Внутренняя ошибка сервера", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)