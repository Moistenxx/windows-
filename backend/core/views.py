from django.http import JsonResponse


def health(request):
    response = JsonResponse(
        {"status": "ok", "service": "api", "app": "ai-video-workbench"}
    )
    # ponytail: dev-only CORS for the Vite/Tauri shell; replace with an origin allowlist before public launch.
    response["Access-Control-Allow-Origin"] = "*"
    return response
