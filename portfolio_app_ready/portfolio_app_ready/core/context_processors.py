from .models import Asset


def portfolio_data(request):
    if request.user.is_authenticated:
        assets = Asset.objects.filter(owner=request.user)

        total_amount = sum(float(asset.amount) for asset in assets)

        portfolio_return = 0

        for asset in assets:
            weight = float(asset.amount) / total_amount if total_amount > 0 else 0
            portfolio_return += weight * asset.expected_return

        return {
            'sidebar_total_amount': round(total_amount, 2),
            'sidebar_portfolio_return': round(portfolio_return, 2),
        }

    return {
        'sidebar_total_amount': 0,
        'sidebar_portfolio_return': 0,
    }