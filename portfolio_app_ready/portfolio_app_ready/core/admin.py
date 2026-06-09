from django.contrib import admin
from .models import Asset


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'ticker', 'asset_type', 'amount', 'expected_return', 'risk', 'owner')
    list_filter = ('asset_type',)
    search_fields = ('name', 'ticker')
