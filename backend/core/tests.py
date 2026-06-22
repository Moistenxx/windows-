from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import (
    AuthToken,
    CustomerProfile,
    CreditAccount,
    CreditLedgerEntry,
    CreditRecharge,
    CreditTask,
    AIProvider,
    InsufficientCredits,
    InvitationCode,
    Workspace,
    WorkspaceMembership,
)


def make_user_workspace(email="owner@example.com"):
    user = User.objects.create_user(username=email, email=email, password="secret123")
    workspace = Workspace.objects.create(name="owner workspace")
    WorkspaceMembership.objects.create(user=user, workspace=workspace, role="owner")
    return user, workspace


class HealthEndpointTests(TestCase):
    def test_health_endpoint_reports_backend_status(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "api", "app": "ai-video-workbench"},
        )
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")


class AdminEntryTests(TestCase):
    def test_admin_entry_is_reachable(self):
        response = self.client.get(reverse("admin:index"))

        self.assertIn(response.status_code, {200, 302})

    def test_admin_registers_auth_workspace_and_credit_models(self):
        self.assertTrue(admin.site.is_registered(InvitationCode))
        self.assertTrue(admin.site.is_registered(Workspace))
        self.assertTrue(admin.site.is_registered(WorkspaceMembership))
        self.assertTrue(admin.site.is_registered(AuthToken))
        self.assertTrue(admin.site.is_registered(CreditAccount))
        self.assertTrue(admin.site.is_registered(CreditRecharge))
        self.assertTrue(admin.site.is_registered(CreditLedgerEntry))
        self.assertTrue(admin.site.is_registered(CreditTask))
        self.assertTrue(admin.site.is_registered(AIProvider))
        self.assertTrue(admin.site.is_registered(CustomerProfile))


