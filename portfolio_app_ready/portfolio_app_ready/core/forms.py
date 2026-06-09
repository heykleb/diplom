from django import forms
from .models import Asset


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = [
            'name',
            'ticker',
            'asset_type',
            'quantity',
            'current_price',
            'expected_return',
            'risk',
        ]

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control auto-field',
                'readonly': 'readonly',
            }),
            'ticker': forms.TextInput(attrs={
                'class': 'form-control auto-field',
                'readonly': 'readonly',
            }),
            'asset_type': forms.Select(attrs={
                'class': 'form-select auto-field',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'min': '0',
                'placeholder': 'Введите количество',
            }),
            'current_price': forms.NumberInput(attrs={
                'class': 'form-control auto-field',
                'step': '0.01',
                'readonly': 'readonly',
            }),
            'expected_return': forms.NumberInput(attrs={
                'class': 'form-control auto-field',
                'step': '0.01',
                'readonly': 'readonly',
            }),
            'risk': forms.NumberInput(attrs={
                'class': 'form-control auto-field',
                'step': '0.01',
                'readonly': 'readonly',
            }),
        }