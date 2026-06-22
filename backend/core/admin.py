from django.contrib import admin

from .models import (
    AIProvider,
    AuthToken,
    CustomerProfile,
    CreditAccount,
    CreditLedgerEntry,
    CreditRecharge,
    CreditTask,
    InvitationCode,
    Workspace,
    WorkspaceMembership,
)


@admin.register(InvitationCode)
class InvitationCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "active", "used_count", "max_uses", "expires_at", "created_at")
    search_fields = ("code",)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "workspace", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "workspace__name")


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    search_fields = ("user__username",)


@admin.register(AIProvider)
class AIProviderAdmin(admin.ModelAdmin):
    list_display = ("capability", "name", "model_name", "enabled", "price_coefficient", "created_at")
    list_filter = ("capability", "enabled")
    search_fields = ("name", "model_name")
    # ponytail: v1 keeps keys server-side in admin only; encrypt when real provider billing starts.
    readonly_fields = ("created_at",)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("workspace", "name", "industry", "updated_at")
    search_fields = ("workspace__name", "name", "industry", "products", "selling_points")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    list_display = ("workspace", "balance", "frozen", "updated_at")
    search_fields = ("workspace__name",)
    readonly_fields = ("balance", "frozen", "updated_at")


@admin.register(CreditRecharge)
class CreditRechargeAdmin(admin.ModelAdmin):
    list_display = ("workspace", "amount", "note", "created_at", "applied_at")
    search_fields = ("workspace__name", "note")
    readonly_fields = ("created_at", "applied_at")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.applied_at:
            return self.readonly_fields + ("workspace", "amount", "note")
        return self.readonly_fields


@admin.register(CreditLedgerEntry)
class CreditLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("workspace", "task", "kind", "amount", "balance_after", "frozen_after", "created_at")
    list_filter = ("kind",)
    search_fields = ("workspace__name", "note")
    readonly_fields = ("workspace", "task", "kind", "amount", "balance_after", "frozen_after", "note", "created_at")


@admin.register(CreditTask)
class CreditTaskAdmin(admin.ModelAdmin):
    list_display = ("workspace", "title", "estimated_credits", "status", "created_by", "created_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("workspace__name", "title", "created_by__username")
    readonly_fields = ("workspace", "created_by", "title", "estimated_credits", "status", "created_at", "completed_at")
