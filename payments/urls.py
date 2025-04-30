from django.urls import path
from . import views

urlpatterns = [
    path('donate/', views.DonateView.as_view(), name='donate'),
    path('callback/paypal/', views.PaymentCallbackView.as_view(), name='paypal_callback'),
    path('callback/telebirr/', views.PaymentCallbackView.as_view(), name='telebirr_callback'),
    path('withdraw/', views.WithdrawView.as_view(), name='withdraw'),
    path('campaigns/', views.CampaignListView.as_view(), name='campaign_list'),
    path('campaigns/<int:pk>/', views.CampaignDetailView.as_view(), name='campaign_detail'),
]