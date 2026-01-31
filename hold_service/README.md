# Hold Service

## Описание
Hold Service - это сервис для удержания и управления сообщениями между Logic и File Storage сервисами. Он построен на базе шаблона `hold_service` из kafka_server_sdk.

## Архитектура

### Позиция в цепочке обработки:
```
in_gateway → logic_in → Logic Service → hold_in → Hold Service → files_proxy → File Storage → out → out_gateway
```

## Порты
- **7097** - основной HTTP API сервис
- **7098** - админский API (для управления и мониторинга)

## Конфигурационные файлы

### config.json
Основная конфигурация сервиса:
- База данных SQLite для хранения удержанных сообщений
- Настройки аутентификации (admin/admin123)
- Время жизни освобожденных сообщений (TTL)

### server_config.json
Конфигурация Kafka:
- Входной топик: `hold_in` (получает от Logic Service)
- Выходной топик: `files_proxy` (отправляет в File Storage)
- Топик событий: `events`
- Consumer group: `hold_service_1`

### admin_config.json
Конфигурация админского API:
- Порт: 7098
- Директории для requests/responses/events/errors
- Аутентификация

## Возможности

1. **Удержание сообщений** - все сообщения от Logic Service автоматически сохраняются
2. **REST API** для управления сообщениями:
   - Просмотр удержанных сообщений
   - Освобождение (unhold) сообщений - отправка в File Storage
   - Удаление сообщений
   - Поиск и фильтрация
3. **Мониторинг** через админский API
4. **События** - отправка событий об успешной/неуспешной обработке

## Зависимости
- Kafka (для получения и отправки сообщений)
- SQLite (для хранения сообщений)

## Запуск

### В Docker Compose:
```bash
cd kafka_queue_sdk_example
docker-compose up -d hold_service
```

### Логи:
```bash
docker-compose logs -f hold_service
```

## API Endpoints

Основной API (порт 7097) предоставляет endpoints для управления удержанными сообщениями. Все endpoints требуют basic аутентификацию (admin/admin123).

Админский API (порт 7098) предоставляет endpoints для мониторинга и отладки сервиса.

Полная документация API доступна через Swagger UI после запуска сервиса.
