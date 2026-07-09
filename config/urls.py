from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="accounts:login", permanent=False)),
    # accounts:select_context redireciona pra "/aluno/" ou "/professor/" após
    # login — essas rotas viram a página inicial de cada contexto (core.urls).
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("", include("simulados.urls")),
    path("", include("redacao.urls")),
    path("", include("reports.urls")),
    path("interno/", include("ops.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
