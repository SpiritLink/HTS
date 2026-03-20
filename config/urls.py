from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls), # 기본 제공되는 강력한 관리자 페이지
    path('hts/', include('hts.urls')),
    path('api/', include('api.urls', namespace='api')),
    path('', RedirectView.as_view(url='/hts/', permanent=False)),
]