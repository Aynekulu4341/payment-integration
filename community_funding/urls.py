from django.urls import path, include
from django.contrib import admin
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/test/', permanent=False), name='root_redirect'),  # Add this for root redirect
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),  # Add this for authentication URLs
    path('', include('payments.urls')),
]