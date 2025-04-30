from django.db import models
from django.utils import timezone
from decimal import Decimal
from payments.utils.exchange_rate import get_exchange_rate
import logging

logger = logging.getLogger(__name__)

class Campaign(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    creator = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    total_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_birr = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    target_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    target_currency = models.CharField(
        max_length=10,
        choices=[('usd', 'USD'), ('birr', 'Birr')],
        default='birr'
    )
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title

    def get_balance_in_birr(self):
        """Calculate total balance in Birr (total_birr + total_usd converted to Birr)."""
        rate = get_exchange_rate('USD', 'ETB')
        if rate == 0:
            rate = 132.1  # Fallback rate
            logger.warning("Using fallback exchange rate USD to ETB: 132.1")
        else:
            logger.debug(f"Using live exchange rate USD to ETB: {rate}")
        balance = self.total_birr + (self.total_usd * Decimal(str(rate)))
        return balance.quantize(Decimal('0.01'))

    def get_percentage_funded(self):
        """Calculate percentage funded based on balance in Birr relative to target_amount."""
        if self.target_amount <= 0:
            return 0.0
        balance = self.get_balance_in_birr()
        target = self.target_amount
        if self.target_currency == 'usd':
            rate = get_exchange_rate('USD', 'ETB')
            if rate == 0:
                rate = 132.1  # Fallback rate
                logger.warning("Using fallback exchange rate USD to ETB: 132.1")
            else:
                logger.debug(f"Using live exchange rate USD to ETB: {rate}")
            target = self.target_amount * Decimal(str(rate))
        percentage = (balance / target) * 100
        logger.debug(f"Campaign {self.id}: balance_in_birr={balance}, target={target}, percentage={percentage}")
        return float(percentage.quantize(Decimal('0.01')))

class Transaction(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=[('paypal', 'PayPal'), ('telebirr', 'Telebirr')])
    transaction_id = models.CharField(max_length=100, unique=True)
    donor_phone = models.CharField(max_length=20, blank=True, null=True)
    donor_email = models.EmailField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.transaction_id} - {self.campaign.title}"

class WithdrawalRequest(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    amount_birr = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=20, choices=[('paypal', 'PayPal'), ('telebirr', 'Telebirr')])
    recipient_phone = models.CharField(max_length=20, blank=True, null=True)
    recipient_email = models.EmailField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending')
    convert_to = models.CharField(max_length=10, choices=[('usd', 'USD'), ('birr', 'Birr')], blank=True, null=True)
    requested_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Withdrawal {self.id} - {self.campaign.title}"