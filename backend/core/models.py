import hashlib
import secrets
import uuid
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone


class InsufficientCredits(Exception):
    pass


class ConcurrencyLimitReached(Exception):
    pass


def require_positive_credits(amount):
    if amount <= 0:
        raise ValueError("Credit amount must be positive")


class InvitationCode(models.Model):
    code = models.CharField(max_length=64, unique=True)
    max_uses = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code

    def can_use(self):
        if not self.active:
            return False
        if self.used_count >= self.max_uses:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True

    def mark_used(self):
        self.used_count += 1
        self.save(update_fields=["used_count"])


class Workspace(models.Model):
    name = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class WorkspaceMembership(models.Model):
    OWNER = "owner"
    MEMBER = "member"
    ROLE_CHOICES = [(OWNER, "Owner"), (MEMBER, "Member")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="workspace_memberships")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "workspace"], name="unique_workspace_member"),
        ]

    def __str__(self):
        return f"{self.user.username} · {self.workspace.name} · {self.role}"


class AuthToken(models.Model):
    digest = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_tokens")
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def digest_token(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def issue_for(cls, user):
        token = secrets.token_urlsafe(32)
        cls.objects.create(user=user, digest=cls.digest_token(token))
        return token

    @classmethod
    def user_for(cls, token):
        if not token:
            return None
        try:
            return cls.objects.select_related("user").get(digest=cls.digest_token(token)).user
        except cls.DoesNotExist:
            return None

    def __str__(self):
        return f"token for {self.user.username}"


class AIProvider(models.Model):
    LLM = "llm"
    TTS = "tts"
    ASR = "asr"
    VISION = "vision"
    VIDEO = "video"
    IMAGE = "image"
    DIGITAL_HUMAN = "digital_human"
    AI_VIDEO = "ai_video"
    VOICE_CLONE = "voice_clone"
    COMFYUI = "comfyui"
    CAPABILITY_CHOICES = [
        (LLM, "LLM"),
        (TTS, "TTS"),
        (ASR, "ASR"),
        (VISION, "Vision"),
        (VIDEO, "Video"),
        (IMAGE, "AI Image"),
        (DIGITAL_HUMAN, "Digital Human"),
        (AI_VIDEO, "AI Video"),
        (VOICE_CLONE, "Voice Clone"),
        (COMFYUI, "ComfyUI"),
    ]

    capability = models.CharField(max_length=20, choices=CAPABILITY_CHOICES)
    name = models.CharField(max_length=120)
    model_name = models.CharField(max_length=120)
    api_key_env = models.CharField("API key env var", max_length=120, blank=True)
    enabled = models.BooleanField(default=False)
    price_coefficient = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def estimate_credits(self, base_credits):
        require_positive_credits(base_credits)
        return int((Decimal(base_credits) * self.price_coefficient).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def fake_call(self, prompt):
        # ponytail: deterministic fake only; replace with provider SDK call when billing starts.
        return f"{self.model_name} generated: {prompt}"

    def public_payload(self):
        return {
            "id": self.id,
            "capability": self.capability,
            "name": self.name,
            "model_name": self.model_name,
            "price_coefficient": f"{self.price_coefficient:.2f}",
        }

    def __str__(self):
        return f"{self.capability} {self.name} ({self.model_name})"


class CustomerProfile(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="customer_profiles")
    name = models.CharField(max_length=160)
    industry = models.CharField(max_length=120, blank=True)
    products = models.TextField(blank=True)
    target_audience = models.TextField(blank=True)
    selling_points = models.TextField(blank=True)
    forbidden_words = models.TextField(blank=True)
    contact_hooks = models.TextField(blank=True)
    style_preference = models.TextField(blank=True)
    logo_or_common_assets = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def public_payload(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "industry": self.industry,
            "products": self.products,
            "target_audience": self.target_audience,
            "selling_points": self.selling_points,
            "forbidden_words": self.forbidden_words,
            "contact_hooks": self.contact_hooks,
            "style_preference": self.style_preference,
            "logo_or_common_assets": self.logo_or_common_assets,
        }

    def __str__(self):
        return f"{self.workspace.name} {self.name}"


class IndustryTemplate(models.Model):
    name = models.CharField(max_length=120)
    industry = models.CharField(max_length=120)
    prompt = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def public_payload(self):
        return {
            "id": self.id,
            "name": self.name,
            "industry": self.industry,
            "prompt": self.prompt,
        }

    def __str__(self):
        return f"{self.industry} {self.name}"


class ViralSample(models.Model):
    SYSTEM = "system"
    WORKSPACE = "workspace"
    SCOPE_CHOICES = [(SYSTEM, "System"), (WORKSPACE, "Workspace")]

    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=WORKSPACE)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, null=True, blank=True, related_name="viral_samples")
    customer = models.ForeignKey(CustomerProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="viral_samples")
    title = models.CharField(max_length=160, blank=True)
    source_url = models.URLField(blank=True)
    copy = models.TextField()
    structure_analysis = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    rewrite = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def public_payload(self):
        return {
            "id": self.id,
            "scope": self.scope,
            "workspace_id": self.workspace_id,
            "customer_id": self.customer_id,
            "title": self.title,
            "source_url": self.source_url,
            "copy": self.copy,
            "structure_analysis": self.structure_analysis,
            "tags": self.tags,
            "rewrite": self.rewrite,
        }

    def __str__(self):
        return self.title or self.copy[:40]


