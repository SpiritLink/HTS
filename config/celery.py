import os
from celery import Celery

# Django의 settings 모듈을 Celery의 기본 설정 모듈로 지정합니다.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('HTS')

# Django 설정 파일에서 'CELERY_'로 시작하는 모든 설정을 Celery가 사용하도록 합니다.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Django의 등록된 모든 앱에서 task 모듈을 자동으로 찾아 로드합니다.
app.autodiscover_tasks()
