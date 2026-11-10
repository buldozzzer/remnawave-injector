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

В `config.yml` включите `subscription_modification.json.enabled`. При переходе с
`append_configs` перенесите общие поля конфигов в `outbound_template`, а объекты
подключений в `append_outbounds`. Оба параметра находятся в секции
`subscription_modification.json`.

Для каждого объекта из `append_outbounds` создаётся отдельный конфиг на основе
`outbound_template`. Объект подключения становится первым элементом `outbounds`,
за ним идут вспомогательные объекты из шаблона, если они заданы.

Объекты добавляются в конец массива ответа в порядке из файла, после применения
`replacements` к исходному ответу. Для всех пользователей используются одни и
те же объекты. Добавление можно отключить через `enabled_append: false` внутри
секции `json`.

Чтобы отключить только текстовые замены, задайте `enabled_replace: false`
в секции `json`. По умолчанию текстовые замены включены.
