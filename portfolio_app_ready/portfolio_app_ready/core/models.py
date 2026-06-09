from django.db import models
from django.contrib.auth.models import User


class Asset(models.Model):
    ASSET_TYPES = [
        ('stock', 'Акция'),
        ('bond', 'Облигация'),
        ('etf', 'ETF'),
        ('cash', 'Деньги'),
        ('crypto', 'Криптовалюта'),
        ('metal', 'Драгметалл'),
        ('other', 'Другое'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    name = models.CharField(max_length=100, verbose_name='Название актива')
    ticker = models.CharField(max_length=30, verbose_name='Тикер')
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPES, default='stock', verbose_name='Тип актива')

    quantity = models.FloatField(default=1, verbose_name='Количество')
    current_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Текущая цена')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Стоимость позиции')

    expected_return = models.FloatField(default=10, verbose_name='Ожидаемая доходность, %')
    risk = models.FloatField(default=15, verbose_name='Риск, %')

    def save(self, *args, **kwargs):
        self.amount = float(self.quantity) * float(self.current_price)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.ticker})'

    class Meta:
        verbose_name = 'Актив'
        verbose_name_plural = 'Активы'