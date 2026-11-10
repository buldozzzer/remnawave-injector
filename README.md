# Remjector
## Features

1. Modify Base64/Json sub for different clients (Remove/Replace/Append)
2. Inject own html/js (I don't know why)

## Work scheme 

`Reverse Proxy` <-> `Remjector` <-> `Remnawave Subscription Page`

## Deploy

1. Create config
    ```
    cp ./config.example.yml ./config.yml
    ```
2. Modify him
3. Modify own reverse-proxy config (replace proxy path from `remnawave-sub-page` to `remjector`)
4. Run
    ```
    docker compose up -d
    ```

## Добавление конфигураций в JSON-подписку

В `config.yml` включите `subscription_modification.json.enabled` и заполните
`subscription_modification.json.append_configs`. Каждый элемент этого списка
должен быть полным объектом конфигурации в формате клиента. JSON-объект можно
вставить в YAML напрямую как элемент списка (`- { ... }`).

Объекты добавляются в конец массива ответа в порядке из файла, после применения
`replacements` к исходному ответу. Для всех пользователей используются одни и
те же объекты. Добавление можно отключить через `enabled_append: false` внутри
секции `json`.
