import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Asset
from .forms import AssetForm
import yfinance as yf
from django.http import JsonResponse
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import ollama

def generate_ai_recommendations(data):

    try:

        prompt = f"""
Ты профессиональный финансовый аналитик.

ВАЖНО:
- Пиши ТОЛЬКО на русском языке.
- Не используй английские слова.
- Не используй английские термины.
- Все финансовые показатели объясняй на русском.
- Вместо Sharpe Ratio пиши "коэффициент Шарпа".
- Вместо Monte Carlo пиши "имитационное моделирование Монте-Карло".
- Вместо efficient frontier пиши "эффективная граница Марковица".
- Вместо correlation matrix пиши "корреляционная матрица".
- Вместо Value at Risk пиши "стоимость под риском (VaR)".
- Не используй списки на английском.
- Не используй английские заголовки.

Проанализируй инвестиционный портфель.

Используй:
- модель Марковица
- эффективную границу
- имитационное моделирование Монте-Карло
- корреляционную матрицу
- стоимость под риском (VaR)
- условную стоимость под риском (CVaR)

Данные портфеля:
{json.dumps(data, ensure_ascii=False, indent=2)}

Сформируй:

1. Общую оценку инвестиционного портфеля
2. Анализ риска
3. Анализ диверсификации
4. Анализ взаимосвязи активов
5. Интерпретацию результатов Монте-Карло
6. Интерпретацию VaR и CVaR
7. Практические рекомендации по ребалансировке

Пиши профессионально, строго и только на русском языке.
"""

        response = ollama.chat(
            model='llama3',
            messages=[
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            options={
                'temperature': 0.3
            }
        )

        return response['message']['content']

    except Exception as e:
        return f"AI-модуль временно недоступен: {e}"

@login_required
def dashboard(request):
    stress = float(request.GET.get('stress', 0) or 0)
    assets = Asset.objects.filter(owner=request.user).order_by('name')
    total_amount = sum(float(asset.amount) for asset in assets)
    portfolio_return = 0
    portfolio_risk = 0
    analyzed_assets = []
    chart_labels = []
    chart_data = []

    for asset in assets:
        weight = float(asset.amount) / total_amount if total_amount > 0 else 0
        adjusted_return = asset.expected_return - stress
        portfolio_return += weight * adjusted_return
        portfolio_risk += weight * asset.risk
        chart_labels.append(asset.name)
        chart_data.append(round(weight * 100, 2))
        analyzed_assets.append({
            'id': asset.id,
            'name': asset.name,
            'ticker': asset.ticker,
            'asset_type': asset.get_asset_type_display(),
            'amount': asset.amount,
            'expected_return': asset.expected_return,
            'adjusted_return': round(adjusted_return, 2),
            'risk': asset.risk,
            'weight': round(weight * 100, 2),
        })

    recommendations = []
    if total_amount == 0:
        recommendations.append('Добавьте активы для начала анализа инвестиционного портфеля.')
    else:
        if portfolio_return < 0:
            recommendations.append('🚨 Критическая ситуация: прогнозная доходность портфеля отрицательная. Требуется пересмотр структуры активов.')
        elif portfolio_return < 8:
            recommendations.append('⚠️ Низкая доходность портфеля. Рекомендуется увеличить долю более доходных инструментов.')
        if portfolio_risk > 25:
            recommendations.append('⚠️ Высокий уровень риска. Рекомендуется увеличить долю облигаций, ETF или денежных средств.')
        if stress >= 5:
            recommendations.append(f'💡 Введен стресс-сценарий снижения доходности на {stress}%. Рекомендуется провести ребалансировку портфеля.')
        for item in analyzed_assets:
            if item['weight'] > 50:
                recommendations.append(f'⚠️ Актив "{item["name"]}" занимает более 50% портфеля. Необходимо повысить диверсификацию.')
        if not recommendations:
            recommendations.append('✅ Структура портфеля сбалансирована. Соотношение риска и доходности находится в допустимых пределах.')

    return render(request, 'core/dashboard.html', {
        'assets': analyzed_assets,
        'total_amount': round(total_amount, 2),
        'portfolio_return': round(portfolio_return, 2),
        'portfolio_risk': round(portfolio_risk, 2),
        'stress': stress,
        'recommendations': recommendations,
        'chart_labels': json.dumps(chart_labels, ensure_ascii=False),
        'chart_data': json.dumps(chart_data),
    })


@login_required
def risk_analysis(request):
    assets = Asset.objects.filter(owner=request.user)
    total_amount = sum(float(asset.amount) for asset in assets)
    analyzed_assets = []
    for asset in assets:
        weight = float(asset.amount) / total_amount if total_amount > 0 else 0
        risk_score = asset.risk + weight * 50
        if risk_score > 60:
            status, color = 'Критический риск', 'danger'
        elif risk_score > 35:
            status, color = 'Умеренный риск', 'warning'
        else:
            status, color = 'Безопасно', 'success'
        analyzed_assets.append({
            'name': asset.name,
            'ticker': asset.ticker,
            'asset_type': asset.get_asset_type_display(),
            'risk': asset.risk,
            'weight': round(weight * 100, 2),
            'score': round(risk_score, 1),
            'status': status,
            'color': color,
        })
    analyzed_assets.sort(key=lambda x: x['score'], reverse=True)
    return render(request, 'core/risks.html', {'analyzed_assets': analyzed_assets})


@login_required
def optimizer(request):

    run_calc = request.GET.get('run') == '1'

    assets = Asset.objects.filter(owner=request.user).exclude(ticker='')

    risk_free_raw = request.GET.get('risk_free')

    try:
        risk_free_rate = float(risk_free_raw) / 100 if risk_free_raw else 0.05
    except:
        risk_free_rate = 0.05

    tickers = [asset.ticker for asset in assets]

    optimized = []
    portfolio_metrics = None
    error = None

    frontier = {
        'risk': [],
        'return': [],
    }

    correlation_matrix = {
        'tickers': [],
        'values': [],
    }

    monte_carlo = {
        'risk': [],
        'return': [],
        'sharpe': [],
    }

    var_data = None

    if len(tickers) < 2:
        return render(request, 'core/optimizer.html', {
            'optimized': optimized,
            'portfolio_metrics': portfolio_metrics,
            'error': 'Для оптимизации по Марковицу нужно добавить минимум 2 актива.',
            'risk_free_rate': risk_free_rate * 100,
            'frontier': {
                'risk': json.dumps(frontier['risk']),
                'return': json.dumps(frontier['return']),
            },
            'correlation_matrix': {
                'tickers': json.dumps(correlation_matrix['tickers']),
                'values': json.dumps(correlation_matrix['values']),
            },
            'monte_carlo': {
                'risk': json.dumps(monte_carlo['risk']),
                'return': json.dumps(monte_carlo['return']),
                'sharpe': json.dumps(monte_carlo['sharpe']),
            },
            'var_data': var_data,

        })
    
    if not run_calc:
        return render(request, 'core/optimizer.html', {
            'optimized': [],
            'portfolio_metrics': None,
            'error': None,
            'risk_free_rate': risk_free_rate * 100,
            'frontier': {'risk': '[]', 'return': '[]'},
            'correlation_matrix': {'tickers': '[]', 'values': '[]'},
            'monte_carlo': {'risk': '[]', 'return': '[]', 'sharpe': '[]'},
            'var_data': None,
        })

    try:
        prices = yf.download(
            tickers,
            period='1y',
            interval='1d',
            auto_adjust=True,
            progress=False
        )['Close']

        if isinstance(prices, pd.Series):
            prices = prices.to_frame()

        prices = prices.dropna(axis=1, how='all')
        returns = prices.pct_change().dropna()

        available_tickers = list(returns.columns)

        if len(available_tickers) < 2:
            raise Exception('Недостаточно исторических данных для расчета.')

        mean_returns = returns.mean() * 252
        cov_matrix = returns.cov() * 252
        corr_matrix = returns.corr()

        n = len(available_tickers)

        def portfolio_return(weights):
            return np.dot(weights, mean_returns)

        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

        def negative_sharpe(weights):
            ret = portfolio_return(weights)
            vol = portfolio_volatility(weights)

            if vol == 0:
                return 999

            return -(ret - risk_free_rate) / vol

        constraints = ({
            'type': 'eq',
            'fun': lambda weights: np.sum(weights) - 1
        })

        bounds = tuple((0.05, 0.40) for _ in range(n))
        initial_weights = np.array([1 / n] * n)

        result = minimize(
            negative_sharpe,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        optimal_weights = result.x

        opt_return = portfolio_return(optimal_weights)
        opt_risk = portfolio_volatility(optimal_weights)
        opt_sharpe = (opt_return - risk_free_rate) / opt_risk if opt_risk else 0

        portfolio_metrics = {
            'return': round(opt_return * 100, 2),
            'risk': round(opt_risk * 100, 2),
            'sharpe': round(opt_sharpe, 2),
        }

        for ticker, weight in zip(available_tickers, optimal_weights):
            asset = assets.filter(ticker=ticker).first()

            optimized.append({
                'name': asset.name if asset else ticker,
                'ticker': ticker,
                'asset_type': asset.get_asset_type_display() if asset else 'Актив',
                'optimal_weight': round(weight * 100, 2),
                'expected_return': round(mean_returns[ticker] * 100, 2),
                'risk': round(np.sqrt(cov_matrix.loc[ticker, ticker]) * 100, 2),
            })

        optimized.sort(key=lambda x: x['optimal_weight'], reverse=True)

        # Эффективная граница
        target_returns = np.linspace(mean_returns.min(), mean_returns.max(), 30)

        for target in target_returns:
            cons = (
                {'type': 'eq', 'fun': lambda weights: np.sum(weights) - 1},
                {'type': 'eq', 'fun': lambda weights, target=target: portfolio_return(weights) - target}
            )

            res = minimize(
                portfolio_volatility,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=cons
            )

            if res.success:
                frontier['risk'].append(round(portfolio_volatility(res.x) * 100, 2))
                frontier['return'].append(round(portfolio_return(res.x) * 100, 2))

        # Корреляционная матрица
        correlation_matrix['tickers'] = available_tickers
        correlation_matrix['values'] = corr_matrix.round(2).values.tolist()

        # VaR 95%
        portfolio_daily_returns = returns.dot(optimal_weights)

        var_95 = np.percentile(portfolio_daily_returns, 5)
        cvar_95 = portfolio_daily_returns[portfolio_daily_returns <= var_95].mean()

        portfolio_value = sum(float(asset.amount) for asset in assets)

        var_data = {
            'var_percent': round(var_95 * 100, 2),
            'cvar_percent': round(cvar_95 * 100, 2),
            'var_money': round(abs(var_95 * portfolio_value), 2),
            'cvar_money': round(abs(cvar_95 * portfolio_value), 2),
            'portfolio_value': round(portfolio_value, 2),
        }

        # Monte Carlo simulation
        simulations = 1000

        for _ in range(simulations):
            weights = np.random.random(n)
            weights = weights / np.sum(weights)

            ret = portfolio_return(weights)
            risk = portfolio_volatility(weights)
            sharpe = (ret - risk_free_rate) / risk if risk else 0

            monte_carlo['return'].append(round(ret * 100, 2))
            monte_carlo['risk'].append(round(risk * 100, 2))
            monte_carlo['sharpe'].append(round(sharpe, 2))

    except Exception as e:
        error = str(e)

    ai_input_data = {
        'portfolio_metrics': portfolio_metrics,
        'optimized_weights': optimized,
        'var_data': var_data,
        'correlation_matrix': correlation_matrix,
        'frontier_points_count': len(frontier['risk']),
        'monte_carlo_points_count': len(monte_carlo['risk']),
    }

    ai_recommendations = None

    if portfolio_metrics:
        ai_recommendations = generate_ai_recommendations(ai_input_data)

    return render(request, 'core/optimizer.html', {
        'optimized': optimized,
        'portfolio_metrics': portfolio_metrics,
        'error': error,
        'risk_free_rate': risk_free_rate * 100,

        'frontier': {
            'risk': json.dumps(frontier['risk']),
            'return': json.dumps(frontier['return']),
        },

        'correlation_matrix': {
            'tickers': json.dumps(correlation_matrix['tickers']),
            'values': json.dumps(correlation_matrix['values']),
        },

        'monte_carlo': {
            'risk': json.dumps(monte_carlo['risk']),
            'return': json.dumps(monte_carlo['return']),
            'sharpe': json.dumps(monte_carlo['sharpe']),
        },

        'var_data': var_data,

        'ai_recommendations': ai_recommendations,
    })


@login_required
def asset_create(request):
    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.owner = request.user
            asset.save()
            return redirect('dashboard')
    else:
        form = AssetForm()
    return render(request, 'core/asset_form.html', {'form': form, 'title': 'Добавление актива'})


@login_required
def asset_update(request, asset_id):
    asset = get_object_or_404(Asset, id=asset_id, owner=request.user)
    if request.method == 'POST':
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = AssetForm(instance=asset)
    return render(request, 'core/asset_form.html', {'form': form, 'title': 'Редактирование актива'})


@login_required
def asset_delete(request, asset_id):
    asset = get_object_or_404(Asset, id=asset_id, owner=request.user)
    if request.method == 'POST':
        asset.delete()
        return redirect('dashboard')
    return render(request, 'core/asset_delete.html', {'asset': asset})


@login_required
def model_docs(request):
    return render(request, 'core/model_docs.html')


@login_required
def ticker_search(request):
    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse({'results': []})

    try:
        search = yf.Search(query, max_results=10)
        quotes = search.quotes

        results = []

        for item in quotes:
            symbol = item.get('symbol')
            name = item.get('shortname') or item.get('longname') or symbol
            quote_type = item.get('quoteType', 'EQUITY')

            if symbol:
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'type': quote_type,
                })

        return JsonResponse({'results': results})

    except Exception as e:
        return JsonResponse({'results': [], 'error': str(e)})


