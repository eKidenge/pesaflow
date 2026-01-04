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
                # Allow if user can manage payments or is admin
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
        if user.organization and obj.organization == user.organization:
            from organizations.models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=user.organization,
                    user=user
                )
                # Allow if user can manage payments or is admin
                return member.can_manage_payments or member.role in ['owner', 'admin']
            except OrganizationMember.DoesNotExist:
                return False
        
        return False