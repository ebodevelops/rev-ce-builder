from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    BLUECAT_VERIFY_TLS=(bool, True),
    OPENGEAR_VERIFY_TLS=(bool, True),
    ZTP_REQUIRE_AUTH=(bool, False),
    GIT_MIRROR_ENABLED=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-key-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "django_htmx",
    "reversion",
    "apps.core",
    "apps.inventory",
    "apps.ztp",
    "apps.integrations",
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
    "django_htmx.middleware.HtmxMiddleware",
    "reversion.middleware.RevisionMiddleware",
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
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": env.db("DATABASE_URL", default="postgres://ztp:ztp@localhost:5432/ztp")}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
}

# Celery
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/2")
CELERY_TASK_TIME_LIMIT = 60 * 30
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 25
CELERY_TASK_ACKS_LATE = True

# Bluecat IPAM
BLUECAT = {
    "BASE_URL": env("BLUECAT_BASE_URL", default=""),
    "USERNAME": env("BLUECAT_USERNAME", default=""),
    "PASSWORD": env("BLUECAT_PASSWORD", default=""),
    "VERIFY_TLS": env("BLUECAT_VERIFY_TLS"),
    "DEFAULT_CONFIG": env("BLUECAT_DEFAULT_CONFIG", default="Production"),
    "LOOPBACK_TAG_GROUP": env("BLUECAT_LOOPBACK_TAG_GROUP", default="ZTP/Loopbacks"),
    "P2P_TAG_GROUP": env("BLUECAT_P2P_TAG_GROUP", default="ZTP/P2P-Networks"),
}

# Opengear
OPENGEAR = {
    "BASE_URL": env("OPENGEAR_BASE_URL", default=""),
    "USERNAME": env("OPENGEAR_USERNAME", default=""),
    "PASSWORD": env("OPENGEAR_PASSWORD", default=""),
    "VERIFY_TLS": env("OPENGEAR_VERIFY_TLS"),
}

# ZTP file server
ZTP_FILES_ROOT = Path(env("ZTP_FILES_ROOT", default=str(BASE_DIR / "ztp_files")))
ZTP_PUBLIC_BASE_URL = env("ZTP_PUBLIC_BASE_URL", default="http://localhost:8000")
ZTP_REQUIRE_AUTH = env("ZTP_REQUIRE_AUTH")

# Git mirror
GIT_MIRROR = {
    "ENABLED": env("GIT_MIRROR_ENABLED"),
    "PATH": env("GIT_MIRROR_PATH", default=str(BASE_DIR / "config_repo")),
    "REMOTE": env("GIT_MIRROR_REMOTE", default=""),
    "AUTHOR_NAME": env("GIT_MIRROR_AUTHOR_NAME", default="ZTP Bot"),
    "AUTHOR_EMAIL": env("GIT_MIRROR_AUTHOR_EMAIL", default="ztp@example.net"),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
