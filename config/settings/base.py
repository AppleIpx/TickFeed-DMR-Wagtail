# ruff: noqa: ERA001, E501
"""Base settings to build other settings files upon."""

import os
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# tickfeeddmr/
APPS_DIR = BASE_DIR / "tickfeeddmr"
env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "UTC"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"
# https://docs.djangoproject.com/en/dev/ref/settings/#languages
# from django.utils.translation import gettext_lazy as _
# LANGUAGES = [
#     ('en', _('English')),
#     ('fr-fr', _('French')),
#     ('pt-br', _('Portuguese')),
# ]
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(BASE_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases

if os.getenv("DATABASE_URL", default=None):
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env.str("POSTGRES_DB"),
            "USER": env.str("POSTGRES_USER"),
            "PASSWORD": env.str("POSTGRES_PASSWORD"),
            "HOST": env.str("POSTGRES_HOST", default="postgres"),
            "PORT": env.str("POSTGRES_PORT", default="5432"),
        },
    }

DATABASES["default"]["ATOMIC_REQUESTS"] = True
# https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "config.urls"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # "django.contrib.humanize", # Handy template tags
    "django.contrib.admin",
    "django.forms",
    "django.contrib.postgres",
]
THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "wagtail_modeladmin",
    "modelcluster",
    "taggit",
    "django_celery_beat",
]

LOCAL_APPS = [
    "tickfeeddmr.users",
    "tickfeeddmr.core",
    "tickfeeddmr.market_data",
    # Your stuff: custom apps go here
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {"sites": "tickfeeddmr.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = "users.User"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "users:redirect"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-url
LOGIN_URL = "account_login"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/en/dev/topics/auth/passwords/#using-argon2-with-django
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(BASE_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [str(APPS_DIR / "static")]
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(APPS_DIR / "media")
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#dirs
        "DIRS": [str(APPS_DIR / "templates")],
        # https://docs.djangoproject.com/en/dev/ref/settings/#app-dirs
        "APP_DIRS": True,
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "tickfeeddmr.users.context_processors.allauth_settings",
            ],
        },
    },
]

# https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-timeout
EMAIL_TIMEOUT = 5

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = ['"Daniel Roy Greenfeld" <daniel-roy-greenfeld@example.com>']
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS
# https://cookiecutter-django.readthedocs.io/en/latest/settings.html#other-environment-settings
# Force the `admin` sign in process to go through the `django-allauth` workflow
DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=False)

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
REDIS_SSL = REDIS_URL.startswith("rediss://")

# CELERY
# ------------------------------------------------------------------------------
# https://docs.celeryq.dev/en/stable/userguide/configuration.html
# Отдельная БД брокера (db 1), НЕ db 0 из REDIS_URL — там живут стримы
# `market_data:trades:*`, очередь Celery в них подмешивать нельзя.
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND = None
CELERY_TIMEZONE = "Europe/Moscow"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# MARKET DATA
# ------------------------------------------------------------------------------
# Binance REST/WebSocket endpoints used by `tickfeeddmr.market_data.providers.binance`.
BINANCE_REST_BASE_URL = env("BINANCE_REST_BASE_URL", default="https://api.binance.com")
BINANCE_WS_BASE_URL = env(
    "BINANCE_WS_BASE_URL",
    default="wss://stream.binance.com:9443",
)
# Redis Stream that `stream_binance` publishes trade events to, and that
# `consume_market_data_stream` reads from via a consumer group.
MARKET_DATA_TRADE_STREAM_KEY = env(
    "MARKET_DATA_TRADE_STREAM_KEY",
    default="market_data:trades:binance",
)
MARKET_DATA_TRADE_CONSUMER_GROUP = env(
    "MARKET_DATA_TRADE_CONSUMER_GROUP",
    default="market_data_ingest",
)
# `consume_market_data_stream` tuning: consumer identity within the group,
# how many stream entries to pull per `XREADGROUP`, and how long to block
# waiting for new ones.
MARKET_DATA_TRADE_CONSUMER_NAME = env(
    "MARKET_DATA_TRADE_CONSUMER_NAME",
    default="consumer-1",
)
MARKET_DATA_TRADE_READ_COUNT = env.int("MARKET_DATA_TRADE_READ_COUNT", default=100)
MARKET_DATA_TRADE_READ_BLOCK_MS = env.int(
    "MARKET_DATA_TRADE_READ_BLOCK_MS",
    default=5000,
)

