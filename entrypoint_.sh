#!/bin/sh
set -e

DB_FILE="/app/data/currency_data.db"

mkdir -p /app/data

if [ ! -f "$DB_FILE" ]; then
    echo "Database file not found. Creating new database..."
    sqlite3 "$DB_FILE" "CREATE TABLE IF NOT EXISTS currencies (id INTEGER PRIMARY KEY, code TEXT, rate REAL, date TEXT);"
fi

chmod 660 "$DB_FILE"

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