class AuthApiTests(TestCase):
    def test_register_rejects_missing_invite_code(self):
        response = self.client.post(
            "/api/auth/register/",
            data={"email": "owner@example.com", "password": "secret123"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Valid invite code required")

    def test_register_creates_user_default_workspace_membership_and_token(self):
        InvitationCode.objects.create(code="ALPHA-1", max_uses=1)

        response = self.client.post(
            "/api/auth/register/",
            data={
                "email": "owner@example.com",
                "password": "secret123",
                "invite_code": "ALPHA-1",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["user"]["email"], "owner@example.com")
        self.assertEqual(payload["workspace"]["name"], "owner workspace")
        self.assertTrue(payload["token"])
        self.assertTrue(User.objects.filter(username="owner@example.com").exists())
        workspace = Workspace.objects.get(name="owner workspace")
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                user__username="owner@example.com", workspace=workspace, role="owner"
            ).exists()
        )
        invite = InvitationCode.objects.get(code="ALPHA-1")
        self.assertEqual(invite.used_count, 1)

    def test_login_returns_token_and_default_workspace(self):
        user, workspace = make_user_workspace()

        response = self.client.post(
            "/api/auth/login/",
            data={"email": user.email, "password": "secret123"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["token"])
        self.assertEqual(payload["workspace"]["id"], workspace.id)

    def test_me_returns_only_authenticated_users_workspaces(self):
        user, own_workspace = make_user_workspace()
        other_workspace = Workspace.objects.create(name="other workspace")
        token = AuthToken.issue_for(user)

        response = self.client.get(
            "/api/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["email"], user.email)
        self.assertEqual(payload["workspaces"], [{"id": own_workspace.id, "name": "owner workspace", "role": "owner"}])
        self.assertNotIn(other_workspace.id, [workspace["id"] for workspace in payload["workspaces"]])

    def test_me_rejects_missing_token(self):
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 401)


class CreditLedgerTests(TestCase):
    def test_admin_recharge_adds_balance_and_auditable_ledger_entry(self):
        _, workspace = make_user_workspace()

        CreditRecharge.objects.create(workspace=workspace, amount=500, note="manual test recharge")

        account = CreditAccount.objects.get(workspace=workspace)
        self.assertEqual(account.balance, 500)
        self.assertEqual(account.frozen, 0)
        self.assertTrue(
            CreditLedgerEntry.objects.filter(
                workspace=workspace,
                kind=CreditLedgerEntry.RECHARGE,
                amount=500,
                balance_after=500,
                frozen_after=0,
                note="manual test recharge",
            ).exists()
        )

    def test_freeze_settle_and_refund_update_available_and_frozen_balances(self):
        _, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=500)

        CreditLedgerEntry.freeze(workspace, 120, note="render estimate")
        account = CreditAccount.objects.get(workspace=workspace)
        self.assertEqual(account.balance, 380)
        self.assertEqual(account.frozen, 120)

        CreditLedgerEntry.settle(workspace, 70, note="render success")
        account.refresh_from_db()
        self.assertEqual(account.balance, 380)
        self.assertEqual(account.frozen, 50)

        CreditLedgerEntry.refund(workspace, 50, note="system failure")
        account.refresh_from_db()
        self.assertEqual(account.balance, 430)
        self.assertEqual(account.frozen, 0)

    def test_freeze_rejects_insufficient_credit(self):
        _, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=10)

        with self.assertRaises(InsufficientCredits):
            CreditLedgerEntry.freeze(workspace, 11)

    def test_submitting_paid_task_freezes_estimated_credits(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=500)

        task = CreditTask.submit(workspace, user, 120, title="script render")

        account = CreditAccount.objects.get(workspace=workspace)
        self.assertEqual(task.status, CreditTask.PENDING)
        self.assertEqual(account.balance, 380)
        self.assertEqual(account.frozen, 120)
        self.assertTrue(
            CreditLedgerEntry.objects.filter(
                workspace=workspace,
                task=task,
                kind=CreditLedgerEntry.FREEZE,
                amount=120,
            ).exists()
        )

    def test_paid_task_success_settles_and_failure_refunds_frozen_credits(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=500)
        success_task = CreditTask.submit(workspace, user, 120, title="success")
        failed_task = CreditTask.submit(workspace, user, 80, title="failure")

        success_task.mark_succeeded()
        failed_task.mark_failed()

        account = CreditAccount.objects.get(workspace=workspace)
        self.assertEqual(account.balance, 380)
        self.assertEqual(account.frozen, 0)
        self.assertTrue(
            CreditLedgerEntry.objects.filter(task=success_task, kind=CreditLedgerEntry.SETTLE, amount=120).exists()
        )
        self.assertTrue(
            CreditLedgerEntry.objects.filter(task=failed_task, kind=CreditLedgerEntry.REFUND, amount=80).exists()
        )

    def test_paid_task_submission_rejects_insufficient_credit_without_task_record(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=10)

        with self.assertRaises(InsufficientCredits):
            CreditTask.submit(workspace, user, 11)

        self.assertFalse(CreditTask.objects.filter(workspace=workspace).exists())

    def test_authenticated_user_can_read_workspace_credit_balance(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=500)
        CreditLedgerEntry.freeze(workspace, 120)
        token = AuthToken.issue_for(user)

        response = self.client.get("/api/credits/", HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"workspace_id": workspace.id, "balance": 380, "frozen": 120})

    def test_credit_balance_requires_authentication(self):
        response = self.client.get("/api/credits/")

        self.assertEqual(response.status_code, 401)

    def test_authenticated_user_can_submit_paid_task_and_freeze_credits(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=500)
        token = AuthToken.issue_for(user)

        response = self.client.post(
            "/api/credit-tasks/",
            data={"title": "test render", "estimated_credits": 120},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["task"]["status"], CreditTask.PENDING)
        self.assertEqual(payload["task"]["estimated_credits"], 120)
        self.assertEqual(payload["credits"], {"workspace_id": workspace.id, "balance": 380, "frozen": 120})

    def test_paid_task_api_blocks_insufficient_credit(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=10)
        token = AuthToken.issue_for(user)

        response = self.client.post(
            "/api/credit-tasks/",
            data={"estimated_credits": 11},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()["error"], "Insufficient credits")
        self.assertFalse(CreditTask.objects.filter(workspace=workspace).exists())


