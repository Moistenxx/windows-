import hashlib
import secrets

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


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
