from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'types', views.IntegrationTypeViewSet, basename='integration-type')
router.register(r'integrations', views.IntegrationViewSet, basename='integration')
router.register(r'logs', views.APILogViewSet, basename='api-log')

urlpatterns = [
    path('', include(router.urls)),
    
    # Integration endpoints
    path('integrations/<uuid:pk>/test/', views.IntegrationViewSet.as_view({'post': 'test'}), name='test_integration'),
    path('integrations/<uuid:pk>/activate/', views.IntegrationViewSet.as_view({'post': 'activate'}), name='activate_integration'),
    path('integrations/<uuid:pk>/deactivate/', views.IntegrationViewSet.as_view({'post': 'deactivate'}), name='deactivate_integration'),
    path('integrations/<uuid:pk>/logs/', views.IntegrationViewSet.as_view({'get': 'logs'}), name='integration_logs'),
    path('integrations/<uuid:pk>/regenerate-webhook/', views.IntegrationViewSet.as_view({'post': 'regenerate_webhook_secret'}), name='regenerate_webhook'),
    path('integrations/<uuid:pk>/update-mpesa/', views.IntegrationViewSet.as_view({'put': 'update_mpesa_credentials'}), name='update_mpesa_credentials'),
    path('integrations/<uuid:pk>/statistics/', views.IntegrationViewSet.as_view({'get': 'statistics'}), name='integration_statistics'),
    
    # API log endpoints
    path('logs/statistics/', views.APILogViewSet.as_view({'get': 'statistics'}), name='api_log_statistics'),
    path('logs/retry-failed/', views.APILogViewSet.as_view({'post': 'retry_failed'}), name='retry_failed_logs'),
    
    # Webhook endpoints
    path('webhooks/mpesa/', views.mpesa_callback, name='mpesa_webhook'),
]