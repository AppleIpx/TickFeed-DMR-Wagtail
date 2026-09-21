# ruff: noqa: ERA001, E501
"""Base settings to build other settings files upon."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

import environ
from dmr.openapi import OpenAPIConfig

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

DATABASES["default"]["ATOMIC_REQUESTS"] = False
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
    "dmr",
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

# API (django-modern-rest)
# ------------------------------------------------------------------------------
DMR_SETTINGS = {
    "openapi_config": OpenAPIConfig(title="TickFeedDmr API", version="0.1.0"),
}

# MARKET DATA
# ------------------------------------------------------------------------------
# Доменная временная зона: граница торгового дня (свечи, история, курсы
# ЦБ) везде считается по Москве — как и `CELERY_TIMEZONE` выше, независимо
# от `TIME_ZONE` проекта (UTC). Единый объект вместо `ZoneInfo("Europe/Moscow")`
# в каждом модуле — `zoneinfo.ZoneInfo` кэширует инстансы по ключу, так что
# дублирование не создавало разных объектов, но текст дублировался.
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

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
# Ретеншн стрима крипты (см. `services/trade_stream_retention.py`). `XACK`
# запись не удаляет, поэтому без обрезки стрим растёт при здоровой системе.
# Потолок — предохранитель у продюсера на случай, когда консьюмер лежит;
# зазор — сколько времени консьюмер оставляет позади границы «записано в БД»
# (защита от гонки с SSE-читателем); интервал — как часто консьюмер обрезает.
# Проверки значений — `services/stream_settings.py`.
MARKET_DATA_TRADE_STREAM_CEILING_SECONDS = env.int(
    "MARKET_DATA_TRADE_STREAM_CEILING_SECONDS",
    default=6 * 60 * 60,
)
MARKET_DATA_TRADE_TRIM_GAP_SECONDS = env.int(
    "MARKET_DATA_TRADE_TRIM_GAP_SECONDS",
    default=300,
)
MARKET_DATA_TRADE_TRIM_INTERVAL_SECONDS = env.int(
    "MARKET_DATA_TRADE_TRIM_INTERVAL_SECONDS",
    default=10,
)

MARKET_DATA_SSE_TOP_N = env.int("MARKET_DATA_SSE_TOP_N", default=3)
MARKET_DATA_SSE_WINDOW_SECONDS = env.float(
    "MARKET_DATA_SSE_WINDOW_SECONDS",
    default=1.0,
)
MARKET_DATA_SSE_READ_COUNT = env.int("MARKET_DATA_SSE_READ_COUNT", default=500)
MARKET_DATA_SSE_HEARTBEAT_SECONDS = env.float(
    "MARKET_DATA_SSE_HEARTBEAT_SECONDS",
    default=15.0,
)
MARKET_DATA_SSE_MAX_TICKERS = env.int("MARKET_DATA_SSE_MAX_TICKERS", default=50)

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
# иначе каждый тик падал бы по бюджету (проверки —
# `services/moex_polling/settings.py`). Запас TTL над
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

# Redis Stream сделок акций для SSE (`services/moex_trade_stream/`). Поллер
# пишет в БД всё, а в стрим — только отобранное: последние TOP_N сделок бумаги
# за прогон среди «свежих». Свежесть считается с поправкой на лаг ISS (~15 мин,
# `MOEX_DATA_DELAY_SECONDS`): сделки моложе `now − лаг − FRESHNESS`. Ретеншн
# — окно, которое стрим держит при каждом `XADD` (у стрима нет консьюмера,
# докачки нет, дольше держать нечего). Проверки значений —
# `services/moex_polling/settings.py`.
MOEX_TRADE_STREAM_KEY = env(
    "MOEX_TRADE_STREAM_KEY",
    default="market_data:trades:moex",
)
MOEX_TRADE_STREAM_RETENTION_SECONDS = env.int(
    "MOEX_TRADE_STREAM_RETENTION_SECONDS",
    default=300,
)
MOEX_TRADE_STREAM_FRESHNESS_SECONDS = env.int(
    "MOEX_TRADE_STREAM_FRESHNESS_SECONDS",
    default=300,
)
MOEX_TRADE_STREAM_TOP_N = env.int("MOEX_TRADE_STREAM_TOP_N", default=10)

# ЦБ РФ
# ------------------------------------------------------------------------------
CBR_DAILY_RATES_BASE_URL = env("CBR_DAILY_RATES_BASE_URL", default="https://www.cbr.ru")
CBR_POLL_BUDGET_SECONDS = env.int("CBR_POLL_BUDGET_SECONDS", default=20)
CBR_POLL_LOCK_TTL_SECONDS = env.int("CBR_POLL_LOCK_TTL_SECONDS", default=30)

# ДНЕВНЫЕ СВЕЧИ
# ------------------------------------------------------------------------------
# Один и тот же механизм догона (сигнал + ночная задача) на три домена. Бюджет/TTL — per-domain (разная
# стоимость запроса: крипта ~4 запроса на полную историю, акции ~10 плюс
# постраничное дочитывание, ЦБ — 1 запрос на валюту); лимит числа активов за
# ночной прогон — один общий, он же основной механизм защиты
# `poll_moex_board`/остальных периодических задач от вытеснения долгим прогоном
MARKET_DATA_DAILY_CANDLES_MAX_ASSETS_PER_RUN = env.int(
    "MARKET_DATA_DAILY_CANDLES_MAX_ASSETS_PER_RUN",
    default=50,
)
CRYPTO_DAILY_CANDLES_POLL_BUDGET_SECONDS = env.int(
    "CRYPTO_DAILY_CANDLES_POLL_BUDGET_SECONDS",
    default=120,
)
CRYPTO_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS = env.int(
    "CRYPTO_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS",
    default=140,
)
STOCK_DAILY_CANDLES_POLL_BUDGET_SECONDS = env.int(
    "STOCK_DAILY_CANDLES_POLL_BUDGET_SECONDS",
    default=300,
)
STOCK_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS = env.int(
    "STOCK_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS",
    default=330,
)
FIAT_DAILY_CANDLES_POLL_BUDGET_SECONDS = env.int(
    "FIAT_DAILY_CANDLES_POLL_BUDGET_SECONDS",
    default=60,
)
FIAT_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS = env.int(
    "FIAT_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS",
    default=75,
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
