import json
import re
import subprocess
import uuid
from pathlib import Path, PurePath

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import (
    AIProvider,
    Asset,
    AuthToken,
    ConcurrencyLimitReached,
    CreditAccount,
    CreditTask,
    CustomerProfile,
    InsufficientCredits,
    IndustryTemplate,
    InvitationCode,
    Job,
    ScriptDraft,
    ViralSample,
    Workspace,
    WorkspaceMembership,
)
from .provider_clients import ProviderError, ark_chat, doubao_asr, doubao_tts


def health(request):
    return JsonResponse({"status": "ok", "service": "api", "app": "ai-video-workbench"})


def client_version(request):
    return JsonResponse(
        {
            "platform": "windows",
            "version": "0.1.0",
            "download_url": "/downloads/ai-video-workbench-windows.zip",
            "notes": "Windows client preview build",
        }
    )


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


def job_list_payload(workspace):
    jobs = Job.objects.filter(workspace=workspace).order_by("-created_at", "id")
    return {
        "jobs": [job.public_payload() for job in jobs],
        "concurrency_limits": {
            "global": Job.GLOBAL_RUNNING_LIMIT,
            "workspace": Job.WORKSPACE_RUNNING_LIMIT,
        },
    }


def fake_subtitle_cues(text):
    # ponytail: fake timing splits sentences; replace with TTS/ASR timestamps when providers are wired.
    parts = [part.strip() for part in re.split(r"[。！？.!?\n]+", text) if part.strip()]
    return [{"start": index * 2, "end": index * 2 + 2, "text": part[:200]} for index, part in enumerate(parts or [text.strip()])]


def clean_subtitles(value):
    if not isinstance(value, list):
        raise ValueError("subtitles must be a list")
    subtitles = []
    for index, cue in enumerate(value):
        if not isinstance(cue, dict):
            raise ValueError("subtitle cue must be an object")
        start = float(cue.get("start", index * 2))
        end = float(cue.get("end", start + 2))
        text = str(cue.get("text") or "").strip()
        if not text or end <= start:
            raise ValueError("Valid subtitle text and timing required")
        subtitles.append({"start": start, "end": end, "text": text[:200]})
    return subtitles


@csrf_exempt
def jobs(request):
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    if request.method == "GET":
        return JsonResponse(job_list_payload(workspace))
    if request.method != "POST":
        return error("GET or POST required", status=405)
    data = read_json(request)
    try:
        draft = ScriptDraft.objects.get(id=int(data.get("script_draft_id")), workspace=workspace)
        if not draft.render_ready:
            raise ValueError
        job = Job.submit(
            workspace,
            user,
            int(data.get("estimated_credits", 0)),
            title=str(data.get("title") or "Render job").strip()[:160],
        )
        job.render = {"script_draft_id": draft.id, "confirmed_script": draft.confirmed_script}
        job.save(update_fields=["render", "updated_at"])
    except (ScriptDraft.DoesNotExist, TypeError, ValueError):
        return error("Confirmed script_draft_id and positive estimated_credits required")
    except InsufficientCredits:
        return error("Insufficient credits", status=402)
    return JsonResponse({"job": job.public_payload(), "credits": credit_payload(workspace)}, status=201)


@csrf_exempt
def job_transition(request, job_id):
    if request.method != "POST":
        return error("POST required", status=405)
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    try:
        job = Job.objects.get(id=job_id, workspace=workspace)
    except Job.DoesNotExist:
        return error("Job not found", status=404)
    data = read_json(request)
    try:
        if data.get("status") == Job.RUNNING:
            job.start(str(data.get("current_step") or ""))
        elif data.get("status") == Job.SUCCEEDED:
            job.succeed()
        elif data.get("status") == Job.FAILED:
            job.fail(data.get("error_message") or "")
        else:
            return error("Supported status required")
    except ConcurrencyLimitReached:
        return JsonResponse({"error": "Concurrency limit reached", "job": job.public_payload(), "credits": credit_payload(workspace)}, status=409)
    except ValueError as exc:
        return error(str(exc))
    return JsonResponse({"job": job.public_payload(), "credits": credit_payload(workspace)})


