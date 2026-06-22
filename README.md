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
