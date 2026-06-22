import json
from pathlib import PurePath

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import (
    AIProvider,
    Asset,
    AuthToken,
    CreditAccount,
    CreditTask,
    CustomerProfile,
    InsufficientCredits,
    InvitationCode,
    Workspace,
    WorkspaceMembership,
)


def health(request):
    return JsonResponse({"status": "ok", "service": "api", "app": "ai-video-workbench"})


def read_json(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def error(message, status=400):
    return JsonResponse({"error": message}, status=status)


def clean_email(value):
    email = (value or "").strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


def workspace_payload(membership):
    return {
        "id": membership.workspace_id,
        "name": membership.workspace.name,
        "role": membership.role,
    }


def auth_payload(user, token):
    memberships = list(
        WorkspaceMembership.objects.select_related("workspace")
        .filter(user=user)
        .order_by("id")
    )
    first = memberships[0] if memberships else None
    return {
        "token": token,
        "user": {"id": user.id, "email": user.email},
        "workspace": {"id": first.workspace_id, "name": first.workspace.name} if first else None,
        "workspaces": [workspace_payload(membership) for membership in memberships],
    }


def bearer_user(request):
    prefix = "Bearer "
    header = request.headers.get("Authorization", "")
    if not header.startswith(prefix):
        return None
    return AuthToken.user_for(header[len(prefix) :].strip())


def first_membership(user):
    return (
        WorkspaceMembership.objects.select_related("workspace")
        .filter(user=user)
        .order_by("id")
        .first()
    )


def credit_payload(workspace):
    account = CreditAccount.for_workspace(workspace)
    return {
        "workspace_id": workspace.id,
        "balance": account.balance,
        "frozen": account.frozen,
    }


@csrf_exempt
def register(request):
    if request.method != "POST":
        return error("POST required", status=405)
    data = read_json(request)
    email = clean_email(data.get("email"))
    password = data.get("password") or ""
    invite_code = (data.get("invite_code") or "").strip().upper()

    if not email or len(password) < 8:
        return error("Email and 8+ character password required")
    if User.objects.filter(username=email).exists():
        return error("Email already registered")

    with transaction.atomic():
        invite = InvitationCode.objects.select_for_update().filter(code=invite_code).first()
        if not invite or not invite.can_use():
            return error("Valid invite code required")
        user = User.objects.create_user(username=email, email=email, password=password)
        workspace_name = f"{email.split('@', 1)[0]} workspace"
        workspace = Workspace.objects.create(name=workspace_name)
        WorkspaceMembership.objects.create(user=user, workspace=workspace, role=WorkspaceMembership.OWNER)
        invite.mark_used()
        token = AuthToken.issue_for(user)
    return JsonResponse(auth_payload(user, token), status=201)


@csrf_exempt
def login(request):
    if request.method != "POST":
        return error("POST required", status=405)
    data = read_json(request)
    email = clean_email(data.get("email"))
    password = data.get("password") or ""
    user = authenticate(username=email, password=password) if email else None
    if user is None:
        return error("Invalid email or password", status=401)
    if not WorkspaceMembership.objects.filter(user=user).exists():
        return error("Workspace required", status=409)
    return JsonResponse(auth_payload(user, AuthToken.issue_for(user)))


def me(request):
    user = bearer_user(request)
    if user is None:
        return error("Authentication required", status=401)
    memberships = list(
        WorkspaceMembership.objects.select_related("workspace")
        .filter(user=user)
        .order_by("id")
    )
    return JsonResponse(
        {
            "user": {"id": user.id, "email": user.email},
            "workspaces": [workspace_payload(membership) for membership in memberships],
        }
    )


def credits(request):
    user = bearer_user(request)
    if user is None:
        return error("Authentication required", status=401)
    membership = first_membership(user)
    if membership is None:
        return error("Workspace required", status=409)
    return JsonResponse(credit_payload(membership.workspace))


@csrf_exempt
def credit_tasks(request):
    if request.method != "POST":
        return error("POST required", status=405)
    user = bearer_user(request)
    if user is None:
        return error("Authentication required", status=401)
    membership = first_membership(user)
    if membership is None:
        return error("Workspace required", status=409)

    data = read_json(request)
    try:
        estimated_credits = int(data.get("estimated_credits", 0))
        title = (data.get("title") or "Paid task").strip()[:160]
        task = CreditTask.submit(membership.workspace, user, estimated_credits, title=title)
    except (TypeError, ValueError):
        return error("Positive estimated_credits required")
    except InsufficientCredits:
        return error("Insufficient credits", status=402)

    return JsonResponse(
        {
            "task": {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "estimated_credits": task.estimated_credits,
            },
            "credits": credit_payload(membership.workspace),
        },
        status=201,
    )


def require_user(request):
    user = bearer_user(request)
    if user is None:
        return None, error("Authentication required", status=401)
    if first_membership(user) is None:
        return None, error("Workspace required", status=409)
    return user, None


def ai_providers(request):
    _, auth_error = require_user(request)
    if auth_error:
        return auth_error
    providers = AIProvider.objects.filter(enabled=True).order_by("capability", "id")
    return JsonResponse({"providers": [provider.public_payload() for provider in providers]})


@csrf_exempt
def ai_estimate(request):
    if request.method != "POST":
        return error("POST required", status=405)
    _, auth_error = require_user(request)
    if auth_error:
        return auth_error
    data = read_json(request)
    try:
        provider = AIProvider.objects.get(id=int(data.get("provider_id")), enabled=True)
        estimated_credits = provider.estimate_credits(int(data.get("base_credits", 0)))
    except (AIProvider.DoesNotExist, TypeError, ValueError):
        return error("Valid provider_id and positive base_credits required")
    return JsonResponse({"provider_id": provider.id, "estimated_credits": estimated_credits})


@csrf_exempt
def ai_fake_call(request):
    if request.method != "POST":
        return error("POST required", status=405)
    _, auth_error = require_user(request)
    if auth_error:
        return auth_error
    data = read_json(request)
    try:
        provider = AIProvider.objects.get(id=int(data.get("provider_id")), enabled=True)
    except (AIProvider.DoesNotExist, TypeError, ValueError):
        return error("Valid provider_id required")
    return JsonResponse({"provider_id": provider.id, "output": provider.fake_call(data.get("prompt", ""))})


CUSTOMER_FIELDS = [
    "name",
    "industry",
    "products",
    "target_audience",
    "selling_points",
    "forbidden_words",
    "contact_hooks",
    "style_preference",
    "logo_or_common_assets",
]


def customer_input(data, existing=None):
    values = {}
    for field in CUSTOMER_FIELDS:
        if field in data:
            value = str(data.get(field) or "").strip()
            if field == "name":
                value = value[:160]
            if field == "industry":
                value = value[:120]
            values[field] = value
    name = values["name"] if "name" in values else (existing.name if existing else "")
    if not name:
        raise ValueError("Customer name required")
    return values


@csrf_exempt
def customers(request):
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    if request.method == "GET":
        profiles = CustomerProfile.objects.filter(workspace=workspace).order_by("-updated_at", "id")
        return JsonResponse({"customers": [profile.public_payload() for profile in profiles]})
    if request.method != "POST":
        return error("GET or POST required", status=405)
    try:
        profile = CustomerProfile.objects.create(workspace=workspace, **customer_input(read_json(request)))
    except ValueError as exc:
        return error(str(exc))
    return JsonResponse(profile.public_payload(), status=201)


@csrf_exempt
def customer_detail(request, customer_id):
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    try:
        profile = CustomerProfile.objects.get(id=customer_id, workspace=workspace)
    except CustomerProfile.DoesNotExist:
        return error("Customer not found", status=404)
    if request.method != "POST":
        return error("POST required", status=405)
    try:
        for field, value in customer_input(read_json(request), existing=profile).items():
            setattr(profile, field, value)
    except ValueError as exc:
        return error(str(exc))
    profile.save()
    return JsonResponse(profile.public_payload())


ASSET_TYPES = {
    "mp4": (Asset.VIDEO, "video/mp4"),
    "mov": (Asset.VIDEO, "video/quicktime"),
    "jpg": (Asset.IMAGE, "image/jpeg"),
    "jpeg": (Asset.IMAGE, "image/jpeg"),
    "png": (Asset.IMAGE, "image/png"),
    "webp": (Asset.IMAGE, "image/webp"),
    "mp3": (Asset.AUDIO, "audio/mpeg"),
    "wav": (Asset.AUDIO, "audio/wav"),
}


def asset_type_for(filename, content_type):
    asset = ASSET_TYPES.get(PurePath(filename).suffix.lower().lstrip("."))
    if not asset or asset[1] != content_type:
        raise ValueError("Supported files: MP4/MOV, JPG/PNG/WEBP, MP3/WAV")
    return asset[0]


@csrf_exempt
def assets(request):
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    if request.method == "GET":
        rows = Asset.objects.filter(workspace=workspace, deleted_at__isnull=True).order_by("-created_at", "id")
        return JsonResponse({"assets": [asset.public_payload() for asset in rows]})
    if request.method != "POST":
        return error("GET or POST required", status=405)
    data = read_json(request)
    filename = str(data.get("filename") or "").strip()
    content_type = str(data.get("content_type") or "").strip().lower()
    try:
        asset_type = asset_type_for(filename, content_type)
    except ValueError as exc:
        return error(str(exc))
    asset = Asset.objects.create(
        workspace=workspace,
        uploaded_by=user,
        filename=PurePath(filename).name[:240] or "asset",
        content_type=content_type,
        asset_type=asset_type,
        object_key=Asset.new_object_key(workspace, filename),
    )
    return JsonResponse(
        {
            "asset": asset.public_payload(),
            "upload": {
                "method": "PUT",
                "url": f"local://{asset.object_key}",
                "headers": {"Content-Type": content_type},
            },
        },
        status=201,
    )


@csrf_exempt
def asset_delete(request, asset_id):
    if request.method != "POST":
        return error("POST required", status=405)
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    try:
        asset = Asset.objects.get(id=asset_id, workspace=workspace)
    except Asset.DoesNotExist:
        return error("Asset not found", status=404)
    asset.deleted_at = timezone.now()
    asset.save(update_fields=["deleted_at"])
    return JsonResponse(asset.public_payload())
