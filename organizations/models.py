from django.db import models
from django.core.validators import RegexValidator
import uuid
from django.utils.translation import gettext_lazy as _


class OrganizationType(models.Model):
    """Predefined organization types"""
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)  # For UI icons
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Organization Type'
        verbose_name_plural = 'Organization Types'


class Organization(models.Model):
    """Business/Client information"""
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('pending', 'Pending Approval'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    organization_type = models.ForeignKey(
        OrganizationType,
        on_delete=models.SET_NULL,
        null=True,
        related_name='organizations'
    )
    
    # Contact Information
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17)
    email = models.EmailField()
    website = models.URLField(blank=True)
    
    # Physical Address
    address = models.TextField()
    city = models.CharField(max_length=100)
    county = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='Kenya')
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Business Registration
    registration_number = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    business_license = models.CharField(max_length=100, blank=True)
    
    # Financial
    currency = models.CharField(max_length=3, default='KES')
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    
    # Status & Settings
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Branding
    logo = models.ImageField(upload_to='organization_logos/', null=True, blank=True)
    primary_color = models.CharField(max_length=7, default='#3B82F6')  # Hex color
    secondary_color = models.CharField(max_length=7, default='#10B981')
    
    # Payment Settings
    mpesa_paybill = models.CharField(max_length=20, blank=True)
    mpesa_till_number = models.CharField(max_length=20, blank=True)
    payment_methods = models.JSONField(default=list)  # ['mpesa', 'card', 'bank']
    
    # Subscription
    subscription_plan = models.CharField(max_length=50, default='basic')
    subscription_status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('trial', 'Trial'), ('expired', 'Expired')],
        default='trial'
    )
    subscription_expiry = models.DateField(null=True, blank=True)
    
    # Limits
    max_users = models.PositiveIntegerField(default=5)
    max_customers = models.PositiveIntegerField(default=100)
    monthly_transaction_limit = models.DecimalField(max_digits=12, decimal_places=2, default=1000000)
    
    # Metadata
    settings = models.JSONField(default=dict)  # Custom settings per organization
    metadata = models.JSONField(default=dict)  # Additional data
    
    # Audit
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_organizations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['created_at']),
        ]


class OrganizationMember(models.Model):
    """Users associated with organizations (staff, owners)"""
    
    ROLE_CHOICES = (
        ('owner', 'Owner'),
        ('admin', 'Administrator'),
        ('finance', 'Finance Manager'),
        ('support', 'Support Staff'),
        ('viewer', 'Viewer'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='members'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='organization_memberships'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='support')
    
    # Permissions (can be customized per role)
    can_manage_payments = models.BooleanField(default=False)
    can_manage_customers = models.BooleanField(default=False)
    can_manage_staff = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='invited_members'
    )
    invitation_accepted = models.BooleanField(default=False)
    
    # Dates
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['organization', 'user']
        verbose_name = 'Organization Member'
        verbose_name_plural = 'Organization Members'
    
    def __str__(self):
        return f"{self.user.email} - {self.role} at {self.organization.name}"