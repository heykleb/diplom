from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.cache import cache
from .models import Asset, Portfolio, Transaction
from .forms import AssetForm, PortfolioForm, TransactionForm
import yfinance as yf
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from datetime import datetime, timedelta
import json


# ── Dashboard ──────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    assets       = Asset.objects.filter(owner=request.user)
    total_amount = sum(float(a.amount) for a in assets)
    total_cost   = sum(float(a.total_cost) for a in assets)
    pnl          = round(total_amount - total_cost, 2)
    pnl_percent  = round((pnl / total_cost * 100), 2) if total_cost > 0 else 0

    portfolio_return = 0
    portfolio_risk   = 0

    for asset in assets:
        weight = float(asset.amount) / total_amount if total_amount > 0 else 0
        asset.weight = round(weight * 100, 1)
        portfolio_return += weight * asset.expected_return
        portfolio_risk   += weight * asset.risk

    chart_labels    = [a.ticker for a in assets]
    chart_data      = [float(a.amount) for a in assets]
    recommendations = _generate_recommendations(assets, portfolio_risk, portfolio_return)

    return render(request, 'core/dashboard.html', {
        'assets':           assets,
        'total_amount':     round(total_amount, 2),
        'total_cost':       round(total_cost, 2),
        'pnl':              pnl,
        'pnl_percent':      pnl_percent,
        'portfolio_return': round(portfolio_return, 2),
        'portfolio_risk':   round(portfolio_risk, 2),
        'chart_labels':     json.dumps(chart_labels),
        'chart_data':       json.dumps(chart_data),
        'recommendations':  recommendations,
    })


def _generate_recommendations(assets, risk, ret):
    recs = []
    if not assets:
        recs.append('Добавьте первый актив, чтобы начать анализ портфеля.')
        return recs
    if risk > 25:
        recs.append(f'Индекс риска {risk:.1f}% — выше нормы. Рассмотрите добавление облигаций или ETF.')
    if risk < 10:
        recs.append(f'Портфель очень консервативный (риск {risk:.1f}%). Небольшая доля акций роста может увеличить доходность.')
    if len(list(assets)) < 5:
        recs.append('Для эффективной диверсификации рекомендуется не менее 5–7 различных активов.')
    high_risk = [a for a in assets if a.risk > 30]
    if high_risk:
        names = ', '.join(a.ticker for a in high_risk)
        recs.append(f'Активы с высоким риском (>30%): {names}. Следите за их долей.')
    if ret > 0:
        recs.append(f'Ожидаемая доходность: +{ret:.1f}%. Регулярно пересматривайте веса активов.')
    return recs


# ── Assets ─────────────────────────────────────────────────────────────────────

@login_required
def asset_create(request):
    form = AssetForm()
    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            asset       = form.save(commit=False)
            asset.owner = request.user
            asset.save()
            cache.delete(f'sidebar_{request.user.id}')
            return redirect('dashboard')
    return render(request, 'core/asset_form.html', {'form': form})


@login_required
def asset_update(request, asset_id):
    asset = get_object_or_404(Asset, id=asset_id, owner=request.user)
    form  = AssetForm(instance=asset)
    if request.method == 'POST':
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            cache.delete(f'sidebar_{request.user.id}')
            return redirect('dashboard')
    return render(request, 'core/asset_form.html', {'form': form, 'asset': asset})


@login_required
def asset_delete(request, asset_id):
    asset = get_object_or_404(Asset, id=asset_id, owner=request.user)
    if request.method == 'POST':
        asset.delete()
        cache.delete(f'sidebar_{request.user.id}')
        return redirect('dashboard')
    return render(request, 'core/asset_delete.html', {'asset': asset})


@login_required
def asset_detail(request, asset_id):
    asset        = get_object_or_404(Asset, id=asset_id, owner=request.user)
    transactions = asset.transactions.all()[:20]
    return render(request, 'core/asset_detail.html', {
        'asset':        asset,
        'transactions': transactions,
    })


# ── Transactions ───────────────────────────────────────────────────────────────

@login_required
def transaction_list(request, asset_id):
    asset        = get_object_or_404(Asset, id=asset_id, owner=request.user)
    transactions = asset.transactions.all()
    return render(request, 'core/transaction_list.html', {
        'asset':        asset,
        'transactions': transactions,
    })


