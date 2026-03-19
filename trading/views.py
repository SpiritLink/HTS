import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

def index(request):
    return HttpResponse("""
    <h1>주식 거래 시스템 (HTS) - Django</h1>
    <p>장고 서버가 정상적으로 실행 중입니다.</p>
    """)

@csrf_exempt
def login_api(request):
    if request.method == "POST":
        data = json.loads(request.body)
        username = data.get("username")
        password = data.get("password")
        
        # 장고에 내장된 authenticate()를 사용하여 손쉽게 로그인 검증이 가능합니다.
        return JsonResponse({
            "message": f"{username}님, 환영합니다!",
            "access_token": "fake-jwt-token"
        })

def get_portfolio(request, username):
    return JsonResponse({
        "username": username,
        "balance": 10000000,
        "stocks": {"삼성전자": 50, "애플": 10}
    })