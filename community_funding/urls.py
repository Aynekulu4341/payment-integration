from django.contrib import admin
from django.urls import path
from payments import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/donate/', views.DonateView.as_view(), name='donate'),
    path('api/callback/paypal/', views.PaymentCallbackView.as_view(), name='paypal_callback'),
    path('api/callback/telebirr/', views.PaymentCallbackView.as_view(), name='telebirr_callback'),
    path('api/withdraw/', views.WithdrawalView.as_view(), name='withdraw'),
    path('', views.home, name='home'),
]