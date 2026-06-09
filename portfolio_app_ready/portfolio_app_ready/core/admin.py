from django.contrib import admin
from .models import Asset, Portfolio, Transaction, PriceHistory


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display  = ('name', 'owner', 'currency', 'created_at')
    list_filter   = ('currency',)
    search_fields = ('name', 'owner__username')


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display  = ('name', 'ticker', 'asset_type', 'amount', 'pnl', 'expected_return', 'risk', 'owner')
    list_filter   = ('asset_type',)
    search_fields = ('name', 'ticker')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ('owner', 'asset', 'tx_type', 'quantity', 'price', 'total', 'commission', 'created_at')
    list_filter   = ('tx_type',)
    search_fields = ('asset__ticker', 'owner__username')


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display  = ('asset', 'date', 'close', 'volume')
    list_filter   = ('asset',)