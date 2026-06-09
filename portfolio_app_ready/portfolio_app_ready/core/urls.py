from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('risks/', views.risk_analysis, name='risks'),
    path('optimizer/', views.optimizer, name='optimizer'),
    path('models-docs/', views.model_docs, name='model_docs'),

    path('assets/add/', views.asset_create, name='asset_create'),
    path('assets/<int:asset_id>/edit/', views.asset_update, name='asset_update'),
    path('assets/<int:asset_id>/delete/', views.asset_delete, name='asset_delete'),
    path('asset/<int:asset_id>/', views.asset_detail, name='asset_detail'),

    path('asset/<int:asset_id>/transactions/', views.transaction_list, name='transaction_list'),
    path('asset/<int:asset_id>/transactions/add/', views.transaction_create, name='transaction_create'),

    path('update-quotes/', views.update_quotes, name='update_quotes'),

    path('api/asset/<int:asset_id>/price/', views.asset_live_price, name='asset_live_price'),
    path('api/asset/<int:asset_id>/history/', views.asset_price_history, name='asset_price_history'),
    path('api/ticker-search/', views.ticker_search, name='ticker_search'),
    path('api/ticker-info/', views.ticker_info, name='ticker_info'),

    path('transactions/', views.all_transactions, name='all_transactions'),

    path('api/assets-search/', views.assets_search, name='assets_search'),
]