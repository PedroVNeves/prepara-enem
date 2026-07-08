"""Django settings for the Prepara ENEM project."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-local-dev-only-change-in-production",
)

DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Atrás de um proxy HTTPS (Cloud Run, Render, etc.), o Django exige que a
# origem apareça aqui para aceitar POSTs (login, respostas de simulado...) —
# sem isso, toda submissão de formulário falha com "CSRF verification
# failed", mesmo com ALLOWED_HOSTS correto. Derivado de ALLOWED_HOSTS para
# não duplicar a lista de hosts em duas variáveis de ambiente.
CSRF_TRUSTED_ORIGINS = [
    f"https://{host}" for host in ALLOWED_HOSTS if host not in ("localhost", "127.0.0.1")
]

# Cloud Run (e Render) terminam TLS no proxy e repassam HTTP puro pro
# container, sinalizando o protocolo original via X-Forwarded-Proto. Sem
# isso, request.is_secure() sempre retorna False, e o Django nem chega a
# usar o CSRF_TRUSTED_ORIGINS acima — cai num caminho de verificação
# diferente (baseado em Referer) que falha atrás de proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # apps do projeto
    "core",
    "llm",
    "accounts",
    "exams",
    "irt",
    "simulados",
    "reports",
    "redacao",
    "ops",
    "billing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Banco: Supabase Postgres via pooler transaction-mode em produção
# (DATABASE_URL), sqlite local se não configurado (dev/testes sem credenciais).
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}
DATABASES["default"].setdefault("CONN_MAX_AGE", 0)  # pooler externo já gerencia conexões

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:select_context"
LOGOUT_REDIRECT_URL = "accounts:login"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True


# Static files: as imagens do dataset (2009/ a 2023/) são servidas como
# assets estáticos versionados via WhiteNoise, sem duplicar os ~90MB dentro
# de uma pasta static/ de app e sem precisar de bucket de storage externo.
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Prefixado por ano (("2023", .../2023)) para não colidir os "questions/"
# e "details.json" de anos diferentes no mesmo namespace estático.
STATICFILES_DIRS = [
    (str(year), BASE_DIR / str(year))
    for year in range(2009, 2024)
    if (BASE_DIR / str(year)).exists()
]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Fotos de redação enviadas por alunos (correção manual pelo professor).
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Gemini (classificação de questões, correção de redação, geração de temas)
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_MODEL_FLASH = env("GEMINI_MODEL_FLASH", default="gemini-flash-lite-latest")
GEMINI_MODEL_PRO = env("GEMINI_MODEL_PRO", default="gemini-pro-latest")

# Jobs periódicos (fila de redação + recalibração TRI) rodam via APScheduler
# dentro do próprio processo — ver ops/scheduler.py. Desligado por padrão
# (inclusive em testes/management commands avulsos); ligar só no processo
# web real via variável de ambiente.
ENABLE_SCHEDULER = env.bool("ENABLE_SCHEDULER", default=False)

# E-mail transacional: mínimo necessário para reset de senha do auth padrão
# do Django. Em dev, imprime no console; em produção, aponta para o SMTP
# relay de um provedor barato/gratuito (Resend ou Brevo cobrem o volume
# inicial) via variáveis de ambiente. Notificações mais ricas (simulado
# atribuído, redação corrigida) ficam para depois, reaproveitando o mesmo
# backend.
if env("EMAIL_HOST", default=""):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Prepara ENEM <no-reply@preparaenem.example.com>")
