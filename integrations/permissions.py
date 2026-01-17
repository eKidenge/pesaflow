# integrations/permissions.py
from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()


class IsSystemAdmin(permissions.BasePermission):
    """Allow access only to system administrators."""
    
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and
            request.user.user_type == 'system_admin'
        )


class IsBusinessOwnerOrAdmin(permissions.BasePermission):
    """Allow access to business owners and business staff with admin permissions."""
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        if user.user_type == 'business_owner':
            return True
        
        if user.user_type == 'business_staff' and user.organization:
            from organizations.models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=user.organization,
                    user=user
                )
                # Allow admin role or staff with specific permissions
                return member.role in ['admin', 'owner'] or member.can_manage_payments
            except OrganizationMember.DoesNotExist:
                return False
        
        return False
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        # Check if object belongs to user's organization
        if hasattr(obj, 'organization') and obj.organization != user.organization:
            return False
        
        if user.user_type == 'business_owner':
            return True
        
        if user.user_type == 'business_staff' and user.organization:
            from organizations.models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=user.organization,
                    user=user
                )
                return member.role in ['admin', 'owner'] or member.can_manage_payments
            except OrganizationMember.DoesNotExist:
                return False
        
        return False


class CanManageIntegrations(permissions.BasePermission):
    """Allow users to manage integrations if they have permission."""
    
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
                # Allow if user can manage payments or is admin/owner
                return member.can_manage_payments or member.role in ['owner', 'admin']
            except OrganizationMember.DoesNotExist:
                return False
        
        return False
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if user.user_type == 'system_admin':
            return True
        
        # Check if user is in the same organization as the integration
        if hasattr(obj, 'organization') and obj.organization != user.organization:
            return False
        
        if user.organization:
            from organizations.models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=user.organization,
                    user=user
                )
                # Allow if user can manage payments or is admin/owner
                return member.can_manage_payments or member.role in ['owner', 'admin']
            except OrganizationMember.DoesNotExist:
                return False
        
        return False


# Optional: Keep your existing IsOrganizationMember if needed elsewhere
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