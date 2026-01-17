from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta
import json

from .models import Payment, Invoice, PaymentPlan
from .serializers import (
    PaymentSerializer,
    PaymentCreateSerializer,
    PaymentUpdateSerializer,
    InvoiceSerializer,
    InvoiceCreateSerializer,
    PaymentPlanSerializer,
    PaymentPlanCreateSerializer,
    PaymentStatisticsSerializer,
    MpesaSTKPushSerializer,
    PaymentReversalSerializer
)
from .permissions import (
    IsOrganizationMember,
    CanManagePayments,
    CanViewPayments,
    CanInitiatePayment
)
from integrations.models import Integration, APILog
from integrations.mpesa import MpesaSTKPush
from notifications.tasks import send_notification


class StandardPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payments.
    """
    queryset = Payment.objects.select_related(
        'organization', 'customer', 'created_by'
    ).all()
    serializer_class = PaymentSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'status', 'payment_method', 'payment_type', 
        'is_reversed', 'organization'
    ]
    search_fields = [
        'payment_reference', 'external_reference',
        'payer_phone', 'payer_name', 'description'
    ]
    ordering_fields = ['created_at', 'amount', 'completed_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PaymentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return PaymentUpdateSerializer
        elif self.action == 'initiate_mpesa':
            return MpesaSTKPushSerializer
        elif self.action == 'reverse':
            return PaymentReversalSerializer
        elif self.action == 'statistics':
            return PaymentStatisticsSerializer
        return PaymentSerializer
    
    def get_permissions(self):
        """
        Custom permissions based on action.
        """
        if self.action in ['create', 'initiate_mpesa']:
            permission_classes = [permissions.IsAuthenticated, CanInitiatePayment]
        elif self.action in ['update', 'partial_update', 'destroy', 'reverse']:
            permission_classes = [permissions.IsAuthenticated, CanManagePayments]
        elif self.action in ['retrieve', 'list']:
            permission_classes = [permissions.IsAuthenticated, CanViewPayments]
        else:
            permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter payments based on user role.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return Payment.objects.none()
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.user_type in ['business_owner', 'business_staff']:
            # Business users can see payments in their organization
            if user.organization:
                # Check if user has permission to view payments
                if not user.organization_memberships.filter(can_manage_payments=True).exists():
                    # If not, they can only see payments they created
                    return self.queryset.filter(
                        organization=user.organization,
                        created_by=user
                    )
                return self.queryset.filter(organization=user.organization)
            return Payment.objects.none()
        
        else:
            # Customers can only see their own payments
            from customers.models import Customer
            customer = Customer.objects.filter(
                Q(phone_number=user.phone_number) |
                Q(email=user.email),
                organization__is_active=True
            ).first()
            
            if customer:
                return self.queryset.filter(customer=customer)
            return Payment.objects.none()
    
    def perform_create(self, serializer):
        """
        Create payment with organization and created_by.
        """
        user = self.request.user
        
        if user.organization:
            serializer.save(organization=user.organization, created_by=user)
        else:
            raise permissions.PermissionDenied(
                "You must be associated with an organization to create payments."
            )
    
    @action(detail=False, methods=['post'])
    def initiate_mpesa(self, request):
        """
        Initiate M-Pesa STK Push payment.
        """
        serializer = MpesaSTKPushSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        organization = user.organization
        
        if not organization:
            return Response(
                {'error': 'You must be associated with an organization to initiate payments.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get M-Pesa integration
        try:
            mpesa_integration = Integration.objects.get(
                organization=organization,
                integration_type__provider='safaricom',
                integration_type__category='payment',
                status='active',
                environment='production' if not settings.DEBUG else 'sandbox'
            )
        except Integration.DoesNotExist:
            return Response(
                {'error': 'M-Pesa integration not configured for this organization.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Prepare payment data
        phone_number = serializer.validated_data['phone_number']
        amount = serializer.validated_data['amount']
        description = serializer.validated_data.get('description', 'Payment via PesaFlow')
        
        # Create payment record
        payment = Payment.objects.create(
            organization=organization,
            amount=amount,
            currency='KES',
            payment_method='mpesa',
            payment_type=serializer.validated_data.get('payment_type', 'other'),
            description=description,
            payer_phone=phone_number,
            status='initiated',
            initiated_at=timezone.now(),
            created_by=user
        )
        
        # Try to find customer by phone number
        from customers.models import Customer
        customer = Customer.objects.filter(
            organization=organization,
            phone_number=phone_number
        ).first()
        
        if customer:
            payment.customer = customer
            payment.payer_name = f"{customer.first_name} {customer.last_name}"
            payment.payer_email = customer.email
            payment.save()
        
        # Initiate M-Pesa STK Push
        try:
            stk_push = MpesaSTKPush(
                integration=mpesa_integration,
                phone_number=phone_number,
                amount=amount,
                account_reference=payment.payment_reference,
                transaction_desc=description
            )
            
            response = stk_push.initiate()
            
            # Update payment with M-Pesa details
            payment.mpesa_checkout_request_id = response.get('CheckoutRequestID')
            payment.mpesa_merchant_request_id = response.get('MerchantRequestID')
            payment.save()
            
            # Log API call
            APILog.objects.create(
                integration=mpesa_integration,
                organization=organization,
                request_type='mpesa_stk_push',
                endpoint=stk_push.endpoint,
                method='POST',
                request_headers=stk_push.headers,
                request_body=stk_push.payload,
                request_timestamp=timezone.now(),
                response_status_code=200,
                response_body=response,
                response_timestamp=timezone.now(),
                status='success',
                correlation_id=response.get('CheckoutRequestID'),
                external_id=response.get('MerchantRequestID'),
                payment=payment
            )
            
            return Response({
                'payment': PaymentSerializer(payment).data,
                'mpesa_response': response,
                'message': 'Payment initiated successfully'
            })
            
        except Exception as e:
            # Update payment status
            payment.status = 'failed'
            payment.save()
            
            # Log error
            APILog.objects.create(
                integration=mpesa_integration,
                organization=organization,
                request_type='mpesa_stk_push',
                endpoint='',
                method='POST',
                request_body={'error': str(e)},
                request_timestamp=timezone.now(),
                status='failed',
                error_message=str(e),
                payment=payment
            )
            
            return Response(
                {'error': f'Failed to initiate payment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        """
        Reverse a payment.
        """
        payment = self.get_object()
        
        # Check if payment can be reversed
        if payment.status != 'completed':
            return Response(
                {'error': 'Only completed payments can be reversed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if payment.is_reversed:
            return Response(
                {'error': 'Payment has already been reversed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = PaymentReversalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # In production, integrate with M-Pesa reversal API
        # For now, just mark as reversed
        payment.is_reversed = True
        payment.reversal_reason = serializer.validated_data['reason']
        payment.reversed_at = timezone.now()
        payment.save()
        
        return Response({
            'message': 'Payment reversal initiated',
            'payment': PaymentSerializer(payment).data
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get payment statistics.
        """
        user = request.user
        
        if user.user_type == 'system_admin':
            queryset = Payment.objects.all()
        elif user.organization:
            queryset = Payment.objects.filter(organization=user.organization)
        else:
            return Response(
                {'detail': 'No organization found.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Date range filters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Calculate statistics
        total_payments = queryset.count()
        completed_payments = queryset.filter(status='completed').count()
        failed_payments = queryset.filter(status='failed').count()
        
        revenue_stats = queryset.filter(status='completed').aggregate(
            total_revenue=Sum('amount'),
            avg_payment=Avg('amount'),
            total_transaction_fees=Sum('transaction_fee')
        )
        
        # Daily revenue for last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        daily_revenue = queryset.filter(
            status='completed',
            completed_at__gte=thirty_days_ago
        ).extra(
            {'date': "date(completed_at)"}
        ).values('date').annotate(
            daily_total=Sum('amount'),
            daily_count=Count('id')
        ).order_by('date')
        
        # Payment method distribution
        payment_methods = queryset.filter(
            status='completed'
        ).values('payment_method').annotate(
            count=Count('id'),
            total=Sum('amount')
        )
        
        stats = {
            'total_payments': total_payments,
            'completed_payments': completed_payments,
            'failed_payments': failed_payments,
            'success_rate': (completed_payments / total_payments * 100) if total_payments > 0 else 0,
            'total_revenue': revenue_stats['total_revenue'] or 0,
            'average_payment': revenue_stats['avg_payment'] or 0,
            'total_transaction_fees': revenue_stats['total_transaction_fees'] or 0,
            'net_revenue': (revenue_stats['total_revenue'] or 0) - (revenue_stats['total_transaction_fees'] or 0),
            'daily_revenue': list(daily_revenue),
            'payment_method_distribution': {
                pm['payment_method']: {
                    'count': pm['count'],
                    'total': pm['total'] or 0
                }
                for pm in payment_methods
            }
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """
        Get dashboard statistics for payments.
        """
        user = request.user
        organization = user.organization
        
        if not organization:
            return Response(
                {'detail': 'No organization found.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        this_month_start = today.replace(day=1)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
        last_month_end = this_month_start - timedelta(days=1)
        
        # Today's stats
        today_payments = Payment.objects.filter(
            organization=organization,
            status='completed',
            completed_at__date=today
        )
        today_stats = today_payments.aggregate(
            count=Count('id'),
            total=Sum('amount'),
            fees=Sum('transaction_fee')
        )
        
        # Yesterday's stats
        yesterday_payments = Payment.objects.filter(
            organization=organization,
            status='completed',
            completed_at__date=yesterday
        )
        yesterday_stats = yesterday_payments.aggregate(
            count=Count('id'),
            total=Sum('amount')
        )
        
        # This month's stats
        this_month_payments = Payment.objects.filter(
            organization=organization,
            status='completed',
            completed_at__date__gte=this_month_start
        )
        this_month_stats = this_month_payments.aggregate(
            count=Count('id'),
            total=Sum('amount')
        )
        
        # Last month's stats
        last_month_payments = Payment.objects.filter(
            organization=organization,
            status='completed',
            completed_at__date__range=[last_month_start, last_month_end]
        )
        last_month_stats = last_month_payments.aggregate(
            count=Count('id'),
            total=Sum('amount')
        )
        
        # Top customers by payment amount
        top_customers = Payment.objects.filter(
            organization=organization,
            status='completed'
        ).values(
            'customer__first_name', 'customer__last_name', 'customer__phone_number'
        ).annotate(
            total_paid=Sum('amount'),
            payment_count=Count('id')
        ).order_by('-total_paid')[:10]
        
        # Recent payments
        recent_payments = Payment.objects.filter(
            organization=organization
        ).select_related('customer').order_by('-created_at')[:10]
        
        dashboard_data = {
            'today': {
                'payments': today_stats['count'] or 0,
                'revenue': today_stats['total'] or 0,
                'fees': today_stats['fees'] or 0,
                'net_revenue': (today_stats['total'] or 0) - (today_stats['fees'] or 0)
            },
            'yesterday': {
                'payments': yesterday_stats['count'] or 0,
                'revenue': yesterday_stats['total'] or 0
            },
            'this_month': {
                'payments': this_month_stats['count'] or 0,
                'revenue': this_month_stats['total'] or 0
            },
            'last_month': {
                'payments': last_month_stats['count'] or 0,
                'revenue': last_month_stats['total'] or 0
            },
            'top_customers': list(top_customers),
            'recent_payments': PaymentSerializer(recent_payments, many=True).data
        }
        
        return Response(dashboard_data)


class InvoiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing invoices.
    """
    queryset = Invoice.objects.select_related(
        'organization', 'customer', 'created_by'
    ).all()
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, CanManagePayments]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'organization', 'customer']
    search_fields = ['invoice_number', 'reference', 'customer__first_name', 'customer__last_name']
    ordering_fields = ['issue_date', 'due_date', 'total_amount']
    ordering = ['-issue_date']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return InvoiceCreateSerializer
        return InvoiceSerializer
    
    def get_queryset(self):
        """
        Filter invoices by organization.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return Invoice.objects.none()
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.organization:
            return self.queryset.filter(organization=user.organization)
        
        return Invoice.objects.none()
    
    def perform_create(self, serializer):
        """
        Set organization and created_by.
        """
        serializer.save(
            organization=self.request.user.organization,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """
        Send invoice to customer.
        """
        invoice = self.get_object()
        
        # Send notification to customer
        if invoice.customer.email:
            send_notification.delay(
                organization_id=invoice.organization.id,
                recipient_type='customer',
                recipient_id=str(invoice.customer.id),
                notification_type='invoice_sent',
                channel='email',
                subject=f"Invoice #{invoice.invoice_number} from {invoice.organization.name}",
                message=f"Your invoice #{invoice.invoice_number} for {invoice.total_amount} is now available.",
                invoice_id=str(invoice.id)
            )
        
        if invoice.customer.phone_number and invoice.customer.receive_sms:
            send_notification.delay(
                organization_id=invoice.organization.id,
                recipient_type='customer',
                recipient_id=str(invoice.customer.id),
                notification_type='invoice_sent',
                channel='sms',
                message=f"Hi {invoice.customer.first_name}, invoice #{invoice.invoice_number} for KES {invoice.total_amount} sent. Due: {invoice.due_date}",
                invoice_id=str(invoice.id)
            )
        
        invoice.status = 'sent'
        invoice.save()
        
        return Response({'message': 'Invoice sent successfully'})
    
    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        """
        Record payment against an invoice.
        """
        invoice = self.get_object()
        amount = request.data.get('amount')
        payment_method = request.data.get('payment_method', 'cash')
        reference = request.data.get('reference', '')
        
        if not amount:
            return Response(
                {'error': 'amount is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = float(amount)
        except ValueError:
            return Response(
                {'error': 'amount must be a number.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create payment record
        payment = Payment.objects.create(
            organization=invoice.organization,
            customer=invoice.customer,
            amount=amount,
            currency=invoice.currency,
            payment_method=payment_method,
            payment_type='invoice',
            description=f"Payment for invoice #{invoice.invoice_number}",
            payer_phone=invoice.customer.phone_number,
            payer_name=f"{invoice.customer.first_name} {invoice.customer.last_name}",
            payer_email=invoice.customer.email,
            status='completed',
            completed_at=timezone.now(),
            created_by=request.user,
            external_reference=reference
        )
        
        # Update invoice
        invoice.amount_paid += amount
        invoice.save()
        
        # Send payment confirmation
        send_notification.delay(
            organization_id=invoice.organization.id,
            recipient_type='customer',
            recipient_id=str(invoice.customer.id),
            notification_type='payment_received',
            channel='sms',
            message=f"Payment of KES {amount} received for invoice #{invoice.invoice_number}. Thank you!",
            payment_id=str(payment.id)
        )
        
        return Response({
            'message': 'Payment recorded successfully',
            'payment': PaymentSerializer(payment).data,
            'invoice': InvoiceSerializer(invoice).data
        })
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Get overdue invoices.
        """
        queryset = self.filter_queryset(self.get_queryset())
        overdue_invoices = queryset.filter(
            status__in=['sent', 'viewed', 'partially_paid'],
            due_date__lt=timezone.now().date()
        )
        
        page = self.paginate_queryset(overdue_invoices)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(overdue_invoices, many=True)
        return Response(serializer.data)


class PaymentPlanViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payment plans.
    """
    queryset = PaymentPlan.objects.select_related(
        'organization', 'customer'
    ).all()
    serializer_class = PaymentPlanSerializer
    permission_classes = [permissions.IsAuthenticated, CanManagePayments]
    pagination_class = StandardPagination
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PaymentPlanCreateSerializer
        return PaymentPlanSerializer
    
    def get_queryset(self):
        """
        Filter payment plans by organization.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return PaymentPlan.objects.none()
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.organization:
            return self.queryset.filter(organization=user.organization)
        
        return PaymentPlan.objects.none()
    
    def perform_create(self, serializer):
        """
        Set organization and calculate installment amount.
        """
        organization = self.request.user.organization
        total_amount = serializer.validated_data['total_amount']
        installments = serializer.validated_data['number_of_installments']
        
        installment_amount = total_amount / installments
        
        serializer.save(
            organization=organization,
            installment_amount=installment_amount,
            balance=total_amount
        )
    
    @action(detail=True, methods=['post'])
    def record_installment(self, request, pk=None):
        """
        Record installment payment for a payment plan.
        """
        payment_plan = self.get_object()
        amount = request.data.get('amount')
        
        if not amount:
            return Response(
                {'error': 'amount is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = float(amount)
        except ValueError:
            return Response(
                {'error': 'amount must be a number.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create payment record
        payment = Payment.objects.create(
            organization=payment_plan.organization,
            customer=payment_plan.customer,
            amount=amount,
            currency='KES',
            payment_method=request.data.get('payment_method', 'mpesa'),
            payment_type='subscription',
            description=f"Installment for {payment_plan.name}",
            payer_phone=payment_plan.customer.phone_number,
            payer_name=f"{payment_plan.customer.first_name} {payment_plan.customer.last_name}",
            status='completed',
            completed_at=timezone.now(),
            created_by=request.user
        )
        
        # Update payment plan
        payment_plan.amount_paid += amount
        payment_plan.balance = payment_plan.total_amount - payment_plan.amount_paid
        
        if payment_plan.balance <= 0:
            payment_plan.status = 'completed'
        
        payment_plan.save()
        
        return Response({
            'message': 'Installment recorded successfully',
            'payment': PaymentSerializer(payment).data,
            'payment_plan': PaymentPlanSerializer(payment_plan).data
        })

    # ==============================================
# TEMPLATE VIEWS
# ==============================================

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q

@login_required
def payments_list_view(request):
    """
    Template view for payments list page
    """
    user = request.user
    
    # Redirect if no organization (for non-admin users)
    if not user.organization and not user.is_system_admin():
        from django.shortcuts import redirect
        if user.is_system_admin():
            return redirect('admin_dashboard')
        elif user.user_type in ['business_owner', 'business_staff']:
            return redirect('business_dashboard')
        else:
            return redirect('customer_dashboard')
    
    # Get payments based on user role
    if user.is_system_admin():
        payments = Payment.objects.all()
    elif user.organization:
        payments = Payment.objects.filter(organization=user.organization)
    else:
        payments = Payment.objects.none()
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    payment_method = request.GET.get('method', '')
    search_query = request.GET.get('q', '')
    
    if status_filter:
        payments = payments.filter(status=status_filter)
    
    if payment_method:
        payments = payments.filter(payment_method=payment_method)
    
    if search_query:
        payments = payments.filter(
            Q(payment_reference__icontains=search_query) |
            Q(external_reference__icontains=search_query) |
            Q(payer_name__icontains=search_query) |
            Q(payer_phone__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Date range filter
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        payments = payments.filter(created_at__date__gte=date_from)
    if date_to:
        payments = payments.filter(created_at__date__lte=date_to)
    
    # Pagination
    paginator = Paginator(payments.order_by('-created_at'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_amount = payments.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    context = {
        'page_obj': page_obj,
        'total_amount': total_amount,
        'total_payments': payments.count(),
        'completed_payments': payments.filter(status='completed').count(),
        'failed_payments': payments.filter(status='failed').count(),
        'status_filter': status_filter,
        'method_filter': payment_method,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'payments/list.html', context)