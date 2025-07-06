FROM python:3.10-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Создаем не-root пользователя
RUN addgroup --system app && adduser --system --no-create-home --ingroup app app

# Создаем рабочие директории
RUN mkdir -p /app/data /app/templates
WORKDIR /app

# Сначала копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем ВСЕ остальные файлы
COPY . .

# Устанавливаем права
RUN chown -R app:app /app && \
    chmod -R 777 /app/data

# Healthcheck (для веб-сервиса)
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:5000/ || exit 1

# Переключаемся на непривилегированного пользователя
USER app

# Порт приложения
EXPOSE 5000

# Команда запуска веб-сервера
CMD ["python", "app.py"]