"""
모바일 화면 축소 비율 및 폰트 크기 설정 Context Processor

이 파일의 값을 변경하면 모든 페이지의 모바일 화면 비율과 폰트 크기가 조절됩니다.
"""

# =============================================================================
# 모바일 화면 축소 설정 - 이 값들을 변경하세요
# =============================================================================

# viewport initial-scale 값 (기본: 0.5)
# 값이 작을수록 화면에 더 많은 내용이 표시됩니다
# 예: 0.3 = 매우 작게, 0.5 = 작게, 0.7 = 중간, 1.0 = 원본 크기
MOBILE_INITIAL_SCALE = 0.75

# CSS zoom 값 - 768px 이하 화면 (기본: 0.8)
MOBILE_ZOOM_SCALE = 0.8

# CSS zoom 값 - 480px 이하 화면 (기본: 0.7)
MOBILE_ZOOM_SCALE_SMALL = 0.7

# =============================================================================
# 폰트 크기 설정 - 이 값들을 변경하세요
# =============================================================================

# 기본 폰트 크기 (px)
FONT_SIZE_BASE = 14

# 제목 폰트 크기 (px)
FONT_SIZE_TITLE = 26

# 부제목 폰트 크기 (px)
FONT_SIZE_SUBTITLE = 18

# 본문 폰트 크기 (px)
FONT_SIZE_BODY = 14

# 작은 폰트 크기 (px)
FONT_SIZE_SMALL = 12

# 버튼 폰트 크기 (px)
FONT_SIZE_BUTTON = 16

# =============================================================================


def mobile_scale_settings(request):
    """
    모든 템플릿에서 모바일 화면 축소 설정과 폰트 크기를 사용할 수 있게 합니다.
    
    템플릿에서 사용 방법:
    - {{ mobile_initial_scale }} : viewport initial-scale 값
    - {{ mobile_zoom_scale }} : 768px 이하 zoom 값
    - {{ mobile_zoom_scale_small }} : 480px 이하 zoom 값
    - {{ font_size_base }} : 기본 폰트 크기
    - {{ font_size_title }} : 제목 폰트 크기
    - {{ font_size_subtitle }} : 부제목 폰트 크기
    - {{ font_size_body }} : 본문 폰트 크기
    - {{ font_size_small }} : 작은 폰트 크기
    - {{ font_size_button }} : 버튼 폰트 크기
    """
    return {
        'mobile_initial_scale': MOBILE_INITIAL_SCALE,
        'mobile_zoom_scale': MOBILE_ZOOM_SCALE,
        'mobile_zoom_scale_small': MOBILE_ZOOM_SCALE_SMALL,
        'font_size_base': FONT_SIZE_BASE,
        'font_size_title': FONT_SIZE_TITLE,
        'font_size_subtitle': FONT_SIZE_SUBTITLE,
        'font_size_body': FONT_SIZE_BODY,
        'font_size_small': FONT_SIZE_SMALL,
        'font_size_button': FONT_SIZE_BUTTON,
    }
