# Volcengine Ark Provider Integration Implementation Plan

**For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) superpowers:executing-plans implement plan task-by-task. Steps use checkbox (`- [ ]`) syntax tracking.

**Goal:** Replace deterministic AI fakes with real Volcengine Ark/Doubao Speech provider calls while keeping the Windows client API flow unchanged.

**Architecture:** Add a small backend provider service layer that owns vendor HTTP calls, error normalization, and env-var secret lookup. Existing views keep accepting `provider_id` and route by `AIProvider.capability`. Generated media stays as normal `Asset` rows so render/preview/download code does not change.

**Tech Stack:** Django backend, stdlib `urllib.request` HTTP client, existing `AIProvider`, existing `Asset`, existing tests with `unittest.mock.patch`.

## Global Constraints

- No plaintext provider API keys in the database; `AIProvider.api_key_env` stores env-var names only.
- No new Python dependency for HTTP; use stdlib unless official SDK becomes unavoidable.
- Client flow stays unchanged for this pass.
- Missing provider credentials return JSON errors; do not silently fall back to fake output for explicitly selected providers.
- Fake/heuristic paths may remain only when no real provider is enabled, with existing `ponytail:` comments.
- Commit after each independently green task.

---

## File Structure

- Create: `backend/core/provider_clients.py` — Volcengine/Doubao HTTP helpers and provider-specific functions.
- Modify: `backend/core/views.py` — route LLM, vision, TTS, and ASR calls through provider clients.
- Modify: `backend/core/tests.py` — integration-style endpoint tests with mocked provider clients.
- Modify: `README.md` — document required env vars and smoke commands.

---

### Task 1: Provider client foundation

**Files:**
- Create: `backend/core/provider_clients.py`
- Test: `backend/core/tests.py`

**Interfaces:**
- Consumes: `AIProvider.api_key_env`, `AIProvider.model_name`
- Produces: `ProviderError`, `ark_chat(provider, messages)`, `ark_base_url()`

- [ ] **Step 1: Write failing tests**

Add tests near `AIProviderTests`:

```python
class ProviderClientTests(TestCase):
    def test_ark_chat_requires_configured_api_key(self):
        provider = AIProvider.objects.create(capability=AIProvider.LLM, name="Ark", model_name="ep-test", api_key_env="MISSING_ARK_KEY", enabled=True)
        from core.provider_clients import ProviderError, ark_chat

        with self.assertRaises(ProviderError) as error:
            ark_chat(provider, [{"role": "user", "content": "写一条爆款脚本"}])

        self.assertIn("MISSING_ARK_KEY", str(error.exception))

    def test_ark_chat_posts_openai_compatible_payload(self):
        provider = AIProvider.objects.create(capability=AIProvider.LLM, name="Ark", model_name="ep-test", api_key_env="ARK_API_KEY", enabled=True)
        from core import provider_clients

        def fake_urlopen(request, timeout):
            self.assertIn("/chat/completions", request.full_url)
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            body = json.loads(request.data.decode("utf-8"))
            self.assertEqual(body["model"], "ep-test")
            return FakeHttpResponse({"choices": [{"message": {"content": "候选脚本"}}]})

        with patch.dict(os.environ, {"ARK_API_KEY": "test-key"}), patch("core.provider_clients.urlopen", side_effect=fake_urlopen):
            self.assertEqual(provider_clients.ark_chat(provider, [{"role": "user", "content": "hi"}]), "候选脚本")
```

Add tiny test helper at module level:

```python
class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def read(self):
        return json.dumps(self.payload).encode("utf-8")
```

- [ ] **Step 2: Run tests verify fail**

Run:

```powershell
rtk test .\.venv\Scripts\python backend\manage.py test core.tests.ProviderClientTests -v 2
```

Expected: FAIL because `core.provider_clients` does not exist.

- [ ] **Step 3: Implement minimal provider client**

Create `backend/core/provider_clients.py`:

```python
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
```

- [ ] **Step 4: Run tests verify pass**

Run same command. Expected: OK.

- [ ] **Step 5: Commit**

```powershell
git add backend/core/provider_clients.py backend/core/tests.py; git commit -m "feat: add volcengine provider client"
```

---

### Task 2: Real Ark LLM script generation

**Files:**
- Modify: `backend/core/views.py`
- Test: `backend/core/tests.py`

**Interfaces:**
- Consumes: `ark_chat(provider, messages)` from Task 1
- Produces: `generate_script_candidates(customer, template, provider, duration_seconds, samples)`

- [ ] **Step 1: Write failing endpoint test**

Add to `ScriptGenerationTests`:

