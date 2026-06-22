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
    CAPABILITY_CHOICES = [
        (LLM, "LLM"),
        (TTS, "TTS"),
        (ASR, "ASR"),
        (VISION, "Vision"),
        (VIDEO, "Video"),
    ]

    capability = models.CharField(max_length=20, choices=CAPABILITY_CHOICES)
    name = models.CharField(max_length=120)
    model_name = models.CharField(max_length=120)
    api_key = models.CharField(max_length=240, blank=True)
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
