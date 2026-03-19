from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls), # 기본 제공되는 강력한 관리자 페이지
    path('', include('trading.urls')),
]