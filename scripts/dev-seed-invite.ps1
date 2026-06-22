$ErrorActionPreference = "Stop"
.\.venv\Scripts\python backend\manage.py shell -c "from core.models import InvitationCode; InvitationCode.objects.get_or_create(code='ALPHA-1', defaults={'max_uses': 100})"
