from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Schema view for API documentation
schema_view = get_schema_view(
    openapi.Info(
        title="PesaFlow API",
        default_version='v1',
        description="API documentation for PesaFlow payment system",
        terms_of_service="https://www.pesaflow.com/terms/",
        contact=openapi.Contact(email="support@pesaflow.com"),
        license=openapi.License(name="Proprietary License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # API endpoints
    path('api/v1/auth/', include('accounts.urls')),
    path('api/v1/organizations/', include('organizations.urls')),
    path('api/v1/customers/', include('customers.urls')),
    path('api/v1/payments/', include('payments.urls')),
    path('api/v1/integrations/', include('integrations.urls')),
    path('api/v1/notifications/', include('notifications.urls')),
    
    # Health check
    path('health/', include('health_check.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)