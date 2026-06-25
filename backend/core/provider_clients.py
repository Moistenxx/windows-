import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderError(Exception):
    pass


def ark_base_url():
    return os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")


def provider_api_key(provider):
    env_name = provider.api_key_env or "ARK_API_KEY"
    api_key = os.environ.get(env_name)
    if not api_key:
        raise ProviderError(f"Missing provider API key env var: {env_name}")
    return api_key


def post_json(url, api_key, payload, timeout=60):
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:500]
        raise ProviderError(f"Provider HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ProviderError(f"Provider request failed: {exc}") from exc


def ark_chat(provider, messages, temperature=0.8, timeout=60):
    payload = {"model": provider.model_name, "messages": messages, "temperature": temperature}
    data = post_json(f"{ark_base_url()}/chat/completions", provider_api_key(provider), payload, timeout=timeout)
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ProviderError("Provider response missing chat content") from exc
