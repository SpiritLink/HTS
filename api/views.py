from django.http import JsonResponse
from django.views import View
import json
# from hts.models import Stock # hts 모델에서 가져온다고 가정

class StockAPIView(View):
    def get(self, request):
        # 주가 정보 조회 로직 스켈레톤
        data = {
            "status": "success",
            "message": "Stock list retrieved successfully",
            "data": []
        }
        return JsonResponse(data)

    def post(self, request):
        # 주가 정보 추가 로직 스켈레톤
        try:
            body = json.loads(request.body)
            # 데이터 처리 로직
            
            data = {
                "status": "success",
                "message": "Stock added successfully"
            }
            return JsonResponse(data, status=201)
        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)