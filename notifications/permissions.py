from rest_framework import permissions


class IsSystemAdmin(permissions.BasePermission):
    """Allow access only to system administrators."""
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and 
                   request.user.user_type == 'system_admin')


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
            from organizations.models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=user.organization,
                    user=user
                )
                return member.role == 'admin' or member.can_manage_staff
            except OrganizationMember.DoesNotExist:
                return False
        
        return False


class CanSendNotifications(permissions.BasePermission):
    """Allow users to send notifications."""
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        if user.organization:
            # Business owners and admins can send notifications
            if user.user_type == 'business_owner':
                return True
            
            # Business staff can send if they have permission
            if user.user_type == 'business_staff':
                from organizations.models import OrganizationMember
                try:
                    member = OrganizationMember.objects.get(
                        organization=user.organization,
                        user=user
                    )
                    # Allow if user can manage payments or customers
                    return member.can_manage_payments or member.can_manage_customers
                except OrganizationMember.DoesNotExist:
                    return False
        
        return False