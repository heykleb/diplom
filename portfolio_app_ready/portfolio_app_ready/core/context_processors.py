from django.core.cache import cache
from .models import Asset


def portfolio_data(request):
    if not request.user.is_authenticated:
        return {
            'sidebar_total_amount':  0,
            'sidebar_portfolio_return': 0,
        }

    cache_key = f'sidebar_{request.user.id}'
    cached    = cache.get(cache_key)
    if cached:
        return cached

    assets       = Asset.objects.filter(owner=request.user).only('amount', 'expected_return')
    total_amount = sum(float(a.amount) for a in assets)

    portfolio_return = 0
    for asset in assets:
        weight = float(asset.amount) / total_amount if total_amount > 0 else 0
        portfolio_return += weight * asset.expected_return

    data = {
        'sidebar_total_amount':     round(total_amount, 2),
        'sidebar_portfolio_return': round(portfolio_return, 2),
    }

    cache.set(cache_key, data, 60)  # 1 минута
    return data