@csrf_exempt
def job_voiceover(request, job_id):
    if request.method != "POST":
        return error("POST required", status=405)
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    try:
        job = Job.objects.get(id=job_id, workspace=workspace)
    except Job.DoesNotExist:
        return error("Job not found", status=404)
    data = read_json(request)
    mode = str(data.get("mode") or Job.VOICEOVER_NONE).strip()
    try:
        if mode == Job.VOICEOVER_NONE:
            job.voiceover_mode = Job.VOICEOVER_NONE
            job.voiceover_provider = None
            job.source_audio_asset = None
            job.audio_placeholder = ""
        elif mode == Job.VOICEOVER_TTS:
            provider = AIProvider.objects.get(id=int(data.get("provider_id")), enabled=True, capability=AIProvider.TTS)
            script = str(data.get("script") or "").strip()
            if not script:
                raise ValueError
            job.voiceover_mode = Job.VOICEOVER_TTS
            job.voiceover_provider = provider
            if provider.api_key_env:
                object_key = f"workspaces/{workspace.id}/voiceovers/{uuid.uuid4().hex}/job-{job.id}.mp3"
                output_path = local_asset_path(object_key)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(doubao_tts(provider, script))
                job.source_audio_asset = Asset.objects.create(
                    workspace=workspace,
                    uploaded_by=user,
                    filename=f"job-{job.id}-voiceover.mp3",
                    content_type="audio/mpeg",
                    asset_type=Asset.AUDIO,
                    object_key=object_key,
                    tags=["voiceover"],
                )
                job.audio_placeholder = f"local://{object_key}"
            else:
                job.source_audio_asset = None
                job.audio_placeholder = f"local://jobs/{job.id}/voiceover/{provider.model_name}.mp3"
            job.subtitles = fake_subtitle_cues(script)
        elif mode == Job.VOICEOVER_ASR:
            provider = AIProvider.objects.get(id=int(data.get("provider_id")), enabled=True, capability=AIProvider.ASR)
            asset = Asset.objects.get(id=int(data.get("asset_id")), workspace=workspace, asset_type__in=[Asset.AUDIO, Asset.VIDEO], deleted_at__isnull=True)
            job.voiceover_mode = Job.VOICEOVER_ASR
            job.voiceover_provider = provider
            job.source_audio_asset = asset
            job.audio_placeholder = ""
            if provider.api_key_env:
                job.subtitles = doubao_asr(provider, local_asset_path(asset.object_key))
            else:
                job.subtitles = [{"start": 0, "end": 2, "text": f"ASR subtitles for {asset.filename}"}]
        else:
            return error("Supported voiceover mode required")
        if "subtitles" in data:
            job.subtitles = clean_subtitles(data.get("subtitles"))
    except (AIProvider.DoesNotExist, Asset.DoesNotExist, TypeError, ValueError):
        return error("Valid voiceover mode, provider, script, asset and subtitles required")
    except ProviderError as exc:
        return error(str(exc), status=502)
    job.save(update_fields=["voiceover_mode", "voiceover_provider", "source_audio_asset", "audio_placeholder", "subtitles", "updated_at"])
    return JsonResponse({"job": job.public_payload(), "credits": credit_payload(workspace)})


@csrf_exempt
def job_subtitles(request, job_id):
    if request.method != "POST":
        return error("POST required", status=405)
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    try:
        job = Job.objects.get(id=job_id, workspace=workspace)
        job.subtitles = clean_subtitles(read_json(request).get("subtitles"))
    except Job.DoesNotExist:
        return error("Job not found", status=404)
    except (TypeError, ValueError) as exc:
        return error(str(exc))
    job.save(update_fields=["subtitles", "updated_at"])
    return JsonResponse({"job": job.public_payload(), "credits": credit_payload(workspace)})


RENDER_TAG_PRIORITY = ["product", "person", "detail", "process", "comparison", "price", "certificate", "storefront", "environment"]

def local_asset_path(object_key):
    return Path(settings.BASE_DIR) / "local_media" / object_key

def preview_user(request):
    return bearer_user(request)

