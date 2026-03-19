from django.urls import path
from . import controllers

urlpatterns = [
    path('', controllers.index, name='index'),
    path('login/', controllers.login_view, name='login'),
    path('register/', controllers.register_view, name='register'),
    path('logout/', controllers.logout_view, name='logout'),
    path('dashboard/', controllers.dashboard, name='dashboard'),
]