@login_required
def ticker_info(request):

    symbol = request.GET.get('symbol', '').strip()

    if not symbol:
        return JsonResponse({'error': 'Тикер не указан'}, status=400)

    try:

        ticker = yf.Ticker(symbol)

        history = ticker.history(period='1y')

        info = ticker.info

        if history.empty:
            return JsonResponse({
                'error': 'Нет исторических данных'
            }, status=404)

        current_price = float(history['Close'].iloc[-1])

        returns = history['Close'].pct_change().dropna()

        expected_return = float(returns.mean() * 252 * 100)

        risk = float(returns.std() * np.sqrt(252) * 100)

        name = (
            info.get('shortName')
            or info.get('longName')
            or symbol
        )

        currency = info.get('currency', '')
        quote_type = info.get('quoteType', 'EQUITY')

        return JsonResponse({
            'symbol': symbol,
            'name': name,
            'price': round(current_price, 2),

            'expected_return': round(expected_return, 2),
            'risk': round(risk, 2),

            'currency': currency,
            'type': quote_type,
        })

    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)
    

@login_required
def update_quotes(request):
    assets = Asset.objects.filter(owner=request.user).exclude(ticker='')

    updated_count = 0

    for asset in assets:
        try:
            ticker = yf.Ticker(asset.ticker)
            history = ticker.history(period='1y')

            if history.empty:
                continue

            current_price = float(history['Close'].iloc[-1])

            returns = history['Close'].pct_change().dropna()

            if len(returns) > 0:
                expected_return = float(returns.mean() * 252 * 100)
                risk = float(returns.std() * np.sqrt(252) * 100)
            else:
                expected_return = asset.expected_return
                risk = asset.risk

            asset.current_price = round(current_price, 2)
            asset.expected_return = round(expected_return, 2)
            asset.risk = round(risk, 2)
            asset.save()

            updated_count += 1

        except Exception:
            continue

    return redirect('dashboard')

