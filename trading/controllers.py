from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .services import get_user_portfolio
from .models import User

def index(request):
    return render(request, 'trading/index.html')

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

def register_view(request):
    # 이미 로그인한 유저는 대시보드로 즉시 이동
    if request.user.is_authenticated:
        return redirect('dashboard')
        
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
            return redirect('login')
            
    return render(request, 'trading/register.html', {'error_message': error_message})

def logout_view(request):
    logout(request)
    return redirect('index')

@login_required(login_url='/login/')
def dashboard(request):
    # 1. Controller가 Service에게 비즈니스 로직 처리(계산)를 위임
    portfolio_data = get_user_portfolio(request.user)
    
    # 2. Service로부터 받은 결과를 Template(화면)으로 전달
    return render(request, 'trading/dashboard.html', portfolio_data)