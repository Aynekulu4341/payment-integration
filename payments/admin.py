from django.contrib import admin, messages
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from .models import Campaign, Transaction, WithdrawalRequest
import logging

logger = logging.getLogger(__name__)

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'creator', 'total_birr', 'total_usd', 'balance_in_birr_display', 'goal_display', 'percentage_funded', 'created_at')
    search_fields = ('title', 'description')
    list_filter = ('created_at',)
    readonly_fields = ('total_usd', 'total_birr', 'created_at')
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('creator')

    def goal_display(self, obj):
        return f"{obj.goal:.2f} Birr"
    goal_display.short_description = 'Goal'

    def percentage_funded(self, obj):
        return f"{obj.get_percentage_funded():.2f}%"
    percentage_funded.short_description = 'Percentage Funded'

    def balance_in_birr_display(self, obj):
        return f"{obj.get_balance_in_birr():.2f} Birr"
    balance_in_birr_display.short_description = 'Balance in Birr'

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_id', 'campaign', 'amount', 'payment_method', 'donor_email', 'completed', 'created_at')
    search_fields = ('transaction_id', 'donor_email', 'campaign__title')
    list_filter = ('payment_method', 'completed', 'created_at')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('campaign')

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'campaign', 'requested_amount', 'payment_method', 'recipient_email', 'status', 'convert_to', 'requested_at', 'processed_at')
    list_filter = ('payment_method', 'status', 'requested_at')
    search_fields = ('campaign__title', 'recipient_email')
    readonly_fields = ('requested_at', 'processed_at')
    actions = ['approve_withdrawal', 'reject_withdrawal']
    date_hierarchy = 'requested_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('campaign')

    def get_exchange_rate(self, from_currency, to_currency):
        from .utils.exchange_rate import get_exchange_rate
        api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', None)
        return get_exchange_rate(from_currency, to_currency, api_key=api_key)

    def approve_withdrawal(self, request, queryset):
        for withdrawal in queryset:
            if withdrawal.status != 'pending':
                self.message_user(request, f"Withdrawal {withdrawal.id} is already {withdrawal.status}.", level=messages.WARNING)
                continue
            campaign = withdrawal.campaign
            requested_amount = withdrawal.requested_amount
            convert_to = withdrawal.convert_to
            payment_method = withdrawal.payment_method

            # Get exchange rate
            rate = self.get_exchange_rate('USD', 'ETB' if convert_to == 'birr' else 'ETB')
            if rate == 0:
                rate = 132.1 if convert_to == 'birr' else 0.007571
                logger.info(f"Using fallback exchange rate {('USD', 'ETB') if convert_to == 'birr' else ('ETB', 'USD')}: {rate}")

            # Calculate total available balance in the requested currency
            if convert_to == 'birr':
                total_available = campaign.total_birr + (campaign.total_usd * Decimal(str(rate)))
            else:  # convert_to == 'usd'
                total_available = campaign.total_usd + (campaign.total_birr / Decimal(str(rate)))
            total_available = total_available.quantize(Decimal('0.01'))

            # Check if sufficient funds are available
            if requested_amount > total_available:
                self.message_user(request, f"Insufficient funds for withdrawal {withdrawal.id}! Requested {requested_amount} {convert_to.upper()}, available {total_available} {convert_to.upper()}.", level=messages.ERROR)
                continue

            # Deduct the requested amount
            deduct_usd = Decimal('0.00')
            deduct_birr = Decimal('0.00')
            if convert_to == 'usd':
                deduct_usd = min(requested_amount, campaign.total_usd)
                remaining_usd = requested_amount - deduct_usd
                if remaining_usd > 0:
                    deduct_birr = (remaining_usd * Decimal(str(rate))).quantize(Decimal('0.01'))
                    if deduct_birr > campaign.total_birr:
                        self.message_user(request, f"Insufficient Birr funds for withdrawal {withdrawal.id}!", level=messages.ERROR)
                        continue
            else:  # convert_to == 'birr'
                deduct_birr = min(requested_amount, campaign.total_birr)
                remaining_birr = requested_amount - deduct_birr
                if remaining_birr > 0:
                    deduct_usd = (remaining_birr / Decimal(str(rate))).quantize(Decimal('0.01'))
                    if deduct_usd > campaign.total_usd:
                        self.message_user(request, f"Insufficient USD funds for withdrawal {withdrawal.id}!", level=messages.ERROR)
                        continue

            # Update campaign balances
            campaign.total_usd -= deduct_usd
            campaign.total_birr -= deduct_birr
            campaign.save()

            # Update withdrawal status
            withdrawal.status = 'approved'
            withdrawal.processed_at = timezone.now()
            withdrawal.save()

            # Calculate total withdrawn amount and process payment
            if convert_to == 'usd':
                total_withdrawn = deduct_usd + (deduct_birr / Decimal(str(rate))).quantize(Decimal('0.01'))
            else:  # convert_to == 'birr'
                total_withdrawn = deduct_birr + (deduct_usd * Decimal(str(rate))).quantize(Decimal('0.01'))

            if payment_method == 'paypal':
                result = {'success': True, 'message': f"Simulated PayPal withdrawal of {total_withdrawn} USD to {withdrawal.recipient_email}"}
                if result.get('success', False):
                    self.message_user(request, f"Withdrawal {withdrawal.id} approved: {result['message']}", messages.SUCCESS)
                    logger.info(f"Withdrawal {withdrawal.id} approved: {result['message']}")
                else:
                    message = result.get('message', 'PayPal transfer error')
                    self.message_user(request, f"Withdrawal {withdrawal.id} failed: {message}", messages.ERROR)
                    logger.error(f"Withdrawal {withdrawal.id} failed: {message}")
            elif payment_method == 'chapa':
                result = {'success': True, 'message': f"Simulated Chapa withdrawal of {total_withdrawn} ETB"}
                if result.get('success', False):
                    self.message_user(request, f"Withdrawal {withdrawal.id} approved: {result['message']}", messages.SUCCESS)
                    logger.info(f"Withdrawal {withdrawal.id} approved: {result['message']}")
                else:
                    message = result.get('message', 'Chapa withdrawal error')
                    self.message_user(request, f"Withdrawal {withdrawal.id} failed: {message}", messages.ERROR)
                    logger.error(f"Withdrawal {withdrawal.id} failed: {message}")

    approve_withdrawal.short_description = "Approve selected withdrawals"

    def reject_withdrawal(self, request, queryset):
        for withdrawal in queryset:
            if withdrawal.status != 'pending':
                self.message_user(request, f"Withdrawal {withdrawal.id} is already {withdrawal.status}.", level=messages.WARNING)
                continue
            withdrawal.status = 'rejected'
            withdrawal.processed_at = timezone.now()
            withdrawal.save()
        self.message_user(request, "Selected withdrawals rejected.", messages.SUCCESS)

    reject_withdrawal.short_description = "Reject selected withdrawals"