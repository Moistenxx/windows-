from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Asset,
    AuthToken,
    CustomerProfile,
    IndustryTemplate,
    ScriptDraft,
    ViralSample,
    CreditAccount,
    CreditLedgerEntry,
    CreditRecharge,
    CreditTask,
    AIProvider,
    InsufficientCredits,
    InvitationCode,
    Job,
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
        self.assertTrue(admin.site.is_registered(Asset))
        self.assertTrue(admin.site.is_registered(IndustryTemplate))
        self.assertTrue(admin.site.is_registered(ViralSample))
        self.assertTrue(admin.site.is_registered(ScriptDraft))
        self.assertTrue(admin.site.is_registered(Job))


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


class AssetLibraryTests(TestCase):
    def test_user_can_create_list_and_delete_asset_upload_intent(self):
        user, workspace = make_user_workspace()
        token = AuthToken.issue_for(user)

        response = self.client.post(
            "/api/assets/",
            data={"filename": "clip.mp4", "content_type": "video/mp4"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["asset"]["workspace_id"], workspace.id)
        self.assertEqual(payload["asset"]["asset_type"], "video")
        self.assertEqual(payload["asset"]["retention_days"], 30)
        self.assertFalse(payload["asset"]["deleted"])
        self.assertEqual(payload["upload"]["method"], "PUT")
        self.assertEqual(payload["upload"]["headers"], {"Content-Type": "video/mp4"})
        self.assertIn("local://", payload["upload"]["url"])

        response = self.client.get("/api/assets/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(len(response.json()["assets"]), 1)

        asset_id = payload["asset"]["id"]
        response = self.client.post(f"/api/assets/{asset_id}/delete/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])

        response = self.client.get("/api/assets/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.json(), {"assets": []})

    def test_assets_are_workspace_scoped_and_validate_supported_media(self):
        user, _ = make_user_workspace()
        other_user, other_workspace = make_user_workspace("asset-other@example.com")
        Asset.objects.create(workspace=other_workspace, uploaded_by=other_user, filename="other.png", content_type="image/png", asset_type=Asset.IMAGE, object_key="x")
        token = AuthToken.issue_for(user)

        response = self.client.get("/api/assets/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.json(), {"assets": []})

        response = self.client.post(
            "/api/assets/",
            data={"filename": "bad.exe", "content_type": "application/octet-stream"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_output_asset_retention_policy_is_90_days(self):
        user, workspace = make_user_workspace()
        asset = Asset.objects.create(workspace=workspace, uploaded_by=user, filename="out.mp4", content_type="video/mp4", asset_type=Asset.OUTPUT, object_key="out")

        self.assertEqual(asset.retention_days, 90)


class AssetTaggingTests(TestCase):
    def test_asset_upload_gets_fake_vision_suggestions_and_user_can_correct_tags(self):
        user, _ = make_user_workspace()
        token = AuthToken.issue_for(user)

        response = self.client.post(
            "/api/assets/",
            data={"filename": "storefront-product.jpg", "content_type": "image/jpeg"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        asset = response.json()["asset"]
        self.assertEqual(asset["suggested_tags"], ["product", "storefront"])
        self.assertEqual(asset["tags"], ["product", "storefront"])

        response = self.client.post(
            f"/api/assets/{asset['id']}/tags/",
            data={"tags": ["price", "detail"]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["tags"], ["price", "detail"])

        response = self.client.get("/api/assets/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.json()["assets"][0]["tags"], ["price", "detail"])

    def test_asset_tags_reject_unsupported_values(self):
        user, workspace = make_user_workspace()
        asset = Asset.objects.create(workspace=workspace, uploaded_by=user, filename="clip.mp4", content_type="video/mp4", asset_type=Asset.VIDEO, object_key="clip")
        token = AuthToken.issue_for(user)

        response = self.client.post(
            f"/api/assets/{asset.id}/tags/",
            data={"tags": ["not-a-tag"]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400)


class TemplateAndViralSampleTests(TestCase):
    def test_user_can_list_enabled_templates_and_system_samples(self):
        user, _ = make_user_workspace()
        token = AuthToken.issue_for(user)
        template = IndustryTemplate.objects.create(name="Jewelry", industry="jewelry", prompt="sell gold", enabled=True)
        IndustryTemplate.objects.create(name="Disabled", industry="x", enabled=False)
        ViralSample.objects.create(scope=ViralSample.SYSTEM, title="System Hook", copy="3 seconds hook", structure_analysis="hook-offer-cta", tags=["hook"])

        response = self.client.get("/api/script-assets/", HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["templates"], [template.public_payload()])
        self.assertEqual(payload["samples"][0]["title"], "System Hook")
        self.assertEqual(payload["samples"][0]["copy"], "3 seconds hook")

    def test_user_can_add_customer_private_sample_from_douyin_link_or_pasted_copy(self):
        user, workspace = make_user_workspace()
        customer = CustomerProfile.objects.create(workspace=workspace, name="Acme")
        token = AuthToken.issue_for(user)

        response = self.client.post(
            "/api/viral-samples/",
            data={
                "customer_id": customer.id,
                "source_url": "https://www.douyin.com/video/123",
                "copy": "viral copy",
                "tags": ["hook", "price"],
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["scope"], "workspace")
        self.assertEqual(payload["source_url"], "https://www.douyin.com/video/123")
        self.assertEqual(payload["copy"], "viral copy")
        self.assertEqual(payload["tags"], ["hook", "price"])
        self.assertNotIn("video_file", payload)

        response = self.client.post(
            "/api/viral-samples/",
            data={"customer_id": customer.id, "copy": "manual paste only"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.post(
            "/api/viral-samples/",
            data={"customer_id": customer.id, "source_url": "not-a-url", "copy": "bad"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_private_samples_are_workspace_scoped(self):
        user, workspace = make_user_workspace()
        other_user, other_workspace = make_user_workspace("sample-other@example.com")
        ViralSample.objects.create(scope=ViralSample.WORKSPACE, workspace=other_workspace, title="Other", copy="hidden")
        token = AuthToken.issue_for(user)

        response = self.client.get("/api/script-assets/", HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["samples"], [])


class ScriptGenerationTests(TestCase):
    def test_fake_llm_generates_candidates_without_freezing_credits_and_user_confirms_one(self):
        user, workspace = make_user_workspace()
        customer = CustomerProfile.objects.create(workspace=workspace, name="Acme", industry="jewelry", products="gold", selling_points="certified")
        template = IndustryTemplate.objects.create(name="Jewelry", industry="jewelry", prompt="premium tone", enabled=True)
        provider = AIProvider.objects.create(capability=AIProvider.LLM, name="Fake LLM", model_name="fake-llm", enabled=True)
        sample = ViralSample.objects.create(scope=ViralSample.WORKSPACE, workspace=workspace, customer=customer, copy="3-second hook")
        token = AuthToken.issue_for(user)

        response = self.client.post(
            "/api/scripts/generate/",
            data={
                "customer_id": customer.id,
                "template_id": template.id,
                "provider_id": provider.id,
                "duration_seconds": 30,
                "sample_ids": [sample.id],
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(len(payload["candidates"]), 3)
        self.assertFalse(payload["render_ready"])
        self.assertIn("Acme", payload["candidates"][0])
        self.assertEqual(CreditTask.objects.filter(workspace=workspace).count(), 0)

        response = self.client.post(
            f"/api/scripts/{payload['id']}/confirm/",
            data={"script": "edited final script"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["render_ready"])
        self.assertEqual(response.json()["confirmed_script"], "edited final script")

    def test_script_generation_validates_workspace_owned_inputs_and_duration(self):
        user, workspace = make_user_workspace()
        customer = CustomerProfile.objects.create(workspace=workspace, name="Acme")
        template = IndustryTemplate.objects.create(name="Jewelry", industry="jewelry", enabled=True)
        provider = AIProvider.objects.create(capability=AIProvider.LLM, name="Fake LLM", model_name="fake-llm", enabled=True)
        _, other_workspace = make_user_workspace("script-other@example.com")
        other_sample = ViralSample.objects.create(scope=ViralSample.WORKSPACE, workspace=other_workspace, copy="hidden")
        token = AuthToken.issue_for(user)

        response = self.client.post(
            "/api/scripts/generate/",
            data={"duration_seconds": 45},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/api/scripts/generate/",
            data={
                "customer_id": customer.id,
                "template_id": template.id,
                "provider_id": provider.id,
                "duration_seconds": 30,
                "sample_ids": [other_sample.id],
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400)


class JobLifecycleTests(TestCase):
    def test_user_creates_lists_and_moves_paid_job_through_lifecycle(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=500)
        token = AuthToken.issue_for(user)

        response = self.client.post(
            "/api/jobs/",
            data={"title": "render 9:16", "estimated_credits": 120},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        job = response.json()["job"]
        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["steps"], ["script", "subtitle", "voiceover", "clipping", "export"])
        self.assertEqual(response.json()["credits"], {"workspace_id": workspace.id, "balance": 380, "frozen": 120})

        response = self.client.get("/api/jobs/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.json()["jobs"][0]["id"], job["id"])

        response = self.client.post(
            f"/api/jobs/{job['id']}/transition/",
            data={"status": "running", "current_step": "subtitle"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["status"], "running")
        self.assertEqual(response.json()["job"]["current_step"], "subtitle")

        response = self.client.post(
            f"/api/jobs/{job['id']}/transition/",
            data={"status": "succeeded"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["status"], "succeeded")
        self.assertEqual(response.json()["credits"], {"workspace_id": workspace.id, "balance": 380, "frozen": 0})

    def test_concurrency_keeps_extra_jobs_pending_and_failed_jobs_refund(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=500)
        token = AuthToken.issue_for(user)
        first = self.client.post("/api/jobs/", data={"title": "first", "estimated_credits": 100}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}").json()["job"]
        second = self.client.post("/api/jobs/", data={"title": "second", "estimated_credits": 100}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}").json()["job"]

        self.client.post(f"/api/jobs/{first['id']}/transition/", data={"status": "running"}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.post(f"/api/jobs/{second['id']}/transition/", data={"status": "running"}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["job"]["status"], "pending")
        self.assertGreater(response.json()["job"]["estimated_wait_seconds"], 0)

        response = self.client.post(f"/api/jobs/{first['id']}/transition/", data={"status": "failed"}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["status"], "failed")
        self.assertEqual(response.json()["credits"], {"workspace_id": workspace.id, "balance": 400, "frozen": 100})


class VoiceoverSubtitleTests(TestCase):
    def test_job_stores_no_voiceover_tts_subtitles_and_user_edits_subtitles(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=500)
        provider = AIProvider.objects.create(capability=AIProvider.TTS, name="Fake TTS", model_name="fake-tts", enabled=True)
        token = AuthToken.issue_for(user)
        job = self.client.post("/api/jobs/", data={"title": "voice job", "estimated_credits": 100}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}").json()["job"]

        response = self.client.post(
            f"/api/jobs/{job['id']}/voiceover/",
            data={"mode": "none"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["voiceover_mode"], "none")

        response = self.client.post(
            f"/api/jobs/{job['id']}/voiceover/",
            data={"mode": "tts", "provider_id": provider.id, "script": "First hook. Second CTA."},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["job"]
        self.assertEqual(payload["voiceover_mode"], "tts")
        self.assertIn("fake-tts", payload["audio_placeholder"])
        self.assertEqual([cue["text"] for cue in payload["subtitles"]], ["First hook", "Second CTA"])

        response = self.client.post(
            f"/api/jobs/{job['id']}/subtitles/",
            data={"subtitles": [{"start": 0, "end": 2, "text": "edited subtitle"}]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["subtitles"][0]["text"], "edited subtitle")

    def test_fake_asr_provider_generates_subtitles_from_source_audio_asset(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=500)
        provider = AIProvider.objects.create(capability=AIProvider.ASR, name="Fake ASR", model_name="fake-asr", enabled=True)
        asset = Asset.objects.create(workspace=workspace, uploaded_by=user, filename="source.wav", content_type="audio/wav", asset_type=Asset.AUDIO, object_key="source")
        token = AuthToken.issue_for(user)
        job = self.client.post("/api/jobs/", data={"title": "asr job", "estimated_credits": 100}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}").json()["job"]

        response = self.client.post(
            f"/api/jobs/{job['id']}/voiceover/",
            data={"mode": "asr", "provider_id": provider.id, "asset_id": asset.id},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["job"]
        self.assertEqual(payload["voiceover_mode"], "asr")
        self.assertEqual(payload["source_audio_asset_id"], asset.id)
        self.assertIn("source.wav", payload["subtitles"][0]["text"])


class SingleVideoRenderTests(TestCase):
    def test_render_job_creates_9_16_downloadable_preview_asset_and_settles_credits(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=500)
        first = Asset.objects.create(workspace=workspace, uploaded_by=user, filename="detail.mp4", content_type="video/mp4", asset_type=Asset.VIDEO, object_key="detail", tags=["detail"])
        second = Asset.objects.create(workspace=workspace, uploaded_by=user, filename="product.mp4", content_type="video/mp4", asset_type=Asset.VIDEO, object_key="product", tags=["product"])
        token = AuthToken.issue_for(user)
        job = self.client.post("/api/jobs/", data={"title": "render job", "estimated_credits": 120}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}").json()["job"]
        self.client.post(f"/api/jobs/{job['id']}/subtitles/", data={"subtitles": [{"start": 0, "end": 1, "text": "buy now"}]}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post(
            f"/api/jobs/{job['id']}/render/",
            data={"asset_ids": [first.id, second.id]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["job"]["status"], "succeeded")
        self.assertEqual(payload["job"]["render"]["width"], 1080)
        self.assertEqual(payload["job"]["render"]["height"], 1920)
        self.assertEqual(payload["job"]["render"]["source_asset_ids"], [second.id, first.id])
        self.assertEqual(payload["output_asset"]["asset_type"], "output")
        self.assertEqual(payload["credits"], {"workspace_id": workspace.id, "balance": 380, "frozen": 0})

        response = self.client.get(payload["output_asset"]["preview_url"], HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "video/mp4")

    def test_render_failure_marks_job_failed_and_refunds_credits(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=200)
        asset = Asset.objects.create(workspace=workspace, uploaded_by=user, filename="clip.mp4", content_type="video/mp4", asset_type=Asset.VIDEO, object_key="clip", tags=["product"])
        token = AuthToken.issue_for(user)
        job = self.client.post("/api/jobs/", data={"title": "bad render", "estimated_credits": 120}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}").json()["job"]

        with patch("core.views.run_ffmpeg_render", side_effect=RuntimeError("boom")):
            response = self.client.post(
                f"/api/jobs/{job['id']}/render/",
                data={"asset_ids": [asset.id]},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["job"]["status"], "failed")
        self.assertEqual(response.json()["credits"], {"workspace_id": workspace.id, "balance": 200, "frozen": 0})


class BatchRemixTests(TestCase):
    def test_batch_remix_creates_variant_render_jobs_with_different_hooks_and_asset_order(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=500)
        product = Asset.objects.create(workspace=workspace, uploaded_by=user, filename="product.mp4", content_type="video/mp4", asset_type=Asset.VIDEO, object_key="batch-product", tags=["product"])
        detail = Asset.objects.create(workspace=workspace, uploaded_by=user, filename="detail.mp4", content_type="video/mp4", asset_type=Asset.VIDEO, object_key="batch-detail", tags=["detail"])
        token = AuthToken.issue_for(user)

        response = self.client.post(
            "/api/jobs/batch-remix/",
            data={"asset_ids": [detail.id, product.id], "variants": 2, "estimated_credits": 50, "script": "gold bracelet"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        jobs = response.json()["jobs"]
        self.assertEqual(len(jobs), 2)
        self.assertEqual({job["status"] for job in jobs}, {"pending"})
        self.assertNotEqual(jobs[0]["subtitles"][0]["text"], jobs[1]["subtitles"][0]["text"])
        self.assertNotEqual(jobs[0]["render"]["source_asset_ids"], jobs[1]["render"]["source_asset_ids"])
        self.assertEqual(response.json()["credits"], {"workspace_id": workspace.id, "balance": 400, "frozen": 100})

    def test_regenerating_after_success_creates_new_paid_jobs(self):
        user, workspace = make_user_workspace()
        CreditRecharge.objects.create(workspace=workspace, amount=300)
        asset = Asset.objects.create(workspace=workspace, uploaded_by=user, filename="product.mp4", content_type="video/mp4", asset_type=Asset.VIDEO, object_key="batch-regenerate", tags=["product"])
        token = AuthToken.issue_for(user)

        first = self.client.post(
            "/api/jobs/batch-remix/",
            data={"asset_ids": [asset.id], "variants": 1, "estimated_credits": 50, "script": "first"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        ).json()["jobs"][0]
        self.client.post(f"/api/jobs/{first['id']}/transition/", data={"status": "running"}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.client.post(f"/api/jobs/{first['id']}/transition/", data={"status": "succeeded"}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post(
            "/api/jobs/batch-remix/",
            data={"asset_ids": [asset.id], "variants": 1, "estimated_credits": 50, "script": "again"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.json()["jobs"][0]["id"], first["id"])
        self.assertEqual(response.json()["credits"], {"workspace_id": workspace.id, "balance": 200, "frozen": 50})