```python
def test_script_generation_uses_real_ark_provider_when_selected(self):
    user, workspace = make_user_workspace()
    token = AuthToken.issue_for(user)
    customer = CustomerProfile.objects.create(workspace=workspace, name="珠宝店", industry="珠宝", products="黄金手镯", selling_points="保真低工费")
    template = IndustryTemplate.objects.create(name="黄金爆款", industry="珠宝", enabled=True)
    provider = AIProvider.objects.create(capability=AIProvider.LLM, name="Ark", model_name="ep-test", api_key_env="ARK_API_KEY", enabled=True)

    with patch("core.views.ark_chat", return_value="1. 开头\n2. 卖点\n---\n第二条\n---\n第三条") as chat:
        response = self.client.post(
            "/api/scripts/generate/",
            data={"customer_id": customer.id, "template_id": template.id, "provider_id": provider.id, "duration_seconds": 30, "sample_ids": []},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    self.assertEqual(response.status_code, 201)
    self.assertEqual(len(response.json()["candidates"]), 3)
    chat.assert_called_once()
```

- [ ] **Step 2: Run test verify fail**

```powershell
rtk test .\.venv\Scripts\python backend\manage.py test core.tests.ScriptGenerationTests.test_script_generation_uses_real_ark_provider_when_selected -v 2
```

Expected: FAIL because `core.views.ark_chat` is not imported/used.

- [ ] **Step 3: Implement minimal LLM routing**

In `backend/core/views.py` import:

```python
from core.provider_clients import ProviderError, ark_chat
```

Replace fake-only generation with:

```python
def split_script_candidates(text):
    chunks = [chunk.strip() for chunk in text.split("---") if chunk.strip()]
    if len(chunks) >= 3:
        return chunks[:3]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return (lines + [text.strip()])[:3]


def real_script_candidates(customer, template, provider, duration_seconds, samples):
    sample_text = "\n".join(f"- {sample.copy[:160]}" for sample in samples)
    prompt = (
        f"你是抖音爆款短视频编导。请为{customer.name}生成3条{duration_seconds}秒中文短视频脚本。\n"
        f"行业：{customer.industry or template.industry}\n产品：{customer.products}\n卖点：{customer.selling_points}\n禁用词：{customer.forbidden_words}\n参考爆款：\n{sample_text}\n"
        "每条脚本用 --- 分隔，包含开头钩子、痛点、卖点、行动号召。"
    )
    return split_script_candidates(ark_chat(provider, [{"role": "user", "content": prompt}]))
```

In `script_generate`, set:

```python
candidates=real_script_candidates(customer, template, provider, duration_seconds, samples),
```

Catch `ProviderError` and return `error(str(exc), status=502)`.

- [ ] **Step 4: Run tests verify pass**

Run the single test, then:

```powershell
rtk test .\.venv\Scripts\python backend\manage.py test core.tests.ScriptGenerationTests -v 2
```

Expected: OK.

- [ ] **Step 5: Commit**

```powershell
git add backend/core/views.py backend/core/tests.py; git commit -m "feat: use ark for script generation"
```

---

### Task 3: Vision provider for asset tags

**Files:**
- Modify: `backend/core/provider_clients.py`
- Modify: `backend/core/views.py`
- Test: `backend/core/tests.py`

**Interfaces:**
- Consumes: `ark_chat(provider, messages)`
- Produces: `suggest_asset_tags(asset, provider=None)` returning `list[str]`

- [ ] **Step 1: Write failing test**

Add to asset tests:

```python
def test_upload_uses_vision_provider_for_suggested_tags(self):
    user, workspace = make_user_workspace()
    token = AuthToken.issue_for(user)
    AIProvider.objects.create(capability=AIProvider.VISION, name="Ark Vision", model_name="ep-vision", api_key_env="ARK_API_KEY", enabled=True)

    with patch("core.views.ark_chat", return_value="product, jewelry, gold"):
        response = self.client.post(
            "/api/assets/",
            data={"filename": "gold.jpg", "content_type": "image/jpeg"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    self.assertEqual(response.status_code, 201)
    self.assertEqual(response.json()["asset"]["suggested_tags"], ["product", "jewelry", "gold"])
```

- [ ] **Step 2: Run test verify fail**

Run the exact test. Expected: FAIL because upload still uses heuristic only.

- [ ] **Step 3: Implement minimal vision routing**

In `views.py`, choose the first enabled vision provider in workspace-independent provider config:

```python
def parse_tags(text):
    return [tag.strip()[:40] for tag in text.replace("，", ",").split(",") if tag.strip()][:8]


def suggested_tags_for_asset(asset):
    provider = AIProvider.objects.filter(capability=AIProvider.VISION, enabled=True).order_by("id").first()
    if provider:
        try:
            return parse_tags(ark_chat(provider, [{"role": "user", "content": f"为素材文件名生成短标签，逗号分隔：{asset.filename}"}]))
        except ProviderError:
            pass
    return heuristic_asset_tags(asset.filename)
```

