FROM python:3.10-slim

# Установка системных зависимостей
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

# Создаем директории и устанавливаем владельца
RUN mkdir -p /app/data /app/templates && \
    chown -R app:app /app

# Переключаемся на непривилегированного пользователя
USER app

# Том для данных
VOLUME /app/data

# Порт приложения
EXPOSE 5000

# Команда запуска
CMD ["python", "app.py"]