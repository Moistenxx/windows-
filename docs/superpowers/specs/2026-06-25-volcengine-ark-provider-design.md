# Volcengine Ark Provider Integration Design

## Goal

Make the MVP use real Volcengine-backed AI capabilities instead of deterministic fakes, while keeping the Windows client flow unchanged.

## Product scope

The product remains a Windows local client + cloud backend AI short-video workbench. This integration covers:

- LLM script generation for Douyin-style viral scripts.
- Vision/image understanding for uploaded asset tagging and script context.
- TTS voiceover generation.
- ASR subtitle generation from uploaded audio/video.
- Extension seams for image generation, video generation, digital human, voice clone, and ComfyUI-style workflows.

## External references checked

- Volcengine Ark OpenAI-compatible integration: https://www.volcengine.com/docs/82379/1330626
- Volcengine Ark Base URL/authentication: https://www.volcengine.com/docs/82379/1298459
- Volcengine Ark Chat API: https://www.volcengine.com/docs/82379/1494384
- Volcengine Ark image understanding: https://www.volcengine.com/docs/82379/1362931
- Volcengine Ark image generation API reference: https://www.volcengine.com/docs/82379/1541523
- Doubao Speech ASR API: https://www.volcengine.com/docs/6561/1354869
- Doubao Speech TTS API: https://www.volcengine.com/docs/6561/1257584

## Architecture

Use one backend provider seam:

```text
client
  -> existing REST endpoints
    -> provider service layer
      -> Volcengine Ark / Doubao Speech HTTP APIs
        -> local_media output assets
```

The client keeps sending `provider_id`; the backend decides whether that provider calls Ark Chat, Ark multimodal, Ark image/video generation, or Doubao Speech.

## Data model

Keep the existing `AIProvider` table:

- `capability`: routes calls (`llm`, `tts`, `asr`, `vision`, `image`, `video`, `digital_human`, `voice_clone`, `comfyui`).
- `model_name`: stores Ark endpoint/model ID or speech model/voice identifier.
- `api_key_env`: stores only the server environment variable name.

No plaintext API keys go into the database.

For v1, provider-specific values stay in environment variables. Add DB config fields only when the admin UI needs editing per-provider advanced options.

## Environment variables

Minimum:

- `ARK_API_KEY`: Ark data-plane API key.
- `ARK_BASE_URL`: optional; default `https://ark.cn-beijing.volces.com/api/v3`.

Speech:

- `VOLCENGINE_SPEECH_APP_ID`
- `VOLCENGINE_SPEECH_ACCESS_TOKEN`
- `VOLCENGINE_TTS_CLUSTER`
- `VOLCENGINE_TTS_VOICE_TYPE`

## Capability behavior

### LLM scripts

`script_generate` builds the existing customer/template/sample prompt, calls Ark Chat, and returns three candidates. If the key is missing or Ark returns an error, the endpoint returns a visible error; it does not silently fall back to fake output.

### Vision tagging

Asset tagging calls Ark multimodal/image understanding when a `vision` provider is enabled. Missing provider keeps the current filename heuristic with its existing `ponytail:` comment.

### TTS voiceover

`job_voiceover` with `mode=tts` calls Doubao Speech TTS and writes an audio asset under `local_media`, then stores the asset on the job. Missing speech env vars return an actionable error.

### ASR subtitles

`job_voiceover` with `mode=asr` calls Doubao Speech ASR for uploaded audio/video and stores subtitle segments on the job. For v1, if the official API requires object storage URLs, return a clear error until OSS upload is wired.

### Image/video/digital-human extension seams

Do not build full UX yet. Add backend service interfaces and provider capability checks so future endpoints can call:

- `generate_image(prompt, provider)`
- `generate_video(prompt, assets, provider)`
- `generate_digital_human(script, assets, provider)`

These stay unused until product flows are designed.

## Error handling

- Provider timeouts and HTTP failures return `400`/`502` JSON errors with no secret leakage.
- Generated media is written as normal `Asset` rows.
- Credit freeze/settle stays with existing job lifecycle; provider calls do not directly mutate credits outside job methods.

## Testing

- Unit tests mock HTTP at the provider service boundary.
- Existing fake paths stay only where no provider is enabled.
- Add one integration-style test per capability endpoint touched.

## Out of scope for this integration pass

- Real payment automation.
- Full secret manager.
- Redis/RabbitMQ queue infrastructure.
- New Windows UI for image/video/digital-human generation.
