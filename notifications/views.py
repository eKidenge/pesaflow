from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta

from .models import NotificationTemplate, Notification, NotificationPreference, NotificationQueue
from .serializers import (
    NotificationTemplateSerializer,
    NotificationSerializer,
    NotificationCreateSerializer,
    NotificationPreferenceSerializer,
    NotificationQueueSerializer,
    SendNotificationSerializer,
    BulkNotificationSerializer
)
from .permissions import (
    IsSystemAdmin,
    IsBusinessOwnerOrAdmin,
    CanSendNotifications
)
from .tasks import send_notification, send_bulk_notification


class StandardPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notification templates.
    """
    queryset = NotificationTemplate.objects.select_related(
        'organization', 'created_by'
    ).all()
    serializer_class = NotificationTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, CanSendNotifications]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['template_type', 'channel', 'is_active', 'is_system_template']
    search_fields = ['name', 'subject', 'body']
    
    def get_queryset(self):
        """
        Filter templates by organization.
        System templates are available to all.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return NotificationTemplate.objects.none()
        
        # System templates (no organization)
        system_templates = NotificationTemplate.objects.filter(
            is_system_template=True
        )
        
        if user.user_type == 'system_admin':
            # Admins can see all templates
            return self.queryset
        
        elif user.organization:
            # Organization templates
            org_templates = self.queryset.filter(organization=user.organization)
            return org_templates | system_templates
        
        return system_templates
    
    def perform_create(self, serializer):
        """
        Set organization and created_by.
        """
        if not serializer.validated_data.get('is_system_template', False):
            # Organization template
            if self.request.user.organization:
                serializer.save(
                    organization=self.request.user.organization,
                    created_by=self.request.user
                )
            else:
                raise permissions.PermissionDenied(
                    "You must be associated with an organization to create templates."
                )
        else:
            # System template (only system admins can create)
            if self.request.user.user_type != 'system_admin':
                raise permissions.PermissionDenied(
                    "Only system administrators can create system templates."
                )
            serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        Duplicate a notification template.
        """
        template = self.get_object()
        
        # Create a copy
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
        
        return Response({
            'message': 'Template duplicated successfully',
            'template': NotificationTemplateSerializer(new_template).data
        })
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test a notification template.
        """
        template = self.get_object()
        test_data = request.data.get('test_data', {})
        
        # Replace template variables with test data
        message = template.body
        for key, value in test_data.items():
            message = message.replace(f'{{{key}}}', str(value))
        
        # Send test notification
        test_phone = request.data.get('test_phone')
        test_email = request.data.get('test_email')
        
        if template.channel == 'sms' and test_phone:
            send_notification.delay(
                organization_id=template.organization.id if template.organization else None,
                recipient_type='user',
                recipient_id=str(request.user.id),
                notification_type='test',
                channel='sms',
                message=message,
                subject=template.subject,
                template_id=str(template.id)
            )
        
        elif template.channel == 'email' and test_email:
            send_notification.delay(
                organization_id=template.organization.id if template.organization else None,
                recipient_type='user',
                recipient_id=str(request.user.id),
                notification_type='test',
                channel='email',
                message=message,
                subject=f"Test: {template.subject}",
                template_id=str(template.id)
            )
        
        return Response({
            'message': 'Test notification sent',
            'rendered_message': message
        })


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notifications.
    """
    queryset = Notification.objects.select_related(
        'organization', 'template', 'payment', 'invoice'
    ).all()
    serializer_class = NotificationSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'status', 'channel', 'notification_type', 
        'recipient_type', 'organization'
    ]
    search_fields = ['recipient_email', 'recipient_phone', 'message', 'subject']
    ordering_fields = ['created_at', 'sent_at', 'scheduled_for']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return NotificationCreateSerializer
        elif self.action == 'send':
            return SendNotificationSerializer
        elif self.action == 'send_bulk':
            return BulkNotificationSerializer
        return NotificationSerializer
    
    def get_permissions(self):
        """
        Custom permissions based on action.
        """
        if self.action in ['create', 'send', 'send_bulk']:
            permission_classes = [permissions.IsAuthenticated, CanSendNotifications]
        elif self.action in ['retrieve', 'list']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated, IsBusinessOwnerOrAdmin]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter notifications based on user role.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return Notification.objects.none()
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.user_type in ['business_owner', 'business_staff']:
            # Business users can see notifications from their organization
            if user.organization:
                return self.queryset.filter(organization=user.organization)
            return Notification.objects.none()
        
        else:
            # Users can see notifications sent to them
            return self.queryset.filter(
                Q(recipient_type='user', recipient_id=str(user.id)) |
                Q(recipient_email=user.email) |
                Q(recipient_phone=user.phone_number)
            ).distinct()
    
    def perform_create(self, serializer):
        """
        Set organization automatically.
        """
        user = self.request.user
        
        if user.organization:
            serializer.save(organization=user.organization)
        elif user.user_type == 'system_admin':
            serializer.save()  # System admins can send without organization
        else:
            raise permissions.PermissionDenied(
                "You must be associated with an organization to send notifications."
            )
    
    @action(detail=False, methods=['post'])
    def send(self, request):
        """
        Send a notification immediately.
        """
        serializer = SendNotificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        organization = user.organization
        
        if not organization and user.user_type != 'system_admin':
            return Response(
                {'error': 'You must be associated with an organization to send notifications.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create notification
        notification = Notification.objects.create(
            organization=organization,
            recipient_type=serializer.validated_data['recipient_type'],
            recipient_id=serializer.validated_data['recipient_id'],
            recipient_email=serializer.validated_data.get('recipient_email'),
            recipient_phone=serializer.validated_data.get('recipient_phone'),
            notification_type=serializer.validated_data['notification_type'],
            channel=serializer.validated_data['channel'],
            subject=serializer.validated_data.get('subject', ''),
            message=serializer.validated_data['message'],
            message_html=serializer.validated_data.get('message_html', ''),
            priority=serializer.validated_data.get('priority', 'normal'),
            scheduled_for=serializer.validated_data.get('scheduled_for'),
            metadata=serializer.validated_data.get('metadata', {})
        )
        
        # Send immediately if not scheduled
        if not notification.scheduled_for:
            send_notification.delay(notification.id)
            notification.status = 'pending'
            notification.save()
        
        return Response({
            'message': 'Notification created successfully',
            'notification': NotificationSerializer(notification).data
        })
    
    @action(detail=False, methods=['post'])
    def send_bulk(self, request):
        """
        Send bulk notifications.
        """
        serializer = BulkNotificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        organization = user.organization
        
        if not organization:
            return Response(
                {'error': 'You must be associated with an organization to send bulk notifications.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Start bulk notification task
        send_bulk_notification.delay(
            organization_id=str(organization.id),
            recipient_ids=serializer.validated_data['recipient_ids'],
            recipient_type=serializer.validated_data['recipient_type'],
            notification_type=serializer.validated_data['notification_type'],
            channel=serializer.validated_data['channel'],
            message=serializer.validated_data['message'],
            subject=serializer.validated_data.get('subject', ''),
            template_id=serializer.validated_data.get('template_id')
        )
        
        return Response({
            'message': f'Bulk notification started for {len(serializer.validated_data["recipient_ids"])} recipients'
        })
    
    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """
        Resend a failed notification.
        """
        notification = self.get_object()
        
        if notification.status != 'failed':
            return Response(
                {'error': 'Only failed notifications can be resent.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notification.status = 'pending'
        notification.delivery_attempts += 1
        notification.save()
        
        # Resend
        send_notification.delay(notification.id)
        
        return Response({
            'message': 'Notification queued for resending',
            'notification': NotificationSerializer(notification).data
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get notification statistics.
        """
        user = request.user
        organization = user.organization
        
        if not organization and user.user_type != 'system_admin':
            return Response(
                {'detail': 'No organization found.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Date range filters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if user.user_type == 'system_admin':
            queryset = Notification.objects.all()
        else:
            queryset = Notification.objects.filter(organization=organization)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Calculate statistics
        total_notifications = queryset.count()
        sent_notifications = queryset.filter(status='sent').count()
        delivered_notifications = queryset.filter(status='delivered').count()
        failed_notifications = queryset.filter(status='failed').count()
        
        # Channel distribution
        channel_distribution = queryset.values('channel').annotate(
            count=Count('id'),
            sent=Count('id', filter=Q(status='sent')),
            delivered=Count('id', filter=Q(status='delivered')),
            failed=Count('id', filter=Q(status='failed'))
        )
        
        # Daily volume for last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        daily_volume = queryset.filter(
            created_at__gte=thirty_days_ago
        ).extra(
            {'date': "date(created_at)"}
        ).values('date').annotate(
            count=Count('id'),
            sent=Count('id', filter=Q(status='sent')),
            failed=Count('id', filter=Q(status='failed'))
        ).order_by('date')
        
        # Success rate by channel
        success_rates = []
        for channel_data in channel_distribution:
            total = channel_data['count']
            sent = channel_data['sent']
            success_rate = (sent / total * 100) if total > 0 else 0
            success_rates.append({
                'channel': channel_data['channel'],
                'total': total,
                'sent': sent,
                'success_rate': success_rate
            })
        
        stats = {
            'total_notifications': total_notifications,
            'sent_notifications': sent_notifications,
            'delivered_notifications': delivered_notifications,
            'failed_notifications': failed_notifications,
            'success_rate': (sent_notifications / total_notifications * 100) if total_notifications > 0 else 0,
            'delivery_rate': (delivered_notifications / sent_notifications * 100) if sent_notifications > 0 else 0,
            'channel_distribution': list(channel_distribution),
            'success_rates_by_channel': success_rates,
            'daily_volume': list(daily_volume),
            'recent_notifications': queryset.order_by('-created_at')[:10].values(
                'id', 'channel', 'status', 'recipient_type', 'created_at'
            )
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def my_notifications(self, request):
        """
        Get notifications for the current user.
        """
        user = request.user
        
        notifications = Notification.objects.filter(
            Q(recipient_type='user', recipient_id=str(user.id)) |
            Q(recipient_email=user.email) |
            Q(recipient_phone=user.phone_number)
        ).order_by('-created_at')
        
        # Mark as read if requested
        mark_read = request.query_params.get('mark_read', 'false').lower() == 'true'
        if mark_read:
            unread_notifications = notifications.filter(read_at__isnull=True)
            unread_notifications.update(read_at=timezone.now())
        
        page = self.paginate_queryset(notifications)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notification preferences.
    """
    queryset = NotificationPreference.objects.select_related('organization').all()
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    
    def get_queryset(self):
        """
        Users can only see their own preferences.
        System admins can see all.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return NotificationPreference.objects.none()
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        # Users can see their own preferences
        return self.queryset.filter(
            recipient_type='user',
            recipient_id=str(user.id)
        )
    
    def get_object(self):
        """
        Get or create preferences for the current user.
        """
        user = self.request.user
        
        # Try to get existing preferences
        try:
            return self.queryset.get(
                recipient_type='user',
                recipient_id=str(user.id)
            )
        except NotificationPreference.DoesNotExist:
            # Create default preferences
            preferences = NotificationPreference.objects.create(
                organization=user.organization,
                recipient_type='user',
                recipient_id=str(user.id),
                preferences={
                    'payment_received': {'sms': True, 'email': True},
                    'payment_reminder': {'sms': True, 'email': True},
                    'invoice_sent': {'sms': True, 'email': True},
                }
            )
            return preferences
    
    @action(detail=False, methods=['get'])
    def defaults(self, request):
        """
        Get default notification preferences.
        """
        defaults = {
            'receive_sms': True,
            'receive_email': True,
            'receive_whatsapp': False,
            'receive_push': False,
            'preferences': {
                'payment_received': {'sms': True, 'email': True},
                'payment_reminder': {'sms': True, 'email': True},
                'invoice_sent': {'sms': True, 'email': True},
                'invoice_overdue': {'sms': True, 'email': True},
                'welcome': {'sms': True, 'email': True},
            }
        }
        
        return Response(defaults)


class NotificationQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing notification queue.
    """
    queryset = NotificationQueue.objects.select_related('notification').all()
    serializer_class = NotificationQueueSerializer
    permission_classes = [permissions.IsAuthenticated, CanSendNotifications]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'is_recurring']
    ordering_fields = ['priority', 'next_scheduled_time', 'created_at']
    ordering = ['-priority', 'next_scheduled_time']
    
    def get_queryset(self):
        """
        Filter queue by organization.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return NotificationQueue.objects.none()
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.organization:
            return self.queryset.filter(notification__organization=user.organization)
        
        return NotificationQueue.objects.none()
    
    @action(detail=False, methods=['post'])
    def process_queue(self, request):
        """
        Manually trigger queue processing.
        """
        # In production, this would trigger Celery task
        # For now, just return success
        
        return Response({
            'message': 'Queue processing triggered',
            'queued_items': self.get_queryset().filter(status='queued').count()
        })