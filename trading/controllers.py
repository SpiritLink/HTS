from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .services import get_user_portfolio

def index(request):
    return HttpResponse("""
    <h1>주식 거래 시스템 (HTS) - Django</h1>
    <p>장고 서버가 정상적으로 실행 중입니다.</p>
    <hr>
    <p>🔑 <a href="/login/"><b>로그인 화면으로 이동하기</b></a></p>
    <p>⚙️ <b>관리자 페이지:</b> <a href="/admin/">/admin/</a></p>
    """)

def login_view(request):
    # 이미 로그인한 유저는 대시보드로 즉시 이동
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    error_message = None
    if request.method == "POST":
        # HTML form에서 전달된 데이터 받기
        username = request.POST.get("username")
        password = request.POST.get("password")
        
        # DB 회원 정보와 일치하는지 검증
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user) # 세션 로그인 처리
            return redirect('dashboard') # 성공 시 대시보드로 이동
        else:
            error_message = "아이디 또는 비밀번호가 일치하지 않습니다."
            
    return render(request, 'trading/login.html', {'error_message': error_message})

def logout_view(request):
    logout(request)
    return redirect('index')

@login_required(login_url='/login/')
def dashboard(request):
    # 1. Controller가 Service에게 비즈니스 로직 처리(계산)를 위임
    portfolio_data = get_user_portfolio(request.user)
    
    # 2. Service로부터 받은 결과를 Template(화면)으로 전달
    return render(request, 'trading/dashboard.html', portfolio_data)