@login_required
def transaction_create(request, asset_id):
    asset = get_object_or_404(Asset, id=asset_id, owner=request.user)
    form  = TransactionForm()

    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            tx       = form.save(commit=False)
            tx.owner = request.user
            tx.asset = asset

            if tx.tx_type == 'buy':
                old_total = float(asset.quantity) * float(asset.avg_buy_price or 0)
                new_total = float(tx.quantity) * float(tx.price)
                asset.quantity += tx.quantity
                if asset.quantity > 0:
                    asset.avg_buy_price = round(
                        (old_total + new_total) / asset.quantity, 2
                    )
            elif tx.tx_type == 'sell':
                asset.quantity = max(0, asset.quantity - tx.quantity)

            asset.save()
            tx.save()
            cache.delete(f'sidebar_{request.user.id}')
            return redirect('asset_detail', asset_id=asset.id)

    return render(request, 'core/transaction_form.html', {
        'form':  form,
        'asset': asset,
    })


# ── API ────────────────────────────────────────────────────────────────────────

@login_required
def asset_live_price(request, asset_id):
    asset     = get_object_or_404(Asset, id=asset_id, owner=request.user)
    cache_key = f'live_price_{asset.ticker}'
    cached    = cache.get(cache_key)
    if cached:
        cached['amount'] = round(cached['price'] * asset.quantity, 2)
        return JsonResponse(cached)

    try:
        ticker = yf.Ticker(asset.ticker)
        info   = ticker.fast_info
        price  = round(float(info.last_price), 2)
        prev   = round(float(info.previous_close), 2)
        change = round(price - prev, 2)
        change_pct = round((change / prev) * 100, 2) if prev else 0
        amount     = round(price * asset.quantity, 2)
        data = {
            'price':          price,
            'change':         change,
            'change_percent': change_pct,
            'amount':         amount,
        }
        cache.set(cache_key, data, 60 * 5)
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def asset_price_history(request, asset_id):
    asset     = get_object_or_404(Asset, id=asset_id, owner=request.user)
    period    = request.GET.get('period', '1mo')
    cache_key = f'price_history_{asset.ticker}_{period}'
    cached    = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)

    try:
        ticker = yf.Ticker(asset.ticker)
        hist   = ticker.history(period=period)
        if hist.empty:
            return JsonResponse({'labels': [], 'prices': [], 'ticker': asset.ticker})
        labels = [str(d.date()) for d in hist.index]
        prices = [round(float(p), 2) for p in hist['Close']]
        data   = {'labels': labels, 'prices': prices, 'ticker': asset.ticker}
        cache.set(cache_key, data, 60 * 60)
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e), 'labels': [], 'prices': []})


@login_required
def ticker_search(request):
    q         = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'results': []})

    cache_key = f'ticker_search_{q.lower()}'
    cached    = cache.get(cache_key)
    if cached:
        return JsonResponse({'results': cached})

    try:
        results = yf.Search(q, max_results=8)
        items   = []
        for r in results.quotes:
            items.append({
                'symbol': r.get('symbol', ''),
                'name':   r.get('longname') or r.get('shortname', ''),
                'type':   r.get('quoteType', ''),
            })
        cache.set(cache_key, items, 60 * 60)
        return JsonResponse({'results': items})
    except Exception as e:
        return JsonResponse({'results': [], 'error': str(e)})


@login_required
def ticker_info(request):
    symbol    = request.GET.get('symbol', '').strip()
    if not symbol:
        return JsonResponse({'error': 'symbol required'}, status=400)

    cache_key = f'ticker_info_{symbol}'
    cached    = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)

    try:
        t    = yf.Ticker(symbol)
        info = t.fast_info
        hist = t.history(period='1y')
        if hist.empty:
            return JsonResponse({'error': 'no data'}, status=400)
        returns      = hist['Close'].pct_change().dropna()
        expected_ret = round(float(returns.mean()) * 252 * 100, 2)
        risk         = round(float(returns.std()) * (252 ** 0.5) * 100, 2)
        quote_type   = t.info.get('quoteType', 'EQUITY')
        data = {
            'name':            symbol,
            'symbol':          symbol,
            'price':           round(float(info.last_price), 2),
            'expected_return': expected_ret,
            'risk':            risk,
            'type':            quote_type,
        }
        cache.set(cache_key, data, 60 * 30)
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def update_quotes(request):
    assets = Asset.objects.filter(owner=request.user)
    for asset in assets:
        try:
            t     = yf.Ticker(asset.ticker)
            price = round(float(t.fast_info.last_price), 2)
            asset.current_price = price
            asset.save()
            cache.delete(f'live_price_{asset.ticker}')
        except Exception:
            continue
    cache.delete(f'sidebar_{request.user.id}')
    return redirect('dashboard')