class ScriptDraft(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="script_drafts")
    customer = models.ForeignKey(CustomerProfile, on_delete=models.PROTECT, related_name="script_drafts")
    template = models.ForeignKey(IndustryTemplate, on_delete=models.PROTECT, related_name="script_drafts")
    provider = models.ForeignKey(AIProvider, on_delete=models.PROTECT, related_name="script_drafts")
    duration_seconds = models.PositiveIntegerField()
    sample_ids = models.JSONField(default=list, blank=True)
    candidates = models.JSONField(default=list, blank=True)
    confirmed_script = models.TextField(blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def render_ready(self):
        return bool(self.confirmed_at and self.confirmed_script.strip())

    def public_payload(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "customer_id": self.customer_id,
            "template_id": self.template_id,
            "provider_id": self.provider_id,
            "duration_seconds": self.duration_seconds,
            "sample_ids": self.sample_ids,
            "candidates": self.candidates,
            "confirmed_script": self.confirmed_script,
            "render_ready": self.render_ready,
        }

    def __str__(self):
        return f"{self.workspace.name} script draft #{self.id}"


class Asset(models.Model):
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    OUTPUT = "output"
    TYPE_CHOICES = [(VIDEO, "Video"), (IMAGE, "Image"), (AUDIO, "Audio"), (OUTPUT, "Output")]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="assets")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    filename = models.CharField(max_length=240)
    content_type = models.CharField(max_length=120)
    asset_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    object_key = models.CharField(max_length=320, unique=True)
    retention_days = models.PositiveIntegerField(default=30)
    suggested_tags = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    expires_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def new_object_key(cls, workspace, filename):
        safe_name = filename.replace("\\", "/").split("/")[-1][:120] or "asset"
        return f"workspaces/{workspace.id}/assets/{uuid.uuid4().hex}/{safe_name}"

    def save(self, *args, **kwargs):
        self.retention_days = 90 if self.asset_type == self.OUTPUT else 30
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=self.retention_days)
        super().save(*args, **kwargs)

    def public_payload(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "asset_type": self.asset_type,
            "object_key": self.object_key,
            "retention_days": self.retention_days,
            "suggested_tags": self.suggested_tags,
            "tags": self.tags,
            "expires_at": self.expires_at.isoformat(),
            "deleted": self.deleted_at is not None,
            "preview_url": f"/api/assets/{self.id}/preview/" if self.asset_type in {self.VIDEO, self.OUTPUT} else "",
        }

    def __str__(self):
        return f"{self.workspace.name} {self.filename}"


class CreditAccount(models.Model):
    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE, related_name="credit_account")
    balance = models.PositiveIntegerField(default=0)
    frozen = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def for_workspace(cls, workspace):
        account, _ = cls.objects.get_or_create(workspace=workspace)
        return account

    def __str__(self):
        return f"{self.workspace.name}: {self.balance} available, {self.frozen} frozen"


class CreditTask(models.Model):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (SUCCEEDED, "Succeeded"),
        (FAILED, "Failed"),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="credit_tasks")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="credit_tasks")
    title = models.CharField(max_length=160, default="Paid task")
    estimated_credits = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def submit(cls, workspace, created_by, estimated_credits, title="Paid task"):
        require_positive_credits(estimated_credits)
        with transaction.atomic():
            task = cls.objects.create(
                workspace=workspace,
                created_by=created_by,
                estimated_credits=estimated_credits,
                title=title or "Paid task",
            )
            CreditLedgerEntry.freeze(workspace, estimated_credits, note=task.title, task=task)
            return task

    def mark_succeeded(self):
        return self._finish(self.SUCCEEDED)

    def mark_failed(self):
        return self._finish(self.FAILED)

    def _finish(self, status):
        with transaction.atomic():
            task = type(self).objects.select_for_update().get(pk=self.pk)
            if task.status != self.PENDING:
                raise ValueError("Credit task is already finished")
            if status == self.SUCCEEDED:
                CreditLedgerEntry.settle(task.workspace, task.estimated_credits, note=task.title, task=task)
            elif status == self.FAILED:
                CreditLedgerEntry.refund(task.workspace, task.estimated_credits, note=task.title, task=task)
            else:
                raise ValueError("Unsupported credit task status")
            task.status = status
            task.completed_at = timezone.now()
            task.save(update_fields=["status", "completed_at"])
            self.status = task.status
            self.completed_at = task.completed_at
            return task

    def __str__(self):
        return f"{self.workspace.name} {self.title} {self.status}"


