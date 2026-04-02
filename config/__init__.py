# Celery 앱을 Django 시작 시 자동으로 로드합니다.
from .celery import app as celery_app

__all__ = ('celery_app',)
