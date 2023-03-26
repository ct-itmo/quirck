# Quirck

Платформа для домашних заданий.

## Quickstart

Зависимости:

1. Python 3.7+, [Poetry](https://python-poetry.org/docs/)
2. Docker
3. PostgreSQL
4. S3-совместимое хранилище
5. SSO-провайдер

> Для локальной разработки можно поднять базу, Minio и SSO-провайдера с помощью `docker compose up -d`.
> В Minio необходимо вручную создать бакет.

Установите зависимости в виртуальное окружение: `poetry install`.

Добавьте плагин для поддержки L2-сети: `docker plugin install kathara/katharanp:amd64`. Если у вас на хосте `nftables`-бекенд, воспользуйтесь [инструкцией](https://github.com/KatharaFramework/NetworkPlugin#use-katharanp-without-kathar%C3%A0).

Запустите: `poetry run python -m quirck`.

## Конфигурация

Вся конфигурация хранится в файле `.env`.

Пример файла:

```
DEBUG=True
DATABASE_URL=postgresql+asyncpg://quirck:quirck@localhost:12005/quirck
SECRET_KEY=1234567890

SSO_CONFIGURATION_URL=http://localhost:12004/.well-known/openid-configuration
SSO_CLIENT_ID=quirck
SSO_CLIENT_SECRET=quirck

ALLOWED_GROUPS=M33391

APP_MODULE=networking

S3_ENDPOINT_URL=http://localhost:12006/
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_DEFAULT_BUCKET=quirck

VPN_HOST=127.0.0.1
```