# ── Analytics ──────────────────────────────────────────────────────────────────

@login_required
def risk_analysis(request):
    assets = Asset.objects.filter(owner=request.user)
    total  = sum(float(a.amount) for a in assets)
    result = []
    for asset in assets:
        weight = float(asset.amount) / total if total > 0 else 0
        score  = round(asset.risk * weight, 2)
        color  = 'danger' if score > 10 else ('warning' if score > 5 else 'safe')
        result.append({
            'name':       asset.name,
            'ticker':     asset.ticker,
            'asset_type': asset.asset_type,
            'risk':       asset.risk,
            'weight':     round(weight * 100, 1),
            'score':      score,
            'color':      color,
        })
    return render(request, 'core/risks.html', {'analyzed_assets': result})


@login_required
def model_docs(request):
    return render(request, 'core/model_docs.html')


# ── Optimizer helpers ──────────────────────────────────────────────────────────

def _fetch_returns(tickers, period_days=365):
    cache_key = f'returns_{"_".join(sorted(tickers))}_{period_days}'
    cached    = cache.get(cache_key)
    if cached is not None:
        try:
            df = pd.DataFrame(
                cached['data'],
                index=pd.to_datetime(cached['index']),
                columns=cached['columns']
            )
            return df, None
        except Exception:
            pass

    end   = datetime.today()
    start = end - timedelta(days=period_days)

    try:
        raw = yf.download(
            tickers,
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d'),
            progress=False,
            auto_adjust=True,
        )
    except Exception as e:
        return None, str(e)

    if raw.empty:
        return None, 'Нет данных от Yahoo Finance. Проверьте тикеры.'

    if isinstance(raw.columns, pd.MultiIndex):
        close = raw['Close']
    else:
        close = raw[['Close']]
        close.columns = tickers

    close = close.dropna(thresh=100, axis=1)

    if close.empty or close.shape[1] < 2:
        return None, 'Недостаточно исторических данных. Проверьте тикеры активов.'

    returns = close.pct_change().dropna()

    cache.set(cache_key, {
        'data':    returns.values.tolist(),
        'index':   [str(i) for i in returns.index],
        'columns': list(returns.columns),
    }, 60 * 60 * 4)

    return returns, None


def _portfolio_performance(weights, mean_returns, cov_matrix, risk_free=0.05):
    ret    = float(np.dot(weights, mean_returns)) * 252 * 100
    vol    = float(np.sqrt(weights @ cov_matrix @ weights) * np.sqrt(252)) * 100
    sharpe = (ret - risk_free * 100) / vol if vol > 0 else 0
    return round(ret, 4), round(vol, 4), round(sharpe, 4)


def _max_sharpe(mean_returns, cov_matrix, risk_free, bounds, constraints):
    n = len(mean_returns)

    def neg_sharpe(w):
        r, v, _ = _portfolio_performance(w, mean_returns, cov_matrix, risk_free)
        return -r / v if v > 0 else 0

    best_res = None
    best_val = float('inf')
    attempts = [np.ones(n) / n] + [np.random.dirichlet(np.ones(n)) for _ in range(4)]

    for w0 in attempts:
        try:
            res = minimize(
                neg_sharpe, w0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 500, 'ftol': 1e-9}
            )
            if res.fun < best_val:
                best_val = res.fun
                best_res = res
        except Exception:
            continue

    return best_res


