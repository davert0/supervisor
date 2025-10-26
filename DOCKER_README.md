# Docker Deployment

## Быстрый старт

1. Скопируйте файл конфигурации:
```bash
cp env.example .env
```

2. Отредактируйте `.env` файл и укажите ваши токены:
```
BOT_TOKEN=your_bot_token_here
ADMIN_ID=your_admin_telegram_id_here
```

3. Запустите контейнер:
```bash
docker-compose up -d
```

## Команды управления

### Запуск
```bash
docker-compose up -d
```

### Остановка
```bash
docker-compose down
```

### Просмотр логов
```bash
docker-compose logs -f
```

### Перезапуск
```bash
docker-compose restart
```

### Обновление после изменений в коде
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Структура файлов

- `Dockerfile` - конфигурация Docker образа
- `docker-compose.yml` - конфигурация для запуска
- `.dockerignore` - файлы, исключаемые из образа
- `env.example` - пример файла с переменными окружения

## База данных

База данных SQLite сохраняется в файле `reports.db` в корне проекта и монтируется в контейнер для сохранения данных между перезапусками.
