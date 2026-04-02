from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.views.decorators.http import require_POST
from .services import get_user_portfolio
from .models import User, Stock, DataFetchRequest
from .tasks import fetch_stock_data, process_pending_fetch_requests
import redis

def index(request):
    return render(request, 'hts/index.html')

def login_view(request):
    # 이미 로그인한 유저는 대시보드로 즉시 이동
    if request.user.is_authenticated:
        return redirect('hts:dashboard')
        
    error_message = None
    if request.method == "POST":
        # HTML form에서 전달된 데이터 받기
        username = request.POST.get("username")
        password = request.POST.get("password")
        
        # DB 회원 정보와 일치하는지 검증
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user) # 세션 로그인 처리
            return redirect('hts:dashboard') # 성공 시 대시보드로 이동
        else:
            error_message = "아이디 또는 비밀번호가 일치하지 않습니다."
            
    return render(request, 'hts/login.html', {'error_message': error_message})

def register_view(request):
    # 이미 로그인한 유저는 대시보드로 즉시 이동
    if request.user.is_authenticated:
        return redirect('hts:dashboard')
        
    error_message = None
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        password_confirm = request.POST.get("password_confirm")
        
        # 검증 로직
        if password != password_confirm:
            error_message = "비밀번호가 일치하지 않습니다. 다시 확인해 주세요."
        elif User.objects.filter(username=username).exists():
            error_message = "이미 존재하는 아이디입니다. 다른 아이디를 사용해 주세요."
        else:
            # 계정 생성 (비밀번호 자동 암호화 처리)
            User.objects.create_user(username=username, password=password)
            # 회원가입 성공 후 로그인 페이지로 이동
            return redirect('hts:login')
            
    return render(request, 'hts/register.html', {'error_message': error_message})

def logout_view(request):
    logout(request)
    return redirect('hts:index')

@login_required(login_url='/hts/login/')
def dashboard(request):
    # 1. Controller가 Service에게 비즈니스 로직 처리(계산)를 위임
    portfolio_data = get_user_portfolio(request.user)
    
    # 시장 목록을 가져옴 (중복 제거)
    markets = Stock.objects.values_list('market', flat=True).distinct()
    portfolio_data['markets'] = markets
    
    # 2. Service로부터 받은 결과를 Template(화면)으로 전달
    return render(request, 'hts/dashboard.html', portfolio_data)

# @login_required 데코레이터 제거 (비로그인 상태에서도 검색 가능하도록 수정)
def search_stocks(request):
    query = request.GET.get('q', '')
    market = request.GET.get('market', '')
    
    stocks = Stock.objects.all()
    
    if query:
        stocks = stocks.filter(name__icontains=query)
    
    if market:
        stocks = stocks.filter(market=market)
        
    results = [
        {'symbol': stock.symbol, 'name': stock.name, 'market': stock.market}
        for stock in stocks
    ]
    
    return JsonResponse({'results': results})

def info_lookup_view(request):
    return render(request, 'hts/info_lookup.html')

def stock_list_view(request):
    return render(request, 'hts/stock_list.html')

def stock_search_page_view(request):
    return render(request, 'hts/stock_search.html')

def dev_guide_view(request):
    return render(request, 'hts/dev_guide.html')

def task_lookup_view(request):
    """작업 조회 메인 페이지"""
    return render(request, 'hts/task_lookup.html')

