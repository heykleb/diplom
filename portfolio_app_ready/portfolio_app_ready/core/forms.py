from django import forms
from .models import Asset, Portfolio, Transaction


class PortfolioForm(forms.ModelForm):
    class Meta:
        model  = Portfolio
        fields = ['name', 'description', 'currency']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Например: Основной портфель',
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Описание стратегии (необязательно)',
                'rows': 3,
            }),
            'currency': forms.Select(choices=[
                ('USD', 'USD — Доллар'),
                ('EUR', 'EUR — Евро'),
                ('RUB', 'RUB — Рубль'),
            ]),
        }


class AssetForm(forms.ModelForm):
    class Meta:
        model  = Asset
        fields = ['name', 'ticker', 'asset_type', 'quantity', 'current_price', 'expected_return', 'risk']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Заполняется автоматически',
            }),
            'ticker': forms.TextInput(attrs={
                'placeholder': 'Заполняется автоматически',
            }),
            'asset_type': forms.Select(),
            'quantity': forms.NumberInput(attrs={
                'step': '0.0001', 'min': '0',
                'placeholder': 'Введите количество',
            }),
            'current_price': forms.NumberInput(attrs={
                'step': '0.01',
                'placeholder': 'Заполняется автоматически',
            }),
            'expected_return': forms.NumberInput(attrs={
                'step': '0.01',
                'placeholder': 'Заполняется автоматически',
            }),
            'risk': forms.NumberInput(attrs={
                'step': '0.01',
                'placeholder': 'Заполняется автоматически',
            }),
        }


class TransactionForm(forms.ModelForm):
    class Meta:
        model  = Transaction
        fields = ['tx_type', 'quantity', 'price', 'commission', 'note']
        widgets = {
            'tx_type': forms.Select(),
            'quantity': forms.NumberInput(attrs={
                'step': '0.0001', 'min': '0',
                'placeholder': '0.00',
            }),
            'price': forms.NumberInput(attrs={
                'step': '0.01', 'min': '0',
                'placeholder': '0.00',
            }),
            'commission': forms.NumberInput(attrs={
                'step': '0.01', 'min': '0',
                'placeholder': '0.00',
            }),
            'note': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Необязательно',
            }),
        }