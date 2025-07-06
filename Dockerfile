FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    wget \
    libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Создаем пользователя только для чтения (UID 1001)
RUN addgroup --system --gid 1001 reader_group && \
    adduser --system --uid 1001 --ingroup reader_group --no-create-home reader_user

# Создаем группу writer (GID 1000) и добавляем читателя в нее
RUN addgroup --gid 1000 writer_group && \
    adduser reader_user writer_group

RUN mkdir -p /app/templates
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Устанавливаем безопасные права
RUN chown -R 1001:1001 /app && \
    find /app -type d -exec chmod 755 {} \; && \
    find /app -type f -exec chmod 644 {} \;

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5000/health || exit 1

USER reader_user

EXPOSE 5000

CMD ["python", "app.py"]