from django.urls import path
from . import views

urlpatterns = [
    path('test/', views.test_page, name='test_page'),
    path('api/create-campaign/', views.CreateCampaignView.as_view(), name='create_campaign'),
    path('api/campaigns/', views.CampaignListView.as_view(), name='campaign_list'),
    path('api/campaigns/<int:pk>/', views.CampaignDetailView.as_view(), name='campaign_detail'),
    path('api/donate/', views.DonateView.as_view(), name='donate'),
    path('api/callback/chapa/', views.ChapaCallbackView.as_view(), name='chapa_callback'),
    path('api/callback/paypal/', views.PayPalCallbackView.as_view(), name='paypal_callback'),
    path('api/withdraw/', views.WithdrawView.as_view(), name='withdraw'),
]