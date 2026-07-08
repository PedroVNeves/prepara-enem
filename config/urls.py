from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import RedirectView


def _debug_diag(request):
    """Endpoint temporário de diagnóstico — remover depois de resolver o CSRF em prod."""
    return JsonResponse(
        {
            "is_secure": request.is_secure(),
            "get_host": request.get_host(),
            "scheme": request.scheme,
            "x_forwarded_proto": request.META.get("HTTP_X_FORWARDED_PROTO"),
            "allowed_hosts": settings.ALLOWED_HOSTS,
            "csrf_trusted_origins": settings.CSRF_TRUSTED_ORIGINS,
            "secure_proxy_ssl_header": settings.SECURE_PROXY_SSL_HEADER,
        }
    )


urlpatterns = [
    path("__diag/", _debug_diag),
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
