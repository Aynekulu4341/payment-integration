from django.db import models
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from payments.utils.exchange_rate import get_exchange_rate
import logging

logger = logging.getLogger(__name__)

class Campaign(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    creator = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    goal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_birr = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title

    def get_balance_in_birr(self):
        """Calculate the total balance in ETB (Birr) including USD conversion."""
        api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', None)
        rate = get_exchange_rate('USD', 'ETB', api_key=api_key)
        if rate == 0:
            rate = 132.1
            logger.warning("Using fallback exchange rate USD to ETB: 132.1 in get_balance_in_birr")
        else:
            logger.debug(f"Using exchange rate USD to ETB: {rate} in get_balance_in_birr")
        balance = self.total_birr + (self.total_usd * Decimal(str(rate)))
        return balance.quantize(Decimal('0.01'))

    def get_percentage_funded(self):
        """Calculate the percentage of the goal funded based on balance in Birr."""
        if self.goal <= 0:
            return 0.0
        balance = self.get_balance_in_birr()
        percentage = (balance / self.goal) * 100
        logger.debug(f"Campaign {self.id}: balance_in_birr={balance}, goal={self.goal}, percentage={percentage}")
        return float(percentage.quantize(Decimal('0.01')))

class Transaction(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=[('paypal', 'PayPal'), ('chapa', 'Chapa')])
    transaction_id = models.CharField(max_length=100, unique=True)
    donor_email = models.EmailField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.transaction_id} - {self.campaign.title}"

class WithdrawalRequest(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    requested_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    payment_method = models.CharField(max_length=20, choices=[('paypal', 'PayPal'), ('chapa', 'Chapa')])
    recipient_email = models.EmailField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending')
    convert_to = models.CharField(max_length=10, choices=[('usd', 'USD'), ('birr', 'Birr')], default='birr')
    requested_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Withdrawal {self.id} - {self.campaign.title}"