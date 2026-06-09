from django.db import models
from django.contrib.auth.models import User


class Portfolio(models.Model):
    owner       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolios', verbose_name='Владелец')
    name        = models.CharField(max_length=100, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    currency    = models.CharField(max_length=10, default='USD', verbose_name='Валюта')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} ({self.owner.username})'

    @property
    def total_amount(self):
        return round(sum(float(a.amount) for a in self.assets.all()), 2)

    @property
    def total_cost(self):
        return round(sum(float(a.total_cost) for a in self.assets.all()), 2)

    @property
    def pnl(self):
        return round(self.total_amount - self.total_cost, 2)

    @property
    def pnl_percent(self):
        if self.total_cost == 0:
            return 0
        return round((self.pnl / self.total_cost) * 100, 2)

    class Meta:
        verbose_name        = 'Портфель'
        verbose_name_plural = 'Портфели'


class Asset(models.Model):
    ASSET_TYPES = [
        ('stock',  'Акция'),
        ('bond',   'Облигация'),
        ('etf',    'ETF'),
        ('cash',   'Деньги'),
        ('crypto', 'Криптовалюта'),
        ('metal',  'Драгметалл'),
        ('other',  'Другое'),
    ]

    portfolio     = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='assets', verbose_name='Портфель', null=True, blank=True)
    owner         = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    name          = models.CharField(max_length=100, verbose_name='Название актива')
    ticker        = models.CharField(max_length=30, verbose_name='Тикер')
    asset_type    = models.CharField(max_length=20, choices=ASSET_TYPES, default='stock', verbose_name='Тип актива')
    quantity      = models.FloatField(default=1, verbose_name='Количество')
    current_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Текущая цена')
    amount        = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Стоимость позиции')
    avg_buy_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Средняя цена покупки', null=True, blank=True)
    expected_return = models.FloatField(default=10, verbose_name='Ожидаемая доходность, %')
    risk          = models.FloatField(default=15, verbose_name='Риск, %')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.amount = round(float(self.quantity) * float(self.current_price), 2)
        super().save(*args, **kwargs)

    @property
    def total_cost(self):
        return round(float(self.quantity) * float(self.avg_buy_price), 2)

    @property
    def pnl(self):
        return round(float(self.amount) - self.total_cost, 2)

    @property
    def pnl_percent(self):
        if self.total_cost == 0:
            return 0
        return round((self.pnl / self.total_cost) * 100, 2)

    @property
    def real_pnl_percent(self):
        cost = float(self.avg_buy_price or 0)
        if cost == 0:
            # Если нет цены покупки — считаем от total_cost
            total_cost = float(self.quantity) * cost
            if total_cost == 0:
                return 0
        return round(
            (float(self.current_price) - float(self.avg_buy_price))
            / float(self.avg_buy_price) * 100, 2
        ) if float(self.avg_buy_price) > 0 else round(
            (float(self.amount) - float(self.total_cost)) / float(self.total_cost) * 100, 2
        ) if float(self.total_cost) > 0 else 0

    @property
    def real_pnl(self):
        return round(
            (float(self.current_price) - float(self.avg_buy_price))
            * float(self.quantity), 2
        )

    def __str__(self):
        return f'{self.name} ({self.ticker})'

    class Meta:
        verbose_name        = 'Актив'
        verbose_name_plural = 'Активы'

    


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('buy',      'Покупка'),
        ('sell',     'Продажа'),
        ('dividend', 'Дивиденд'),
        ('deposit',  'Пополнение'),
        ('withdraw', 'Вывод'),
    ]

    owner      = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    asset      = models.ForeignKey(Asset, on_delete=models.SET_NULL, related_name='transactions', verbose_name='Актив', null=True, blank=True)
    asset_ticker = models.CharField(max_length=30, blank=True, default='', verbose_name='Тикер актива')
    asset_name   = models.CharField(max_length=100, blank=True, default='', verbose_name='Название актива')
    tx_type    = models.CharField(max_length=20, choices=TRANSACTION_TYPES, verbose_name='Тип операции')
    quantity   = models.FloatField(default=0, verbose_name='Количество')
    price      = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Цена')
    total      = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Сумма')
    commission = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='Комиссия')
    note       = models.TextField(blank=True, verbose_name='Заметка')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.total = round(float(self.quantity) * float(self.price), 2)
        # Сохраняем тикер и имя при создании
        if self.asset and not self.asset_ticker:
            self.asset_ticker = self.asset.ticker
        if self.asset and not self.asset_name:
            self.asset_name = self.asset.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_tx_type_display()} {self.asset} — {self.total} $'

    class Meta:
        verbose_name        = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        ordering            = ['-created_at']


class PriceHistory(models.Model):
    asset  = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='price_history', verbose_name='Актив')
    date   = models.DateField(verbose_name='Дата')
    open   = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Открытие')
    high   = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Максимум')
    low    = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Минимум')
    close  = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Закрытие')
    volume = models.BigIntegerField(default=0, verbose_name='Объём')

    class Meta:
        verbose_name        = 'История цен'
        verbose_name_plural = 'История цен'
        unique_together     = ('asset', 'date')
        ordering            = ['-date']

    def __str__(self):
        return f'{self.asset.ticker} — {self.date}'