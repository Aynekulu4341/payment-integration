from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Campaign, Transaction, WithdrawalRequest

# Register and customize Campaign model
@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'total_birr', 'total_usd', 'created_at', 'updated_at')
    list_filter = ('creator', 'created_at')
    search_fields = ('title', 'description')
    ordering = ('-created_at',)

# Register and customize Transaction model
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'campaign', 'amount', 'payment_method', 'completed', 'created_at')
    list_filter = ('payment_method', 'completed', 'created_at')
    search_fields = ('transaction_id', 'campaign__title')
    ordering = ('-created_at',)

# Register and customize WithdrawalRequest model
@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'amount_birr', 'amount_usd', 'payment_method', 'status', 'requested_at')
    list_filter = ('payment_method', 'status', 'requested_at')
    search_fields = ('campaign__title',)
    ordering = ('-requested_at',)