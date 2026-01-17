from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'types', views.OrganizationTypeViewSet, basename='organization-type')
router.register(r'organizations', views.OrganizationViewSet, basename='organization')
router.register(r'members', views.OrganizationMemberViewSet, basename='organization-member')

urlpatterns = [
    path('organizations/create/', views.OrganizationViewSet.as_view({'get': 'create'}), name='organizations_create'),
    # ADD THIS LINE (inside urlpatterns):
    path('organizations/list/', views.OrganizationViewSet.as_view({'get': 'list'}), name='organizations_list'),
    
    path('', include(router.urls)),
]