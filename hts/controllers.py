from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.views.decorators.http import require_POST
from hts.services.services import get_user_portfolio
from .models import User, Stock, DataFetchRequest, StockPrice, StockTradingCalendar
from .tasks import fetch_stock_data, process_pending_fetch_requests
from .cache_service import get_all_cache_items, delete_cache_items, delete_all_cache
from datetime import datetime, timedelta
import redis
import json


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
    
    from django.db.models import Q
    
    stocks = Stock.objects.all()
    
    if query:
        # 종목명으로만 검색 (종목코드 검색 제외)
        stocks = stocks.filter(name__icontains=query)
    
    if market:
        # 시장 필터링 - stock_list.html과 동일한 로직
        if market == 'KR':
            stocks = stocks.filter(market__in=['KR', 'KOSPI'])
        elif market == 'KQ':
            stocks = stocks.filter(market__in=['KQ', 'KOSDAQ'])
        else:
            stocks = stocks.filter(market=market)
        
    results = [
        {'symbol': stock.symbol, 'name': stock.name, 'market': stock.market}
        for stock in stocks[:20]  # 최대 20개 결과
    ]
    
    return JsonResponse({'results': results})


def info_lookup_view(request):
    return render(request, 'hts/info_lookup.html')


def stock_list_view(request):
    return render(request, 'hts/stock_list.html')


def stock_chart_view(request, symbol):
    """주식 차트 상세 페이지"""
    from .models import Stock
    try:
        stock = Stock.objects.get(symbol=symbol)
    except Stock.DoesNotExist:
        stock = None
    return render(request, 'hts/stock_chart.html', {'stock': stock, 'symbol': symbol})


def dev_guide_view(request):
    return render(request, 'hts/dev_guide.html')


def task_lookup_view(request):
    """작업 조회 메인 페이지"""
    return render(request, 'hts/task_lookup.html')


def task_register_view(request):
    """가격 정보 작업 등록 페이지"""
    return render(request, 'hts/task_register.html')


