from django.urls import path, include
from django.contrib import admin  # Add this import

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('payments.urls')),  # Include payments URLs under root
]