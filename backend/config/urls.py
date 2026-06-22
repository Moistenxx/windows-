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
    path("api/ai/providers/", views.ai_providers, name="ai_providers"),
    path("api/ai/estimate/", views.ai_estimate, name="ai_estimate"),
    path("api/ai/fake-call/", views.ai_fake_call, name="ai_fake_call"),
    path("api/customers/", views.customers, name="customers"),
    path("api/customers/<int:customer_id>/", views.customer_detail, name="customer_detail"),
]