@login_required
def asset_detail(request, asset_id):
    asset = get_object_or_404(Asset, id=asset_id, owner=request.user)
    return render(request, 'core/asset_detail.html', {'asset': asset})


@login_required
def asset_live_price(request, asset_id):
    asset = get_object_or_404(Asset, id=asset_id, owner=request.user)

    try:
        ticker = yf.Ticker(asset.ticker)
        history = ticker.history(period='2d')

        if history.empty:
            return JsonResponse({'error': 'Нет данных по тикеру'}, status=404)

        current_price = float(history['Close'].iloc[-1])
        previous_price = float(history['Close'].iloc[-2]) if len(history) > 1 else current_price

        change = current_price - previous_price
        change_percent = (change / previous_price * 100) if previous_price else 0

        asset.current_price = round(current_price, 2)
        asset.save()

        return JsonResponse({
            'price': round(current_price, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'amount': round(float(asset.amount), 2),
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def asset_price_history(request, asset_id):
    asset = get_object_or_404(Asset, id=asset_id, owner=request.user)

    period = request.GET.get('period', '1mo')

    try:
        ticker = yf.Ticker(asset.ticker)
        history = ticker.history(period=period)

        labels = []
        prices = []

        for date, row in history.iterrows():
            labels.append(date.strftime('%d.%m'))
            prices.append(round(float(row['Close']), 2))

        return JsonResponse({
            'labels': labels,
            'prices': prices,
            'ticker': asset.ticker,
            'name': asset.name,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)