class AIProviderTests(TestCase):
    def test_enabled_providers_api_never_returns_api_keys(self):
        user, _ = make_user_workspace()
        token = AuthToken.issue_for(user)
        AIProvider.objects.create(
            capability=AIProvider.LLM,
            name="Volcengine Script",
            model_name="doubao-test",
            api_key="secret-key",
            price_coefficient=2,
            enabled=True,
        )
        AIProvider.objects.create(capability=AIProvider.TTS, name="disabled", model_name="tts-off", api_key="secret", enabled=False)

        response = self.client.get("/api/ai/providers/", HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "providers": [
                    {
                        "id": AIProvider.objects.get(name="Volcengine Script").id,
                        "capability": "llm",
                        "name": "Volcengine Script",
                        "model_name": "doubao-test",
                        "price_coefficient": "2.00",
                    }
                ]
            },
        )
        self.assertNotIn("secret-key", str(response.json()))

    def test_cost_estimate_uses_selected_model_price_coefficient(self):
        user, _ = make_user_workspace()
        token = AuthToken.issue_for(user)
        provider = AIProvider.objects.create(
            capability=AIProvider.LLM,
            name="Volcengine Script",
            model_name="doubao-test",
            api_key="secret-key",
            price_coefficient=2.5,
            enabled=True,
        )

        response = self.client.post(
            "/api/ai/estimate/",
            data={"provider_id": provider.id, "base_credits": 40},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"provider_id": provider.id, "estimated_credits": 100})

    def test_fake_provider_call_returns_deterministic_output(self):
        user, _ = make_user_workspace()
        token = AuthToken.issue_for(user)
        provider = AIProvider.objects.create(capability=AIProvider.LLM, name="Fake LLM", model_name="fake-llm", enabled=True)

        response = self.client.post(
            "/api/ai/fake-call/",
            data={"provider_id": provider.id, "prompt": "gold jewelry"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["output"], "fake-llm generated: gold jewelry")


class CustomerProfileTests(TestCase):
    def test_authenticated_user_can_create_list_and_update_workspace_profile(self):
        user, workspace = make_user_workspace()
        token = AuthToken.issue_for(user)

        response = self.client.post(
            "/api/customers/",
            data={
                "name": "Acme Jewelry",
                "industry": "jewelry",
                "products": "gold bracelets",
                "target_audience": "brides",
                "selling_points": "handmade, certified",
                "forbidden_words": "guaranteed returns",
                "contact_hooks": "DM for price",
                "style_preference": "premium",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        profile_id = response.json()["id"]
        self.assertEqual(response.json()["workspace_id"], workspace.id)

        response = self.client.get("/api/customers/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(len(response.json()["customers"]), 1)
        self.assertEqual(response.json()["customers"][0]["name"], "Acme Jewelry")
        self.assertEqual(response.json()["customers"][0]["selling_points"], "handmade, certified")

        response = self.client.post(
            f"/api/customers/{profile_id}/",
            data={"name": "Acme Jewelry Updated", "industry": "luxury jewelry"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Acme Jewelry Updated")
        self.assertEqual(response.json()["industry"], "luxury jewelry")

        response = self.client.post(
            f"/api/customers/{profile_id}/",
            data={"name": ""},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_customer_profiles_are_workspace_scoped(self):
        user, workspace = make_user_workspace()
        other_user, other_workspace = make_user_workspace("other@example.com")
        CustomerProfile.objects.create(workspace=other_workspace, name="Other Brand")
        token = AuthToken.issue_for(user)

        response = self.client.get("/api/customers/", HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"customers": []})
        self.assertFalse(CustomerProfile.objects.filter(workspace=workspace).exists())

    def test_customer_profile_requires_authentication_and_name(self):
        response = self.client.get("/api/customers/")
        self.assertEqual(response.status_code, 401)

        user, _ = make_user_workspace()
        token = AuthToken.issue_for(user)
        response = self.client.post("/api/customers/", data={"industry": "food"}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 400)
