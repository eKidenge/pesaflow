from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()


class IsSystemAdmin(permissions.BasePermission):
    """Allow access only to system administrators."""
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and 
                   request.user.user_type == 'system_admin')


class IsBusinessOwner(permissions.BasePermission):
    """Allow access only to business owners."""
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and 
                   request.user.user_type == 'business_owner')


class IsBusinessStaff(permissions.BasePermission):
    """Allow access only to business staff."""
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and 
                   request.user.user_type == 'business_staff')


class IsUserOwner(permissions.BasePermission):
    """Allow access only to the user who owns the object."""
    
    def has_object_permission(self, request, view, obj):
        # Check if the object is a User instance
        if isinstance(obj, User):
            return obj == request.user
        
        # Check if the object has a user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if the object has a created_by attribute
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class IsBusinessOwnerOrAdmin(permissions.BasePermission):
    """Allow access to business owners and system admins."""
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and 
                   request.user.user_type in ['business_owner', 'system_admin'])


class IsBusinessMember(permissions.BasePermission):
    """Allow access to business owners, staff, and system admins."""
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and 
                   request.user.user_type in ['business_owner', 'business_staff', 'system_admin'])


class CanManageOrganization(permissions.BasePermission):
    """Allow users to manage organizations they own or are admins of."""
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        # System admins can manage any organization
        if user.user_type == 'system_admin':
            return True
        
        # Business owners can manage their own organization
        if user.user_type == 'business_owner':
            return user.organization == obj
        
        # Business staff can manage if they have permission
        if user.user_type == 'business_staff':
            from organizations.models import OrganizationMember
            try:
                member = OrganizationMember.objects.get(
                    organization=obj,
                    user=user
                )
                return member.can_manage_staff
            except OrganizationMember.DoesNotExist:
                return False
        
        return False