class Job(models.Model):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (RUNNING, "Running"),
        (SUCCEEDED, "Succeeded"),
        (FAILED, "Failed"),
    ]
    VOICEOVER_NONE = "none"
    VOICEOVER_TTS = "tts"
    VOICEOVER_ASR = "asr"
    VOICEOVER_CHOICES = [
        (VOICEOVER_NONE, "No voiceover"),
        (VOICEOVER_TTS, "TTS voiceover"),
        (VOICEOVER_ASR, "ASR subtitles"),
    ]
    DEFAULT_STEPS = ["script", "subtitle", "voiceover", "clipping", "export"]
    GLOBAL_RUNNING_LIMIT = 2
    WORKSPACE_RUNNING_LIMIT = 1

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="jobs")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs")
    credit_task = models.ForeignKey(CreditTask, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs")
    provider = models.ForeignKey(AIProvider, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs")
    capability = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=160, default="Render job")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    steps = models.JSONField(default=list, blank=True)
    current_step = models.CharField(max_length=40, blank=True)
    estimated_wait_seconds = models.PositiveIntegerField(default=0)
    error_message = models.CharField(max_length=240, blank=True)
    voiceover_mode = models.CharField(max_length=20, choices=VOICEOVER_CHOICES, default=VOICEOVER_NONE)
    voiceover_provider = models.ForeignKey(AIProvider, on_delete=models.SET_NULL, null=True, blank=True, related_name="voiceover_jobs")
    source_audio_asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name="asr_jobs")
    output_asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name="output_jobs")
    audio_placeholder = models.CharField(max_length=320, blank=True)
    subtitles = models.JSONField(default=list, blank=True)
    render = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def submit(cls, workspace, created_by, estimated_credits, title="Render job"):
        with transaction.atomic():
            credit_task = CreditTask.submit(workspace, created_by, estimated_credits, title=title)
            running = cls.objects.filter(workspace=workspace, status=cls.RUNNING).count()
            pending = cls.objects.filter(workspace=workspace, status=cls.PENDING).count()
            return cls.objects.create(
                workspace=workspace,
                created_by=created_by,
                credit_task=credit_task,
                title=(title or "Render job")[:160],
                steps=cls.DEFAULT_STEPS,
                current_step=cls.DEFAULT_STEPS[0],
                estimated_wait_seconds=(running + pending) * 60,
            )

    def start(self, current_step=""):
        if self.status != self.PENDING:
            raise ValueError("Only pending jobs can start")
        # ponytail: naive counts are enough for v1; use DB locks or a worker queue when real concurrency matters.
        if (
            type(self).objects.filter(status=self.RUNNING).count() >= self.GLOBAL_RUNNING_LIMIT
            or type(self).objects.filter(workspace=self.workspace, status=self.RUNNING).count() >= self.WORKSPACE_RUNNING_LIMIT
        ):
            self.estimated_wait_seconds = max(self.estimated_wait_seconds, 60)
            self.save(update_fields=["estimated_wait_seconds", "updated_at"])
            raise ConcurrencyLimitReached("Concurrency limit reached")
        self.status = self.RUNNING
        self.current_step = current_step if current_step in self.steps else self.steps[0]
        self.estimated_wait_seconds = 0
        self.save(update_fields=["status", "current_step", "estimated_wait_seconds", "updated_at"])
        return self

    def succeed(self):
        if self.status != self.RUNNING:
            raise ValueError("Only running jobs can succeed")
        if self.credit_task:
            self.credit_task.mark_succeeded()
        self.status = self.SUCCEEDED
        self.current_step = self.steps[-1]
        self.save(update_fields=["status", "current_step", "updated_at"])
        return self

    def fail(self, message=""):
        if self.status not in {self.PENDING, self.RUNNING}:
            raise ValueError("Only active jobs can fail")
        if self.credit_task:
            self.credit_task.mark_failed()
        self.status = self.FAILED
        self.error_message = str(message or "")[:240]
        self.save(update_fields=["status", "error_message", "updated_at"])
        return self

    def public_payload(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "title": self.title,
            "status": self.status,
            "steps": self.steps,
            "current_step": self.current_step,
            "estimated_wait_seconds": self.estimated_wait_seconds,
            "error_message": self.error_message,
            "credit_task_id": self.credit_task_id,
            "provider_id": self.provider_id,
            "capability": self.capability,
            "voiceover_mode": self.voiceover_mode,
            "voiceover_provider_id": self.voiceover_provider_id,
            "source_audio_asset_id": self.source_audio_asset_id,
            "audio_placeholder": self.audio_placeholder,
            "subtitles": self.subtitles,
            "output_asset_id": self.output_asset_id,
            "render": self.render,
            "created_at": self.created_at.isoformat(),
        }

    def __str__(self):
        return f"{self.workspace.name} {self.title} {self.status}"


