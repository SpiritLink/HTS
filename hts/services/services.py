def get_user_portfolio(user):
    """
    [Service Layer]
    사용자의 이벤트 소싱 거래 내역과 스냅샷을 기반으로 현재 보유 주식 수량과 잔액을 계산합니다.
    """
    from hts.event_sourcing import reconstruct_user_state
    balance, portfolio = reconstruct_user_state(user)
    return {
        'balance': balance,
        'portfolio': portfolio
    }