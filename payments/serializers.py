from rest_framework import serializers
from .models import Campaign

class CampaignSerializer(serializers.ModelSerializer):
    balance_in_birr = serializers.SerializerMethodField()
    percentage_funded = serializers.SerializerMethodField()
    total_usd = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_birr = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = Campaign
        fields = [
            'id', 'title', 'description', 'creator', 'total_usd', 'total_birr',
            'target_amount', 'target_currency', 'balance_in_birr', 'percentage_funded',
            'created_at'
        ]

    def get_balance_in_birr(self, obj):
        return obj.get_balance_in_birr()

    def get_percentage_funded(self, obj):
        return obj.get_percentage_funded()