class CreditLedgerEntry(models.Model):
    RECHARGE = "recharge"
    FREEZE = "freeze"
    SETTLE = "settle"
    REFUND = "refund"
    KIND_CHOICES = [
        (RECHARGE, "Recharge"),
        (FREEZE, "Freeze"),
        (SETTLE, "Settle"),
        (REFUND, "Refund"),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="credit_ledger_entries")
    task = models.ForeignKey(CreditTask, on_delete=models.SET_NULL, null=True, blank=True, related_name="ledger_entries")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    amount = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    balance_after = models.PositiveIntegerField()
    frozen_after = models.PositiveIntegerField()
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def _locked_account(cls, workspace):
        CreditAccount.objects.get_or_create(workspace=workspace)
        return CreditAccount.objects.select_for_update().get(workspace=workspace)

    @classmethod
    def recharge(cls, workspace, amount, note="", task=None):
        require_positive_credits(amount)
        with transaction.atomic():
            account = cls._locked_account(workspace)
            account.balance += amount
            account.save(update_fields=["balance", "updated_at"])
            return cls.objects.create(
                workspace=workspace,
                task=task,
                kind=cls.RECHARGE,
                amount=amount,
                balance_after=account.balance,
                frozen_after=account.frozen,
                note=note,
            )

    @classmethod
    def freeze(cls, workspace, amount, note="", task=None):
        require_positive_credits(amount)
        with transaction.atomic():
            account = cls._locked_account(workspace)
            if account.balance < amount:
                raise InsufficientCredits("Insufficient credits")
            account.balance -= amount
            account.frozen += amount
            account.save(update_fields=["balance", "frozen", "updated_at"])
            return cls.objects.create(
                workspace=workspace,
                task=task,
                kind=cls.FREEZE,
                amount=amount,
                balance_after=account.balance,
                frozen_after=account.frozen,
                note=note,
            )

    @classmethod
    def settle(cls, workspace, amount, note="", task=None):
        require_positive_credits(amount)
        with transaction.atomic():
            account = cls._locked_account(workspace)
            if account.frozen < amount:
                raise InsufficientCredits("Insufficient frozen credits")
            account.frozen -= amount
            account.save(update_fields=["frozen", "updated_at"])
            return cls.objects.create(
                workspace=workspace,
                task=task,
                kind=cls.SETTLE,
                amount=amount,
                balance_after=account.balance,
                frozen_after=account.frozen,
                note=note,
            )

    @classmethod
    def refund(cls, workspace, amount, note="", task=None):
        require_positive_credits(amount)
        with transaction.atomic():
            account = cls._locked_account(workspace)
            if account.frozen < amount:
                raise InsufficientCredits("Insufficient frozen credits")
            account.frozen -= amount
            account.balance += amount
            account.save(update_fields=["balance", "frozen", "updated_at"])
            return cls.objects.create(
                workspace=workspace,
                task=task,
                kind=cls.REFUND,
                amount=amount,
                balance_after=account.balance,
                frozen_after=account.frozen,
                note=note,
            )

    def __str__(self):
        return f"{self.workspace.name} {self.kind} {self.amount}"


class CreditRecharge(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="credit_recharges")
    amount = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        require_positive_credits(self.amount)
        apply_after_save = self.applied_at is None
        with transaction.atomic():
            super().save(*args, **kwargs)
            if apply_after_save:
                CreditLedgerEntry.recharge(self.workspace, self.amount, self.note)
                self.applied_at = timezone.now()
                type(self).objects.filter(pk=self.pk, applied_at__isnull=True).update(applied_at=self.applied_at)

    def __str__(self):
        return f"{self.workspace.name} recharge {self.amount}"