Keep existing `ponytail:` heuristic comment on fallback.

- [ ] **Step 4: Run asset tests**

```powershell
rtk test .\.venv\Scripts\python backend\manage.py test core.tests.AssetLibraryTests core.tests.AssetTaggingTests -v 2
```

Expected: OK.

- [ ] **Step 5: Commit**

```powershell
git add backend/core/views.py backend/core/tests.py; git commit -m "feat: use ark vision for asset tags"
```

---

### Task 4: Doubao Speech TTS output asset

**Files:**
- Modify: `backend/core/provider_clients.py`
- Modify: `backend/core/views.py`
- Test: `backend/core/tests.py`

**Interfaces:**
- Produces: `doubao_tts(provider, text) -> bytes`
- Consumes: existing `job_voiceover` TTS mode

- [ ] **Step 1: Write failing TTS test**

```python
def test_tts_voiceover_creates_audio_asset_from_provider_bytes(self):
    user, workspace = make_user_workspace()
    CreditRecharge.objects.create(workspace=workspace, amount=200)
    token = AuthToken.issue_for(user)
    draft = make_confirmed_draft(workspace, user)
    job = self.client.post("/api/jobs/", data={"estimated_credits": 50, "script_draft_id": draft.id}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}").json()["job"]
    provider = AIProvider.objects.create(capability=AIProvider.TTS, name="Doubao TTS", model_name="voice", api_key_env="VOLCENGINE_SPEECH_ACCESS_TOKEN", enabled=True)

    with patch("core.views.doubao_tts", return_value=b"mp3-bytes"):
        response = self.client.post(f"/api/jobs/{job['id']}/voiceover/", data={"mode": "tts", "provider_id": provider.id, "script": "你好"}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")

    self.assertEqual(response.status_code, 200)
    self.assertIn("audio_placeholder", response.json()["job"])
```

- [ ] **Step 2: Run test verify fail**

Expected: FAIL because current TTS stores placeholder only.

- [ ] **Step 3: Implement minimal TTS client and asset write**

In `provider_clients.py`:

```python
def doubao_tts(provider, text, timeout=60):
    token = provider_api_key(provider)
    payload = {"text": text, "voice_type": os.environ.get("VOLCENGINE_TTS_VOICE_TYPE", provider.model_name)}
    data = post_json(os.environ["VOLCENGINE_TTS_URL"], token, payload, timeout=timeout)
    audio = data.get("audio") or data.get("data")
    if not audio:
        raise ProviderError("TTS response missing audio")
    return audio.encode("utf-8") if isinstance(audio, str) else audio
```

In `job_voiceover`, write bytes to `local_media` and attach/create an audio `Asset`. Keep existing placeholder text as display metadata.

- [ ] **Step 4: Run voiceover tests**

```powershell
rtk test .\.venv\Scripts\python backend\manage.py test core.tests.VoiceoverSubtitleTests -v 2
```

Expected: OK.

- [ ] **Step 5: Commit**

```powershell
git add backend/core/provider_clients.py backend/core/views.py backend/core/tests.py; git commit -m "feat: use doubao speech for tts"
```

---

### Task 5: Doubao Speech ASR subtitles

**Files:**
- Modify: `backend/core/provider_clients.py`
- Modify: `backend/core/views.py`
- Test: `backend/core/tests.py`

**Interfaces:**
- Produces: `doubao_asr(provider, asset_path) -> list[dict]`
- Consumes: existing `job_voiceover` ASR mode

- [ ] **Step 1: Write failing ASR test**

```python
def test_asr_voiceover_uses_provider_segments(self):
    user, workspace = make_user_workspace()
    token = AuthToken.issue_for(user)
    provider = AIProvider.objects.create(capability=AIProvider.ASR, name="Doubao ASR", model_name="asr", api_key_env="VOLCENGINE_SPEECH_ACCESS_TOKEN", enabled=True)
    asset = Asset.objects.create(workspace=workspace, uploaded_by=user, filename="clip.mp4", content_type="video/mp4", asset_type=Asset.VIDEO, object_key="asr/clip.mp4")
    draft = make_confirmed_draft(workspace, user)
    job = self.client.post("/api/jobs/", data={"estimated_credits": 50, "script_draft_id": draft.id}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}").json()["job"]

    with patch("core.views.doubao_asr", return_value=[{"start": 0, "end": 1.5, "text": "你好"}]):
        response = self.client.post(f"/api/jobs/{job['id']}/voiceover/", data={"mode": "asr", "provider_id": provider.id, "asset_id": asset.id}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json()["job"]["subtitles"], [{"start": 0, "end": 1.5, "text": "你好"}])
```

