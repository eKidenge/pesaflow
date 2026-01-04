from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator, EmailValidator
from django.utils import timezone
import uuid
import os


class CustomUserManager(BaseUserManager):
    """Custom user manager for email as username"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', 'system_admin')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)
    
    def create_admin_user(self, email, password, **extra_fields):
        """Create a system admin user"""
        extra_fields.setdefault('user_type', 'system_admin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)
    
    def create_business_owner(self, email, password, **extra_fields):
        """Create a business owner user"""
        extra_fields.setdefault('user_type', 'business_owner')
        return self.create_user(email, password, **extra_fields)
    
    def create_client(self, email, password, **extra_fields):
        """Create a client/customer user"""
        extra_fields.setdefault('user_type', 'client')
        return self.create_user(email, password, **extra_fields)


class Organization(models.Model):
    """Organization model for business accounts"""
    
    BUSINESS_TYPES = [
        ('sole_proprietor', 'Sole Proprietor'),
        ('partnership', 'Partnership'),
        ('llc', 'Limited Liability Company'),
        ('corporation', 'Corporation'),
        ('non_profit', 'Non-Profit Organization'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True, validators=[EmailValidator()])
    
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+254...'"
    )
    phone = models.CharField(validators=[phone_regex], max_length=17)
    
    country = models.CharField(max_length=100, default='Kenya')
    address = models.TextField(blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    business_type = models.CharField(max_length=100, choices=BUSINESS_TYPES, blank=True)
    
    # Verification fields
    is_verified = models.BooleanField(default=False)
    verification_document = models.FileField(upload_to='business_docs/', blank=True, null=True)
    
    # Business settings
    currency = models.CharField(max_length=3, default='KES')
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    
    # Metadata
    settings = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    @property
    def total_users(self):
        return self.users.count()
    
    @property
    def active_users(self):
        return self.users.filter(is_active=True).count()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'


class User(AbstractUser):
    """Custom user model with email as username - INTEGRATED WITH TEMPLATES"""
    
    # Role choices - MATCHING TEMPLATE ROLES
    USER_TYPE_CHOICES = [
        ('system_admin', 'System Administrator'),     # Admin in template
        ('business_owner', 'Business Owner'),         # Business in template
        ('business_staff', 'Business Staff'),         # Business staff
        ('client', 'Client'),                         # Client in template
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # Remove username field
    email = models.EmailField(_('email address'), unique=True)
    
    # Personal information
    first_name = models.CharField(_('first name'), max_length=150)
    last_name = models.CharField(_('last name'), max_length=150)
    
    # Contact information
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+254...'"
    )
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    
    # User type and role
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='client')
    
    # Organization relationship (for business users)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    
    # Address information
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Kenya')
    
    # Client-specific fields (from register.html)
    id_number = models.CharField(max_length=50, blank=True, verbose_name='ID/Passport Number')
    
    # Business-specific fields (from register.html)
    position = models.CharField(max_length=100, blank=True, verbose_name='Position')
    department = models.CharField(max_length=100, blank=True, verbose_name='Department')
    
    # Verification fields
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, blank=True)
    verification_code_expiry = models.DateTimeField(null=True, blank=True)
    
    # Password reset
    password_reset_token = models.UUIDField(default=uuid.uuid4, editable=True)
    password_reset_token_expiry = models.DateTimeField(null=True, blank=True)
    
    # Profile picture
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        null=True,
        blank=True,
        default='profile_pictures/default.png'
    )
    
    # Settings and preferences
    receive_email_notifications = models.BooleanField(default=True)
    receive_sms_notifications = models.BooleanField(default=True)
    two_factor_enabled = models.BooleanField(default=False)
    
    # Security
    last_password_change = models.DateTimeField(null=True, blank=True)
    must_change_password = models.BooleanField(default=False)
    
    # Login tracking
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_location = models.CharField(max_length=255, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = CustomUserManager()
    
    def __str__(self):
        return f"{self.email} ({self.get_user_type_display()})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_system_admin(self):
        return self.user_type == 'system_admin'
    
    @property
    def is_business_owner(self):
        return self.user_type == 'business_owner'
    
    @property
    def is_business_staff(self):
        return self.user_type == 'business_staff'
    
    @property
    def is_client(self):
        return self.user_type == 'client'
    
    @property
    def template_role(self):
        """Map database user_type to template role names"""
        mapping = {
            'system_admin': 'admin',
            'business_owner': 'business',
            'business_staff': 'business',
            'client': 'client'
        }
        return mapping.get(self.user_type, 'client')
    
    def get_dashboard_url(self):
        """Get dashboard URL based on user type"""
        from django.urls import reverse
        
        if self.is_system_admin:
            return reverse('admin_dashboard')
        elif self.is_business_owner or self.is_business_staff:
            return reverse('business_dashboard')
        elif self.is_client:
            return reverse('customer_dashboard')
        else:
            return reverse('login')
    
    def generate_verification_code(self):
        """Generate 6-digit verification code"""
        import random
        code = str(random.randint(100000, 999999))
        self.verification_code = code
        self.verification_code_expiry = timezone.now() + timezone.timedelta(minutes=30)
        self.save()
        return code
    
    def check_verification_code(self, code):
        """Check if verification code is valid"""
        if not self.verification_code or not self.verification_code_expiry:
            return False
        
        if self.verification_code != code:
            return False
        
        if timezone.now() > self.verification_code_expiry:
            return False
        
        return True
    
    def mark_email_verified(self):
        """Mark email as verified"""
        self.email_verified = True
        self.save()
    
    def mark_phone_verified(self):
        """Mark phone as verified"""
        self.phone_verified = True
        self.save()
    
    def generate_password_reset_token(self):
        """Generate password reset token"""
        self.password_reset_token = uuid.uuid4()
        self.password_reset_token_expiry = timezone.now() + timezone.timedelta(hours=1)
        self.save()
        return self.password_reset_token
    
    def check_password_reset_token(self, token):
        """Check if password reset token is valid"""
        try:
            token_uuid = uuid.UUID(str(token))
            if self.password_reset_token != token_uuid:
                return False
            
            if not self.password_reset_token_expiry:
                return False
            
            if timezone.now() > self.password_reset_token_expiry:
                return False
            
            return True
        except (ValueError, AttributeError):
            return False
    
    def reset_password(self, new_password):
        """Reset user password"""
        self.set_password(new_password)
        self.password_reset_token = uuid.uuid4()  # Invalidate token
        self.password_reset_token_expiry = None
        self.last_password_change = timezone.now()
        self.save()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['user_type']),
            models.Index(fields=['organization', 'user_type']),
        ]


class UserProfile(models.Model):
    """Extended profile information for users"""
    
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_profile')
    
    # Personal information
    national_id = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    
    # Professional information
    designation = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    
    # Contact information
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=17, blank=True)
    website = models.URLField(blank=True)
    twitter = models.CharField(max_length=100, blank=True)
    linkedin = models.CharField(max_length=100, blank=True)
    
    # Preferences
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    language = models.CharField(max_length=10, default='en')
    currency = models.CharField(max_length=3, default='KES')
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    marketing_emails = models.BooleanField(default=True)
    
    # Security settings
    login_attempts = models.IntegerField(default=0)
    last_login_attempt = models.DateTimeField(null=True, blank=True)
    account_locked = models.BooleanField(default=False)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    preferences = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile of {self.user.email}"
    
    def increment_login_attempts(self):
        """Increment failed login attempts"""
        self.login_attempts += 1
        self.last_login_attempt = timezone.now()
        
        # Lock account after 5 failed attempts
        if self.login_attempts >= 5:
            self.account_locked = True
            self.account_locked_until = timezone.now() + timezone.timedelta(minutes=30)
        
        self.save()
    
    def reset_login_attempts(self):
        """Reset failed login attempts"""
        self.login_attempts = 0
        self.account_locked = False
        self.account_locked_until = None
        self.save()
    
    def is_account_locked(self):
        """Check if account is locked"""
        if not self.account_locked:
            return False
        
        if self.account_locked_until and timezone.now() > self.account_locked_until:
            self.reset_login_attempts()
            return False
        
        return True
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'


class LoginHistory(models.Model):
    """Track user login history"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    
    # Login details
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    location = models.CharField(max_length=255, blank=True)
    device_type = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=100, blank=True)
    
    # Login result
    success = models.BooleanField(default=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    
    # Timestamps
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    session_duration = models.DurationField(null=True, blank=True)
    
    def __str__(self):
        status = "Success" if self.success else "Failed"
        return f"{self.user.email} - {self.login_time} - {status}"
    
    def save(self, *args, **kwargs):
        # Auto-detect device and browser
        if self.user_agent:
            import re
            # Simple detection (in production use a proper library)
            if 'Mobile' in self.user_agent:
                self.device_type = 'Mobile'
            elif 'Tablet' in self.user_agent:
                self.device_type = 'Tablet'
            else:
                self.device_type = 'Desktop'
            
            # Browser detection
            if 'Chrome' in self.user_agent:
                self.browser = 'Chrome'
            elif 'Firefox' in self.user_agent:
                self.browser = 'Firefox'
            elif 'Safari' in self.user_agent and 'Chrome' not in self.user_agent:
                self.browser = 'Safari'
            elif 'Edge' in self.user_agent:
                self.browser = 'Edge'
            else:
                self.browser = 'Other'
            
            # OS detection
            if 'Windows' in self.user_agent:
                self.os = 'Windows'
            elif 'Mac' in self.user_agent:
                self.os = 'macOS'
            elif 'Linux' in self.user_agent:
                self.os = 'Linux'
            elif 'Android' in self.user_agent:
                self.os = 'Android'
            elif 'iOS' in self.user_agent:
                self.os = 'iOS'
            else:
                self.os = 'Other'
        
        super().save(*args, **kwargs)
    
    def record_logout(self):
        """Record logout time and calculate session duration"""
        self.logout_time = timezone.now()
        if self.login_time:
            self.session_duration = self.logout_time - self.login_time
        self.save()
    
    class Meta:
        verbose_name_plural = "Login Histories"
        ordering = ['-login_time']
        indexes = [
            models.Index(fields=['user', 'login_time']),
            models.Index(fields=['login_time']),
            models.Index(fields=['success']),
        ]


class VerificationCode(models.Model):
    """Store verification codes for email/phone verification"""
    
    PURPOSES = [
        ('email_verification', 'Email Verification'),
        ('phone_verification', 'Phone Verification'),
        ('password_reset', 'Password Reset'),
        ('two_factor', 'Two-Factor Authentication'),
        ('account_recovery', 'Account Recovery'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_codes')
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=50, choices=PURPOSES)
    
    # Validity
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    
    # Additional data
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.code} - {self.purpose}"
    
    def is_valid(self):
        """Check if code is still valid"""
        if self.used:
            return False
        
        if timezone.now() > self.expires_at:
            return False
        
        return True
    
    def mark_used(self):
        """Mark code as used"""
        self.used = True
        self.used_at = timezone.now()
        self.save()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'purpose', 'created_at']),
            models.Index(fields=['code', 'used']),
        ]


class UserSession(models.Model):
    """Track user sessions"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    
    # Session data
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    location = models.CharField(max_length=255, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_mobile = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    def __str__(self):
        return f"{self.user.email} - {self.session_key[:10]}..."
    
    def is_expired(self):
        """Check if session is expired"""
        return timezone.now() > self.expires_at
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = timezone.now()
        self.save()
    
    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['expires_at']),
        ]