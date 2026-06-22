from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import AuthToken, InvitationCode, Workspace, WorkspaceMembership


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

    def test_admin_registers_auth_and_workspace_models(self):
        self.assertTrue(admin.site.is_registered(InvitationCode))
        self.assertTrue(admin.site.is_registered(Workspace))
        self.assertTrue(admin.site.is_registered(WorkspaceMembership))
        self.assertTrue(admin.site.is_registered(AuthToken))


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
        user = User.objects.create_user(username="owner@example.com", email="owner@example.com", password="secret123")
        workspace = Workspace.objects.create(name="owner workspace")
        WorkspaceMembership.objects.create(user=user, workspace=workspace, role="owner")

        response = self.client.post(
            "/api/auth/login/",
            data={"email": "owner@example.com", "password": "secret123"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["token"])
        self.assertEqual(payload["workspace"]["id"], workspace.id)

    def test_me_returns_only_authenticated_users_workspaces(self):
        user = User.objects.create_user(username="owner@example.com", email="owner@example.com", password="secret123")
        own_workspace = Workspace.objects.create(name="owner workspace")
        other_workspace = Workspace.objects.create(name="other workspace")
        WorkspaceMembership.objects.create(user=user, workspace=own_workspace, role="owner")
        token = AuthToken.issue_for(user)

        response = self.client.get(
            "/api/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["email"], "owner@example.com")
        self.assertEqual(payload["workspaces"], [{"id": own_workspace.id, "name": "owner workspace", "role": "owner"}])
        self.assertNotIn(other_workspace.id, [workspace["id"] for workspace in payload["workspaces"]])

    def test_me_rejects_missing_token(self):
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 401)