- [ ] **Step 2: Run test verify fail**

Expected: FAIL because ASR currently uses generated placeholder subtitles.

- [ ] **Step 3: Implement minimal ASR routing**

In `provider_clients.py`:

```python
def doubao_asr(provider, asset_path, timeout=120):
    token = provider_api_key(provider)
    payload = {"audio": asset_path.read_bytes().hex(), "model": provider.model_name}
    data = post_json(os.environ["VOLCENGINE_ASR_URL"], token, payload, timeout=timeout)
    segments = data.get("segments") or data.get("result", {}).get("segments")
    if not isinstance(segments, list):
        raise ProviderError("ASR response missing segments")
    return [{"start": float(item["start"]), "end": float(item["end"]), "text": str(item["text"])[:200]} for item in segments]
```

In `job_voiceover`, use `local_asset_path(asset.object_key)` and return a clear `ProviderError` if the file is missing.

- [ ] **Step 4: Run voiceover tests**

Run `VoiceoverSubtitleTests`. Expected: OK.

- [ ] **Step 5: Commit**

```powershell
git add backend/core/provider_clients.py backend/core/views.py backend/core/tests.py; git commit -m "feat: use doubao speech for asr"
```

---

### Task 6: Generation seams for image/video/digital human

**Files:**
- Modify: `backend/core/provider_clients.py`
- Test: `backend/core/tests.py`

**Interfaces:**
- Produces: `generate_image(prompt, provider)`, `generate_video(prompt, provider)`, `generate_digital_human(script, provider)`

- [ ] **Step 1: Write seam tests**

```python
def test_future_generation_seams_require_matching_capability(self):
    provider = AIProvider.objects.create(capability=AIProvider.IMAGE, name="Ark Image", model_name="image", api_key_env="ARK_API_KEY", enabled=True)
    from core.provider_clients import generate_image

    with patch("core.provider_clients.ark_chat", return_value="asset-url"):
        self.assertEqual(generate_image("黄金手镯海报", provider), "asset-url")
```

- [ ] **Step 2: Run test verify fail**

Expected: FAIL because functions do not exist.

- [ ] **Step 3: Implement thin seams only**

```python
def require_capability(provider, capability):
    if provider.capability != capability:
        raise ProviderError(f"Provider {provider.id} is not {capability}")


def generate_image(prompt, provider):
    require_capability(provider, "image")
    return ark_chat(provider, [{"role": "user", "content": prompt}])


def generate_video(prompt, provider):
    require_capability(provider, "video")
    return ark_chat(provider, [{"role": "user", "content": prompt}])


def generate_digital_human(script, provider):
    require_capability(provider, "digital_human")
    return ark_chat(provider, [{"role": "user", "content": script}])
```

- [ ] **Step 4: Run provider client tests**

Expected: OK.

- [ ] **Step 5: Commit**

```powershell
git add backend/core/provider_clients.py backend/core/tests.py; git commit -m "feat: add ark generation seams"
```

---

### Task 7: README and full verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: all tasks above
- Produces: documented local smoke setup

- [ ] **Step 1: Document env vars**

Add to README:

```markdown
## Volcengine provider env

- `ARK_API_KEY`: Ark data-plane API key.
- `ARK_BASE_URL`: optional, defaults to `https://ark.cn-beijing.volces.com/api/v3`.
- `VOLCENGINE_SPEECH_APP_ID`: Doubao Speech app id.
- `VOLCENGINE_SPEECH_ACCESS_TOKEN`: Doubao Speech token.
- `VOLCENGINE_TTS_CLUSTER`: TTS cluster.
- `VOLCENGINE_TTS_VOICE_TYPE`: TTS voice type.
- `VOLCENGINE_TTS_URL`: TTS API URL used by the v1 adapter.
- `VOLCENGINE_ASR_URL`: ASR API URL used by the v1 adapter.
```

- [ ] **Step 2: Run full verification**

```powershell
rtk test .\.venv\Scripts\python backend\manage.py test core -v 2
cd client; npm test; npm run build; cd ..
.\.venv\Scripts\python backend\manage.py makemigrations --check --dry-run
git diff --check
```

Expected: backend tests OK, frontend tests OK, build OK, no migrations, no whitespace errors.

- [ ] **Step 3: Commit docs and final fixes**

```powershell
git add README.md backend/core/provider_clients.py backend/core/views.py backend/core/tests.py; git commit -m "docs: document volcengine provider setup"
```
