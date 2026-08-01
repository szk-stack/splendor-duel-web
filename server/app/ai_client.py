"""DeepSeek 大模型客户端（OpenAI 兼容 API）。

配置优先读环境变量，其次读 server/.env（已被 gitignore，不进仓库）。
注：本网络环境下 httpx 连接被中间设备重置（BrokenResourceError），
改用 urllib（同步调用 + asyncio.to_thread 异步化）。
"""
import asyncio
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

_DEFAULT_ENV = Path(__file__).resolve().parent.parent / ".env"


def _load_env_file(path: Path = _DEFAULT_ENV):
    """加载 .env 到 os.environ（不覆盖已存在的环境变量）。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


def api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY（环境变量或 server/.env）")
    return key


def model() -> str:
    return os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()


def base_url() -> str:
    return os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()


class AIError(Exception):
    """DeepSeek API 调用失败。"""


def _chat_sync(messages: list, temperature: float, max_tokens: int) -> str:
    url = f"{base_url().rstrip('/')}/chat/completions"
    payload = json.dumps({
        "model": model(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key()}",
        },
    )
    timeout = float(os.environ.get("DEEPSEEK_TIMEOUT", "40"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise AIError(f"DeepSeek API {e.code}: {e.read()[:200]!r}") from e
    except (OSError, ValueError) as e:
        raise AIError(f"DeepSeek API 请求失败: {e}") from e
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise AIError(f"DeepSeek 响应格式异常: {str(data)[:200]}") from e


async def chat(messages: list, temperature: float = 0.7, max_tokens: int = 2048) -> str:
    """调用 DeepSeek chat completions，返回回复文本。失败抛 AIError。"""
    return await asyncio.to_thread(_chat_sync, messages, temperature, max_tokens)
