import json

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import (
    AuthToken,
    CreditAccount,
    CreditTask,
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
