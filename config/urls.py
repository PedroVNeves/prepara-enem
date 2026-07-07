from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="accounts:login", permanent=False)),
    path("", include("accounts.urls")),
    path("", include("simulados.urls")),
    path("", include("redacao.urls")),
    path("", include("reports.urls")),
    path("interno/", include("ops.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