def ordered_render_assets(workspace, raw_ids):
    if not isinstance(raw_ids, list):
        raise ValueError("asset_ids must be a list")
    asset_ids = [int(asset_id) for asset_id in raw_ids]
    assets = list(Asset.objects.filter(id__in=asset_ids, workspace=workspace, deleted_at__isnull=True).exclude(asset_type=Asset.OUTPUT))
    if len(assets) != len(set(asset_ids)) or not assets:
        raise ValueError("Valid asset_ids required")
    def rank(asset):
        ranks = [RENDER_TAG_PRIORITY.index(tag) for tag in asset.tags if tag in RENDER_TAG_PRIORITY]
        return (min(ranks) if ranks else len(RENDER_TAG_PRIORITY), asset.id)
    return sorted(assets, key=rank)

def rotated(items, offset):
    if not items:
        return []
    offset %= len(items)
    return items[offset:] + items[:offset]

def render_source_args(assets):
    for asset in assets:
        if asset.asset_type not in {Asset.VIDEO, Asset.IMAGE}:
            continue
        path = local_asset_path(asset.object_key)
        if not path.exists():
            continue
        if asset.asset_type == Asset.IMAGE:
            return ["-loop", "1", "-t", "1", "-i", str(path)]
        return ["-t", "1", "-i", str(path)]
    # ponytail: local smoke falls back to black when OSS bytes are absent; real worker streams object storage.
    return ["-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1"]

