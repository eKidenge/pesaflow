from django.db import models
import uuid
from django.utils.translation import gettext_lazy as _


class NotificationTemplate(models.Model):
    """Reusable notification templates"""
    
    TYPE_CHOICES = (
        ('payment_received', 'Payment Received'),
        ('payment_reminder', 'Payment Reminder'),
        ('invoice_sent', 'Invoice Sent'),
        ('invoice_overdue', 'Invoice Overdue'),
        ('welcome', 'Welcome Message'),
        ('password_reset', 'Password Reset'),
        ('account_verification', 'Account Verification'),
        ('custom', 'Custom'),
    )
    
    CHANNEL_CHOICES = (
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
        ('push', 'Push Notification'),
        ('in_app', 'In-App Notification'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='notification_templates',
        null=True,
        blank=True
    )
    
    # Template Details
    name = models.CharField(max_length=200)
    template_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    
    # Content
    subject = models.CharField(max_length=200, blank=True)  # For email
    body = models.TextField()
    body_html = models.TextField(blank=True)  # For email/WhatsApp
    language = models.CharField(max_length=10, default='en')
    
    # Variables
    available_variables = models.JSONField(
        default=list,
        help_text="List of template variables available for this template"
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_system_template = models.BooleanField(default=False)  # System-wide templates
    
    # Audit
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
        unique_together = ['organization', 'name', 'channel', 'language']
    
    def __str__(self):
        return f"{self.name} ({self.get_channel_display()})"


class Notification(models.Model):
    """Sent notifications"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('read', 'Read'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Recipient
    recipient_type = models.CharField(
        max_length=20,
        choices=[
            ('customer', 'Customer'),
            ('user', 'User'),
            ('organization', 'Organization'),
            ('group', 'Group'),
        ]
    )
    recipient_id = models.CharField(max_length=100)  # ID of the recipient (customer_id, user_id, etc.)
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=17, blank=True)
    
    # Notification Details
    notification_type = models.CharField(max_length=50)
    channel = models.CharField(max_length=20, choices=NotificationTemplate.CHANNEL_CHOICES)
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    message_html = models.TextField(blank=True)
    
    # Status & Delivery
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery Info
    provider_message_id = models.CharField(max_length=200, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    delivery_attempts = models.PositiveIntegerField(default=0)
    failure_reason = models.TextField(blank=True)
    
    # Related Objects
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    invoice = models.ForeignKey(
        'payments.Invoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['status', 'scheduled_for']),
            models.Index(fields=['recipient_type', 'recipient_id']),
            models.Index(fields=['organization', 'created_at']),
            models.Index(fields=['channel', 'status']),
        ]
    
    def __str__(self):
        return f"{self.notification_type} to {self.recipient_phone or self.recipient_email}"
    
    def mark_as_sent(self, provider_message_id=None, provider_response=None):
        from django.utils import timezone
        self.status = 'sent'
        self.sent_at = timezone.now()
        if provider_message_id:
            self.provider_message_id = provider_message_id
        if provider_response:
            self.provider_response = provider_response
        self.save()
    
    def mark_as_failed(self, failure_reason):
        from django.utils import timezone
        self.status = 'failed'
        self.failure_reason = failure_reason
        self.delivery_attempts += 1
        self.save()


class NotificationPreference(models.Model):
    """User/Customer notification preferences"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Recipient
    recipient_type = models.CharField(max_length=20, choices=[('customer', 'Customer'), ('user', 'User')])
    recipient_id = models.CharField(max_length=100)
    
    # Preferences by notification type
    preferences = models.JSONField(
        default=dict,
        help_text="Dictionary of notification_type: {channel: enabled}"
    )
    
    # Global settings
    receive_sms = models.BooleanField(default=True)
    receive_email = models.BooleanField(default=True)
    receive_whatsapp = models.BooleanField(default=False)
    receive_push = models.BooleanField(default=False)
    
    # Quiet hours
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['organization', 'recipient_type', 'recipient_id']
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"Preferences for {self.recipient_type} {self.recipient_id}"


class NotificationQueue(models.Model):
    """Queue for scheduled notifications"""
    
    STATUS_CHOICES = (
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.OneToOneField(
        Notification,
        on_delete=models.CASCADE,
        related_name='queue_entry'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    priority = models.IntegerField(default=0)  # Higher number = higher priority
    processing_attempts = models.PositiveIntegerField(default=0)
    last_processing_attempt = models.DateTimeField(null=True, blank=True)
    
    # For recurring notifications
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.CharField(max_length=100, blank=True)  # cron expression or interval
    next_scheduled_time = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', 'next_scheduled_time', 'created_at']
        verbose_name = 'Notification Queue'
        verbose_name_plural = 'Notification Queue'
        indexes = [
            models.Index(fields=['status', 'next_scheduled_time']),
            models.Index(fields=['priority', 'created_at']),
        ]
    
    def __str__(self):
        return f"Queue entry for {self.notification}"