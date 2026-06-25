# AI 短视频批量生产工作台

Current smoke path: Django API + React/Tauri client shell with invite auth, workspace credits, manual recharge, and credit-task freezing.

## Local commands

Backend API and admin:

```powershell
.\scripts\dev-backend.ps1
```

- API health: http://127.0.0.1:8000/api/health/
- Admin: http://127.0.0.1:8000/admin/
- Credit balance: `GET /api/credits/`
- Paid task smoke: `POST /api/credit-tasks/` freezes estimated credits
- Render worker smoke: `.\.venv\Scripts\python backend\manage.py run_render_worker --limit 1`

Windows client shell:

```powershell
.\scripts\dev-client.ps1
```

- Client: http://127.0.0.1:5173/

Launch/download page:

```powershell
.\scripts\dev-site.ps1
```

- Site: http://127.0.0.1:4174/

## Volcengine provider env

- `ARK_API_KEY`: Ark data-plane API key.
- `ARK_BASE_URL`: optional, defaults to `https://ark.cn-beijing.volces.com/api/v3`.
- `VOLCENGINE_SPEECH_APP_ID`: Doubao Speech app id.
- `VOLCENGINE_SPEECH_ACCESS_TOKEN`: Doubao Speech token.
- `VOLCENGINE_TTS_URL`: TTS API URL used by the v1 adapter.
- `VOLCENGINE_TTS_CLUSTER`: TTS cluster.
- `VOLCENGINE_TTS_VOICE_TYPE`: optional TTS voice type; falls back to provider `model_name`.
- `VOLCENGINE_ASR_URL`: ASR API URL used by the v1 adapter.

## Checks

```powershell
.\.venv\Scripts\python backend\manage.py test core -v 2
cd client
npm test
npm run typecheck
npm run build
```

## Dev invite code

After running backend migrations, seed a reusable invite code for local testing:

```powershell
.\scripts\dev-seed-invite.ps1
```

Use `ALPHA-1` in the client registration form. The script also seeds one enabled fake LLM provider for advanced model selection.

## Dev credits

Manual recharge is intentionally admin-first for v1. In `/admin/`, create a `Credit recharge` with a workspace and amount; it automatically creates the ledger entry and updates the workspace balance. The client then shows the balance and can submit the 120-credit smoke task.
