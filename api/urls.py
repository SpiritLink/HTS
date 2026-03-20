from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    path('stocks/', views.StockAPIView.as_view(), name='stock-list'),
]