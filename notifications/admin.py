from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import timedelta
from .models import NotificationTemplate, Notification, NotificationPreference, NotificationQueue


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """Admin configuration for NotificationTemplate model"""
    
    list_display = [
        'name', 'organization', 'template_type', 'channel',
        'language', 'is_active', 'is_system_template',
        'created_at', 'usage_count'
    ]
    
    list_filter = [
        'template_type', 'channel', 'language', 'is_active',
        'is_system_template', 'organization', 'created_at'
    ]
    
    search_fields = [
        'name', 'subject', 'body', 'organization__name'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'usage_count', 'preview_subject',
        'preview_body'
    ]
    
    fieldsets = (
        (_('Template Information'), {
            'fields': (
                'organization', 'name', 'template_type', 'channel',
                'language', 'is_active', 'is_system_template'
            )
        }),
        (_('Content'), {
            'fields': (
                'subject', 'body', 'body_html', 'available_variables'
            )
        }),
        (_('Preview'), {
            'fields': ('preview_subject', 'preview_body'),
            'classes': ('collapse',)
        }),
        (_('Statistics'), {
            'fields': ('usage_count',),
            'classes': ('collapse',)
        }),
        (_('Audit'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ['organization', 'created_by']
    
    actions = [
        'activate_templates', 'deactivate_templates',
        'duplicate_templates', 'test_templates'
    ]
    
    def usage_count(self, obj):
        """Display usage count"""
        return obj.notifications.count()
    usage_count.short_description = 'Usage Count'
    
    def preview_subject(self, obj):
        """Display subject preview"""
        if obj.subject:
            if len(obj.subject) > 100:
                return f"{obj.subject[:100]}..."
            return obj.subject
        return "No subject"
    preview_subject.short_description = 'Subject Preview'
    
    def preview_body(self, obj):
        """Display body preview"""
        if obj.body:
            if len(obj.body) > 200:
                return f"{obj.body[:200]}..."
            return obj.body
        return "No body"
    preview_body.short_description = 'Body Preview'
    
    def activate_templates(self, request, queryset):
        """Activate selected templates"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} templates were activated.')
    activate_templates.short_description = "Activate selected templates"
    
    def deactivate_templates(self, request, queryset):
        """Deactivate selected templates"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} templates were deactivated.')
    deactivate_templates.short_description = "Deactivate selected templates"
    
    def duplicate_templates(self, request, queryset):
        """Duplicate selected templates"""
        count = 0
        for template in queryset:
            new_template = NotificationTemplate.objects.create(
                organization=template.organization,
                name=f"{template.name} (Copy)",
                template_type=template.template_type,
                channel=template.channel,
                subject=template.subject,
                body=template.body,
                body_html=template.body_html,
                language=template.language,
                available_variables=template.available_variables,
                is_active=template.is_active,
                is_system_template=template.is_system_template,
                created_by=request.user
            )
            count += 1
        
        self.message_user(request, f'{count} templates were duplicated.')
    duplicate_templates.short_description = "Duplicate templates"
    
    def test_templates(self, request, queryset):
        """Test selected templates"""
        self.message_user(
            request,
            f'Ready to test {queryset.count()} templates. '
            f'Select a template and use the "Test" button in the detail view.'
        )
    test_templates.short_description = "Test templates"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('organization', 'created_by')
        qs = qs.annotate(usage_count=Count('notifications'))
        return qs


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin configuration for Notification model"""
    
    list_display = [
        'notification_type', 'organization', 'recipient_display',
        'channel', 'status', 'priority', 'sent_at', 'delivered_at',
        'read_at', 'created_at', 'has_template'
    ]
    
    list_filter = [
        'status', 'channel', 'notification_type', 'priority',
        'organization', 'recipient_type', 'created_at', 'sent_at',
        'delivered_at', 'read_at'
    ]
    
    search_fields = [
        'recipient_email', 'recipient_phone', 'subject', 'message',
        'provider_message_id', 'organization__name'
    ]
    
    readonly_fields = [
        'sent_at', 'delivered_at', 'read_at', 'provider_message_id',
        'provider_response', 'delivery_attempts', 'created_at',
        'updated_at', 'delivery_time', 'recipient_details',
        'related_objects'
    ]
    
    fieldsets = (
        (_('Notification Information'), {
            'fields': (
                'organization', 'notification_type', 'channel',
                'priority', 'status'
            )
        }),
        (_('Recipient'), {
            'fields': (
                'recipient_type', 'recipient_id', 'recipient_details',
                'recipient_email', 'recipient_phone'
            )
        }),
        (_('Content'), {
            'fields': ('subject', 'message', 'message_html')
        }),
        (_('Schedule'), {
            'fields': ('scheduled_for',),
            'classes': ('collapse',)
        }),
        (_('Delivery Information'), {
            'fields': (
                'sent_at', 'delivered_at', 'read_at', 'delivery_time',
                'provider_message_id', 'provider_response',
                'delivery_attempts', 'failure_reason'
            ),
            'classes': ('collapse',)
        }),
        (_('Related Objects'), {
            'fields': ('template', 'payment', 'invoice', 'related_objects'),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = [
        'organization', 'template', 'payment', 'invoice'
    ]
    
    actions = [
        'resend_notifications', 'mark_as_read', 'mark_as_unread',
        'cancel_scheduled', 'export_selected_notifications'
    ]
    
    def recipient_display(self, obj):
        """Display recipient information"""
        if obj.recipient_type == 'user':
            from accounts.models import User
            try:
                user = User.objects.get(id=obj.recipient_id)
                url = reverse('admin:accounts_user_change', args=[user.id])
                return format_html(
                    '<a href="{}">User: {}</a>',
                    url,
                    user.email
                )
            except User.DoesNotExist:
                return f"User: {obj.recipient_id}"
        elif obj.recipient_type == 'customer':
            from customers.models import Customer
            try:
                customer = Customer.objects.get(id=obj.recipient_id)
                url = reverse('admin:customers_customer_change', args=[customer.id])
                return format_html(
                    '<a href="{}">Customer: {} ({})</a>',
                    url,
                    f"{customer.first_name} {customer.last_name}",
                    customer.phone_number
                )
            except Customer.DoesNotExist:
                return f"Customer: {obj.recipient_id}"
        elif obj.recipient_email:
            return f"Email: {obj.recipient_email}"
        elif obj.recipient_phone:
            return f"Phone: {obj.recipient_phone}"
        return f"{obj.recipient_type}: {obj.recipient_id}"
    recipient_display.short_description = 'Recipient'
    
    def delivery_time(self, obj):
        """Calculate delivery time"""
        if obj.sent_at and obj.delivered_at:
            duration = obj.delivered_at - obj.sent_at
            return f"{duration.total_seconds():.1f} seconds"
        return "N/A"
    delivery_time.short_description = 'Delivery Time'
    
    def recipient_details(self, obj):
        """Display recipient details"""
        details = []
        
        if obj.recipient_type == 'user':
            from accounts.models import User
            try:
                user = User.objects.get(id=obj.recipient_id)
                details.append(f"Name: {user.get_full_name()}")
                details.append(f"Email: {user.email}")
                details.append(f"Phone: {user.phone_number}")
            except User.DoesNotExist:
                details.append("User not found")
        
        elif obj.recipient_type == 'customer':
            from customers.models import Customer
            try:
                customer = Customer.objects.get(id=obj.recipient_id)
                details.append(f"Name: {customer.first_name} {customer.last_name}")
                details.append(f"Email: {customer.email}")
                details.append(f"Phone: {customer.phone_number}")
                details.append(f"Organization: {customer.organization.name}")
            except Customer.DoesNotExist:
                details.append("Customer not found")
        
        return format_html('<br>'.join(details))
    recipient_details.short_description = 'Recipient Details'
    
    def related_objects(self, obj):
        """Display related objects as links"""
        links = []
        
        if obj.template:
            url = reverse('admin:notifications_notificationtemplate_change', args=[obj.template.id])
            links.append(f'<a href="{url}">Template: {obj.template.name}</a>')
        
        if obj.payment:
            url = reverse('admin:payments_payment_change', args=[obj.payment.id])
            links.append(f'<a href="{url}">Payment: {obj.payment.payment_reference}</a>')
        
        if obj.invoice:
            url = reverse('admin:payments_invoice_change', args=[obj.invoice.id])
            links.append(f'<a href="{url}">Invoice: {obj.invoice.invoice_number}</a>')
        
        if not links:
            return "No related objects"
        
        return format_html('<br>'.join(links))
    related_objects.short_description = 'Related Objects'
    
    def has_template(self, obj):
        """Check if notification has template"""
        return obj.template is not None
    has_template.boolean = True
    has_template.short_description = 'Has Template'
    
    def resend_notifications(self, request, queryset):
        """Resend selected notifications"""
        from notifications.tasks import send_notification
        
        resendable = queryset.filter(status__in=['failed', 'pending'])
        count = resendable.count()
        
        for notification in resendable:
            send_notification.delay(notification.id)
        
        self.message_user(request, f'{count} notifications were queued for resending.')
    resend_notifications.short_description = "Resend notifications"
    
    def mark_as_read(self, request, queryset):
        """Mark selected notifications as read"""
        unread = queryset.filter(read_at__isnull=True)
        count = unread.count()
        unread.update(read_at=timezone.now())
        self.message_user(request, f'{count} notifications were marked as read.')
    mark_as_read.short_description = "Mark as read"
    
    def mark_as_unread(self, request, queryset):
        """Mark selected notifications as unread"""
        read = queryset.filter(read_at__isnull=False)
        count = read.count()
        read.update(read_at=None)
        self.message_user(request, f'{count} notifications were marked as unread.')
    mark_as_unread.short_description = "Mark as unread"
    
    def cancel_scheduled(self, request, queryset):
        """Cancel scheduled notifications"""
        scheduled = queryset.filter(
            status='pending',
            scheduled_for__isnull=False,
            sent_at__isnull=True
        )
        count = scheduled.count()
        scheduled.update(status='cancelled')
        self.message_user(request, f'{count} scheduled notifications were cancelled.')
    cancel_scheduled.short_description = "Cancel scheduled"
    
    def export_selected_notifications(self, request, queryset):
        """Export selected notifications to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="notifications_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Notification Type', 'Organization', 'Recipient Type',
            'Recipient', 'Channel', 'Status', 'Priority',
            'Subject', 'Sent At', 'Delivered At', 'Read At',
            'Created At'
        ])
        
        for notification in queryset:
            recipient = ''
            if notification.recipient_email:
                recipient = notification.recipient_email
            elif notification.recipient_phone:
                recipient = notification.recipient_phone
            else:
                recipient = f"{notification.recipient_type}: {notification.recipient_id}"
            
            writer.writerow([
                notification.notification_type,
                notification.organization.name if notification.organization else '',
                notification.recipient_type,
                recipient,
                notification.channel,
                notification.status,
                notification.priority,
                notification.subject or '',
                notification.sent_at.strftime('%Y-%m-%d %H:%M:%S') if notification.sent_at else '',
                notification.delivered_at.strftime('%Y-%m-%d %H:%M:%S') if notification.delivered_at else '',
                notification.read_at.strftime('%Y-%m-%d %H:%M:%S') if notification.read_at else '',
                notification.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_selected_notifications.short_description = "Export selected notifications to CSV"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('organization', 'template', 'payment', 'invoice')
        return qs
    
    def changelist_view(self, request, extra_context=None):
        """Add summary statistics to changelist"""
        extra_context = extra_context or {}
        
        # Today's stats
        today = timezone.now().date()
        today_notifications = Notification.objects.filter(created_at__date=today)
        
        # Calculate statistics
        extra_context.update({
            'today_total': today_notifications.count(),
            'today_sent': today_notifications.filter(status='sent').count(),
            'today_delivered': today_notifications.filter(status='delivered').count(),
            'today_failed': today_notifications.filter(status='failed').count(),
            'delivery_rate': Notification.objects.filter(
                status='delivered'
            ).count() / max(Notification.objects.filter(status='sent').count(), 1) * 100,
        })
        
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin configuration for NotificationPreference model"""
    
    list_display = [
        'recipient_type', 'recipient_id', 'organization',
        'receive_sms', 'receive_email', 'receive_whatsapp',
        'receive_push', 'created_at'
    ]
    
    list_filter = [
        'recipient_type', 'receive_sms', 'receive_email',
        'receive_whatsapp', 'receive_push', 'organization',
        'created_at'
    ]
    
    search_fields = [
        'recipient_id', 'organization__name'
    ]
    
    readonly_fields = ['created_at', 'updated_at', 'recipient_details']
    
    fieldsets = (
        (_('Recipient'), {
            'fields': (
                'organization', 'recipient_type', 'recipient_id',
                'recipient_details'
            )
        }),
        (_('Global Preferences'), {
            'fields': (
                'receive_sms', 'receive_email', 'receive_whatsapp',
                'receive_push'
            )
        }),
        (_('Type-specific Preferences'), {
            'fields': ('preferences',),
            'classes': ('collapse',)
        }),
        (_('Quiet Hours'), {
            'fields': ('quiet_hours_start', 'quiet_hours_end'),
            'classes': ('collapse',)
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ['organization']
    
    actions = [
        'enable_all_channels', 'disable_all_channels',
        'enable_sms_only', 'enable_email_only'
    ]
    
    def recipient_details(self, obj):
        """Display recipient details"""
        if obj.recipient_type == 'user':
            from accounts.models import User
            try:
                user = User.objects.get(id=obj.recipient_id)
                return f"User: {user.email} ({user.get_full_name()})"
            except User.DoesNotExist:
                return "User not found"
        elif obj.recipient_type == 'customer':
            from customers.models import Customer
            try:
                customer = Customer.objects.get(id=obj.recipient_id)
                return f"Customer: {customer.first_name} {customer.last_name} ({customer.phone_number})"
            except Customer.DoesNotExist:
                return "Customer not found"
        return f"{obj.recipient_type}: {obj.recipient_id}"
    recipient_details.short_description = 'Recipient Details'
    
    def enable_all_channels(self, request, queryset):
        """Enable all notification channels"""
        updated = queryset.update(
            receive_sms=True,
            receive_email=True,
            receive_whatsapp=True,
            receive_push=True
        )
        self.message_user(request, f'{updated} preferences had all channels enabled.')
    enable_all_channels.short_description = "Enable all channels"
    
    def disable_all_channels(self, request, queryset):
        """Disable all notification channels"""
        updated = queryset.update(
            receive_sms=False,
            receive_email=False,
            receive_whatsapp=False,
            receive_push=False
        )
        self.message_user(request, f'{updated} preferences had all channels disabled.')
    disable_all_channels.short_description = "Disable all channels"
    
    def enable_sms_only(self, request, queryset):
        """Enable SMS notifications only"""
        updated = queryset.update(
            receive_sms=True,
            receive_email=False,
            receive_whatsapp=False,
            receive_push=False
        )
        self.message_user(request, f'{updated} preferences had SMS-only enabled.')
    enable_sms_only.short_description = "Enable SMS only"
    
    def enable_email_only(self, request, queryset):
        """Enable email notifications only"""
        updated = queryset.update(
            receive_sms=False,
            receive_email=True,
            receive_whatsapp=False,
            receive_push=False
        )
        self.message_user(request, f'{updated} preferences had email-only enabled.')
    enable_email_only.short_description = "Enable email only"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('organization')
        return qs


@admin.register(NotificationQueue)
class NotificationQueueAdmin(admin.ModelAdmin):
    """Admin configuration for NotificationQueue model"""
    
    list_display = [
        'notification', 'status', 'priority', 'processing_attempts',
        'next_scheduled_time', 'is_recurring', 'created_at'
    ]
    
    list_filter = [
        'status', 'priority', 'is_recurring', 'next_scheduled_time',
        'created_at'
    ]
    
    search_fields = [
        'notification__subject', 'notification__message',
        'notification__recipient_email', 'notification__recipient_phone'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'last_processing_attempt',
        'notification_details'
    ]
    
    fieldsets = (
        (_('Queue Information'), {
            'fields': ('notification', 'notification_details')
        }),
        (_('Status'), {
            'fields': ('status', 'priority', 'processing_attempts')
        }),
        (_('Schedule'), {
            'fields': (
                'is_recurring', 'recurrence_pattern',
                'next_scheduled_time', 'last_processing_attempt'
            )
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ['notification']
    
    actions = [
        'process_selected', 'cancel_selected', 'retry_failed',
        'increase_priority', 'decrease_priority'
    ]
    
    def notification_details(self, obj):
        """Display notification details"""
        notification = obj.notification
        details = [
            f"Type: {notification.notification_type}",
            f"Channel: {notification.channel}",
            f"Recipient: {notification.recipient_email or notification.recipient_phone or notification.recipient_id}",
            f"Subject: {notification.subject[:50] if notification.subject else 'No subject'}"
        ]
        return format_html('<br>'.join(details))
    notification_details.short_description = 'Notification Details'
    
    def process_selected(self, request, queryset):
        """Process selected queue items"""
        processable = queryset.filter(status='queued')
        count = processable.count()
        
        # In production, this would trigger Celery tasks
        processable.update(status='processing')
        
        self.message_user(request, f'{count} queue items were marked for processing.')
    process_selected.short_description = "Process selected"
    
    def cancel_selected(self, request, queryset):
        """Cancel selected queue items"""
        cancellable = queryset.filter(status__in=['queued', 'processing'])
        count = cancellable.count()
        cancellable.update(status='cancelled')
        self.message_user(request, f'{count} queue items were cancelled.')
    cancel_selected.short_description = "Cancel selected"
    
    def retry_failed(self, request, queryset):
        """Retry failed queue items"""
        failed = queryset.filter(status='failed', processing_attempts__lt=3)
        count = failed.count()
        failed.update(status='queued', processing_attempts=models.F('processing_attempts') + 1)
        self.message_user(request, f'{count} failed queue items were queued for retry.')
    retry_failed.short_description = "Retry failed"
    
    def increase_priority(self, request, queryset):
        """Increase priority of selected items"""
        queryset.update(priority=models.F('priority') + 1)
        self.message_user(request, f'{queryset.count()} queue items had their priority increased.')
    increase_priority.short_description = "Increase priority"
    
    def decrease_priority(self, request, queryset):
        """Decrease priority of selected items"""
        queryset.update(priority=models.F('priority') - 1)
        self.message_user(request, f'{queryset.count()} queue items had their priority decreased.')
    decrease_priority.short_description = "Decrease priority"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('notification')
        return qs
    
    def changelist_view(self, request, extra_context=None):
        """Add summary statistics to changelist"""
        extra_context = extra_context or {}
        
        # Queue statistics
        extra_context.update({
            'queued_count': NotificationQueue.objects.filter(status='queued').count(),
            'processing_count': NotificationQueue.objects.filter(status='processing').count(),
            'processed_count': NotificationQueue.objects.filter(status='processed').count(),
            'failed_count': NotificationQueue.objects.filter(status='failed').count(),
            'recurring_count': NotificationQueue.objects.filter(is_recurring=True).count(),
        })
        
        return super().changelist_view(request, extra_context=extra_context)