def _min_volatility(mean_returns, cov_matrix, bounds, constraints):
    n = len(mean_returns)

    def portfolio_vol(w):
        return float(np.sqrt(w @ cov_matrix @ w) * np.sqrt(252)) * 100

    best_res = None
    best_val = float('inf')
    attempts = [np.ones(n) / n] + [np.random.dirichlet(np.ones(n)) for _ in range(4)]

    for w0 in attempts:
        try:
            res = minimize(
                portfolio_vol, w0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 500, 'ftol': 1e-9}
            )
            if res.fun < best_val:
                best_val = res.fun
                best_res = res
        except Exception:
            continue

    return best_res


def _efficient_frontier(mean_returns, cov_matrix, bounds, constraints, points=30):
    min_ret = float(np.min(mean_returns)) * 252 * 100 * 0.99
    max_ret = float(np.max(mean_returns)) * 252 * 100 * 0.99
    targets = np.linspace(min_ret, max_ret, points)
    frontier_risk, frontier_ret = [], []
    n  = len(mean_returns)
    w0 = np.ones(n) / n

    for target in targets:
        try:
            cons = list(constraints) + [{
                'type': 'eq',
                'fun':  lambda w, t=target: float(np.dot(w, mean_returns)) * 252 * 100 - t
            }]
            res = minimize(
                lambda w: float(np.sqrt(w @ cov_matrix @ w) * np.sqrt(252)) * 100,
                w0,
                method='SLSQP',
                bounds=bounds,
                constraints=cons,
                options={'maxiter': 200, 'ftol': 1e-7}
            )
            if res.success:
                r, v, _ = _portfolio_performance(res.x, mean_returns, cov_matrix)
                frontier_risk.append(round(v, 3))
                frontier_ret.append(round(r, 3))
                w0 = res.x
        except Exception:
            continue

    if frontier_risk:
        paired        = sorted(zip(frontier_risk, frontier_ret))
        frontier_risk = [p[0] for p in paired]
        frontier_ret  = [p[1] for p in paired]

    return frontier_risk, frontier_ret


def _monte_carlo(mean_returns, cov_matrix, risk_free, n_portfolios=1000):
    n = len(mean_returns)
    mc_ret, mc_risk, mc_sharpe, mc_weights = [], [], [], []

    for _ in range(n_portfolios):
        w        = np.random.dirichlet(np.ones(n))
        r, v, sh = _portfolio_performance(w, mean_returns, cov_matrix, risk_free)
        mc_ret.append(round(r, 3))
        mc_risk.append(round(v, 3))
        mc_sharpe.append(round(sh, 3))
        mc_weights.append(w.tolist())

    return mc_ret, mc_risk, mc_sharpe, mc_weights


def _generate_optimizer_recommendations(rebalance, portfolio_metrics, minvol_metrics, var_data):
    recs = []

    overweight  = [r for r in rebalance if r['action'] == 'sell' and r['diff_weight'] > 5]
    underweight = [r for r in rebalance if r['action'] == 'buy'  and r['diff_weight'] > 5]
    hold        = [r for r in rebalance if r['action'] == 'hold']

    if overweight:
        names      = ', '.join(r['ticker'] for r in overweight)
        total_sell = sum(r['diff_val'] for r in overweight)
        recs.append({
            'type':  'danger',
            'title': 'Избыточная концентрация',
            'text':  f'Активы {names} занимают слишком большую долю. Рекомендуется сократить позиции на общую сумму ${total_sell:,.2f} для снижения риска.',
        })

    if underweight:
        names     = ', '.join(r['ticker'] for r in underweight)
        total_buy = sum(r['diff_val'] for r in underweight)
        recs.append({
            'type':  'info',
            'title': 'Недостаточная диверсификация',
            'text':  f'Модель рекомендует увеличить позиции в {names} на общую сумму ${total_buy:,.2f} для улучшения соотношения риска и доходности.',
        })

    if hold and len(hold) == len(rebalance):
        recs.append({
            'type':  'success',
            'title': 'Портфель сбалансирован',
            'text':  'Текущая структура портфеля близка к оптимальной. Существенных изменений не требуется.',
        })

    if portfolio_metrics['sharpe'] > 1:
        recs.append({
            'type':  'success',
            'title': 'Высокий коэффициент Шарпа',
            'text':  f'Sharpe = {portfolio_metrics["sharpe"]} — отличное соотношение доходности и риска.',
        })
    elif portfolio_metrics['sharpe'] < 0.5:
        recs.append({
            'type':  'warning',
            'title': 'Низкий коэффициент Шарпа',
            'text':  f'Sharpe = {portfolio_metrics["sharpe"]} — портфель недостаточно эффективен. Рассмотрите замену низкодоходных активов.',
        })

    if var_data['var_percent'] > 3:
        recs.append({
            'type':  'danger',
            'title': 'Высокий дневной риск',
            'text':  f'VaR 95% = {var_data["var_percent"]}% — в неблагоприятный день портфель может потерять ${var_data["var_money"]}. Рассмотрите добавление защитных активов.',
        })

    ret_diff  = round(portfolio_metrics['return'] - minvol_metrics['return'], 2)
    risk_diff = round(portfolio_metrics['risk']   - minvol_metrics['risk'],   2)

    if risk_diff > 5:
        recs.append({
            'type':  'info',
            'title': 'Альтернативная стратегия',
            'text':  f'Портфель минимального риска даёт на {risk_diff}% меньше волатильности, теряя всего {ret_diff}% доходности.',
        })

    return recs


