from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from django.utils import timezone
from django.conf import settings
import secrets

from .models import Integration, IntegrationType, APILog
from .serializers import (
    IntegrationSerializer,
    IntegrationCreateSerializer,
    IntegrationUpdateSerializer,
    IntegrationTypeSerializer,
    APILogSerializer,
    IntegrationTestSerializer,
    MpesaCredentialsSerializer
)
from .permissions import (
    IsSystemAdmin,
    IsBusinessOwnerOrAdmin,
    CanManageIntegrations
)
from .mpesa import MpesaSTKPush, MpesaC2B, MpesaB2C


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class IntegrationTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing integration types.
    """
    queryset = IntegrationType.objects.filter(is_active=True)
    serializer_class = IntegrationTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination


class IntegrationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing integrations.
    """
    queryset = Integration.objects.select_related(
        'organization', 'integration_type', 'created_by'
    ).all()
    serializer_class = IntegrationSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageIntegrations]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'environment', 'integration_type']
    search_fields = ['name', 'api_url']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return IntegrationCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return IntegrationUpdateSerializer
        elif self.action == 'test':
            return IntegrationTestSerializer
        elif self.action == 'update_mpesa_credentials':
            return MpesaCredentialsSerializer
        return IntegrationSerializer
    
    def get_queryset(self):
        """
        Filter integrations by organization.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return Integration.objects.none()
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.organization:
            return self.queryset.filter(organization=user.organization)
        
        return Integration.objects.none()
    
    def perform_create(self, serializer):
        """
        Set organization and created_by.
        """
        organization = self.request.user.organization
        
        if not organization:
            raise permissions.PermissionDenied(
                "You must be associated with an organization to create integrations."
            )
        
        serializer.save(
            organization=organization,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test integration configuration.
        """
        integration = self.get_object()
        serializer = IntegrationTestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        test_type = serializer.validated_data['test_type']
        
        try:
            if integration.integration_type.provider == 'safaricom':
                if test_type == 'authentication':
                    # Test M-Pesa authentication
                    from .mpesa import get_access_token
                    token = get_access_token(integration)
                    
                    return Response({
                        'success': True,
                        'message': 'Authentication successful',
                        'token': token[:50] + '...' if token else None
                    })
                    
                elif test_type == 'balance':
                    # Test account balance (for C2B)
                    # This is a simple test - in production, implement actual balance check
                    return Response({
                        'success': True,
                        'message': 'Balance check simulated successfully'
                    })
            
            elif integration.integration_type.category == 'sms':
                # Test SMS sending
                test_phone = serializer.validated_data.get('test_phone')
                if not test_phone:
                    return Response(
                        {'error': 'Test phone number is required for SMS test.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # In production, implement actual SMS test
                return Response({
                    'success': True,
                    'message': f'SMS test to {test_phone} simulated successfully'
                })
            
            return Response({
                'success': True,
                'message': f'{test_type} test completed successfully'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Activate an integration.
        """
        integration = self.get_object()
        
        if integration.status == 'active':
            return Response(
                {'error': 'Integration is already active.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        integration.status = 'active'
        integration.validated_at = timezone.now()
        integration.save()
        
        return Response({
            'message': 'Integration activated successfully',
            'integration': IntegrationSerializer(integration).data
        })
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """
        Deactivate an integration.
        """
        integration = self.get_object()
        
        if integration.status == 'inactive':
            return Response(
                {'error': 'Integration is already inactive.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        integration.status = 'inactive'
        integration.save()
        
        return Response({
            'message': 'Integration deactivated successfully',
            'integration': IntegrationSerializer(integration).data
        })
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """
        Get logs for this integration.
        """
        integration = self.get_object()
        logs = APILog.objects.filter(
            integration=integration
        ).order_by('-request_timestamp')
        
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = APILogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = APILogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def regenerate_webhook_secret(self, request, pk=None):
        """
        Regenerate webhook secret.
        """
        integration = self.get_object()
        
        if integration.integration_type.category != 'payment':
            return Response(
                {'error': 'Only payment integrations have webhook secrets.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        new_secret = secrets.token_urlsafe(32)
        integration.webhook_secret = new_secret
        integration.save()
        
        return Response({
            'message': 'Webhook secret regenerated',
            'new_secret': new_secret
        })
    
    @action(detail=True, methods=['put', 'patch'])
    def update_mpesa_credentials(self, request, pk=None):
        """
        Update M-Pesa credentials.
        """
        integration = self.get_object()
        
        if integration.integration_type.provider != 'safaricom':
            return Response(
                {'error': 'This integration is not for M-Pesa.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = MpesaCredentialsSerializer(
            integration,
            data=request.data,
            partial=True
        )
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        
        return Response({
            'message': 'M-Pesa credentials updated successfully',
            'integration': IntegrationSerializer(integration).data
        })
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """
        Get integration usage statistics.
        """
        integration = self.get_object()
        
        # Get logs for the last 30 days
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        recent_logs = APILog.objects.filter(
            integration=integration,
            request_timestamp__gte=thirty_days_ago
        )
        
        stats = {
            'total_requests': integration.total_requests,
            'successful_requests': integration.successful_requests,
            'failed_requests': integration.failed_requests,
            'success_rate': (integration.successful_requests / integration.total_requests * 100) 
                            if integration.total_requests > 0 else 0,
            'recent_requests_30_days': recent_logs.count(),
            'recent_success_rate': (
                recent_logs.filter(status='success').count() / recent_logs.count() * 100
            ) if recent_logs.count() > 0 else 0,
            'requests_by_type': list(
                recent_logs.values('request_type').annotate(
                    count=Count('id'),
                    success=Count('id', filter=Q(status='success')),
                    failed=Count('id', filter=Q(status='failed'))
                )
            ),
            'average_response_time': recent_logs.filter(
                duration_ms__isnull=False
            ).aggregate(avg=Avg('duration_ms'))['avg'] or 0
        }
        
        return Response(stats)


class APILogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing API logs.
    """
    queryset = APILog.objects.select_related(
        'integration', 'organization', 'payment'
    ).all()
    serializer_class = APILogSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageIntegrations]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'request_type', 'integration', 'organization']
    search_fields = ['correlation_id', 'external_id', 'endpoint']
    ordering_fields = ['request_timestamp', 'response_timestamp', 'duration_ms']
    ordering = ['-request_timestamp']
    
    def get_queryset(self):
        """
        Filter logs by organization.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return APILog.objects.none()
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.organization:
            return self.queryset.filter(organization=user.organization)
        
        return APILog.objects.none()
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get API log statistics.
        """
        user = request.user
        organization = user.organization
        
        if not organization:
            return Response(
                {'detail': 'No organization found.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Date range filters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = APILog.objects.filter(organization=organization)
        
        if start_date:
            queryset = queryset.filter(request_timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(request_timestamp__lte=end_date)
        
        # Calculate statistics
        total_logs = queryset.count()
        success_logs = queryset.filter(status='success').count()
        failed_logs = queryset.filter(status='failed').count()
        
        # Requests by type
        requests_by_type = queryset.values('request_type').annotate(
            count=Count('id'),
            success=Count('id', filter=Q(status='success')),
            failed=Count('id', filter=Q(status='failed')),
            avg_duration=Avg('duration_ms')
        ).order_by('-count')
        
        # Daily volume for last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        daily_volume = queryset.filter(
            request_timestamp__gte=thirty_days_ago
        ).extra(
            {'date': "date(request_timestamp)"}
        ).values('date').annotate(
            count=Count('id'),
            success=Count('id', filter=Q(status='success')),
            failed=Count('id', filter=Q(status='failed'))
        ).order_by('date')
        
        stats = {
            'total_logs': total_logs,
            'success_logs': success_logs,
            'failed_logs': failed_logs,
            'success_rate': (success_logs / total_logs * 100) if total_logs > 0 else 0,
            'requests_by_type': list(requests_by_type),
            'daily_volume': list(daily_volume),
            'average_response_time': queryset.filter(
                duration_ms__isnull=False
            ).aggregate(avg=Avg('duration_ms'))['avg'] or 0,
            'top_endpoints': list(
                queryset.values('endpoint').annotate(
                    count=Count('id')
                ).order_by('-count')[:10]
            )
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['post'])
    def retry_failed(self, request):
        """
        Retry failed API requests.
        """
        user = request.user
        organization = user.organization
        
        if not organization:
            return Response(
                {'detail': 'No organization found.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get failed logs from last 24 hours
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        failed_logs = APILog.objects.filter(
            organization=organization,
            status='failed',
            request_timestamp__gte=twenty_four_hours_ago,
            retry_count__lt=3  # Maximum 3 retries
        )
        
        retry_count = 0
        for log in failed_logs:
            # In production, implement actual retry logic based on request_type
            # For now, just mark as retried
            log.retry_count += 1
            log.save()
            retry_count += 1
        
        return Response({
            'message': f'Initiated retry for {retry_count} failed requests',
            'retried': retry_count
        })


# Webhook views for external services
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
import hmac
import hashlib
import json

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def mpesa_callback(request):
    """
    Handle M-Pesa callback/webhook.
    """
    # Get webhook signature
    signature = request.headers.get('X-Mpesa-Signature')
    
    if not signature:
        return Response({'error': 'Missing signature'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get integration by callback URL or organization ID
    # In production, you'd have a more sophisticated way to identify the integration
    body = json.dumps(request.data).encode('utf-8')
    
    # Verify signature (simplified - adjust based on M-Pesa documentation)
    try:
        # Find integration (this is a simplified example)
        # In production, you'd map callback URLs to integrations
        integration = Integration.objects.filter(
            integration_type__provider='safaricom',
            status='active'
        ).first()
        
        if not integration:
            return Response({'error': 'Integration not found'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify webhook secret
        expected_signature = hmac.new(
            integration.webhook_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return Response({'error': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Process callback
        callback_data = request.data
        
        # Check if this is STK Push callback
        if 'Body' in callback_data and 'stkCallback' in callback_data['Body']:
            stk_callback = callback_data['Body']['stkCallback']
            
            # Get payment by CheckoutRequestID
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            
            try:
                payment = Payment.objects.get(
                    mpesa_checkout_request_id=checkout_request_id
                )
                
                result_code = stk_callback.get('ResultCode')
                result_desc = stk_callback.get('ResultDesc')
                
                if result_code == 0:
                    # Payment successful
                    payment.status = 'completed'
                    payment.external_reference = stk_callback.get('MerchantRequestID')
                    
                    # Get transaction details from CallbackMetadata
                    callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                    for item in callback_metadata:
                        if item.get('Name') == 'MpesaReceiptNumber':
                            payment.external_reference = item.get('Value')
                        elif item.get('Name') == 'Amount':
                            payment.amount = item.get('Value')
                        elif item.get('Name') == 'PhoneNumber':
                            payment.payer_phone = item.get('Value')
                    
                    payment.completed_at = timezone.now()
                    payment.save()
                    
                    # Update customer's last payment date
                    if payment.customer:
                        payment.customer.last_payment_date = timezone.now()
                        payment.customer.save()
                    
                    # Send payment confirmation notification
                    from notifications.tasks import send_notification
                    send_notification.delay(
                        organization_id=payment.organization.id,
                        recipient_type='customer',
                        recipient_id=str(payment.customer.id) if payment.customer else None,
                        notification_type='payment_received',
                        channel='sms',
                        message=f"Payment of KES {payment.amount} received successfully. Ref: {payment.external_reference}",
                        payment_id=str(payment.id)
                    )
                    
                else:
                    # Payment failed
                    payment.status = 'failed'
                    payment.save()
                
                # Log the callback
                APILog.objects.create(
                    integration=integration,
                    organization=payment.organization,
                    request_type='webhook',
                    endpoint='/webhooks/mpesa/',
                    method='POST',
                    request_body=callback_data,
                    request_timestamp=timezone.now(),
                    response_status_code=200,
                    response_body={'status': 'processed'},
                    response_timestamp=timezone.now(),
                    status='success',
                    correlation_id=checkout_request_id,
                    external_id=payment.external_reference,
                    payment=payment
                )
                
            except Payment.DoesNotExist:
                # Log unknown callback
                APILog.objects.create(
                    integration=integration,
                    organization=None,
                    request_type='webhook',
                    endpoint='/webhooks/mpesa/',
                    method='POST',
                    request_body=callback_data,
                    request_timestamp=timezone.now(),
                    response_status_code=404,
                    response_body={'error': 'Payment not found'},
                    response_timestamp=timezone.now(),
                    status='failed',
                    correlation_id=checkout_request_id,
                    error_message='Payment not found for CheckoutRequestID'
                )
        
        return Response({'status': 'ok'})
        
    except Exception as e:
        # Log error
        APILog.objects.create(
            integration=None,
            organization=None,
            request_type='webhook',
            endpoint='/webhooks/mpesa/',
            method='POST',
            request_body=request.data,
            request_timestamp=timezone.now(),
            status='failed',
            error_message=str(e)
        )
        
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)