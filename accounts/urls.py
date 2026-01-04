from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'profiles', views.UserProfileViewSet, basename='profile')

urlpatterns = [
    # ==============================================
    # HTML TEMPLATE ROUTES (For your login/register pages)
    # ==============================================
    
    # Authentication pages
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # Password reset pages
    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         views.password_reset_confirm_view, 
         name='password_reset_confirm'),
    
    # Dashboard pages
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('business/dashboard/', views.business_dashboard, name='business_dashboard'),
    path('customer/dashboard/', views.customer_dashboard, name='customer_dashboard'),
    
    # ==============================================
    # API ROUTES (For AJAX/REST API calls)
    # ==============================================
    
    # Include router URLs
    path('api/', include(router.urls)),
    
    # Authentication APIs
    path('api/register/', views.UserRegistrationAPIView.as_view(), name='api_register'),
    path('api/logout/', views.api_logout, name='api_logout'),
    path('api/check-auth/', views.check_auth_status, name='check_auth_status'),
    
    # Custom user endpoints
    path('api/users/me/', views.UserViewSet.as_view({'get': 'me'}), name='user_me'),
    path('api/users/login/', views.UserViewSet.as_view({'post': 'login_api'}), name='api_login'),
    
    # Password management
    path('api/change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('api/password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('api/password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # Profile management
    path('api/update-profile/', views.update_profile_api, name='update_profile_api'),
    
    # Token refresh
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]