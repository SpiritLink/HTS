def get_user_portfolio(user):
    """
    [Service Layer]
    사용자의 주문 내역(Order)을 바탕으로 현재 보유 주식 수량과 잔액을 계산합니다.
    """
    portfolio = {}
    
    # 매수/매도 주문을 종합하여 현재 보유 주식 수량 계산
    for order in user.orders.all():
        if order.order_type == "BUY":
            portfolio[order.stock_symbol] = portfolio.get(order.stock_symbol, 0) + order.quantity
        elif order.order_type == "SELL":
            portfolio[order.stock_symbol] = portfolio.get(order.stock_symbol, 0) - order.quantity
            
    # 수량이 0보다 큰(실제 보유 중인) 주식만 필터링
    active_portfolio = {symbol: qty for symbol, qty in portfolio.items() if qty > 0}
    
    return {
        'balance': user.balance,
        'portfolio': active_portfolio
    }