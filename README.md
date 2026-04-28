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