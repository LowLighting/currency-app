#!/bin/sh
set -e

echo ">> Entrypoint started with argument: '$1'"

APP_DIR="/app"
DATA_DIR="$APP_DIR/data"
DB_FILE="$DATA_DIR/currency_data.db"

echo ">> Ensuring data directory exists..."
mkdir -p "$DATA_DIR"

echo ">> Current working directory: $(pwd)"
echo ">> Listing $APP_DIR:"
ls -la "$APP_DIR"
echo ">> Listing $DATA_DIR:"
ls -la "$DATA_DIR" || echo "No $DATA_DIR"

# Создание базы, если её нет
if [ ! -f "$DB_FILE" ]; then
    echo ">> Database file not found. Creating..."
    sqlite3 "$DB_FILE" "CREATE TABLE IF NOT EXISTS currencies (id INTEGER PRIMARY KEY, code TEXT, rate REAL, date TEXT);"
else
    echo ">> Database already exists."
fi

chmod 660 "$DB_FILE"

# Основной запуск
case "$1" in
    web)
        echo ">> Starting web server (app.py)..."
        exec python /app/app.py
        ;;
    parser)
        echo ">> Starting parser (parser.py)..."
        exec python /app/parser.py
        ;;
    *)
        echo ">> Unknown or missing argument: '$1'"
        echo ">> Please pass 'web' or 'parser' as CMD argument."
        echo ">> Sleeping for debug..."
        sleep 60
        exit 1
        ;;
esac
