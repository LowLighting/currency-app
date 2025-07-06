#!/bin/sh
set -e

if [ "$1" = "parser" ]; then
  echo "Запускаем парсер..."
  python parser.py
elif [ "$1" = "web" ]; then
  echo "Запускаем веб-сервис..."
  python app.py
else
  echo "Неизвестная команда: $1"
  exit 1
