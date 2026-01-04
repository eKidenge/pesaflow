from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Sum, Q
from django.utils import timezone

from .models import Organization, OrganizationType, OrganizationMember
from .serializers import (
    OrganizationSerializer,
    OrganizationTypeSerializer,
    OrganizationMemberSerializer,
    OrganizationCreateSerializer,
    OrganizationStatisticsSerializer,
    OrganizationSettingsSerializer
)
# TO THIS:
from accounts.permissions import IsSystemAdmin
from .permissions import (
    IsBusinessOwnerOrAdmin,
    IsOrganizationMember,
    CanManageStaff,
    CanViewOrganization
)


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class OrganizationTypeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organization types.
    Only system admins can manage organization types.
    """
    queryset = OrganizationType.objects.filter(is_active=True)
    serializer_class = OrganizationTypeSerializer
    permission_classes = [IsSystemAdmin]
    pagination_class = StandardPagination


class OrganizationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organizations.
    System admins can view all organizations.
    Business owners can view/manage their own organization.
    """
    queryset = Organization.objects.select_related(
        'organization_type', 'created_by'
    ).prefetch_related('members', 'users').all()
    serializer_class = OrganizationSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'organization_type', 'is_active', 'subscription_status']
    search_fields = ['name', 'legal_name', 'email', 'phone_number', 'registration_number']
    ordering_fields = ['created_at', 'name', 'subscription_expiry']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return OrganizationCreateSerializer
        elif self.action == 'update_settings':
            return OrganizationSettingsSerializer
        elif self.action == 'statistics':
            return OrganizationStatisticsSerializer
        return OrganizationSerializer
    
    def get_permissions(self):
        """
        Custom permissions based on action.
        """
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsSystemAdmin | IsBusinessOwnerOrAdmin]
        elif self.action in ['retrieve']:
            permission_classes = [CanViewOrganization]
        elif self.action in ['list']:
            # Users can list organizations they belong to
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter organizations based on user role.
        """
        user = self.request.user
        
        if not user.is_authenticated:
            return Organization.objects.none()
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.user_type in ['business_owner', 'business_staff']:
            # Users can see organizations they belong to
            return self.queryset.filter(
                Q(id=user.organization_id) | 
                Q(members__user=user)
            ).distinct()
        
        else:
            # Regular customers can see organizations they're associated with via payments
            from customers.models import Customer
            customer_orgs = Customer.objects.filter(
                Q(phone_number=user.phone_number) |
                Q(email=user.email)
            ).values_list('organization_id', flat=True)
            
            return self.queryset.filter(
                id__in=customer_orgs,
                is_active=True,
                status='active'
            )
    
    def perform_create(self, serializer):
        """
        Set created_by to current user and create initial organization member.
        """
        organization = serializer.save(created_by=self.request.user)
        
        # Make the creator an owner of the organization
        if self.request.user.user_type in ['business_owner', 'system_admin']:
            OrganizationMember.objects.create(
                organization=organization,
                user=self.request.user,
                role='owner',
                can_manage_payments=True,
                can_manage_customers=True,
                can_manage_staff=True,
                can_view_reports=True,
                invitation_accepted=True,
                invited_by=self.request.user
            )
            
            # Update user's organization
            self.request.user.organization = organization
            self.request.user.save()
    
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """
        Get all members of an organization.
        """
        organization = self.get_object()
        self.check_object_permissions(request, organization)
        
        members = OrganizationMember.objects.filter(
            organization=organization
        ).select_related('user', 'invited_by')
        
        page = self.paginate_queryset(members)
        if page is not None:
            serializer = OrganizationMemberSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = OrganizationMemberSerializer(members, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """
        Get organization statistics.
        """
        organization = self.get_object()
        self.check_object_permissions(request, organization)
        
        from django.db.models import Count, Sum
        from customers.models import Customer
        from payments.models import Payment, Invoice
        from accounts.models import User
        
        # Calculate statistics
        stats = {
            'total_customers': Customer.objects.filter(organization=organization).count(),
            'active_customers': Customer.objects.filter(organization=organization, status='active').count(),
            'total_users': User.objects.filter(organization=organization).count(),
            'total_payments': Payment.objects.filter(organization=organization).count(),
            'total_revenue': Payment.objects.filter(
                organization=organization,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'pending_invoices': Invoice.objects.filter(
                organization=organization,
                status__in=['sent', 'viewed', 'partially_paid']
            ).count(),
            'overdue_invoices': Invoice.objects.filter(
                organization=organization,
                status='overdue'
            ).count(),
            'payment_methods': {
                'mpesa': Payment.objects.filter(
                    organization=organization,
                    payment_method='mpesa',
                    status='completed'
                ).count(),
                'card': Payment.objects.filter(
                    organization=organization,
                    payment_method='card',
                    status='completed'
                ).count(),
                'cash': Payment.objects.filter(
                    organization=organization,
                    payment_method='cash',
                    status='completed'
                ).count(),
            }
        }
        
        return Response(stats)
    
    @action(detail=True, methods=['get', 'put', 'patch'])
    def settings(self, request, pk=None):
        """
        Get or update organization settings.
        """
        organization = self.get_object()
        self.check_object_permissions(request, organization)
        
        if request.method in ['PUT', 'PATCH']:
            serializer = OrganizationSettingsSerializer(
                organization, 
                data=request.data, 
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        
        serializer = OrganizationSettingsSerializer(organization)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def upgrade_plan(self, request, pk=None):
        """
        Upgrade organization subscription plan.
        """
        organization = self.get_object()
        self.check_object_permissions(request, organization)
        
        plan = request.data.get('plan')
        if not plan:
            return Response(
                {'error': 'Plan is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # In production, integrate with payment gateway for subscription
        organization.subscription_plan = plan
        organization.subscription_status = 'active'
        organization.save()
        
        return Response({
            'message': f'Plan upgraded to {plan}',
            'subscription_plan': organization.subscription_plan
        })
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """
        Deactivate organization.
        """
        organization = self.get_object()
        self.check_object_permissions(request, organization)
        
        organization.is_active = False
        organization.status = 'inactive'
        organization.save()
        
        return Response({'message': 'Organization deactivated successfully.'})
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Activate organization.
        """
        organization = self.get_object()
        self.check_object_permissions(request, organization)
        
        organization.is_active = True
        organization.status = 'active'
        organization.save()
        
        return Response({'message': 'Organization activated successfully.'})


class OrganizationMemberViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organization members.
    """
    queryset = OrganizationMember.objects.select_related(
        'organization', 'user', 'invited_by'
    ).all()
    serializer_class = OrganizationMemberSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageStaff]
    pagination_class = StandardPagination
    
    def get_queryset(self):
        """
        Filter members based on user permissions.
        """
        user = self.request.user
        
        if user.user_type == 'system_admin':
            return self.queryset
        
        elif user.user_type == 'business_owner':
            # Owners can see members of their organizations
            return self.queryset.filter(organization=user.organization)
        
        elif user.user_type == 'business_staff':
            # Staff can only see themselves if they don't have permission
            if user.organization_memberships.filter(can_manage_staff=True).exists():
                return self.queryset.filter(organization=user.organization)
            return self.queryset.filter(user=user)
        
        else:
            return self.queryset.filter(user=user)
    
    def perform_create(self, serializer):
        """
        Set invited_by and validate organization.
        """
        user = self.request.user
        
        # Check if user has permission to add members to this organization
        if user.user_type != 'system_admin':
            organization = serializer.validated_data['organization']
            if organization != user.organization:
                raise permissions.PermissionDenied(
                    "You can only add members to your own organization."
                )
        
        serializer.save(invited_by=user)
        
        # Send invitation email (in production, use Celery)
        member = serializer.instance
        if member.user.email:
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                
                send_mail(
                    subject=f'Invitation to join {member.organization.name} on PesaFlow',
                    message=f'You have been invited to join {member.organization.name}.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[member.user.email],
                    fail_silently=True,
                )
            except Exception:
                pass  # Log this in production
    
    @action(detail=True, methods=['post'])
    def resend_invitation(self, request, pk=None):
        """
        Resend invitation email to member.
        """
        member = self.get_object()
        self.check_object_permissions(request, member)
        
        if member.user.email:
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                
                send_mail(
                    subject=f'Reminder: Invitation to join {member.organization.name}',
                    message=f'This is a reminder for your invitation to join {member.organization.name}.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[member.user.email],
                    fail_silently=True,
                )
                return Response({'message': 'Invitation resent successfully.'})
            except Exception as e:
                return Response(
                    {'error': f'Failed to send invitation: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(
            {'error': 'Member does not have an email address.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'])
    def accept_invitation(self, request, pk=None):
        """
        Accept organization invitation.
        """
        member = self.get_object()
        
        # Only the invited user can accept
        if member.user != request.user:
            raise permissions.PermissionDenied(
                "Only the invited user can accept the invitation."
            )
        
        member.invitation_accepted = True
        member.joined_at = timezone.now()
        member.save()
        
        # Update user's organization
        request.user.organization = member.organization
        request.user.save()
        
        return Response({'message': 'Invitation accepted successfully.'})