def task_queue_list_view(request):
    """가격 조회 큐 조회 페이지 (FAILED와 non-FAILED 분리 표시)"""
    # 필터 파라미터 받기 (심볼 필터는 계속 지원)
    symbol_filter = request.GET.get('symbol', '')
    
    # FAILED가 아닌 작업 (PENDING, PROCESSING, COMPLETED) - 최근 20개
    non_failed_tasks = DataFetchRequest.objects.exclude(
        status='FAILED'
    ).order_by('-created_at')
    
    # FAILED 작업 - 최근 20개
    failed_tasks = DataFetchRequest.objects.filter(
        status='FAILED'
    ).order_by('-created_at')
    
    # 심볼 필터 적용
    if symbol_filter:
        non_failed_tasks = non_failed_tasks.filter(symbol__icontains=symbol_filter)
        failed_tasks = failed_tasks.filter(symbol__icontains=symbol_filter)
    
    # 각각 상위 20개로 제한
    non_failed_tasks = non_failed_tasks[:20]
    failed_tasks = failed_tasks[:20]
    
    # 상태별 개수 집계
    total_count = DataFetchRequest.objects.count()
    pending_count = DataFetchRequest.objects.filter(status='PENDING').count()
    processing_count = DataFetchRequest.objects.filter(status='PROCESSING').count()
    completed_count = DataFetchRequest.objects.filter(status='COMPLETED').count()
    failed_count = DataFetchRequest.objects.filter(status='FAILED').count()
    
    context = {
        'non_failed_tasks': non_failed_tasks,
        'failed_tasks': failed_tasks,
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
def retry_all_failed(request):
    """모든 FAILED 상태의 작업을 PENDING으로 변경"""
    try:
        failed_tasks = DataFetchRequest.objects.filter(status='FAILED')
        count = failed_tasks.count()
        
        if count == 0:
            return JsonResponse({
                'success': True,
                'count': 0,
                'message': 'FAILED 상태의 작업이 없습니다.'
            })
        
        # FAILED -> PENDING 상태 변경
        failed_tasks.update(status='PENDING')
        
        # Celery 큐에 등록
        for task in failed_tasks:
            fetch_stock_data.delay(task.id)
        
        return JsonResponse({
            'success': True,
            'count': count,
            'message': f'{count}개의 FAILED 작업을 PENDING 상태로 변경하고 큐에 등록했습니다.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'재시도 중 오류 발생: {str(e)}'
        }, status=500)


@require_POST
def retry_failed_limit(request):
    """지정된 개수만큼 FAILED 상태의 작업을 PENDING으로 변경"""
    try:
        limit = int(request.GET.get('limit', 100))
        
        # FAILED 상태의 작업을 지정된 개수만큼 가져오기 (created_at 오름차순 - 오래된 것부터)
        failed_tasks = DataFetchRequest.objects.filter(
            status='FAILED'
        ).order_by('created_at')[:limit]
        
        count = 0
        for task in failed_tasks:
            task.status = 'PENDING'
            task.save()
            # Celery 큐에 등록
            fetch_stock_data.delay(task.id)
            count += 1
        
        if count == 0:
            return JsonResponse({
                'success': True,
                'count': 0,
                'message': 'FAILED 상태의 작업이 없습니다.'
            })
        
        return JsonResponse({
            'success': True,
            'count': count,
            'message': f'{count}개의 FAILED 작업을 PENDING 상태로 변경하고 큐에 등록했습니다.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'재시도 중 오류 발생: {str(e)}'
        }, status=500)


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


def queue_summary_api(request):
    """작업 큐 요약 정보 API (task_queue_list와 동일한 데이터)"""
    try:
        total_count = DataFetchRequest.objects.count()
        pending_count = DataFetchRequest.objects.filter(status='PENDING').count()
        processing_count = DataFetchRequest.objects.filter(status='PROCESSING').count()
        completed_count = DataFetchRequest.objects.filter(status='COMPLETED').count()
        failed_count = DataFetchRequest.objects.filter(status='FAILED').count()
        
        return JsonResponse({
            'success': True,
            'total_count': total_count,
            'pending_count': pending_count,
            'processing_count': processing_count,
            'completed_count': completed_count,
            'failed_count': failed_count
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def redis_cache_view(request):
    """Redis 캐시 조회 페이지"""
    return render(request, 'hts/redis_cache.html')


def redis_cache_list_api(request):
    """Redis 캐시 목록 조회 API"""
    try:
        items = get_all_cache_items()
        return JsonResponse({
            'success': True,
            'count': len(items),
            'items': items
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
def redis_cache_delete_selected(request):
    """선택한 Redis 캐시 항목 삭제 API"""
    try:
        data = json.loads(request.body)
        keys = data.get('keys', [])
        
        if not keys:
            return JsonResponse({
                'success': False,
                'message': '삭제할 항목을 선택해주세요.'
            })
        
        deleted_count = delete_cache_items(keys)
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count}개의 캐시 항목이 삭제되었습니다.',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
def redis_cache_delete_all(request):
    """모든 Redis 캐시 삭제 API"""
    try:
        deleted_count = delete_all_cache()
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count}개의 캐시 항목이 모두 삭제되었습니다.',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_incomplete_stocks(request):
    """
    기간 내에 가격 정보가 불충분한 종목들을 조회하는 API
    """
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    interval = request.GET.get('interval', '1d')  # 기본값: 일별
    
    if not start_date_str or not end_date_str:
        return JsonResponse({
            'success': False,
            'message': '시작일과 종료일이 필요합니다.'
        }, status=400)
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': '잘못된 날짜 형식입니다. (YYYY-MM-DD)'
        }, status=400)
    
    if start_date > end_date:
        return JsonResponse({
            'success': False,
            'message': '시작일은 종료일보다 이전이어야 합니다.'
        }, status=400)
    
    # 거래일 수 계산 (주말 제외)
    total_days = (end_date - start_date).days + 1
    trading_days = sum(1 for d in range(total_days) 
                      if (start_date + timedelta(days=d)).weekday() < 5)
    
    # interval에 따른 예상 데이터 수 계산
    if interval == '1d':
        expected_count = trading_days
    elif interval == '1h':
        # 한국: 09:00~15:30 (6.5시간), 미국: 09:30~16:00 (6.5시간) -> 대략 7시간
        expected_count = trading_days * 7
    elif interval == '30m':
        expected_count = trading_days * 7 * 2  # 시간당 2개
    elif interval == '15m':
        expected_count = trading_days * 7 * 4  # 시간당 4개
    elif interval == '5m':
        expected_count = trading_days * 7 * 12  # 시간당 12개
    else:
        expected_count = trading_days
    
    # 모든 종목 조회
    stocks = Stock.objects.all()
    incomplete_stocks = []
    
    for stock in stocks:
        # 해당 기간의 해당 interval 데이터 수 조회
        data_count = StockPrice.objects.filter(
            symbol=stock.symbol,
            interval=interval,
            timestamp__date__range=(start_date, end_date)
        ).count()
        
        # 80% 미만인 경우만 포함
        threshold = int(expected_count * 0.8)
        
        if data_count < threshold:
            incomplete_stocks.append({
                'symbol': stock.symbol,
                'name': stock.name,
                'market': stock.market,
                'data_count': data_count,
                'expected_count': expected_count,
                'missing_count': expected_count - data_count,
                'fill_rate': round((data_count / expected_count) * 100, 1) if expected_count > 0 else 0
            })
    
    # 부족률 기준으로 정렬 (채워진 비율이 낮은 순)
    incomplete_stocks.sort(key=lambda x: x['fill_rate'])
    
    return JsonResponse({
        'success': True,
        'stocks': incomplete_stocks,
        'interval': interval,
        'trading_days': trading_days,
        'count': len(incomplete_stocks)
    })


@require_POST
def bulk_request_prices(request):
    """
    선택한 종목들의 기간별 가격 정보를 요청하는 API
    """
    try:
        data = json.loads(request.body)
        symbols = data.get('symbols', [])
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        interval = data.get('interval', '1d')  # 기본값: 일별
        
        if not symbols or not start_date_str or not end_date_str:
            return JsonResponse({
                'success': False,
                'message': '종목, 시작일, 종료일이 모두 필요합니다.'
            }, status=400)
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        registered_count = 0
        already_exists_count = 0
        restarted_count = 0
        
        for symbol in symbols:
            # 이미 진행 중인 요청인지 확인 (PENDING/PROCESSING)
            existing_active = DataFetchRequest.objects.filter(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                status__in=['PENDING', 'PROCESSING']
            ).first()
            
            if existing_active:
                already_exists_count += 1
                continue
            
            # COMPLETED/FAILED 상태의 기존 요청이 있으면 재시작, 없으면 새로 생성
            obj, created = DataFetchRequest.objects.update_or_create(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                defaults={'status': 'PENDING'}
            )
            
            if created:
                registered_count += 1
            else:
                restarted_count += 1
        
        # 결과 메시지 구성
        message_parts = []
        if registered_count > 0:
            message_parts.append(f'신규 {registered_count}개')
        if restarted_count > 0:
            message_parts.append(f'재시작 {restarted_count}개')
        if already_exists_count > 0:
            message_parts.append(f'진행중 {already_exists_count}개')
        
        message = ', '.join(message_parts) + f' 작업 처리 완료 (간격: {interval})'
        
        return JsonResponse({
            'success': True,
            'registered_count': registered_count,
            'restarted_count': restarted_count,
            'already_exists_count': already_exists_count,
            'interval': interval,
            'message': message
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': '잘못된 JSON 형식입니다.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


def stock_update_view(request):
    """종목 정보 갱신 페이지"""
    return render(request, 'hts/stock_update.html')


@require_POST
def update_stocks_from_nasdaq(request):
    """
    FinanceDataReader(KOSPI/KOSDAQ) 및 Nasdaq API에서 종목 정보를 가져와 DB를 갱신하는 API
    """
    import requests
    from datetime import datetime
    
    try:
        data = json.loads(request.body)
        market_type = data.get('market', 'KOSPI')  # KOSPI, KOSDAQ, NASDAQ, NYSE, AMEX
        
        updated_count = 0
        created_count = 0
        skipped_count = 0
        errors = []
        
        # 한국 시장 (FinanceDataReader 사용)
        if market_type in ['KOSPI', 'KOSDAQ']:
            try:
                import FinanceDataReader as fdr
                import traceback
                import ssl
                
        # SSL 인증서 검증 우회 (개발 환경용)
                ssl._create_default_https_context = ssl._create_unverified_context
                
                # FinanceDataReader로 종목 리스트 가져오기
                df = fdr.StockListing(market_type)
                
                if df is None or df.empty:
                    errors.append(f'{market_type}: 데이터를 가져올 수 없습니다.')
                else:
                    for _, row in df.iterrows():
                        try:
                            symbol = str(row.get('Code', '')).strip()
                            name = str(row.get('Name', '')).strip()[:200]  # 200자로 제한
                            
                            if not symbol or not name:
                                continue
                            
                            # 시장 타입 설정
                            market = market_type
                            
                            # 기존 종목 확인
                            try:
                                stock = Stock.objects.get(symbol=symbol)
                                # 정보가 완전히 일치하는지 확인
                                if stock.name == name and stock.market == market:
                                    skipped_count += 1  # 변경 없음 - 스킵
                                else:
                                    # 정보 업데이트
                                    stock.name = name
                                    stock.market = market
                                    stock.save()
                                    updated_count += 1
                            except Stock.DoesNotExist:
                                # 신규 생성
                                Stock.objects.create(
                                    symbol=symbol,
                                    name=name,
                                    market=market
                                )
                                created_count += 1
                                
                        except Exception as e:
                            errors.append(f'{symbol}: {str(e)}')
                            continue
                        
            except ImportError as e:
                errors.append(f'FinanceDataReader 라이브러리 오류: {str(e)}')
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                errors.append(f'{market_type} 처리 중 오류: {str(e)}')
                # 로그에 상세 오류 기록
                print(f"[ERROR] FinanceDataReader {market_type}: {error_detail}")
        
        # 미국 시장 (Nasdaq API 사용)
        else:
            exchanges = []
            if market_type == 'NASDAQ':
                exchanges.append('NASDAQ')
            elif market_type == 'NYSE':
                exchanges.append('NYSE')
            elif market_type == 'AMEX':
                exchanges.append('AMEX')
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin': 'https://www.nasdaq.com',
                'Referer': 'https://www.nasdaq.com/',
            }
            
            for exchange in exchanges:
                try:
                    # Nasdaq API v2 - JSON 형식
                    url = f'https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&offset=0&exchange={exchange}'
                    
                    response = requests.get(url, headers=headers, timeout=60)
                    response.raise_for_status()
                    
                    data_json = response.json()
                    
                    # 응답 구조 확인
                    if not data_json.get('data') or not data_json['data'].get('table') or not data_json['data']['table'].get('rows'):
                        errors.append(f'{exchange}: 데이터가 비어있습니다.')
                        continue
                    
                    rows = data_json['data']['table']['rows']
                    
                    for row in rows:
                        try:
                            symbol = row.get('symbol', '').strip()
                            name = row.get('name', '').strip()[:200]  # 200자로 제한
                            
                            if not symbol or not name:
                                continue
                            
                            # 티커 심볼 정제 (예: ^IXIC 제외)
                            if '^' in symbol or '/' in symbol:
                                continue
                                
                            # 시장 타입 설정
                            market = exchange
                            
                            # 기존 종목 확인
                            try:
                                stock = Stock.objects.get(symbol=symbol)
                                # 정보가 완전히 일치하는지 확인
                                if stock.name == name and stock.market == market:
                                    skipped_count += 1  # 변경 없음 - 스킵
                                else:
                                    # 정보 업데이트
                                    stock.name = name
                                    stock.market = market
                                    stock.save()
                                    updated_count += 1
                            except Stock.DoesNotExist:
                                # 신규 생성
                                Stock.objects.create(
                                    symbol=symbol,
                                    name=name,
                                    market=market
                                )
                                created_count += 1
                                
                        except Exception as e:
                            errors.append(f'{symbol}: {str(e)}')
                            continue
                            
                except Exception as e:
                    errors.append(f'{exchange} 처리 중 오류: {str(e)}')
                    continue
        
        total_processed = created_count + updated_count + skipped_count
        return JsonResponse({
            'success': True,
            'message': f'종목 정보 갱신 완료 (신규: {created_count}개, 갱신: {updated_count}개, 스킵: {skipped_count}개)',
            'created_count': created_count,
            'updated_count': updated_count,
            'skipped_count': skipped_count,
            'total_processed': total_processed,
            'errors': errors[:10] if errors else []  # 최대 10개 오류만 반환
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': '잘못된 JSON 형식입니다.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'종목 정보 갱신 중 오류 발생: {str(e)}'
        }, status=500)
