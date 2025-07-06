#!/bin/sh
set -e

# Создаем директорию данных при необходимости
if [ ! -d "/app/data" ]; then
    mkdir -p /app/data
    logger "Создана директория /app/data"
fi

# Устанавливаем правильные права
chown -R 1000:1000 /app/data
chmod 770 /app/data

# Запуск основной команды
exec "$@"