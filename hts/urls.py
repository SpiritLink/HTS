from django.urls import path
from . import controllers

app_name = 'hts'

urlpatterns = [
    path('', controllers.index, name='index'),
    path('login/', controllers.login_view, name='login'),
    path('register/', controllers.register_view, name='register'),
    path('logout/', controllers.logout_view, name='logout'),
    path('dashboard/', controllers.dashboard, name='dashboard'),
    path('search_stocks/', controllers.search_stocks, name='search_stocks'),
    path('info/', controllers.info_lookup_view, name='info_lookup'),
    path('info/list/', controllers.stock_list_view, name='stock_list'),
    path('info/search/', controllers.stock_search_page_view, name='stock_search_page'),
    path('guide/', controllers.dev_guide_view, name='dev_guide'),
]