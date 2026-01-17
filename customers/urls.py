from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'customers', views.CustomerViewSet, basename='customer')
router.register(r'groups', views.CustomerGroupViewSet, basename='customer-group')

urlpatterns = [
    # Template views
    path('list/', views.CustomerViewSet.as_view({'get': 'list'}), name='customers_list'),
    
    # ADD THIS LINE:
    path('create/', views.CustomerViewSet.as_view({'get': 'create'}), name='customers_create'),
    
    # Include router URLs for API
    path('', include(router.urls)),
]