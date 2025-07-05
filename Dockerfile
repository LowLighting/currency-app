# Используем официальный образ Python
FROM python:3.10-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Создаем не-root пользователя
RUN addgroup --system app && adduser --system --no-create-home --ingroup app app

# Рабочая директория
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем директории для данных и шаблонов
RUN mkdir -p /app/data /app/templates

# Устанавливаем владельца для директории данных
RUN chown -R app:app /app/data

# Переключаемся на непривилегированного пользователя
USER app

# Создаем поддиректорию data в рабочей директории (если нужно)
RUN mkdir -p data

# Том для данных (теперь внутри рабочей директории)
VOLUME /app/data

# Порт приложения
EXPOSE 5000

# Команда запуска веб-сервера по умолчанию
CMD ["python", "app.py"]