def task_queue_list_view(request):
    """가격 조회 큐 조회 페이지 (페이지네이션)"""
    # 필터 파라미터 받기
    status_filter = request.GET.get('status', '')
    symbol_filter = request.GET.get('symbol', '')
    
    # 기본 쿼리셋
    tasks = DataFetchRequest.objects.all().order_by('-created_at')
    
    # 필터 적용
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if symbol_filter:
        tasks = tasks.filter(symbol__icontains=symbol_filter)
    
    # 페이지네이션 설정 (페이지당 10개)
    paginator = Paginator(tasks, 10)
    page = request.GET.get('page', 1)
    
    try:
        tasks_page = paginator.page(page)
    except PageNotAnInteger:
        tasks_page = paginator.page(1)
    except EmptyPage:
        tasks_page = paginator.page(paginator.num_pages)
    
    # 페이지 범위 계산 (현재 페이지 주변 2페이지씩 표시)
    current_page = tasks_page.number
    total_pages = paginator.num_pages
    
    page_range = []
    if total_pages <= 7:
        page_range = list(range(1, total_pages + 1))
    else:
        if current_page <= 3:
            page_range = list(range(1, 6)) + ['...', total_pages]
        elif current_page >= total_pages - 2:
            page_range = [1, '...'] + list(range(total_pages - 4, total_pages + 1))
        else:
            page_range = [1, '...'] + list(range(current_page - 1, current_page + 2)) + ['...', total_pages]
    
    # 상태별 개수 집계
    total_count = DataFetchRequest.objects.count()
    pending_count = DataFetchRequest.objects.filter(status='PENDING').count()
    processing_count = DataFetchRequest.objects.filter(status='PROCESSING').count()
    completed_count = DataFetchRequest.objects.filter(status='COMPLETED').count()
    failed_count = DataFetchRequest.objects.filter(status='FAILED').count()
    
    context = {
        'tasks': tasks_page,
        'page_range': page_range,
        'current_status': status_filter,
        'current_symbol': symbol_filter,
        'total_count': total_count,
        'pending_count': pending_count,
        'processing_count': processing_count,
        'completed_count': completed_count,
        'failed_count': failed_count,
    }
    
    return render(request, 'hts/task_queue_list.html', context)


@require_POST
def retry_failed_task(request, task_id):
    """FAILED 상태의 작업을 다시 PENDING으로 변경하고 큐에 넣음"""
    try:
        task = DataFetchRequest.objects.get(id=task_id)
        if task.status == 'FAILED':
            task.status = 'PENDING'
            task.save()
            # Celery 작업 실행
            fetch_stock_data.delay(task.id)
            return JsonResponse({'success': True, 'message': f'Task {task_id} 재시작됨'})
        return JsonResponse({'success': False, 'message': 'FAILED 상태의 작업만 재시작할 수 있습니다.'})
    except DataFetchRequest.DoesNotExist:
        return JsonResponse({'success': False, 'message': '작업을 찾을 수 없습니다.'})


@require_POST
def process_all_pending(request):
    """모든 PENDING 상태 작업을 큐에 넣음"""
    pending_tasks = DataFetchRequest.objects.filter(status='PENDING')
    count = 0
    for task in pending_tasks:
        fetch_stock_data.delay(task.id)
        count += 1
    return JsonResponse({'success': True, 'message': f'{count}개의 작업이 큐에 추가됨'})


@require_POST
def clear_completed_tasks(request):
    """COMPLETED 상태의 모든 작업 삭제"""
    deleted_count, _ = DataFetchRequest.objects.filter(status='COMPLETED').delete()
    return JsonResponse({'success': True, 'message': f'{deleted_count}개의 완료된 작업 삭제됨'})


def celery_queue_status(request):
    """Celery/Redis 큐 상태 확인 API"""
    if request.method == 'POST' and request.body:
        # POST with CSRF check for state-changing operations
        pass
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # 큐 길이 확인
        queue_len = r.llen('celery')
        
        # 스케줄된 작업 확인 (Celery beat)
        scheduled = r.zrange('celery:schedule', 0, -1, withscores=True)
        
        # 큐 내용 샘플 (최대 5개)
        queue_items = r.lrange('celery', 0, 4)
        queue_sample = []
        for item in queue_items:
            try:
                import json
                data = json.loads(item)
                queue_sample.append({
                    'task': data.get('headers', {}).get('task', 'unknown'),
                    'id': data.get('headers', {}).get('id', 'unknown')[:8] + '...'
                })
            except:
                queue_sample.append({'raw': str(item)[:50]})
        
        return JsonResponse({
            'success': True,
            'queue_length': queue_len,
            'scheduled_count': len(scheduled),
            'queue_sample': queue_sample,
            'pending_db_count': DataFetchRequest.objects.filter(status='PENDING').count(),
            'processing_db_count': DataFetchRequest.objects.filter(status='PROCESSING').count(),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