def run_ffmpeg_render(job, assets, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = " ".join(str(cue.get("text", "")) for cue in job.subtitles[:2]) or job.title
    safe_text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff ]+", " ", text).strip()[:120] or "AI video"
    command = [
        "ffmpeg",
        "-y",
        *render_source_args(assets),
        "-vf",
        f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,drawtext=text='{safe_text}':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=h-240",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(result.stderr.decode("utf-8", errors="ignore")[-500:] or "ffmpeg failed")
    return output_path

def complete_render_job(job_id):
    job = Job.objects.select_related("workspace", "created_by").get(id=job_id)
    workspace = job.workspace
    output = None
    object_key = f"workspaces/{workspace.id}/outputs/{uuid.uuid4().hex}/job-{job.id}.mp4"
    output_path = local_asset_path(object_key)
    try:
        source_ids = [int(asset_id) for asset_id in job.render.get("source_asset_ids", [])]
        by_id = {
            asset.id: asset
            for asset in Asset.objects.filter(id__in=source_ids, workspace=workspace, deleted_at__isnull=True).exclude(asset_type=Asset.OUTPUT)
        }
        assets = [by_id[asset_id] for asset_id in source_ids if asset_id in by_id]
        if not assets or len(assets) != len(source_ids):
            raise ValueError("Queued render needs source_asset_ids")
        if job.status == Job.PENDING:
            job.start("export")
    except ConcurrencyLimitReached:
        return {"job": job.public_payload(), "output_asset": None, "credits": credit_payload(workspace)}
    except Exception as exc:
        job.fail(str(exc))
        return {"job": job.public_payload(), "output_asset": None, "credits": credit_payload(workspace)}
    try:
        run_ffmpeg_render(job, assets, output_path)
        output = Asset.objects.create(
            workspace=workspace,
            uploaded_by=job.created_by,
            filename=f"job-{job.id}.mp4",
            content_type="video/mp4",
            asset_type=Asset.OUTPUT,
            object_key=object_key,
            tags=["output"],
        )
        job.output_asset = output
        job.render = {
            **job.render,
            "width": 1080,
            "height": 1920,
            "subtitles_burned": True,
            "source_asset_ids": source_ids,
        }
        job.save(update_fields=["output_asset", "render", "updated_at"])
        job.succeed()
    except Exception as exc:
        job.fail(str(exc))
    return {"job": job.public_payload(), "output_asset": output.public_payload() if output else None, "credits": credit_payload(workspace)}

@csrf_exempt
def job_render(request, job_id):
    if request.method != "POST":
        return error("POST required", status=405)
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    try:
        job = Job.objects.get(id=job_id, workspace=workspace)
        data = read_json(request)
        raw_asset_ids = [int(asset_id) for asset_id in data.get("asset_ids")]
        assets = ordered_render_assets(workspace, raw_asset_ids)
        if job.render.get("batch_id"):
            by_id = {asset.id: asset for asset in assets}
            assets = [by_id[asset_id] for asset_id in raw_asset_ids if asset_id in by_id]
    except Job.DoesNotExist:
        return error("Job not found", status=404)
    except (TypeError, ValueError) as exc:
        return error(str(exc))
    if job.status not in {Job.PENDING, Job.RUNNING}:
        return error("Only pending or running jobs can queue render")
    job.render = {**job.render, "source_asset_ids": [asset.id for asset in assets], "subtitles_burned": True}
    job.current_step = "clipping"
    job.save(update_fields=["render", "current_step", "updated_at"])
    return JsonResponse({"job": job.public_payload(), "credits": credit_payload(workspace)}, status=202)

@csrf_exempt
def batch_remix(request):
    if request.method != "POST":
        return error("POST required", status=405)
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    data = read_json(request)
    try:
        variants = int(data.get("variants", 0))
        if variants < 1 or variants > 20:
            raise ValueError
        estimated_credits = int(data.get("estimated_credits", 0))
        assets = ordered_render_assets(workspace, data.get("asset_ids"))
        draft = ScriptDraft.objects.get(id=int(data.get("script_draft_id")), workspace=workspace)
        if not draft.render_ready:
            raise ValueError
        script = draft.confirmed_script[:200]
    except ScriptDraft.DoesNotExist:
        return error("Confirmed script_draft_id required")
    except (TypeError, ValueError) as exc:
        return error(str(exc) or "Valid asset_ids, variants, confirmed script_draft_id and estimated_credits required")
    batch_id = uuid.uuid4().hex
    jobs_created = []
    try:
        with transaction.atomic():
            for index in range(variants):
                job = Job.submit(workspace, user, estimated_credits, title=f"Batch remix {index + 1}")
                ordered = rotated(assets, index)
                hook = f"变体{index + 1}：{script}"
                job.subtitles = [{"start": 0, "end": 2, "text": hook}]
                job.render = {
                    "batch_id": batch_id,
                    "script_draft_id": draft.id,
                    "variant_index": index + 1,
                    "hook": hook,
                    "source_asset_ids": [asset.id for asset in ordered],
                    "subtitles_burned": True,
                }
                job.save(update_fields=["subtitles", "render", "updated_at"])
                jobs_created.append(job)
    except InsufficientCredits:
        return error("Insufficient credits", status=402)
    return JsonResponse({"jobs": [job.public_payload() for job in jobs_created], "credits": credit_payload(workspace)}, status=201)

def asset_preview(request, asset_id):
    user = preview_user(request)
    if user is None:
        return error("Authentication required", status=401)
    membership = first_membership(user)
    if membership is None:
        return error("Workspace required", status=409)
    try:
        asset = Asset.objects.get(id=asset_id, workspace=membership.workspace, deleted_at__isnull=True)
    except Asset.DoesNotExist:
        return error("Asset not found", status=404)
    path = local_asset_path(asset.object_key)
    if not path.exists():
        return error("Preview file not found", status=404)
    return FileResponse(path.open("rb"), content_type=asset.content_type)


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

ASSET_TAGS = ["product", "person", "environment", "price", "process", "comparison", "certificate", "storefront", "detail"]


def asset_type_for(filename, content_type):
    asset = ASSET_TYPES.get(PurePath(filename).suffix.lower().lstrip("."))
    if not asset or asset[1] != content_type:
        raise ValueError("Supported files: MP4/MOV, JPG/PNG/WEBP, MP3/WAV")
    return asset[0]


def fake_vision_tags(filename):
    # ponytail: filename heuristic only; replace with a vision provider job when real uploads land in OSS.
    lower = filename.lower()
    tags = [tag for tag in ASSET_TAGS if tag in lower]
    if "people" in lower or "person" in lower:
        tags.append("person")
    if "store" in lower or "shop" in lower:
        tags.append("storefront")
    if "close" in lower:
        tags.append("detail")
    # ponytail: filename heuristic only; replace with real vision provider when provider jobs exist.
    return list(dict.fromkeys(tags or ["product"]))


def parse_provider_tags(text):
    return [tag.strip()[:40] for tag in text.replace("，", ",").split(",") if tag.strip()][:8]


def suggested_tags_for_upload(filename):
    provider = AIProvider.objects.filter(capability=AIProvider.VISION, enabled=True).order_by("id").first()
    if provider:
        try:
            tags = parse_provider_tags(ark_chat(provider, [{"role": "user", "content": f"为素材文件名生成短标签，逗号分隔：{filename}"}]))
            if tags:
                return tags
        except ProviderError:
            pass
    return fake_vision_tags(filename)


def clean_asset_tags(raw_tags):
    if not isinstance(raw_tags, list):
        raise ValueError("tags must be a list")
    tags = []
    for tag in raw_tags:
        tag = str(tag).strip()
        if tag not in ASSET_TAGS:
            raise ValueError("Unsupported asset tag")
        if tag not in tags:
            tags.append(tag)
    return tags


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
    suggested_tags = suggested_tags_for_upload(filename)
    asset = Asset.objects.create(
        workspace=workspace,
        uploaded_by=user,
        filename=PurePath(filename).name[:240] or "asset",
        content_type=content_type,
        asset_type=asset_type,
        object_key=Asset.new_object_key(workspace, filename),
        suggested_tags=suggested_tags,
        tags=suggested_tags,
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


@csrf_exempt
def asset_tags(request, asset_id):
    if request.method != "POST":
        return error("POST required", status=405)
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    try:
        asset = Asset.objects.get(id=asset_id, workspace=workspace, deleted_at__isnull=True)
        asset.tags = clean_asset_tags(read_json(request).get("tags"))
    except Asset.DoesNotExist:
        return error("Asset not found", status=404)
    except ValueError as exc:
        return error(str(exc))
    asset.save(update_fields=["tags"])
    return JsonResponse(asset.public_payload())


SCRIPT_DURATIONS = {15, 30, 60}

def clean_script_sample_ids(value):
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("sample_ids must be a list")
    sample_ids = []
    for item in value:
        sample_id = int(item)
        if sample_id not in sample_ids:
            sample_ids.append(sample_id)
    return sample_ids

def fake_script_candidates(customer, template, provider, duration_seconds, samples):
    # ponytail: deterministic candidates keep v1 testable; replace with LLM prompt orchestration when provider billing starts.
    hooks = " / ".join(sample.copy[:40] for sample in samples) or "首屏钩子"
    brief = (
        f"{customer.name}｜{customer.industry or template.industry}｜{customer.products or '产品'}｜"
        f"{customer.selling_points or '核心卖点'}｜{template.prompt or '抖音口播'}｜参考：{hooks}"
    )
    return [
        provider.fake_call(f"抖音{duration_seconds}秒爆款脚本 方案{i}: {brief}｜钩子-痛点-卖点-行动")
        for i in range(1, 4)
    ]

def split_script_candidates(text):
    chunks = [chunk.strip() for chunk in text.split("---") if chunk.strip()]
    if len(chunks) >= 3:
        return chunks[:3]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return (lines + [text.strip()])[:3]


def real_script_candidates(customer, template, provider, duration_seconds, samples):
    sample_text = "\n".join(f"- {sample.copy[:160]}" for sample in samples)
    prompt = (
        f"??????????????{customer.name}??3?{duration_seconds}?????????\n"
        f"???{customer.industry or template.industry}\n???{customer.products}\n???{customer.selling_points}\n"
        f"????{customer.forbidden_words}\n?????\n{sample_text}\n"
        "????? --- ?????????????????????"
    )
    return split_script_candidates(ark_chat(provider, [{"role": "user", "content": prompt}]))


def script_candidates(customer, template, provider, duration_seconds, samples):
    if provider.api_key_env:
        return real_script_candidates(customer, template, provider, duration_seconds, samples)
    return fake_script_candidates(customer, template, provider, duration_seconds, samples)


@csrf_exempt
def script_generate(request):
    if request.method != "POST":
        return error("POST required", status=405)
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    data = read_json(request)
    try:
        duration_seconds = int(data.get("duration_seconds"))
        if duration_seconds not in SCRIPT_DURATIONS:
            raise ValueError
        customer = CustomerProfile.objects.get(id=int(data.get("customer_id")), workspace=workspace)
        template = IndustryTemplate.objects.get(id=int(data.get("template_id")), enabled=True)
        provider = AIProvider.objects.get(id=int(data.get("provider_id")), enabled=True, capability=AIProvider.LLM)
        sample_ids = clean_script_sample_ids(data.get("sample_ids"))
        sample_rows = ViralSample.objects.filter(id__in=sample_ids, scope=ViralSample.SYSTEM) | ViralSample.objects.filter(id__in=sample_ids, workspace=workspace)
        samples_by_id = {sample.id: sample for sample in sample_rows}
        if len(samples_by_id) != len(sample_ids):
            raise ValueError
        samples = [samples_by_id[sample_id] for sample_id in sample_ids]
    except (CustomerProfile.DoesNotExist, IndustryTemplate.DoesNotExist, AIProvider.DoesNotExist, TypeError, ValueError):
        return error("Valid customer_id, template_id, provider_id, duration_seconds and sample_ids required")
    except ProviderError as exc:
        return error(str(exc), status=502)

    draft = ScriptDraft.objects.create(
        workspace=workspace,
        customer=customer,
        template=template,
        provider=provider,
        duration_seconds=duration_seconds,
        sample_ids=sample_ids,
        candidates=script_candidates(customer, template, provider, duration_seconds, samples),
    )
    return JsonResponse(draft.public_payload(), status=201)

@csrf_exempt
def script_confirm(request, script_id):
    if request.method != "POST":
        return error("POST required", status=405)
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    try:
        draft = ScriptDraft.objects.get(id=script_id, workspace=workspace)
    except ScriptDraft.DoesNotExist:
        return error("Script draft not found", status=404)
    script = str(read_json(request).get("script") or "").strip()
    if not script:
        return error("Script required")
    draft.confirmed_script = script
    draft.confirmed_at = timezone.now()
    draft.save(update_fields=["confirmed_script", "confirmed_at"])
    return JsonResponse(draft.public_payload())


def script_assets(request):
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    templates = IndustryTemplate.objects.filter(enabled=True).order_by("industry", "id")
    samples = ViralSample.objects.filter(scope=ViralSample.SYSTEM) | ViralSample.objects.filter(workspace=workspace)
    return JsonResponse(
        {
            "templates": [template.public_payload() for template in templates],
            "samples": [sample.public_payload() for sample in samples.order_by("-created_at", "id")],
        }
    )


@csrf_exempt
def viral_samples(request):
    if request.method != "POST":
        return error("POST required", status=405)
    user, auth_error = require_user(request)
    if auth_error:
        return auth_error
    workspace = first_membership(user).workspace
    data = read_json(request)
    copy = str(data.get("copy") or "").strip()
    source_url = str(data.get("source_url") or "").strip()
    if not copy:
        return error("Copy required")
    if source_url:
        try:
            URLValidator()(source_url)
        except ValidationError:
            return error("Valid source_url required")
    customer = None
    customer_id = data.get("customer_id")
    if customer_id:
        try:
            customer = CustomerProfile.objects.get(id=int(customer_id), workspace=workspace)
        except (CustomerProfile.DoesNotExist, TypeError, ValueError):
            return error("Valid customer_id required")
    tags = data.get("tags") if isinstance(data.get("tags"), list) else []
    sample = ViralSample.objects.create(
        scope=ViralSample.WORKSPACE,
        workspace=workspace,
        customer=customer,
        title=str(data.get("title") or "")[:160],
        source_url=source_url,
        copy=copy,
        structure_analysis=str(data.get("structure_analysis") or "hook-offer-cta").strip(),
        tags=[str(tag).strip() for tag in tags if str(tag).strip()],
        rewrite=str(data.get("rewrite") or "").strip(),
    )
    return JsonResponse(sample.public_payload(), status=201)
