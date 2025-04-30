from django.contrib import admin, messages
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from .models import Campaign, Transaction, WithdrawalRequest
from .views import simulate_paypal_transfer, simulate_telebirr_transfer
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging

logger = logging.getLogger(__name__)

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'creator', 'total_birr', 'total_usd', 'balance_in_birr_display', 'target_amount_display', 'percentage_funded', 'created_at')
    search_fields = ('title', 'description')
    list_filter = ('created_at', 'target_currency')
    readonly_fields = ('total_usd', 'total_birr', 'created_at')
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('creator')

    def target_amount_display(self, obj):
        """Display target amount with currency."""
        return f"{obj.target_amount:.2f} {obj.target_currency.title()}"
    target_amount_display.short_description = 'Target Amount'

    def percentage_funded(self, obj):
        """Display percentage funded."""
        return f"{obj.get_percentage_funded():.2f}%"
    percentage_funded.short_description = 'Percentage Funded'

    def balance_in_birr_display(self, obj):
        """Display balance in Birr."""
        return f"{obj.get_balance_in_birr():.2f} Birr"
    balance_in_birr_display.short_description = 'Balance in Birr'

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_id', 'campaign', 'amount', 'payment_method', 'donor_phone', 'donor_email', 'completed', 'created_at')
    search_fields = ('transaction_id', 'donor_phone', 'donor_email', 'campaign__title')
    list_filter = ('payment_method', 'completed', 'created_at')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('campaign')

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'campaign', 'amount_birr', 'amount_usd', 'payment_method', 'recipient_phone', 'recipient_email', 'status', 'convert_to', 'requested_at', 'processed_at')
    list_filter = ('payment_method', 'status', 'requested_at')
    search_fields = ('campaign__title', 'recipient_email', 'recipient_phone')
    readonly_fields = ('requested_at', 'processed_at')
    actions = ['approve_withdrawal', 'reject_withdrawal']
    date_hierarchy = 'requested_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('campaign')

    def get_exchange_rate(self, from_currency, to_currency):
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            url = f"https://v6.exchangerate-api.com/v6/{settings.EXCHANGE_RATE_API_KEY}/latest/{from_currency}"
            response = session.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Exchange rate API response: {data}")
            if data.get('result') != 'success':
                logger.error(f"Exchange rate API error: {data.get('error-type')}")
                return 0
            rate = data.get('conversion_rates', {}).get(to_currency, 0)
            if rate == 0:
                logger.error(f"Exchange rate not found for {to_currency}")
            else:
                logger.debug(f"Exchange rate {from_currency} to {to_currency}: {rate}")
            return rate
        except requests.exceptions.RequestException as e:
            logger.error(f"Exchange rate fetch failed: {str(e)}")
            return 0

    def approve_withdrawal(self, request, queryset):
        for withdrawal in queryset:
            if withdrawal.status != 'pending':
                self.message_user(request, f"Withdrawal {withdrawal.id} is already {withdrawal.status}.", level=messages.WARNING)
                continue
            campaign = withdrawal.campaign
            amount_usd = withdrawal.amount_usd or Decimal('0.00')
            amount_birr = withdrawal.amount_birr or Decimal('0.00')

            # Calculate total available funds in the target currency
            available_usd = campaign.total_usd
            available_birr = campaign.total_birr
            if withdrawal.convert_to == 'usd':
                rate = self.get_exchange_rate('ETB', 'USD')
                if rate == 0:
                    rate = 0.007571
                    logger.info("Using fallback exchange rate ETB to USD: 0.007571")
                total_available_usd = available_usd + (available_birr * Decimal(str(rate)))
                total_available_usd = total_available_usd.quantize(Decimal('0.01'))
                amount_usd = amount_usd.quantize(Decimal('0.01'))
                if amount_usd > total_available_usd:
                    self.message_user(request, f"Insufficient funds for withdrawal {withdrawal.id}! Requested {amount_usd} USD, available {total_available_usd} USD.", level=messages.ERROR)
                    continue
                # Deduct proportionally
                if amount_usd == total_available_usd:
                    # Deduct all funds
                    deduct_usd = available_usd
                    deduct_birr = available_birr
                else:
                    # Deduct proportionally
                    deduct_usd = min(amount_usd, available_usd)
                    remaining_usd = amount_usd - deduct_usd
                    deduct_birr = (remaining_usd / Decimal(str(rate))).quantize(Decimal('0.01')) if rate != 0 else Decimal('0.00')
                    if deduct_birr > available_birr:
                        self.message_user(request, f"Insufficient birr funds for withdrawal {withdrawal.id}! Requested {deduct_birr} ETB, available {available_birr} ETB.", level=messages.ERROR)
                        continue
            elif withdrawal.convert_to == 'birr':
                rate = self.get_exchange_rate('USD', 'ETB')
                if rate == 0:
                    rate = 132.1
                    logger.info("Using fallback exchange rate USD to ETB: 132.1")
                total_available_birr = available_birr + (available_usd * Decimal(str(rate)))
                total_available_birr = total_available_birr.quantize(Decimal('0.01'))
                amount_birr = amount_birr.quantize(Decimal('0.01'))
                if amount_birr > total_available_birr:
                    self.message_user(request, f"Insufficient funds for withdrawal {withdrawal.id}! Requested {amount_birr} ETB, available {total_available_birr} ETB.", level=messages.ERROR)
                    continue
                # Deduct proportionally
                if amount_birr == total_available_birr:
                    deduct_birr = available_birr
                    deduct_usd = available_usd
                else:
                    deduct_birr = min(amount_birr, available_birr)
                    remaining_birr = amount_birr - deduct_birr
                    deduct_usd = (remaining_birr / Decimal(str(rate))).quantize(Decimal('0.01')) if rate != 0 else Decimal('0.00')
                    if deduct_usd > available_usd:
                        self.message_user(request, f"Insufficient USD funds for withdrawal {withdrawal.id}! Requested {deduct_usd} USD, available {available_usd} USD.", level=messages.ERROR)
                        continue
            else:
                amount_usd = amount_usd.quantize(Decimal('0.01'))
                amount_birr = amount_birr.quantize(Decimal('0.01'))
                if amount_usd > available_usd or amount_birr > available_birr:
                    self.message_user(request, f"Insufficient funds for withdrawal {withdrawal.id}! Requested {amount_usd} USD/{amount_birr} ETB, available {available_usd} USD/{available_birr} ETB.", level=messages.ERROR)
                    continue
                deduct_usd = amount_usd
                deduct_birr = amount_birr

            # Update campaign balances
            campaign.total_usd -= deduct_usd
            campaign.total_birr -= deduct_birr
            campaign.total_usd = campaign.total_usd.quantize(Decimal('0.01'))
            campaign.total_birr = campaign.total_birr.quantize(Decimal('0.01'))
            campaign.save()
            withdrawal.amount_usd = amount_usd
            withdrawal.amount_birr = amount_birr
            withdrawal.status = 'approved'
            withdrawal.processed_at = timezone.now()
            withdrawal.save()

            if withdrawal.payment_method == 'paypal':
                result = simulate_paypal_transfer(amount_usd, withdrawal.recipient_email)
                if isinstance(result, dict) and result.get('success', False):
                    self.message_user(request, f"Withdrawal {withdrawal.id} approved: {result['message']}", messages.SUCCESS)
                    logger.info(f"Withdrawal {withdrawal.id} approved: {result['message']}")
                elif result is True:
                    message = f"Simulated PayPal transfer: {amount_usd} USD to {withdrawal.recipient_email}"
                    self.message_user(request, f"Withdrawal {withdrawal.id} approved: {message}", messages.SUCCESS)
                    logger.info(f"Withdrawal {withdrawal.id} approved: {message}")
                else:
                    message = result.get('message', 'PayPal transfer error') if isinstance(result, dict) else 'PayPal transfer error'
                    self.message_user(request, f"Withdrawal {withdrawal.id} failed: {message}", messages.ERROR)
                    logger.error(f"Withdrawal {withdrawal.id} failed: {message}")
            elif withdrawal.payment_method == 'telebirr':
                result = simulate_telebirr_transfer(amount_birr, withdrawal.recipient_phone)
                if isinstance(result, dict) and result.get('success', False):
                    self.message_user(request, f"Withdrawal {withdrawal.id} approved: {result['message']}", messages.SUCCESS)
                    logger.info(f"Withdrawal {withdrawal.id} approved: {result['message']}")
                elif result is True:
                    message = f"Simulated Telebirr transfer: {amount_birr} ETB to {withdrawal.recipient_phone}"
                    self.message_user(request, f"Withdrawal {withdrawal.id} approved: {message}", messages.SUCCESS)
                    logger.info(f"Withdrawal {withdrawal.id} approved: {message}")
                else:
                    message = result.get('message', 'Telebirr transfer error') if isinstance(result, dict) else 'Telebirr transfer error'
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