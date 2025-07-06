#!/bin/sh
set -e

# Выбор режима работы на основе первого аргумента
mode=${1:-web}

case $mode in
    web|app|server)
        echo "Запуск веб-сервера"
        exec python app.py
        ;;
    parser|job|worker)
        echo "Запуск парсера"
        exec python parser.py
        ;;
    *)
        echo "Неизвестный режим: $mode"
        echo "Доступные команды:"
        echo "  web    - запуск веб-сервера"
        echo "  parser - запуск парсера"
        exit 1
        ;;
esac