from django.db import models
from django.contrib.auth.models import User

class Campaign(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='campaigns')
    total_birr = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)  # ETB
    total_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)  # USD
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class Transaction(models.Model):
    PAYMENT_METHODS = (
        ('paypal', 'PayPal'),
        ('telebirr', 'Telebirr'),
    )
    
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    transaction_id = models.CharField(max_length=100, unique=True)  # External ID from PayPal/Telebirr
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_id} - {self.payment_method}"

class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='withdrawals')
    amount_birr = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)  # ETB
    amount_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)  # USD
    payment_method = models.CharField(max_length=10, choices=Transaction.PAYMENT_METHODS)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.campaign.title} - {self.amount_birr} ETB / {self.amount_usd} USD"