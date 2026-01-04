from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg
from .models import Integration, IntegrationType, APILog


@admin.register(IntegrationType)
class IntegrationTypeAdmin(admin.ModelAdmin):
    """Admin configuration for IntegrationType model"""
    
    list_display = [
        'name', 'provider', 'category', 'is_active',
        'integration_count', 'documentation_link'
    ]
    
    list_filter = ['category', 'provider', 'is_active']
    
    search_fields = ['name', 'provider', 'description']
    
    readonly_fields = ['integration_count']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'provider', 'category', 'description')
        }),
        (_('Configuration'), {
            'fields': ('icon', 'documentation_url')
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
        (_('Statistics'), {
            'fields': ('integration_count',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_types', 'deactivate_types']
    
    def integration_count(self, obj):
        """Display integration count"""
        return obj.integrations.count()
    integration_count.short_description = 'Integrations'
    
    def documentation_link(self, obj):
        """Display documentation as link"""
        if obj.documentation_url:
            return format_html(
                '<a href="{}" target="_blank">Documentation</a>',
                obj.documentation_url
            )
        return "No documentation"
    documentation_link.short_description = 'Docs'
    
    def activate_types(self, request, queryset):
        """Activate selected integration types"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} integration types were activated.')
    activate_types.short_description = "Activate selected integration types"
    
    def deactivate_types(self, request, queryset):
        """Deactivate selected integration types"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} integration types were deactivated.')
    deactivate_types.short_description = "Deactivate selected integration types"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.annotate(integration_count=Count('integrations'))
        return qs


@admin.register(Integration)
class IntegrationAdmin(admin.ModelAdmin):
    """Admin configuration for Integration model"""
    
    list_display = [
        'name', 'organization', 'integration_type', 'environment',
        'status', 'is_default', 'last_used', 'success_rate',
        'total_requests', 'created_at'
    ]
    
    list_filter = [
        'status', 'environment', 'is_default', 'integration_type',
        'organization', 'created_at', 'validated_at'
    ]
    
    search_fields = [
        'name', 'api_url', 'webhook_url',
        'organization__name', 'integration_type__name'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'validated_at', 'last_used',
        'total_requests', 'successful_requests', 'failed_requests',
        'success_rate', 'average_response_time', 'recent_logs'
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'organization', 'integration_type', 'name', 'environment'
            )
        }),
        (_('API Configuration'), {
            'fields': (
                'api_key', 'api_secret', 'api_url', 'consumer_key',
                'consumer_secret', 'passkey'
            ),
            'classes': ('collapse',)
        }),
        (_('Webhook Configuration'), {
            'fields': ('webhook_url', 'webhook_secret'),
            'classes': ('collapse',)
        }),
        (_('Status & Settings'), {
            'fields': ('status', 'is_default', 'settings', 'metadata')
        }),
        (_('Statistics'), {
            'fields': (
                'total_requests', 'successful_requests', 'failed_requests',
                'success_rate', 'average_response_time', 'last_used',
                'recent_logs'
            ),
            'classes': ('collapse',)
        }),
        (_('Audit'), {
            'fields': (
                'created_by', 'created_at', 'updated_at', 'validated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ['organization', 'integration_type', 'created_by']
    
    actions = [
        'activate_integrations', 'deactivate_integrations',
        'set_as_default', 'test_integrations', 'rotate_api_keys'
    ]
    
    def success_rate(self, obj):
        """Calculate success rate"""
        if obj.total_requests > 0:
            rate = (obj.successful_requests / obj.total_requests) * 100
            return f"{rate:.1f}%"
        return "0%"
    success_rate.short_description = 'Success Rate'
    
    def average_response_time(self, obj):
        """Calculate average response time"""
        avg_time = APILog.objects.filter(
            integration=obj,
            duration_ms__isnull=False
        ).aggregate(avg=Avg('duration_ms'))['avg']
        
        if avg_time:
            return f"{avg_time:.2f} ms"
        return "N/A"
    average_response_time.short_description = 'Avg Response Time'
    
    def recent_logs(self, obj):
        """Display recent logs as links"""
        logs = APILog.objects.filter(integration=obj).order_by('-request_timestamp')[:5]
        if not logs:
            return "No logs"
        
        links = []
        for log in logs:
            url = reverse('admin:integrations_apilog_change', args=[log.id])
            status_color = 'green' if log.status == 'success' else 'red'
            links.append(
                f'<a href="{url}" style="color: {status_color};">'
                f'{log.request_type} - {log.status}'
                f'</a>'
            )
        
        return format_html('<br>'.join(links))
    recent_logs.short_description = 'Recent Logs'
    
    def activate_integrations(self, request, queryset):
        """Activate selected integrations"""
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} integrations were activated.')
    activate_integrations.short_description = "Activate selected integrations"
    
    def deactivate_integrations(self, request, queryset):
        """Deactivate selected integrations"""
        updated = queryset.update(status='inactive')
        self.message_user(request, f'{updated} integrations were deactivated.')
    deactivate_integrations.short_description = "Deactivate selected integrations"
    
    def set_as_default(self, request, queryset):
        """Set selected integrations as default"""
        # First, unset all defaults for the same integration type and organization
        for integration in queryset:
            Integration.objects.filter(
                organization=integration.organization,
                integration_type=integration.integration_type,
                is_default=True
            ).exclude(id=integration.id).update(is_default=False)
        
        # Set selected as default
        updated = queryset.update(is_default=True)
        self.message_user(request, f'{updated} integrations were set as default.')
    set_as_default.short_description = "Set as default"
    
    def test_integrations(self, request, queryset):
        """Test selected integrations"""
        from integrations.mpesa import get_access_token
        
        success_count = 0
        for integration in queryset:
            if integration.integration_type.provider == 'safaricom':
                try:
                    token = get_access_token(integration)
                    if token:
                        success_count += 1
                        self.message_user(
                            request,
                            f'{integration.name}: Authentication successful',
                            level='SUCCESS'
                        )
                    else:
                        self.message_user(
                            request,
                            f'{integration.name}: Authentication failed',
                            level='ERROR'
                        )
                except Exception as e:
                    self.message_user(
                        request,
                        f'{integration.name}: Error - {str(e)}',
                        level='ERROR'
                    )
            else:
                self.message_user(
                    request,
                    f'{integration.name}: Test not implemented for this provider',
                    level='WARNING'
                )
        
        self.message_user(
            request,
            f'{success_count} out of {queryset.count()} integrations tested successfully.'
        )
    test_integrations.short_description = "Test integrations"
    
    def rotate_api_keys(self, request, queryset):
        """Rotate API keys for selected integrations"""
        import secrets
        
        count = 0
        for integration in queryset:
            integration.api_key = secrets.token_urlsafe(32)
            integration.api_secret = secrets.token_urlsafe(64)
            integration.webhook_secret = secrets.token_urlsafe(32)
            integration.save()
            count += 1
        
        self.message_user(request, f'{count} integrations had their API keys rotated.')
    rotate_api_keys.short_description = "Rotate API keys"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('organization', 'integration_type', 'created_by')
        return qs


@admin.register(APILog)
class APILogAdmin(admin.ModelAdmin):
    """Admin configuration for APILog model"""
    
    list_display = [
        'request_type', 'integration', 'organization', 'status',
        'response_status_code', 'duration_display', 'request_timestamp',
        'correlation_id', 'has_payment'
    ]
    
    list_filter = [
        'status', 'request_type', 'integration', 'organization',
        'method', 'request_timestamp', 'response_timestamp'
    ]
    
    search_fields = [
        'endpoint', 'correlation_id', 'external_id', 'error_message',
        'integration__name', 'organization__name', 'payment__payment_reference'
    ]
    
    readonly_fields = [
        'request_timestamp', 'response_timestamp', 'created_at',
        'updated_at', 'duration_display', 'request_body_preview',
        'response_body_preview'
    ]
    
    fieldsets = (
        (_('Request Information'), {
            'fields': (
                'integration', 'organization', 'request_type',
                'endpoint', 'method'
            )
        }),
        (_('Request Details'), {
            'fields': (
                'request_headers', 'request_body', 'request_body_preview',
                'request_timestamp'
            ),
            'classes': ('collapse',)
        }),
        (_('Response Details'), {
            'fields': (
                'response_status_code', 'response_headers', 'response_body',
                'response_body_preview', 'response_timestamp',
                'duration_display'
            ),
            'classes': ('collapse',)
        }),
        (_('Status & Error'), {
            'fields': ('status', 'error_message', 'retry_count')
        }),
        (_('Identifiers'), {
            'fields': ('correlation_id', 'external_id'),
            'classes': ('collapse',)
        }),
        (_('Performance'), {
            'fields': ('duration_ms',),
            'classes': ('collapse',)
        }),
        (_('Related Objects'), {
            'fields': ('payment',),
            'classes': ('collapse',)
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ['integration', 'organization', 'payment']
    
    actions = [
        'retry_failed_requests', 'delete_old_logs',
        'export_selected_logs', 'clear_error_messages'
    ]
    
    def duration_display(self, obj):
        """Display duration in readable format"""
        if obj.duration_ms:
            if obj.duration_ms < 1000:
                return f"{obj.duration_ms:.0f} ms"
            else:
                return f"{obj.duration_ms/1000:.2f} s"
        return "N/A"
    duration_display.short_description = 'Duration'
    
    def request_body_preview(self, obj):
        """Display request body preview"""
        if obj.request_body:
            import json
            body_str = json.dumps(obj.request_body, indent=2)
            if len(body_str) > 500:
                return f"{body_str[:500]}..."
            return body_str
        return "Empty"
    request_body_preview.short_description = 'Request Body (Preview)'
    
    def response_body_preview(self, obj):
        """Display response body preview"""
        if obj.response_body:
            import json
            body_str = json.dumps(obj.response_body, indent=2)
            if len(body_str) > 500:
                return f"{body_str[:500]}..."
            return body_str
        return "Empty"
    response_body_preview.short_description = 'Response Body (Preview)'
    
    def has_payment(self, obj):
        """Check if log has associated payment"""
        return obj.payment is not None
    has_payment.boolean = True
    has_payment.short_description = 'Has Payment'
    
    def retry_failed_requests(self, request, queryset):
        """Retry failed API requests"""
        failed_requests = queryset.filter(status='failed', retry_count__lt=3)
        count = failed_requests.count()
        
        # Increment retry count
        failed_requests.update(retry_count=models.F('retry_count') + 1)
        
        # In production, this would queue the requests for retry
        self.message_user(
            request,
            f'{count} failed requests were marked for retry.'
        )
    retry_failed_requests.short_description = "Retry failed requests"
    
    def delete_old_logs(self, request, queryset):
        """Delete logs older than 90 days"""
        from django.utils import timezone
        from datetime import timedelta
        
        ninety_days_ago = timezone.now() - timedelta(days=90)
        old_logs = queryset.filter(request_timestamp__lt=ninety_days_ago)
        count = old_logs.count()
        old_logs.delete()
        
        self.message_user(request, f'{count} logs older than 90 days were deleted.')
    delete_old_logs.short_description = "Delete logs older than 90 days"
    
    def export_selected_logs(self, request, queryset):
        """Export selected logs to CSV"""
        import csv
        import json
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="api_logs_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Request Type', 'Integration', 'Organization', 'Endpoint',
            'Method', 'Status', 'Response Code', 'Duration (ms)',
            'Request Timestamp', 'Error Message', 'Correlation ID'
        ])
        
        for log in queryset:
            writer.writerow([
                log.request_type,
                log.integration.name if log.integration else '',
                log.organization.name if log.organization else '',
                log.endpoint,
                log.method,
                log.status,
                log.response_status_code or '',
                log.duration_ms or '',
                log.request_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.error_message or '',
                log.correlation_id or ''
            ])
        
        return response
    export_selected_logs.short_description = "Export selected logs to CSV"
    
    def clear_error_messages(self, request, queryset):
        """Clear error messages for selected logs"""
        updated = queryset.update(error_message='')
        self.message_user(request, f'{updated} logs had their error messages cleared.')
    clear_error_messages.short_description = "Clear error messages"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('integration', 'organization', 'payment')
        return qs
    
    def changelist_view(self, request, extra_context=None):
        """Add summary statistics to changelist"""
        extra_context = extra_context or {}
        
        # Today's stats
        from django.utils import timezone
        from django.db.models import Count, Avg
        
        today = timezone.now().date()
        today_logs = APILog.objects.filter(request_timestamp__date=today)
        
        # Calculate statistics
        extra_context.update({
            'today_total': today_logs.count(),
            'today_success': today_logs.filter(status='success').count(),
            'today_failed': today_logs.filter(status='failed').count(),
            'success_rate': APILog.objects.filter(
                status='success'
            ).count() / max(APILog.objects.count(), 1) * 100,
            'avg_response_time': APILog.objects.filter(
                duration_ms__isnull=False
            ).aggregate(avg=Avg('duration_ms'))['avg'] or 0,
        })
        
        return super().changelist_view(request, extra_context=extra_context)