"""
URL configuration for paws_on_stream_web project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from core.auth_views import (
    auth_login,
    telegram_callback,
    telegram_login_denied,
    telegram_logout,
    telegram_start,
)
from core.monitor_views import web_display, web_display_access, web_display_feed
from core.views import (
    DisplayDeviceViewSet,
    DisplayLogViewSet,
    HealthAPIView,
    MetricsAPIView,
    ReadinessAPIView,
    SettingsViewSet,
)
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from participants.views import (
    ParticipantBanAPIView,
    ParticipantMuteAPIView,
    ParticipantViewSet,
)
from rest_framework.routers import DefaultRouter
from streaming.views import (
    DisplayEventAPIView,
    EventViewSet,
    MediaUploadAPIView,
    MessageViewSet,
    media_asset_content,
)

router = DefaultRouter()
router.register(r"events", EventViewSet, basename="event")
router.register(r"messages", MessageViewSet, basename="message")
router.register(r"participants", ParticipantViewSet, basename="participant")
router.register(r"settings", SettingsViewSet, basename="settings")
router.register(r"devices", DisplayDeviceViewSet, basename="displaydevice")
router.register(r"logs", DisplayLogViewSet, basename="displaylog")

urlpatterns = [
    path("auth/login/", auth_login, name="login"),
    path("auth/telegram/", telegram_start, name="telegram_start"),
    path("auth/callback/", telegram_callback, name="telegram_callback"),
    path("auth/denied/", telegram_login_denied, name="telegram_login_denied"),
    path("auth/logout/", telegram_logout, name="telegram_logout"),
    path("admin/", admin.site.urls),
    path("api/v1/health/", HealthAPIView.as_view()),
    path("api/v1/readiness/", ReadinessAPIView.as_view()),
    path("metrics/", MetricsAPIView.as_view()),
    path("monitor/", web_display, name="web_display"),
    path("monitor/access/", web_display_access, name="web_display_access"),
    path("monitor/feed/", web_display_feed, name="web_display_feed"),
    path("media/media_assets/<path:file_name>", media_asset_content),
    path("api/v1/media/upload/", MediaUploadAPIView.as_view()),
    path("api/v1/events/killswitch/", DisplayEventAPIView.as_view()),
    path("api/v1/message/", MessageViewSet.as_view({"post": "create"})),
    path(
        "api/v1/participant/<int:telegram_id>/ban/",
        ParticipantBanAPIView.as_view(),
    ),
    path(
        "api/v1/participant/<int:telegram_id>/mute/",
        ParticipantMuteAPIView.as_view(),
    ),
    path("api/v1/", include(router.urls)),
    path("", include("dashboard.urls", namespace="dashboard")),
    path("streaming/", include("streaming.urls", namespace="streaming")),
    path("participants/", include("participants.urls", namespace="participants")),
    path("core/", include("core.urls", namespace="core")),
]

if settings.DEBUG:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
