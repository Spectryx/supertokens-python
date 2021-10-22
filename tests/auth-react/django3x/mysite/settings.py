"""
Django settings for mysite project.

Generated by 'django-admin startproject' using Django 2.2.23.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
from corsheaders.defaults import default_headers
from supertokens_python import init, get_all_cors_headers
from supertokens_python.recipe import session, thirdpartyemailpassword, thirdparty, emailpassword
from supertokens_python.recipe.thirdpartyemailpassword import Github, Google, Facebook
from dotenv import load_dotenv
from django.conf import settings

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'f_d6ar@t2n+e@&7b^i^**kzo68w^e*1kn9%40#sp@0v2t#=vs2'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

LATEST_URL_WITH_TOKEN = None


async def create_and_send_custom_email(_, url_with_token):
    global LATEST_URL_WITH_TOKEN
    setattr(settings, "LATEST_URL_WITH_TOKEN", url_with_token)
    LATEST_URL_WITH_TOKEN = url_with_token


async def validate_age(value):
    try:
        if int(value) < 18:
            return "You must be over 18 to register"
    except Exception:
        pass

    return None

form_fields = [{
    'id': 'name'
}, {
    'id': 'age',
    'validate': validate_age
}, {
    'id': 'country',
    'optional': True
}]


def get_api_port():
    return '8083'


def get_website_port():
    return '3031'


def get_website_domain():
    return 'http://localhost:' + get_website_port()


init({
    'supertokens': {
        'connection_uri': "http://localhost:9000",
    },
    'framework': 'django',
    'mode': os.environ.get('APP_MODE', 'asgi'),
    'app_info': {
        'app_name': "SuperTokens",
        'api_domain': "0.0.0.0:" + get_api_port(),
        'website_domain': get_website_domain(),
    },
    'recipe_list': [
        session.init({}),
        emailpassword.init({
            'sign_up_feature': {
                'form_fields': form_fields
            },
            'reset_password_using_token_feature': {
                'create_and_send_custom_email': create_and_send_custom_email
            },
            'email_verification_feature': {
                'create_and_send_custom_email': create_and_send_custom_email
            }
        }),
        thirdparty.init({
            'sign_in_and_up_feature': {
                'providers': [
                    Google(
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                    ), Facebook(
                        client_id=os.environ.get('FACEBOOK_CLIENT_ID'),
                        client_secret=os.environ.get('FACEBOOK_CLIENT_SECRET')
                    ), Github(
                        client_id=os.environ.get('GITHUB_CLIENT_ID'),
                        client_secret=os.environ.get('GITHUB_CLIENT_SECRET')
                    )
                ]
            }
        }),
        thirdpartyemailpassword.init({
            'sign_up_feature': {
                'form_fields': form_fields
            },
            'providers': [
                Google(
                    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                ), Facebook(
                    client_id=os.environ.get('FACEBOOK_CLIENT_ID'),
                    client_secret=os.environ.get('FACEBOOK_CLIENT_SECRET')
                ), Github(
                    client_id=os.environ.get('GITHUB_CLIENT_ID'),
                    client_secret=os.environ.get('GITHUB_CLIENT_SECRET')
                )
            ]
        })
    ],
    'telemetry': False
})


ALLOWED_HOSTS = ['localhost']

CORS_ORIGIN_WHITELIST = [
    get_website_domain()
]
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    get_website_domain()
]
CORS_ALLOWED_ORIGIN_REGEXES = [
    get_website_domain()
]

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = list(default_headers) + [
    "Content-Type"
] + get_all_cors_headers()

# Application definition

INSTALLED_APPS = [
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'mysite.middleware.custom_cors_middleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'supertokens_python.framework.django.django_middleware.middleware',
]

ROOT_URLCONF = 'mysite.urls'
SETTINGS_PATH = os.path.dirname(os.path.dirname(__file__))

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(os.path.dirname(__file__), '../', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ASGI_APPLICATION = 'asgi.application'

# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

STATIC_URL = '/static/'
