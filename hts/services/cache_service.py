"""
주식 가격 정보 캐싱 서비스
- Redis를 사용하여 주식 가격 데이터 캐싱
- 조회 시 캐시 확인 → 없으면 DB 조회 후 캐싱
- 저장 시 캐시 무효화
"""
import redis
import json
import pickle
from datetime import datetime
from django.conf import settings
from typing import List, Optional, Tuple


class StockPriceCache:
    """주식 가격 정보 Redis 캐싱 클래스"""
    
    def __init__(self, host=None, port=None, db=None, ttl=None):
        # Django settings에서 설정 가져오기 (없으면 기본값)
        host = host or getattr(settings, 'REDIS_HOST', 'localhost')
        port = port or getattr(settings, 'REDIS_PORT', 6379)
        db = db or getattr(settings, 'REDIS_DB_CACHE', 1)
        ttl = ttl or getattr(settings, 'STOCK_PRICE_CACHE_TTL', 3600)
        """
        Args:
            host: Redis 호스트
            port: Redis 포트
            db: Redis 데이터베이스 번호
            ttl: 캐시 만료 시간 (초), 기본 1시간
        """
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=False  # binary 데이터 처리를 위해 False
        )
        self.ttl = ttl
        self.key_prefix = "stock_price"
    
    def _make_key(self, symbol: str, interval: str, start_date, end_date) -> str:
        """캐시 키 생성"""
        start_str = start_date.strftime('%Y%m%d') if hasattr(start_date, 'strftime') else str(start_date).replace('-', '')
        end_str = end_date.strftime('%Y%m%d') if hasattr(end_date, 'strftime') else str(end_date).replace('-', '')
        return f"{self.key_prefix}:{symbol}:{interval}:{start_str}:{end_str}"
    
    def _make_pattern(self, symbol: str, interval: str = None) -> str:
        """캐시 삭제를 위한 패턴 생성"""
        if interval:
            return f"{self.key_prefix}:{symbol}:{interval}:*"
        return f"{self.key_prefix}:{symbol}:*"
    
    def get(self, symbol: str, interval: str, start_date, end_date) -> Optional[List[dict]]:
        """
        캐시에서 주식 가격 데이터 조회
        
        Returns:
            캐시된 데이터 리스트 또는 None
        """
        try:
            key = self._make_key(symbol, interval, start_date, end_date)
            cached_data = self.redis_client.get(key)
            
            if cached_data:
                # pickle로 직렬화된 데이터 복원
                data = pickle.loads(cached_data)
                return data
            return None
        except Exception as e:
            # 캐시 오류 시 로깅하고 None 반환 (DB fallback)
            print(f"[Cache Error] get: {e}")
            return None
    
    def set(self, symbol: str, interval: str, start_date, end_date, data: List[dict]) -> bool:
        """
        주식 가격 데이터를 캐시에 저장
        
        Returns:
            저장 성공 여부
        """
        try:
            key = self._make_key(symbol, interval, start_date, end_date)
            # pickle로 직렬화 (datetime 객체 등 복잡한 타입 처리)
            serialized_data = pickle.dumps(data)
            self.redis_client.setex(key, self.ttl, serialized_data)
            return True
        except Exception as e:
            print(f"[Cache Error] set: {e}")
            return False
    
    def delete(self, symbol: str, interval: str = None) -> int:
        """
        특정 종목의 캐시 삭제
        
        Args:
            symbol: 종목 코드
            interval: 데이터 간격 (None이면 해당 종목의 모든 간격 캐시 삭제)
        
        Returns:
            삭제된 키 수
        """
        try:
            pattern = self._make_pattern(symbol, interval)
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            print(f"[Cache Error] delete: {e}")
            return 0
    
    def delete_range(self, symbol: str, interval: str, start_date, end_date) -> int:
        """
        특정 기간의 캐시 삭제
        
        Returns:
            삭제된 키 수
        """
        try:
            key = self._make_key(symbol, interval, start_date, end_date)
            return self.redis_client.delete(key)
        except Exception as e:
            print(f"[Cache Error] delete_range: {e}")
            return 0


# 전역 캐시 인스턴스 (싱글톤 패턴)
_stock_price_cache = None


def get_stock_price_cache() -> StockPriceCache:
    """StockPriceCache 싱글톤 인스턴스 반환"""
    global _stock_price_cache
    if _stock_price_cache is None:
        _stock_price_cache = StockPriceCache()
    return _stock_price_cache


def get_cached_prices(symbol: str, interval: str, start_date, end_date) -> Tuple[bool, Optional[List[dict]]]:
    """
    캐시된 주식 가격 데이터 조회
    
    Returns:
        (캐시 히트 여부, 데이터)
    """
    cache = get_stock_price_cache()
    data = cache.get(symbol, interval, start_date, end_date)
    if data is not None:
        return True, data
    return False, None


def cache_prices(symbol: str, interval: str, start_date, end_date, data: List[dict]) -> bool:
    """주식 가격 데이터 캐싱"""
    cache = get_stock_price_cache()
    return cache.set(symbol, interval, start_date, end_date, data)


def invalidate_price_cache(symbol: str, interval: str = None) -> int:
    """
    주식 가격 캐시 무효화
    - DB에 새 데이터 저장 후 호출하여 캐시 삭제
    """
    cache = get_stock_price_cache()
    return cache.delete(symbol, interval)