# MOEX
# ------------------------------------------------------------------------------
MOEX_ISS_BASE_URL = env("MOEX_ISS_BASE_URL", default="https://iss.moex.com")
MOEX_DEFAULT_BOARD = env("MOEX_DEFAULT_BOARD", default="TQBR")
MOEX_TRADES_PAGE_LIMIT = env.int("MOEX_TRADES_PAGE_LIMIT", default=5)
# Бюджет прогона — потолок на сетевые вызовы одного прогона опроса
# (`asyncio.timeout` в `services/moex_polling/`); повторы/таймауты одного
# запроса — константы `providers/moex/client.py`. Инвариант: бюджет < TTL
# лока с запасом не меньше `_MOEX_POLL_MIN_LOCK_MARGIN_SECONDS`, иначе лок
# истечёт под живым прогоном и следующий тик наложится на него; бюджет > 0,
# иначе каждый тик падал бы по бюджету (проверки ниже). Запас TTL над
# бюджетом покрывает то, что внутри лока, но вне бюджета: запись в БД,
# `aclose()`, снятие лока.
# Борд (тик 60 с): бюджет 45 < TTL 55 < тик — лок, осиротевший после
# жёсткого падения процесса, истекает до следующего тика.
# Сделки (тик 60 с): бюджет 100 < TTL 120 — сознательно больше тика:
# догон ленты законно длится дольше минуты, следующий тик при этом
# пропускается по занятому локу.
MOEX_BOARD_POLL_BUDGET_SECONDS = env.int(
    "MOEX_BOARD_POLL_BUDGET_SECONDS",
    default=45,
)
MOEX_BOARD_POLL_LOCK_TTL_SECONDS = env.int(
    "MOEX_BOARD_POLL_LOCK_TTL_SECONDS",
    default=55,
)
MOEX_TRADES_POLL_BUDGET_SECONDS = env.int(
    "MOEX_TRADES_POLL_BUDGET_SECONDS",
    default=100,
)
MOEX_TRADES_POLL_LOCK_TTL_SECONDS = env.int(
    "MOEX_TRADES_POLL_LOCK_TTL_SECONDS",
    default=120,
)
_MOEX_POLL_MIN_LOCK_MARGIN_SECONDS = 5


def _validate_moex_poll_budget(kind: str, budget: int, ttl: int) -> None:
    budget_name = f"MOEX_{kind}_POLL_BUDGET_SECONDS"
    ttl_name = f"MOEX_{kind}_POLL_LOCK_TTL_SECONDS"
    if budget <= 0:
        msg = f"{budget_name} must be a positive number of seconds, got {budget}"
        raise ImproperlyConfigured(msg)
    if ttl - budget < _MOEX_POLL_MIN_LOCK_MARGIN_SECONDS:
        msg = (
            f"{ttl_name} ({ttl}) must exceed {budget_name} ({budget}) by at least "
            f"{_MOEX_POLL_MIN_LOCK_MARGIN_SECONDS}s: the margin covers DB writes, "
            f"client close and lock release that run inside the lock but outside "
            f"the run budget"
        )
        raise ImproperlyConfigured(msg)


_validate_moex_poll_budget(
    "BOARD",
    MOEX_BOARD_POLL_BUDGET_SECONDS,
    MOEX_BOARD_POLL_LOCK_TTL_SECONDS,
)
_validate_moex_poll_budget(
    "TRADES",
    MOEX_TRADES_POLL_BUDGET_SECONDS,
    MOEX_TRADES_POLL_LOCK_TTL_SECONDS,
)


# django-allauth
# ------------------------------------------------------------------------------
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_LOGIN_METHODS = {"email"}
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_ADAPTER = "tickfeeddmr.users.adapters.AccountAdapter"
# https://docs.allauth.org/en/latest/account/forms.html
ACCOUNT_FORMS = {"signup": "tickfeeddmr.users.forms.UserSignupForm"}
# https://docs.allauth.org/en/latest/socialaccount/configuration.html
SOCIALACCOUNT_ADAPTER = "tickfeeddmr.users.adapters.SocialAccountAdapter"
# https://docs.allauth.org/en/latest/socialaccount/configuration.html
SOCIALACCOUNT_FORMS = {"signup": "tickfeeddmr.users.forms.UserSocialSignupForm"}

# WAGTAIL
# ------------------------------------------------------------------------------
WAGTAIL_SITE_NAME = "TickFeedDmr"
WAGTAILADMIN_BASE_URL = env.str(
    "WAGTAIL_ADMIN_BASE_URL",
    default="http://localhost:8000",
)
WAGTAIL_ADMIN_URL = "cms/admin/"

# Docs
# ------------------------------------------------------------------------------
WAGTAILDOCS_EXTENSIONS = ["pdf", "doc", "docx", "xls", "xlsx"]


# Your stuff...
# ------------------------------------------------------------------------------
