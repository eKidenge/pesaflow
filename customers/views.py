from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
import csv
from django.http import HttpResponse

from .models import Customer, CustomerGroup
from .serializers import (
    CustomerSerializer,
    CustomerCreateSerializer,
    CustomerUpdateSerializer,
    CustomerGroupSerializer,
    CustomerStatisticsSerializer,
    CustomerImportSerializer
)
from .permissions import (
    IsOrganizationMember,
    CanManageCustomers,
    CanViewCustomers
)
from organizations.models import OrganizationMember


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class CustomerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing customers.
    """
    queryset = Customer.objects.select_related(
        'organization', 'created_by'
    ).prefetch_related('groups').all()
    serializer_class = CustomerSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'customer_type', 'gender', 'receive_sms', 'receive_email']
    search_fields = [
        'first_name', 'last_name', 'email', 'phone_number', 
        'customer_code', 'national_id', 'registration_number'
    ]
    ordering_fields = [
        'created_at', 'last_payment_date', 'first_name', 
        'last_name', 'account_balance'
    ]
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CustomerCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CustomerUpdateSerializer
        elif self.action == 'statistics':
            return CustomerStatisticsSerializer
        elif self.action == 'import':
            return CustomerImportSerializer
        return CustomerSerializer
    
    def get_permissions(self):
        """
        Custom permissions based on action.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, CanManageCustomers]
        elif self.action in ['retrieve', 'list']:
            permission_classes = [permissions.IsAuthenticated, CanViewCustomers]
        elif self.action == 'me':
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter customers based on user role and organization.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return Customer.objects.none()
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.user_type in ['business_owner', 'business_staff']:
            # Business users can see customers in their organization
            if user.organization:
                # Check if user has specific permission to view customers
                if not user.organization_memberships.filter(can_manage_customers=True).exists():
                    # If not, they can only see customers they created
                    return self.queryset.filter(
                        organization=user.organization,
                        created_by=user
                    )
                return self.queryset.filter(organization=user.organization)
            return Customer.objects.none()
        
        else:
            # Regular users can only see themselves as customers
            # This happens when a customer logs in to view their own payments
            return self.queryset.filter(
                Q(phone_number=user.phone_number) |
                Q(email=user.email)
            ).distinct()
    
    def perform_create(self, serializer):
        """
        Set organization and created_by automatically.
        """
        user = self.request.user
        
        if user.organization:
            serializer.save(organization=user.organization, created_by=user)
        else:
            raise permissions.PermissionDenied(
                "You must be associated with an organization to create customers."
            )
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Get current user as a customer (if exists).
        """
        user = request.user
        
        # Try to find customer by phone or email
        customer = Customer.objects.filter(
            Q(phone_number=user.phone_number) |
            Q(email=user.email),
            organization__is_active=True
        ).first()
        
        if customer:
            serializer = self.get_serializer(customer)
            return Response(serializer.data)
        
        return Response(
            {'detail': 'Customer profile not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get customer statistics for the organization.
        """
        user = request.user
        
        if not user.organization:
            return Response(
                {'detail': 'You are not associated with an organization.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        organization = user.organization
        
        # Calculate statistics
        total_customers = Customer.objects.filter(organization=organization).count()
        active_customers = Customer.objects.filter(
            organization=organization, 
            status='active'
        ).count()
        
        # Payment statistics
        from payments.models import Payment
        payment_stats = Payment.objects.filter(
            organization=organization,
            status='completed'
        ).aggregate(
            total_revenue=Sum('amount'),
            avg_payment=Avg('amount'),
            total_payments=Count('id')
        )
        
        # Customer type distribution
        customer_types = Customer.objects.filter(
            organization=organization
        ).values('customer_type').annotate(
            count=Count('id')
        )
        
        # Recent customers (last 30 days)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        recent_customers = Customer.objects.filter(
            organization=organization,
            created_at__gte=thirty_days_ago
        ).count()
        
        stats = {
            'total_customers': total_customers,
            'active_customers': active_customers,
            'inactive_customers': total_customers - active_customers,
            'recent_customers': recent_customers,
            'total_revenue': payment_stats['total_revenue'] or 0,
            'average_payment': payment_stats['avg_payment'] or 0,
            'total_payments': payment_stats['total_payments'] or 0,
            'customer_type_distribution': {
                ct['customer_type']: ct['count']
                for ct in customer_types
            },
            'account_balance_summary': {
                'positive_balance': Customer.objects.filter(
                    organization=organization,
                    account_balance__gt=0
                ).count(),
                'zero_balance': Customer.objects.filter(
                    organization=organization,
                    account_balance=0
                ).count(),
                'negative_balance': Customer.objects.filter(
                    organization=organization,
                    account_balance__lt=0
                ).count(),
            }
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['post'])
    def import_csv(self, request):
        """
        Import customers from CSV file.
        """
        serializer = CustomerImportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        csv_file = request.FILES['file']
        organization = request.user.organization
        
        if not organization:
            return Response(
                {'error': 'You must be associated with an organization to import customers.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            
            imported = 0
            errors = []
            
            for row_num, row in enumerate(reader, start=2):  # start=2 for header row
                try:
                    # Create customer from row
                    customer_data = {
                        'organization': organization.id,
                        'first_name': row.get('first_name', '').strip(),
                        'last_name': row.get('last_name', '').strip(),
                        'email': row.get('email', '').strip(),
                        'phone_number': row.get('phone_number', '').strip(),
                        'customer_type': row.get('customer_type', 'other').strip(),
                        'status': 'active',
                        'created_by': request.user.id
                    }
                    
                    # Validate required fields
                    if not customer_data['first_name'] or not customer_data['phone_number']:
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue
                    
                    # Check for duplicate phone number
                    if Customer.objects.filter(
                        organization=organization,
                        phone_number=customer_data['phone_number']
                    ).exists():
                        errors.append(f"Row {row_num}: Customer with this phone number already exists")
                        continue
                    
                    # Create customer
                    customer_serializer = CustomerCreateSerializer(data=customer_data)
                    if customer_serializer.is_valid():
                        customer_serializer.save()
                        imported += 1
                    else:
                        errors.append(f"Row {row_num}: {customer_serializer.errors}")
                        
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            return Response({
                'imported': imported,
                'errors': errors,
                'message': f'Successfully imported {imported} customers'
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to process CSV file: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        """
        Export customers to CSV.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="customers.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Customer Code', 'First Name', 'Last Name', 'Email',
            'Phone Number', 'Customer Type', 'Status', 'Account Balance',
            'Created At', 'Last Payment Date'
        ])
        
        # Write data
        for customer in queryset:
            writer.writerow([
                customer.customer_code,
                customer.first_name,
                customer.last_name,
                customer.email,
                customer.phone_number,
                customer.customer_type,
                customer.status,
                customer.account_balance,
                customer.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                customer.last_payment_date.strftime('%Y-%m-%d %H:%M:%S') if customer.last_payment_date else ''
            ])
        
        return response
    
    @action(detail=True, methods=['post'])
    def add_to_group(self, request, pk=None):
        """
        Add customer to a group.
        """
        customer = self.get_object()
        group_id = request.data.get('group_id')
        
        if not group_id:
            return Response(
                {'error': 'group_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            group = CustomerGroup.objects.get(
                id=group_id,
                organization=customer.organization
            )
            customer.groups.add(group)
            return Response({'message': f'Customer added to {group.name}'})
        except CustomerGroup.DoesNotExist:
            return Response(
                {'error': 'Group not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def payment_history(self, request, pk=None):
        """
        Get payment history for a customer.
        """
        customer = self.get_object()
        
        from payments.models import Payment
        payments = Payment.objects.filter(
            customer=customer
        ).order_by('-created_at')
        
        from payments.serializers import PaymentSerializer
        page = self.paginate_queryset(payments)
        if page is not None:
            serializer = PaymentSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)


class CustomerGroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing customer groups.
    """
    queryset = CustomerGroup.objects.select_related(
        'organization'
    ).prefetch_related('customers').all()
    serializer_class = CustomerGroupSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageCustomers]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['group_type', 'is_active']
    search_fields = ['name', 'description']
    
    def get_queryset(self):
        """
        Filter groups by organization.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return CustomerGroup.objects.none()
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.organization:
            return self.queryset.filter(organization=user.organization)
        
        return CustomerGroup.objects.none()
    
    def perform_create(self, serializer):
        """
        Set organization automatically.
        """
        if self.request.user.organization:
            serializer.save(organization=self.request.user.organization)
        else:
            raise permissions.PermissionDenied(
                "You must be associated with an organization to create groups."
            )
    
    @action(detail=True, methods=['post'])
    def add_customers(self, request, pk=None):
        """
        Add multiple customers to a group.
        """
        group = self.get_object()
        customer_ids = request.data.get('customer_ids', [])
        
        if not customer_ids:
            return Response(
                {'error': 'customer_ids is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get customers that belong to the same organization
        customers = Customer.objects.filter(
            id__in=customer_ids,
            organization=group.organization
        )
        
        added_count = 0
        for customer in customers:
            if customer not in group.customers.all():
                group.customers.add(customer)
                added_count += 1
        
        return Response({
            'message': f'Added {added_count} customers to {group.name}',
            'total_customers': group.customers.count()
        })
    
    @action(detail=True, methods=['post'])
    def remove_customers(self, request, pk=None):
        """
        Remove customers from a group.
        """
        group = self.get_object()
        customer_ids = request.data.get('customer_ids', [])
        
        if not customer_ids:
            return Response(
                {'error': 'customer_ids is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        removed_count = 0
        for customer_id in customer_ids:
            try:
                customer = Customer.objects.get(
                    id=customer_id,
                    organization=group.organization
                )
                group.customers.remove(customer)
                removed_count += 1
            except Customer.DoesNotExist:
                continue
        
        return Response({
            'message': f'Removed {removed_count} customers from {group.name}',
            'total_customers': group.customers.count()
        })
    
    @action(detail=True, methods=['post'])
    def send_group_notification(self, request, pk=None):
        """
        Send notification to all customers in a group.
        """
        group = self.get_object()
        message = request.data.get('message')
        channel = request.data.get('channel', 'sms')
        
        if not message:
            return Response(
                {'error': 'message is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # In production, use Celery for this
        from notifications.tasks import send_bulk_notification
        send_bulk_notification.delay(
            organization_id=group.organization.id,
            recipient_ids=[str(customer.id) for customer in group.customers.all()],
            recipient_type='customer',
            notification_type='group_notification',
            channel=channel,
            message=message,
            subject=f"Notification from {group.organization.name}"
        )
        
        return Response({
            'message': f'Notification scheduled for {group.customers.count()} customers'
        })

# ==============================================
# TEMPLATE VIEWS
# ==============================================

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

@login_required
def customers_list_view(request):
    """
    Template view for customers list page
    """
    user = request.user
    
    if not user.organization:
        # Redirect to appropriate dashboard
        from django.shortcuts import redirect
        if user.is_system_admin():
            return redirect('admin_dashboard')
        elif user.user_type in ['business_owner', 'business_staff']:
            return redirect('business_dashboard')
        else:
            return redirect('customer_dashboard')
    
    # Get customers for the organization
    customers = Customer.objects.filter(organization=user.organization)
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    customer_type = request.GET.get('type', '')
    search_query = request.GET.get('q', '')
    
    if status_filter:
        customers = customers.filter(status=status_filter)
    
    if customer_type:
        customers = customers.filter(customer_type=customer_type)
    
    if search_query:
        customers = customers.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone_number__icontains=search_query) |
            Q(customer_code__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(customers.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get statistics
    total_customers = customers.count()
    active_customers = customers.filter(status='active').count()
    
    context = {
        'page_obj': page_obj,
        'total_customers': total_customers,
        'active_customers': active_customers,
        'inactive_customers': total_customers - active_customers,
        'status_filter': status_filter,
        'type_filter': customer_type,
        'search_query': search_query,
    }
    
    return render(request, 'customers/list.html', context)