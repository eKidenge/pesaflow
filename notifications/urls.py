from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'templates', views.NotificationTemplateViewSet, basename='notification-template')
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'preferences', views.NotificationPreferenceViewSet, basename='notification-preference')
router.register(r'queue', views.NotificationQueueViewSet, basename='notification-queue')

urlpatterns = [
    path('', include(router.urls)),
    
    # Notification endpoints
    path('notifications/send/', views.NotificationViewSet.as_view({'post': 'send'}), name='send_notification'),
    path('notifications/send/bulk/', views.NotificationViewSet.as_view({'post': 'send_bulk'}), name='send_bulk_notification'),
    path('notifications/<uuid:pk>/resend/', views.NotificationViewSet.as_view({'post': 'resend'}), name='resend_notification'),
    path('notifications/statistics/', views.NotificationViewSet.as_view({'get': 'statistics'}), name='notification_statistics'),
    path('notifications/my/', views.NotificationViewSet.as_view({'get': 'my_notifications'}), name='my_notifications'),
    
    path('notifications/list/', views.NotificationViewSet.as_view({'get': 'list'}), name='notifications_list'),
    # ADD THIS LINE:
    path('templates/list/', views.NotificationTemplateViewSet.as_view({'get': 'list'}), name='notifications_templates_list'),
    # Template endpoints
    path('templates/<uuid:pk>/duplicate/', views.NotificationTemplateViewSet.as_view({'post': 'duplicate'}), name='duplicate_template'),
    path('templates/<uuid:pk>/test/', views.NotificationTemplateViewSet.as_view({'post': 'test'}), name='test_template'),
    
    # Preference endpoints
    path('preferences/defaults/', views.NotificationPreferenceViewSet.as_view({'get': 'defaults'}), name='default_preferences'),
    
    # Queue endpoints
    path('queue/process/', views.NotificationQueueViewSet.as_view({'post': 'process_queue'}), name='process_queue'),
]