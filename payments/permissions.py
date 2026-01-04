from rest_framework import permissions


class IsOrganizationMember(permissions.BasePermission):
    """Allow access only to members of the organization."""
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        # Users must be associated with an organization
        if not user.organization:
            return False
        
        # Check if user is a member of the organization
        from organizations.models import OrganizationMember
        return OrganizationMember.objects.filter(
            organization=user.organization,
            user=user,
            is_active=True
        ).exists()


class CanManagePayments(permissions.BasePermission):
    """Allow users to manage payments if they have permission."""
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        if user.organization:
            from organizations.models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=user.organization,
                    user=user
                )
                return member.can_manage_payments
            except OrganizationMember.DoesNotExist:
                return False
        
        return False
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        # Check if user is in the same organization as the payment
        if user.organization and obj.organization == user.organization:
            from organizations.models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=user.organization,
                    user=user
                )
                return member.can_manage_payments
            except OrganizationMember.DoesNotExist:
                return False
        
        return False


class CanViewPayments(permissions.BasePermission):
    """Allow users to view payments if they have permission."""
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        if user.organization:
            from organizations.models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=user.organization,
                    user=user
                )
                return member.can_manage_payments or member.can_view_reports
            except OrganizationMember.DoesNotExist:
                return False
        
        # Customers can view their own payments
        return user.user_type == 'customer'
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        # Check if user is viewing their own payment
        if user.user_type == 'customer':
            # Check if this payment belongs to the user
            from customers.models import Customer
            customer = Customer.objects.filter(
                organization=obj.organization,
                phone_number=user.phone_number
            ).first()
            return customer == obj.customer
        
        # Check if user is in the same organization as the payment
        if user.organization and obj.organization == user.organization:
            from organizations.models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=user.organization,
                    user=user
                )
                return member.can_manage_payments or member.can_view_reports
            except OrganizationMember.DoesNotExist:
                return False
        
        return False


class CanInitiatePayment(permissions.BasePermission):
    """Allow users to initiate payments."""
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        if user.organization:
            from organizations.models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=user.organization,
                    user=user
                )
                return member.can_manage_payments
            except OrganizationMember.DoesNotExist:
                return False
        
        # Customers can initiate payments for themselves
        return user.user_type == 'customer'