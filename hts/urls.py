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
    path('info/chart/<str:symbol>/', controllers.stock_chart_view, name='stock_chart'),
    path('info/update/', controllers.stock_update_view, name='stock_update'),
    path('info/update/api/', controllers.update_stocks_from_nasdaq, name='update_stocks_api'),
    path('guide/', controllers.dev_guide_view, name='dev_guide'),
    path('tasks/', controllers.task_lookup_view, name='task_lookup'),
    path('tasks/register/', controllers.task_register_view, name='task_register'),
    path('tasks/queue/', controllers.task_queue_list_view, name='task_queue_list'),
    path('api/stocks/incomplete-data/', controllers.get_incomplete_stocks, name='incomplete_stocks'),
    path('api/stocks/bulk-request/', controllers.bulk_request_prices, name='bulk_request_prices'),
    path('tasks/queue/retry/<int:task_id>/', controllers.retry_failed_task, name='retry_task'),
    path('tasks/queue/retry-all-failed/', controllers.retry_all_failed, name='retry_all_failed'),
    path('tasks/queue/retry-failed/', controllers.retry_failed_limit, name='retry_failed_limit'),
    path('tasks/queue/process-pending/', controllers.process_all_pending, name='process_pending'),
    path('tasks/queue/clear-completed/', controllers.clear_completed_tasks, name='clear_completed'),
    path('tasks/queue/celery-status/', controllers.celery_queue_status, name='celery_status'),  # GET/POST 모두 허용
    path('api/queue-summary/', controllers.queue_summary_api, name='queue_summary'),
    path('tasks/redis-cache/', controllers.redis_cache_view, name='redis_cache'),
    path('tasks/redis-cache/api/list/', controllers.redis_cache_list_api, name='redis_cache_list'),
    path('tasks/redis-cache/api/delete-selected/', controllers.redis_cache_delete_selected, name='redis_cache_delete_selected'),
    path('tasks/redis-cache/api/delete-all/', controllers.redis_cache_delete_all, name='redis_cache_delete_all'),
]