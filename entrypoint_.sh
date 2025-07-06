#!/bin/sh
set -e

# Проверка и инициализация БД
DB_FILE="/app/data/currency_data.db"
if [ ! -f "$DB_FILE" ]; then
    echo "Database file not found. Creating new database..."
    touch "$DB_FILE"
    sqlite3 "$DB_FILE" "CREATE TABLE IF NOT EXISTS currencies (id INTEGER PRIMARY KEY, code TEXT, rate REAL, date TEXT);"
fi

# Устанавливаем правильные права на БД
chmod 660 "$DB_FILE"

# Запуск приложения
case "$1" in
    web)
        echo "Starting web server"
        exec python /app/app.py
        ;;
    parser)
        echo "Starting parser"
        exec python /app/parser.py
        ;;
    *)
        echo "Unknown mode: $1"
        exit 1
        ;;
esac