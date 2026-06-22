$ErrorActionPreference = "Stop"
$code = @"
from core.models import AIProvider, InvitationCode
InvitationCode.objects.get_or_create(code='ALPHA-1', defaults={'max_uses': 100})
AIProvider.objects.get_or_create(
    name='Fake LLM',
    model_name='fake-llm',
    defaults={'capability': AIProvider.LLM, 'enabled': True, 'price_coefficient': '1.00'},
)
"@
.\.venv\Scripts\python backend\manage.py shell -c $code
