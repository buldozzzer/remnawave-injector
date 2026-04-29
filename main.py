import yaml
import sys
from pathlib import Path
import re

import base64
import json

from mitmproxy import http
from mitmproxy.tools.main import mitmdump
from logger import setup_structlog, logger

CONFIG_PATH = Path("config.yml")

if not CONFIG_PATH.exists():
    logger.error(f"Ошибка", msg=f"Файл конфигурации {CONFIG_PATH} не найден")
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


LISTEN_HOST = config.get("listen_host", "0.0.0.0")
LISTEN_PORT = config.get("listen_port", 8081)

backend = config.get("backend", {})
BACKEND_HOST = backend.get("host", "remnawave-subscription-page")
BACKEND_PORT = backend.get("port", 443)


injection = config.get("injection", {})
INJECT_JS = injection.get("inject_js", True)
INJECT_HTML = injection.get("inject_html", False)
CUSTOM_JS = injection.get("custom_js", "")
CUSTOM_HTML = injection.get("custom_html", "")


sub_config = config.get("subscription_modification", {})
SUB_MOD_ENABLED = sub_config.get("enabled", True)
TARGET_PATHS = sub_config.get("target_paths", ["/sub", "/subscription", "/api/sub"])


base64_config = sub_config.get("base64", {})
json_config = sub_config.get("json", {})


ua_exceptions = sub_config.get("user_agent_exceptions", {})

EXCLUDE_UA_ENABLED = ua_exceptions.get("enabled", True)
EXCLUDE_UA_REGEXES = []
EXCLUDE_UA_STRINGS = ua_exceptions.get("exclude", [])

for pattern in ua_exceptions.get("exclude_regex", []):
    try:
        EXCLUDE_UA_REGEXES.append(re.compile(pattern, re.IGNORECASE))
    except re.error as e:
        logger.error(f"Неверное регулярное выражение: {pattern}", error=str(e))


header_mods = config.get("header_modifications", {})
LOG_HEADERS = config.get("logging", {}).get("log_headers", True)
IMPORTANT_HEADERS = config.get("logging", {}).get("important_headers", [])
LOG_LEVEL = config.get("logging", {}).get("level", "INFO")
JSON_LOG = config.get("logging", {}).get("json_log", False)


def should_skip_subscription_modification(flow: http.HTTPFlow) -> bool:
    if not EXCLUDE_UA_ENABLED:
        return False

    user_agent = flow.request.headers.get("User-Agent", "")
    if not user_agent:
        return False

    for regex in EXCLUDE_UA_REGEXES:
        if regex.search(user_agent):
            logger.info("[SUB] Модификация пропущена по regex", 
                       user_agent=user_agent[:100], 
                       pattern=regex.pattern)
            return True

    for excluded in EXCLUDE_UA_STRINGS:
        if excluded and excluded.lower() in user_agent.lower():
            logger.info("[SUB] Модификация пропущена по строке", 
                       user_agent=user_agent[:100])
            return True

    return False


def is_subscription_response(flow: http.HTTPFlow) -> bool:
    if not flow.response or not flow.response.content:
        return False

    path_lower = flow.request.path.lower()
    if any(p in path_lower for p in TARGET_PATHS):
        return True

    content_type = flow.response.headers.get("content-type", "").lower()
    if any(ct in content_type for ct in ["text/plain", "application/json", "application/octet-stream"]):
        return True

    return False


def inject_into_html(flow: http.HTTPFlow):
    if not flow.response or not flow.response.content:
        return

    content_type = flow.response.headers.get("content-type", "")
    if not content_type.startswith("text/html"):
        return

    try:
        content = flow.response.content.decode('utf-8', errors='ignore')
    except:
        return

    modified = False

    if INJECT_JS and CUSTOM_JS:
        if '</head>' in content:
            content = content.replace('</head>', CUSTOM_JS + '\n</head>', 1)
            modified = True
        elif '</body>' in content:
            content = content.replace('</body>', CUSTOM_JS + '\n</body>', 1)
            modified = True

    if INJECT_HTML and CUSTOM_HTML and '</body>' in content:
        content = content.replace('</body>', CUSTOM_HTML + '\n</body>', 1)
        modified = True

    if modified:
        flow.response.content = content.encode('utf-8')
        if "Content-Length" in flow.response.headers:
            flow.response.headers["Content-Length"] = str(len(flow.response.content))