# ── Optimizer ──────────────────────────────────────────────────────────────────

@login_required
def optimizer(request):
    assets     = Asset.objects.filter(owner=request.user)
    risk_free  = float(request.GET.get('risk_free', 5.0))
    min_weight = float(request.GET.get('min_weight', 1.0)) / 100
    max_weight = float(request.GET.get('max_weight', 100.0)) / 100
    period     = int(request.GET.get('period', 365))

    context = {
        'risk_free_rate': risk_free,
        'min_weight':     round(min_weight * 100, 1),
        'max_weight':     round(max_weight * 100, 1),
        'optimized':      assets,
        'period':         period,
    }

    if assets.count() < 2:
        context['error'] = 'Для оптимизации необходимо минимум 2 актива.'
        return render(request, 'core/optimizer.html', context)

    if request.GET.get('run') != '1':
        return render(request, 'core/optimizer.html', context)

    # 1. Исторические данные
    tickers            = [a.ticker for a in assets]
    returns_df, error  = _fetch_returns(tickers, period_days=period)

    if error:
        context['error'] = error
        return render(request, 'core/optimizer.html', context)

    available_tickers = list(returns_df.columns)
    assets_filtered   = [a for a in assets if a.ticker in available_tickers]

    if len(assets_filtered) < 2:
        context['error'] = 'Недостаточно данных по тикерам. Проверьте правильность тикеров.'
        return render(request, 'core/optimizer.html', context)

    returns_df   = returns_df[available_tickers]
    mean_returns = returns_df.mean().values
    cov_matrix   = returns_df.cov().values
    n            = len(available_tickers)

    # 2. Параметры
    bounds      = tuple((min_weight, max_weight) for _ in range(n))
    constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]

    # 3. Макс. Sharpe
    sharpe_res = _max_sharpe(mean_returns, cov_matrix, risk_free / 100, bounds, constraints)
    if sharpe_res is None:
        context['error'] = 'Не удалось рассчитать оптимальный портфель. Добавьте больше активов.'
        return render(request, 'core/optimizer.html', context)

    sharpe_weights             = sharpe_res.x
    sharpe_ret, sharpe_vol, sharpe_val = _portfolio_performance(
        sharpe_weights, mean_returns, cov_matrix, risk_free / 100
    )

    # 4. Мин. риск
    minvol_res                    = _min_volatility(mean_returns, cov_matrix, bounds, constraints)
    minvol_weights                = minvol_res.x
    minvol_ret, minvol_vol, minvol_sharpe = _portfolio_performance(
        minvol_weights, mean_returns, cov_matrix, risk_free / 100
    )

    # 5. Метрики по активам
    optimized = []
    for i, asset in enumerate(assets_filtered):
        if asset.ticker not in available_tickers:
            continue
        idx      = available_tickers.index(asset.ticker)
        ann_ret  = round(float(mean_returns[idx]) * 252 * 100, 2)
        ann_vol  = round(float(np.sqrt(cov_matrix[idx][idx]) * np.sqrt(252)) * 100, 2)
        asset.real_return    = ann_ret
        asset.real_risk      = ann_vol
        asset.optimal_weight = round(sharpe_weights[idx] * 100, 1)
        asset.minvol_weight  = round(minvol_weights[idx] * 100, 1)
        optimized.append(asset)

    # 6. Ребалансировка
    total_current = sum(float(a.amount) for a in assets_filtered)
    rebalance     = []

    for asset in optimized:
        idx            = available_tickers.index(asset.ticker)
        current_val    = float(asset.amount)
        current_weight = round(current_val / total_current * 100, 1) if total_current > 0 else 0
        optimal_weight = asset.optimal_weight
        optimal_val    = round(total_current * sharpe_weights[idx], 2)
        diff_val       = round(optimal_val - current_val, 2)
        diff_weight    = round(optimal_weight - current_weight, 1)
        price          = float(asset.current_price) if float(asset.current_price) > 0 else 1
        shares_diff    = round(abs(diff_val) / price, 4)

        if abs(diff_weight) < 1.0:
            action = 'hold'
        elif diff_val > 0:
            action = 'buy'
        else:
            action = 'sell'

        rebalance.append({
            'name':           asset.name,
            'ticker':         asset.ticker,
            'current_val':    round(current_val, 2),
            'current_weight': current_weight,
            'optimal_weight': optimal_weight,
            'optimal_val':    optimal_val,
            'diff_val':       round(abs(diff_val), 2),
            'diff_weight':    round(abs(diff_weight), 1),
            'shares_diff':    shares_diff,
            'action':         action,
            'price':          round(price, 2),
        })

    total_to_buy  = round(sum(r['diff_val'] for r in rebalance if r['action'] == 'buy'), 2)
    total_to_sell = round(sum(r['diff_val'] for r in rebalance if r['action'] == 'sell'), 2)

    # 7. Эффективная граница
    frontier_risk, frontier_ret = _efficient_frontier(
        mean_returns, cov_matrix, bounds, constraints
    )

    # 8. Monte Carlo
    mc_ret, mc_risk, mc_sharpe, _ = _monte_carlo(
        mean_returns, cov_matrix, risk_free / 100, n_portfolios=1000
    )

    # 9. Корреляция
    corr_matrix = returns_df.corr().round(3).values.tolist()

    # 10. VaR / CVaR
    portfolio_daily = returns_df.dot(sharpe_weights)
    total_val       = total_current
    var_95          = float(np.percentile(portfolio_daily, 5))
    cvar_95         = float(portfolio_daily[portfolio_daily <= var_95].mean())
    var_pct         = round(abs(var_95) * 100, 2)
    cvar_pct        = round(abs(cvar_95) * 100, 2)

    var_data = {
        'var_percent':     var_pct,
        'cvar_percent':    cvar_pct,
        'var_money':       round(total_val * var_pct / 100, 2),
        'cvar_money':      round(total_val * cvar_pct / 100, 2),
        'portfolio_value': round(total_val, 2),
    }

    # 11. Рекомендации
    portfolio_metrics = {'return': sharpe_ret, 'risk': sharpe_vol, 'sharpe': sharpe_val}
    minvol_metrics    = {'return': minvol_ret, 'risk': minvol_vol, 'sharpe': minvol_sharpe}

    optimizer_recommendations = _generate_optimizer_recommendations(
        rebalance, portfolio_metrics, minvol_metrics, var_data
    )

    context.update({
        'portfolio_metrics': portfolio_metrics,
        'minvol_metrics':    minvol_metrics,
        'optimized':         optimized,
        'rebalance':         rebalance,
        'optimizer_recommendations': optimizer_recommendations,
        'frontier': {
            'risk':   json.dumps(frontier_risk),
            'return': json.dumps(frontier_ret),
        },
        'point_sharpe': {'risk': sharpe_vol, 'return': sharpe_ret},
        'point_minvol': {'risk': minvol_vol, 'return': minvol_ret},
        'monte_carlo': {
            'risk':   json.dumps(mc_risk),
            'return': json.dumps(mc_ret),
            'sharpe': json.dumps(mc_sharpe),
        },
        'correlation_matrix': {
            'tickers': json.dumps(available_tickers),
            'values':  json.dumps(corr_matrix),
        },
        'var_data': var_data,
        'total_to_buy':  total_to_buy,
        'total_to_sell': total_to_sell,
    })

    return render(request, 'core/optimizer.html', context)