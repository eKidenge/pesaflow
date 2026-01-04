from rest_framework import permissions


class IsOrganizationMember(permissions.BasePermission):
    """Allow access only to members of the organization."""
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        # System admins can access everything
        if user.user_type == 'system_admin':
            return True
        
        # Users must be associated with an organization
        if not user.organization:
            return False
        
        # Check if user is a member of the organization
        from .models import OrganizationMember
        return OrganizationMember.objects.filter(
            organization=user.organization,
            user=user,
            is_active=True
        ).exists()


class IsBusinessOwnerOrAdmin(permissions.BasePermission):
    """Allow access to business owners and system admins."""
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        if user.user_type == 'business_owner':
            return True
        
        # Check if business staff has admin permissions
        if user.user_type == 'business_staff':
            from .models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=user.organization,
                    user=user
                )
                return member.role == 'admin' or member.can_manage_staff
            except OrganizationMember.DoesNotExist:
                return False
        
        return False


class CanManageStaff(permissions.BasePermission):
    """Allow users to manage staff if they have permission."""
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        if user.organization:
            from .models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=user.organization,
                    user=user
                )
                return member.can_manage_staff
            except OrganizationMember.DoesNotExist:
                return False
        
        return False


class CanViewOrganization(permissions.BasePermission):
    """Allow users to view organizations they are associated with."""
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        # Check if user is a member of this organization
        from .models import OrganizationMember
        if OrganizationMember.objects.filter(
            organization=obj,
            user=user,
            is_active=True
        ).exists():
            return True
        
        # Check if user is the owner of this organization
        if user.organization == obj:
            return True
        
        # Check if user is a customer of this organization
        from customers.models import Customer
        if Customer.objects.filter(
            organization=obj,
            phone_number=user.phone_number
        ).exists():
            return True
        
        return False