def modify_base64_subscription(content: bytes) -> bytes:
    if not base64_config.get("enabled", False):
        return content

    try:
        decoded = base64.b64decode(content).decode('utf-8')
        lines = [line.strip() for line in decoded.strip().split('\n') if line.strip()]

        if base64_config.get("enabled_filtering", False):
            if keep_keywords := [k.lower() for k in base64_config.get("keep_if_contains", [])]:
                lines = [line for line in lines if any(kw in line.lower() for kw in keep_keywords)]

            if base64_config.get("enabled_removing", False):
                if remove_keywords := [k.lower() for k in base64_config.get("remove_if_contains", [])]:
                    lines = [line for line in lines if not any(kw in line.lower() for kw in remove_keywords)]

        if base64_config.get("enabled_replace", False):
            for rule in base64_config.get("replacements", []):
                search = rule.get("search", "")
                replace = rule.get("replace", "")
                lines = [line.replace(search, replace) for line in lines]

        if base64_config.get("enabled_append", True):         # исправил опечатку
            for link in base64_config.get("append_links", []):
                if link and link.strip():
                    lines.append(link.strip())

        new_content = '\n'.join(lines).encode('utf-8')
        return base64.b64encode(new_content)

    except Exception as e:
        logger.error("Ошибка модификации Base64", error=str(e))
        return content


def modify_json_subscription(content: bytes) -> bytes:
    if not json_config.get("enabled", False):
        return content

    try:
        text = content.decode('utf-8')
        for rule in json_config.get("replacements", []):
            text = text.replace(rule.get("search", ""), rule.get("replace", ""))
        return text.encode('utf-8')
    except Exception as e:
        logger.error("Ошибка модификации JSON", error=str(e))
        return content


def modify_subscription(flow: http.HTTPFlow):
    if not SUB_MOD_ENABLED or not is_subscription_response(flow):
        return

    if should_skip_subscription_modification(flow):
        ua = flow.request.headers.get("User-Agent", "")[:120]
        logger.info("[SUB] Модификация пропущена по User-Agent", user_agent=ua)
        return

    original_size = len(flow.response.content or b'')
    content_type = flow.response.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        flow.response.content = modify_json_subscription(flow.response.content)
        logger.info("[SUB] JSON модифицирована", orig_len=original_size, new_len=len(flow.response.content))
    else:
        flow.response.content = modify_base64_subscription(flow.response.content)
        logger.info("[SUB] Base64 модифицирована", orig_len=original_size, new_len=len(flow.response.content))

    if flow.response.content:
        flow.response.headers["Content-Length"] = str(len(flow.response.content))


def apply_header_modifications(flow: http.HTTPFlow):
    if BACKEND_HOST not in flow.request.pretty_host:
        return

    for header_name, value in header_mods.items():
        if value is None:
            flow.request.headers.pop(header_name, None)
            logger.info("[-] Удалён заголовок", header_name=header_name)
        elif isinstance(value, str):
            if value == "{original_host}":
                original = flow.request.headers.get("Host") or flow.request.pretty_host
                flow.request.headers[header_name] = original
            else:
                flow.request.headers[header_name] = value
                logger.info("   [→]", new={header_name: value})


def fix_headers(flow: http.HTTPFlow):
    if not flow.response or flow.response.raw_content is None:
        return

    if flow.response.headers.get("Transfer-Encoding", "").lower() == "chunked":
        flow.response.headers.pop("Content-Length", None)
    elif flow.response.content is not None:
        flow.response.headers["Content-Length"] = str(len(flow.response.content))
        flow.response.headers.pop("Transfer-Encoding", None)


def request(flow: http.HTTPFlow):
    if BACKEND_HOST not in flow.request.pretty_host:
        return

    logger.info("[→ REQUEST]", method=flow.request.method, url=flow.request.url)
    apply_header_modifications(flow)

    if LOG_HEADERS and IMPORTANT_HEADERS:
        for h in IMPORTANT_HEADERS:
            if h in flow.request.headers:
                val = flow.request.headers[h]
                logger.info(f"      {h}: {val[:100]}{'...' if len(val) > 100 else ''}")


def response(flow: http.HTTPFlow):
    if BACKEND_HOST not in flow.request.pretty_host:
        return

    logger.info(f"[← RESPONSE]", status_code=flow.response.status_code, url=flow.request.url)

    inject_into_html(flow)
    modify_subscription(flow)
    fix_headers(flow)


if __name__ == "__main__":
    setup_structlog(log_level=LOG_LEVEL, json_logs=JSON_LOG)

    logger.info("=== Remnawave Subscription Page Injector запущен ===")
    logger.info(f"Listen  → http://{LISTEN_HOST}:{LISTEN_PORT}")
    logger.info(f"Backend → http://{BACKEND_HOST}:{BACKEND_PORT}")

    mitmdump([
        "--listen-host", LISTEN_HOST,
        "--listen-port", str(LISTEN_PORT),
        "--mode", f"reverse:http://{BACKEND_HOST}:{BACKEND_PORT}",
        "--ssl-insecure",
        "--quiet",
        "--no-http2",
        "--set", "console_eventlog_verbosity=error",
        "--set", "flow_detail=0",
        "--set", "termlog_verbosity=error",
        "-s", __file__
    ])