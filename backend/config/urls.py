from django.contrib import admin
from django.urls import path

from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", views.health, name="health"),
    path("api/auth/register/", views.register, name="register"),
    path("api/auth/login/", views.login, name="login"),
    path("api/auth/me/", views.me, name="me"),
    path("api/credits/", views.credits, name="credits"),
    path("api/credit-tasks/", views.credit_tasks, name="credit_tasks"),
    path("api/jobs/", views.jobs, name="jobs"),
    path("api/jobs/<int:job_id>/transition/", views.job_transition, name="job_transition"),
    path("api/jobs/<int:job_id>/voiceover/", views.job_voiceover, name="job_voiceover"),
    path("api/jobs/<int:job_id>/subtitles/", views.job_subtitles, name="job_subtitles"),
    path("api/jobs/<int:job_id>/render/", views.job_render, name="job_render"),
    path("api/ai/providers/", views.ai_providers, name="ai_providers"),
    path("api/ai/estimate/", views.ai_estimate, name="ai_estimate"),
    path("api/ai/fake-call/", views.ai_fake_call, name="ai_fake_call"),
    path("api/customers/", views.customers, name="customers"),
    path("api/customers/<int:customer_id>/", views.customer_detail, name="customer_detail"),
    path("api/assets/", views.assets, name="assets"),
    path("api/assets/<int:asset_id>/preview/", views.asset_preview, name="asset_preview"),
    path("api/assets/<int:asset_id>/delete/", views.asset_delete, name="asset_delete"),
    path("api/assets/<int:asset_id>/tags/", views.asset_tags, name="asset_tags"),
    path("api/scripts/generate/", views.script_generate, name="script_generate"),
    path("api/scripts/<int:script_id>/confirm/", views.script_confirm, name="script_confirm"),
    path("api/script-assets/", views.script_assets, name="script_assets"),
    path("api/viral-samples/", views.viral_samples, name="viral_samples"),
]
