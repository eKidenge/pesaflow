from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.db.models import Q
import uuid
import logging

from .models import User, UserProfile, Organization, LoginHistory
from .serializers import (
    UserSerializer, 
    UserProfileSerializer,
    UserRegistrationSerializer,
    UserLoginSerializer,
    ChangePasswordSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    OrganizationSerializer
)
from .permissions import IsSystemAdmin, IsBusinessOwner, IsBusinessStaff, IsUserOwner
from .forms import (
    UserLoginForm,
    UserRegistrationForm,
    AdminRegistrationForm,
    BusinessRegistrationForm,
    ClientRegistrationForm,
    PasswordResetForm,
    SetNewPasswordForm
)

logger = logging.getLogger(__name__)


# ==============================================
# HELPER FUNCTIONS
# ==============================================

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_redirect_url(user):
    """Determine redirect URL based on user type"""
    if user.is_system_admin():
        return reverse('admin_dashboard')
    elif user.user_type in ['business_owner', 'business_staff']:
        return reverse('business_dashboard')
    elif user.is_client():
        return reverse('customer_dashboard')
    else:
        return reverse('login')


def send_welcome_email(user):
    """Send welcome email to new user"""
    try:
        subject = f"Welcome to PesaFlow, {user.first_name}!"
        message = f"""
        Hello {user.first_name},
        
        Welcome to PesaFlow! Your account has been successfully created.
        
        Account Details:
        - Email: {user.email}
        - Account Type: {user.get_user_type_display()}
        - Status: Active
        
        Please verify your email address to unlock all features.
        
        If you have any questions, contact our support team at support@pesaflow.co.ke
        
        Best regards,
        The PesaFlow Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")


# ==============================================
# TEMPLATE VIEWS (For your HTML templates)
# ==============================================

def login_view(request):
    """
    Handle login requests from the template - INTEGRATED WITH YOUR LOGIN.HTML
    """
    # If user is already logged in, redirect to appropriate dashboard
    if request.user.is_authenticated:
        return redirect(get_user_redirect_url(request.user))
    
    if request.method == 'POST':
        # Extract form data
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role', 'business')
        remember_me = request.POST.get('remember_me') == 'on'
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                
                # Handle "remember me"
                if remember_me:
                    request.session.set_expiry(1209600)  # 2 weeks
                else:
                    request.session.set_expiry(0)  # Session cookie
                
                # Log login history
                LoginHistory.objects.create(
                    user=user,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    success=True
                )
                
                # Set session role
                request.session['user_role'] = role
                
                # Redirect based on role - MATCHING YOUR TEMPLATE LOGIC
                if role == 'admin':
                    if user.is_system_admin():
                        messages.success(request, 'Welcome to Admin Dashboard!')
                        return redirect('admin_dashboard')
                    else:
                        messages.error(request, 'Admin access denied. Please login with admin credentials.')
                        logout(request)
                        return redirect('login')
                
                elif role == 'business':
                    if user.user_type in ['business_owner', 'business_staff']:
                        messages.success(request, 'Welcome to Business Dashboard!')
                        return redirect('business_dashboard')
                    else:
                        messages.error(request, 'Business account required.')
                        logout(request)
                        return redirect('login')
                
                elif role == 'client':
                    if user.is_client():
                        messages.success(request, 'Welcome to Customer Portal!')
                        return redirect('customer_dashboard')
                    else:
                        messages.error(request, 'Client account required.')
                        logout(request)
                        return redirect('login')
                
            else:
                messages.error(request, 'Your account is disabled. Please contact support.')
        else:
            messages.error(request, 'Invalid username or password.')
            
            # Track failed login attempts
            try:
                user = User.objects.get(Q(username=username) | Q(email=username))
                if hasattr(user, 'profile'):
                    user.profile.login_attempts += 1
                    user.profile.last_login_attempt = timezone.now()
                    user.profile.save()
                    
                    # Log failed attempt
                    LoginHistory.objects.create(
                        user=user,
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        success=False
                    )
            except User.DoesNotExist:
                pass
        
        # If authentication failed, stay on login page
        return render(request, 'accounts/login.html', {
            'username': username,
            'role': role,
            'remember_me': remember_me
        })
    
    # GET request - show login form
    return render(request, 'accounts/login.html', {
        'role': request.GET.get('role', 'business')
    })


def register_view(request):
    """
    Handle registration requests - INTEGRATED WITH YOUR REGISTER.HTML
    """
    # If user is already logged in, redirect to dashboard
    if request.user.is_authenticated:
        return redirect(get_user_redirect_url(request.user))
    
    if request.method == 'POST':
        role = request.POST.get('role', 'business')
        
        # Map template role to database user_type
        role_mapping = {
            'admin': 'system_admin',
            'business': 'business_owner',
            'client': 'client'
        }
        
        try:
            with transaction.atomic():
                # Extract common fields
                email = request.POST.get('email')
                first_name = request.POST.get('first_name')
                last_name = request.POST.get('last_name')
                phone = request.POST.get('phone')
                country = request.POST.get('country')
                password = request.POST.get('password')
                confirm_password = request.POST.get('confirm_password')
                
                # Validation
                if User.objects.filter(email=email).exists():
                    messages.error(request, 'Email already registered.')
                    return redirect('register')
                
                if password != confirm_password:
                    messages.error(request, 'Passwords do not match.')
                    return redirect('register')
                
                # Create user
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    user_type=role_mapping.get(role, 'client'),
                    country=country
                )
                
                # Handle role-specific fields
                if role == 'business':
                    business_name = request.POST.get('business_name')
                    business_type = request.POST.get('business_type')
                    business_address = request.POST.get('business_address', '')
                    
                    if business_name:
                        organization = Organization.objects.create(
                            name=business_name,
                            email=email,
                            phone=phone,
                            country=country,
                            business_type=business_type,
                            address=business_address
                        )
                        user.organization = organization
                        user.save()
                
                elif role == 'client':
                    id_number = request.POST.get('id_number', '')
                    address = request.POST.get('address', '')
                    
                    user.id_number = id_number
                    user.address = address
                    user.save()
                
                # Create user profile
                UserProfile.objects.create(user=user)
                
                # Send welcome email
                send_welcome_email(user)
                
                # Log the user in automatically
                login(request, user)
                
                # Redirect with success message
                messages.success(request, f'Account created successfully! Welcome to PesaFlow.')
                
                # Redirect based on role
                if role == 'admin':
                    return redirect('admin_dashboard')
                elif role == 'business':
                    return redirect('business_dashboard')
                else:
                    return redirect('customer_dashboard')
                    
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            messages.error(request, f'An error occurred during registration: {str(e)}')
            return redirect('register')
    
    # GET request - show registration form
    return render(request, 'accounts/register.html')


def logout_view(request):
    """
    Handle user logout
    """
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


def password_reset_view(request):
    """
    Handle password reset request
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = User.objects.get(email=email)
            
            # Generate password reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Build reset URL
            reset_url = request.build_absolute_uri(
                reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
            )
            
            # Send reset email
            send_mail(
                subject='Password Reset Request - PesaFlow',
                message=f'Click the link to reset your password: {reset_url}\n\nThis link will expire in 1 hour.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )
            
            messages.success(request, 'Password reset link has been sent to your email.')
            return redirect('login')
            
        except User.DoesNotExist:
            # Still show success to prevent email enumeration
            messages.success(request, 'If your email exists in our system, you will receive a reset link.')
            return redirect('login')
    
    return render(request, 'accounts/password_reset.html')


def password_reset_confirm_view(request, uidb64, token):
    """
    Handle password reset confirmation
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if new_password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return render(request, 'accounts/password_reset_confirm.html')
            
            if len(new_password) < 8:
                messages.error(request, 'Password must be at least 8 characters long.')
                return render(request, 'accounts/password_reset_confirm.html')
            
            # Set new password
            user.set_password(new_password)
            user.save()
            
            messages.success(request, 'Password has been reset successfully. You can now login with your new password.')
            return redirect('login')
        
        return render(request, 'accounts/password_reset_confirm.html')
    else:
        messages.error(request, 'The password reset link is invalid or has expired.')
        return redirect('password_reset')


# ==============================================
# DASHBOARD VIEWS
# ==============================================

def admin_dashboard(request):
    """Admin dashboard view - RENDERS YOUR ADMIN DASHBOARD"""
    if not request.user.is_authenticated:
        messages.error(request, 'Please login to access the dashboard.')
        return redirect('login')
    
    if not request.user.is_system_admin():
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect(get_user_redirect_url(request.user))
    
    # Get dashboard statistics
    total_users = User.objects.count()
    total_businesses = Organization.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    
    context = {
        'total_users': total_users,
        'total_businesses': total_businesses,
        'active_users': active_users,
        'recent_users': User.objects.order_by('-date_joined')[:10],
        'recent_organizations': Organization.objects.order_by('-created_at')[:10],
    }
    
    return render(request, 'dashboard/admin_dashboard.html', context)


def business_dashboard(request):
    """Business dashboard view - RENDERS YOUR BUSINESS DASHBOARD"""
    if not request.user.is_authenticated:
        messages.error(request, 'Please login to access the dashboard.')
        return redirect('login')
    
    if not request.user.user_type in ['business_owner', 'business_staff']:
        messages.error(request, 'Access denied. Business account required.')
        return redirect(get_user_redirect_url(request.user))
    
    user = request.user
    organization = user.organization
    
    # Get business-specific statistics
    business_users = User.objects.filter(organization=organization).count() if organization else 0
    
    context = {
        'user': user,
        'organization': organization,
        'total_staff': business_users,
        'user_type_display': user.get_user_type_display(),
    }
    
    return render(request, 'dashboard/business_dashboard.html', context)


def customer_dashboard(request):
    """Customer dashboard view - RENDERS YOUR CUSTOMER DASHBOARD"""
    if not request.user.is_authenticated:
        messages.error(request, 'Please login to access the dashboard.')
        return redirect('login')
    
    if not request.user.is_client():
        messages.error(request, 'Access denied. Please login as a customer.')
        return redirect(get_user_redirect_url(request.user))
    
    user = request.user
    
    context = {
        'user': user,
        'full_name': user.get_full_name(),
        'email_verified': user.email_verified,
        'phone_verified': user.phone_verified,
    }
    
    return render(request, 'dashboard/customer_dashboard.html', context)


# ==============================================
# API VIEWSETS (REST Framework - KEEPING YOUR EXISTING CODE)
# ==============================================

class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users via API
    """
    queryset = User.objects.select_related('organization', 'profile').all()
    serializer_class = UserSerializer
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action == 'create':
            # Allow anyone to register
            permission_classes = [permissions.AllowAny]
        elif self.action in ['update', 'partial_update', 'destroy']:
            # Only allow user owners, system admins, or business owners
            permission_classes = [IsUserOwner | IsSystemAdmin | IsBusinessOwner]
        elif self.action in ['retrieve', 'list']:
            # Allow authenticated users to view
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter queryset based on user role.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return User.objects.none()
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.user_type == 'business_owner':
            # Business owners can see users in their organization
            if user.organization:
                return self.queryset.filter(organization=user.organization)
            return User.objects.none()
        
        elif user.user_type == 'business_staff':
            # Staff can see users in their organization
            if user.organization:
                return self.queryset.filter(organization=user.organization)
            return User.objects.none()
        
        else:
            # Regular users can only see themselves
            return self.queryset.filter(id=user.id)
    
    def perform_create(self, serializer):
        """
        Set organization for business users based on the creating user.
        """
        user = self.request.user
        
        if user.is_authenticated and user.organization and \
           serializer.validated_data.get('user_type') in ['business_owner', 'business_staff']:
            serializer.save(organization=user.organization)
        else:
            serializer.save()
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """
        Get current user profile.
        """
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsUserOwner | IsSystemAdmin])
    def verify_email(self, request, pk=None):
        """
        Verify user email.
        """
        user = self.get_object()
        user.email_verified = True
        user.save()
        return Response({'status': 'email verified'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsUserOwner | IsSystemAdmin])
    def verify_phone(self, request, pk=None):
        """
        Verify user phone number.
        """
        user = self.get_object()
        user.phone_verified = True
        user.save()
        return Response({'status': 'phone verified'})
    
    @action(detail=False, methods=['get'], permission_classes=[IsSystemAdmin | IsBusinessOwner])
    def statistics(self, request):
        """
        Get user statistics.
        """
        user = request.user
        total_users = User.objects.count()
        
        if user.user_type == 'business_owner' and user.organization:
            org_users = User.objects.filter(organization=user.organization).count()
            stats = {
                'total_users': org_users,
                'active_users': User.objects.filter(organization=user.organization, is_active=True).count(),
                'verified_emails': User.objects.filter(organization=user.organization, email_verified=True).count(),
                'verified_phones': User.objects.filter(organization=user.organization, phone_verified=True).count(),
                'by_user_type': {
                    utype[0]: User.objects.filter(organization=user.organization, user_type=utype[0]).count()
                    for utype in User.USER_TYPE_CHOICES
                }
            }
        else:
            stats = {
                'total_users': total_users,
                'active_users': User.objects.filter(is_active=True).count(),
                'verified_emails': User.objects.filter(email_verified=True).count(),
                'verified_phones': User.objects.filter(phone_verified=True).count(),
                'by_user_type': {
                    utype[0]: User.objects.filter(user_type=utype[0]).count()
                    for utype in User.USER_TYPE_CHOICES
                }
            }
        
        return Response(stats)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login_api(self, request):
        """
        API login endpoint - for AJAX login from your templates
        """
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            role = serializer.validated_data.get('role', 'business')
            
            user = authenticate(username=username, password=password)
            
            if user and user.is_active:
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                
                # Log login
                LoginHistory.objects.create(
                    user=user,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    success=True
                )
                
                return Response({
                    'user': UserSerializer(user).data,
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'redirect_url': get_user_redirect_url(user),
                    'role': role
                })
            
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user profiles.
    """
    queryset = UserProfile.objects.select_related('user').all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsUserOwner]
    
    def get_queryset(self):
        """
        Users can only see their own profile.
        System admins can see all profiles.
        """
        user = self.request.user
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.user_type == 'business_owner' and user.organization:
            # Business owners can see profiles of users in their organization
            return self.queryset.filter(user__organization=user.organization)
        
        elif user.user_type == 'business_staff' and user.organization:
            # Staff can see profiles of users in their organization
            return self.queryset.filter(user__organization=user.organization)
        
        else:
            # Regular users can only see their own profile
            return self.queryset.filter(user=user)
    
    def get_object(self):
        """
        For retrieve/update/delete, allow users to access their own profile
        by using their user ID in the URL.
        """
        if 'pk' in self.kwargs:
            # If pk is provided, try to get that profile
            return super().get_object()
        
        # Otherwise return current user's profile
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile
    
    def perform_create(self, serializer):
        """
        Automatically associate profile with the current user.
        """
        serializer.save(user=self.request.user)


class UserRegistrationAPIView(generics.CreateAPIView):
    """
    Register a new user via API.
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Create user profile
        UserProfile.objects.create(user=user)
        
        # Send welcome email
        if user.email:
            try:
                send_mail(
                    subject='Welcome to PesaFlow',
                    message=f'Welcome {user.email}! Your account has been created successfully.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception:
                pass
        
        return Response({
            'user': UserSerializer(user, context=self.get_serializer_context()).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)


class ChangePasswordView(generics.UpdateAPIView):
    """
    Change user password.
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            # Check old password
            if not user.check_password(serializer.validated_data['old_password']):
                return Response(
                    {'old_password': ['Wrong password.']},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Set new password
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            return Response({'status': 'password changed'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(generics.GenericAPIView):
    """
    Request password reset.
    """
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        user = User.objects.filter(email=email).first()
        
        if user:
            # Generate reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Send reset email
            reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
            
            try:
                send_mail(
                    subject='Password Reset Request',
                    message=f'Click the link to reset your password: {reset_link}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=True,
                )
            except Exception:
                pass
        
        # Always return success to prevent email enumeration
        return Response({
            'message': 'If the email exists, a reset link has been sent.'
        })


class PasswordResetConfirmView(generics.GenericAPIView):
    """
    Confirm password reset.
    """
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        uidb64 = serializer.validated_data['uid']
        new_password = serializer.validated_data['new_password']
        
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        
        if user and default_token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save()
            
            return Response({'message': 'Password has been reset successfully.'})
        
        return Response(
            {'error': ['Invalid or expired token.']},
            status=status.HTTP_400_BAD_REQUEST
        )


# ==============================================
# ADDITIONAL API ENDPOINTS FOR TEMPLATE INTEGRATION
# ==============================================

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def api_logout(request):
    """API logout endpoint for AJAX logout"""
    try:
        refresh_token = request.data.get("refresh_token")
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"message": "Successfully logged out"}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def update_profile_api(request):
    """Update user profile via API"""
    user = request.user
    data = request.data.copy()
    
    # Update user fields
    if 'first_name' in data:
        user.first_name = data['first_name']
    if 'last_name' in data:
        user.last_name = data['last_name']
    if 'phone' in data:
        user.phone = data['phone']
    
    user.save()
    
    # Update profile if it exists
    if hasattr(user, 'profile'):
        profile = user.profile
        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
        if 'bio' in data:
            profile.bio = data['bio']
        profile.save()
    
    return Response({
        'message': 'Profile updated successfully',
        'user': UserSerializer(user).data
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def check_auth_status(request):
    """Check if user is authenticated (for template JavaScript)"""
    if request.user.is_authenticated:
        return Response({
            'authenticated': True,
            'user': UserSerializer(request.user).data,
            'role': request.user.user_type
        })
    return Response({'authenticated': False})


# ==============================================
# ERROR HANDLING VIEWS
# ==============================================

def handler404(request, exception):
    """Custom 404 page"""
    return render(request, 'errors/404.html', status=404)


def handler500(request):
    """Custom 500 page"""
    return render(request, 'errors/500.html', status=500)


def handler403(request, exception):
    """Custom 403 page"""
    return render(request, 'errors/403.html', status=403)


def handler400(request, exception):
    """Custom 400 page"""
    return render(request, 'errors/400.html', status=400)