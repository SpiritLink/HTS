import os
from datetime import timedelta
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
    
    # Third-party apps
    'rest_framework',
    'django_celery_beat',
    
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
                'hts.context_processors.mobile_scale_settings',  # 모바일 화면 축소 설정
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

# Django REST Framework 설정
REST_FRAMEWORK = {
    # 'DEFAULT_AUTHENTICATION_CLASSES': [
    #     'rest_framework.authentication.SessionAuthentication',
    # ],
    # 'DEFAULT_PERMISSION_CLASSES': [
    #     'rest_framework.permissions.IsAuthenticated',
    # ],
}

# ==========================================
# Redis 설정
# ==========================================

# Redis 서버 설정
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB_CELERY = int(os.environ.get('REDIS_DB_CELERY', 0))  # Celery용 DB
REDIS_DB_CACHE = int(os.environ.get('REDIS_DB_CACHE', 1))     # 캐싱용 DB

# 주식 가격 캐싱 설정
STOCK_PRICE_CACHE_TTL = int(os.environ.get('STOCK_PRICE_CACHE_TTL', 3600))  # 기본 1시간

# ==========================================
# Celery 설정
# ==========================================

# Redis를 브로커로 사용
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CELERY}')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CELERY}')

# 직렬화 설정
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# 타임존 설정
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Celery Beat 스케줄 설정
CELERY_BEAT_SCHEDULE = {
    # 1분마다 PENDING 상태의 요청 처리
    'process-pending-fetch-requests': {
        'task': 'hts.tasks.process_pending_fetch_requests',
        'schedule': 60.0,  # 60초
    },
    # 매일 새벽 3시에 오래된 완료된 요청 정리
    'cleanup-old-requests': {
        'task': 'hts.tasks.cleanup_old_completed_requests',
        'schedule': timedelta(days=1),
        'kwargs': {'days': 7},  # 7일 이상 지난 요청 삭제
    },
}