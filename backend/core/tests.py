from django.test import TestCase
from django.urls import reverse


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
