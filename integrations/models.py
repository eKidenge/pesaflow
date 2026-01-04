from django.db import models
import uuid
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinLengthValidator
import secrets


class IntegrationType(models.Model):
    """Types of external integrations"""
    
    name = models.CharField(max_length=100, unique=True)
    provider = models.CharField(max_length=100)  # safaricom, africas_talking, etc.
    category = models.CharField(
        max_length=50,
        choices=[
            ('payment', 'Payment Gateway'),
            ('sms', 'SMS Gateway'),
            ('email', 'Email Service'),
            ('whatsapp', 'WhatsApp API'),
            ('analytics', 'Analytics'),
            ('other', 'Other'),
        ]
    )
    documentation_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.provider})"
    
    class Meta:
        verbose_name = 'Integration Type'
        verbose_name_plural = 'Integration Types'


class Integration(models.Model):
    """Organization's integration configurations"""
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('testing', 'Testing'),
        ('failed', 'Failed Configuration'),
    )
    
    ENVIRONMENT_CHOICES = (
        ('sandbox', 'Sandbox/Test'),
        ('production', 'Production'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='integrations'
    )
    integration_type = models.ForeignKey(
        IntegrationType,
        on_delete=models.CASCADE,
        related_name='integrations'
    )
    
    # Configuration
    name = models.CharField(max_length=200)
    environment = models.CharField(max_length=20, choices=ENVIRONMENT_CHOICES, default='sandbox')
    
    # API Credentials (encrypted in production)
    api_key = models.CharField(max_length=500, blank=True)
    api_secret = models.CharField(max_length=500, blank=True)
    api_url = models.URLField(blank=True)
    consumer_key = models.CharField(max_length=500, blank=True)
    consumer_secret = models.CharField(max_length=500, blank=True)
    passkey = models.CharField(max_length=500, blank=True)
    
    # Webhook Configuration
    webhook_url = models.URLField(blank=True)
    webhook_secret = models.CharField(max_length=100, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    is_default = models.BooleanField(default=False)  # Default integration for this type
    
    # Settings
    settings = models.JSONField(default=dict, blank=True)  # Provider-specific settings
    metadata = models.JSONField(default=dict, blank=True)
    
    # Usage Stats
    last_used = models.DateTimeField(null=True, blank=True)
    total_requests = models.PositiveIntegerField(default=0)
    successful_requests = models.PositiveIntegerField(default=0)
    failed_requests = models.PositiveIntegerField(default=0)
    
    # Audit
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_integrations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Integration'
        verbose_name_plural = 'Integrations'
        unique_together = ['organization', 'integration_type', 'environment']
    
    def __str__(self):
        return f"{self.name} ({self.get_environment_display()})"
    
    def save(self, *args, **kwargs):
        if not self.webhook_secret and self.integration_type.category == 'payment':
            self.webhook_secret = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


class APILog(models.Model):
    """Logs for all API requests and responses"""
    
    REQUEST_TYPE_CHOICES = (
        ('mpesa_stk_push', 'M-Pesa STK Push'),
        ('mpesa_c2b', 'M-Pesa C2B'),
        ('mpesa_b2c', 'M-Pesa B2C'),
        ('sms_send', 'SMS Send'),
        ('email_send', 'Email Send'),
        ('whatsapp_send', 'WhatsApp Send'),
        ('webhook', 'Webhook'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('timeout', 'Timeout'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(
        Integration,
        on_delete=models.SET_NULL,
        null=True,
        related_name='api_logs'
    )
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='api_logs'
    )
    
    # Request Details
    request_type = models.CharField(max_length=50, choices=REQUEST_TYPE_CHOICES)
    endpoint = models.CharField(max_length=500)
    method = models.CharField(max_length=10, choices=[('GET', 'GET'), ('POST', 'POST'), ('PUT', 'PUT'), ('DELETE', 'DELETE')])
    
    # Payload
    request_headers = models.JSONField(default=dict, blank=True)
    request_body = models.JSONField(default=dict, blank=True)
    request_timestamp = models.DateTimeField()
    
    # Response
    response_status_code = models.IntegerField(null=True, blank=True)
    response_headers = models.JSONField(default=dict, blank=True)
    response_body = models.JSONField(default=dict, blank=True)
    response_timestamp = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    # Metadata
    correlation_id = models.CharField(max_length=100, blank=True)
    external_id = models.CharField(max_length=100, blank=True)
    duration_ms = models.FloatField(null=True, blank=True)  # Response time in milliseconds
    
    # Related Objects
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_logs'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-request_timestamp']
        verbose_name = 'API Log'
        verbose_name_plural = 'API Logs'
        indexes = [
            models.Index(fields=['request_timestamp']),
            models.Index(fields=['status', 'request_timestamp']),
            models.Index(fields=['correlation_id']),
            models.Index(fields=['external_id']),
        ]
    
    def __str__(self):
        return f"{self.request_type} - {self.status} - {self.request_timestamp}"