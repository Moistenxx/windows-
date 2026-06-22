# AI 短视频批量生产工作台

Issue #1 skeleton: Django API, React/Tauri client shell, admin entry, and launch/download page entry.

## Local commands

Backend API and admin:

```powershell
.\scripts\dev-backend.ps1
```

- API health: http://127.0.0.1:8000/api/health/
- Admin: http://127.0.0.1:8000/admin/

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
