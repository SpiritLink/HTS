import os
from pathlib import Path

# BASE_DIR 설정 (프로젝트 최상위 디렉토리)
BASE_DIR = Path(__file__).resolve().parent.parent

# 보안 키 (개발용 임시 키)
SECRET_KEY = 'django-insecure-temporary-key-for-hts-project'

# 디버그 모드 (개발 중에는 True)
DEBUG = True

# 연결하신 도메인 이름을 여기에 입력하세요 (예: 'hts.example.com')
ALLOWED_HOSTS = ['*']

# ==========================================
# HTTPS 및 운영(Production) 환경 보안 설정
# ==========================================
# 웹 서버(Nginx 등)가 HTTPS로 요청을 받았음을 Django에게 알려주는 설정입니다.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# 실제 도메인(HTTPS)으로 서비스할 준비가 완료되면 아래 주석을 해제하여 보안을 강화하세요.
# SECURE_SSL_REDIRECT = True        # 모든 HTTP 접속을 HTTPS로 자동 리다이렉트
# SESSION_COOKIE_SECURE = True      # HTTPS 연결에서만 로그인 세션 쿠키 전송
# CSRF_COOKIE_SECURE = True         # HTTPS 연결에서만 CSRF 보안 쿠키 전송


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 직접 만든 앱 등록
    'hts',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# PostgreSQL 설정
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',       # 구성하신 PostgreSQL 데이터베이스 이름으로 변경하세요
        'USER': 'yoojisang',     # 사용자명
        'PASSWORD': '1q2w3e4r', # 비밀번호
        'HOST': '127.0.0.1',    # DB 호스트 주소 (로컬인 경우 127.0.0.1)
        'PORT': '5432',         # 기본 포트
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]


# Internationalization
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 커스텀 유저 모델 설정 (필수!)
AUTH_USER_MODEL = 'hts.User'
