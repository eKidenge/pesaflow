from django.db import models
from django.core.validators import RegexValidator
import uuid
from django.utils.translation import gettext_lazy as _


class Customer(models.Model):
    """End-payee data (students, tenants, members)"""
    
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say'),
    )
    
    CUSTOMER_TYPE_CHOICES = (
        ('student', 'Student'),
        ('tenant', 'Tenant'),
        ('patient', 'Patient'),
        ('member', 'Member'),
        ('subscriber', 'Subscriber'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='customers'
    )
    
    # Basic Information
    customer_code = models.CharField(max_length=50, unique=True, editable=False)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    
    # Contact
    email = models.EmailField(blank=True)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17)
    alternate_phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    
    # Demographics
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=100, default='Kenyan')
    national_id = models.CharField(max_length=20, blank=True)
    passport_number = models.CharField(max_length=50, blank=True)
    
    # Address
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    county = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Customer Specific
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES)
    registration_number = models.CharField(max_length=100, blank=True)  # Student ID, Member ID, etc.
    
    # Account Information
    account_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)  # Percentage
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('suspended', 'Suspended'),
            ('graduated', 'Graduated'),
            ('terminated', 'Terminated'),
        ],
        default='active'
    )
    
    # Categories/Tags
    tags = models.JSONField(default=list, blank=True)  # ['vip', 'alumni', 'senior']
    
    # Relationships (for grouping)
    guardian_name = models.CharField(max_length=200, blank=True)
    guardian_phone = models.CharField(max_length=17, blank=True)
    guardian_relationship = models.CharField(max_length=50, blank=True)
    
    # Employment/Study Details
    employer_name = models.CharField(max_length=200, blank=True)
    employer_address = models.TextField(blank=True)
    school_name = models.CharField(max_length=200, blank=True)
    course = models.CharField(max_length=200, blank=True)
    year_of_study = models.IntegerField(null=True, blank=True)
    
    # Communication Preferences
    receive_sms = models.BooleanField(default=True)
    receive_email = models.BooleanField(default=True)
    receive_whatsapp = models.BooleanField(default=False)
    preferred_language = models.CharField(max_length=10, default='en')
    
    # Metadata
    custom_fields = models.JSONField(default=dict, blank=True)  # Organization-specific fields
    notes = models.TextField(blank=True)
    
    # Audit
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_customers'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_payment_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['customer_code']),
            models.Index(fields=['last_payment_date']),
        ]
        unique_together = ['organization', 'phone_number']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone_number})"
    
    def save(self, *args, **kwargs):
        if not self.customer_code:
            # Generate unique customer code: ORG-YYYYMM-XXXXX
            org_prefix = self.organization.name[:3].upper()
            from django.utils import timezone
            date_part = timezone.now().strftime('%Y%m')
            last_customer = Customer.objects.filter(
                organization=self.organization
            ).order_by('-created_at').first()
            
            if last_customer and last_customer.customer_code:
                last_num = int(last_customer.customer_code.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
                
            self.customer_code = f"{org_prefix}-{date_part}-{str(new_num).zfill(5)}"
        super().save(*args, **kwargs)


class CustomerGroup(models.Model):
    """Group customers for bulk operations (classes, buildings, etc.)"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='customer_groups'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Group Type
    group_type = models.CharField(
        max_length=50,
        choices=[
            ('class', 'Class/Grade'),
            ('building', 'Building/Block'),
            ('ward', 'Ward/Department'),
            ('plan', 'Subscription Plan'),
            ('custom', 'Custom Group'),
        ],
        default='custom'
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    default_payment_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payment_frequency = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly'),
            ('custom', 'Custom'),
        ],
        blank=True
    )
    
    customers = models.ManyToManyField(
        Customer,
        related_name='groups',
        blank=True
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.organization.name})"
    
    class Meta:
        unique_together = ['organization', 'name']
        verbose_name = 'Customer Group'
        verbose_name_plural = 'Customer Groups'