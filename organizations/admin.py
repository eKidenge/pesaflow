from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from .models import Organization, OrganizationType, OrganizationMember


@admin.register(OrganizationType)
class OrganizationTypeAdmin(admin.ModelAdmin):
    """Admin configuration for OrganizationType model"""
    
    list_display = ['name', 'provider', 'category', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active']
    actions = ['activate_types', 'deactivate_types']
    
    def activate_types(self, request, queryset):
        """Activate selected organization types"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} organization types were activated.')
    activate_types.short_description = "Activate selected organization types"
    
    def deactivate_types(self, request, queryset):
        """Deactivate selected organization types"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} organization types were deactivated.')
    deactivate_types.short_description = "Deactivate selected organization types"


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Admin configuration for Organization model"""
    
    list_display = [
        'name', 'organization_type', 'phone_number', 'email', 'city',
        'status', 'is_active', 'is_verified', 'subscription_plan',
        'subscription_status', 'created_at', 'member_count', 'customer_count'
    ]
    
    list_filter = [
        'status', 'is_active', 'is_verified', 'organization_type',
        'subscription_status', 'subscription_plan', 'country', 'county',
        'created_at'
    ]
    
    search_fields = [
        'name', 'legal_name', 'email', 'phone_number', 'registration_number',
        'tax_id', 'city', 'county'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'member_count', 'customer_count',
        'revenue_today', 'revenue_this_month'
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'name', 'legal_name', 'organization_type', 'logo',
                'primary_color', 'secondary_color'
            )
        }),
        (_('Contact Information'), {
            'fields': (
                'phone_number', 'email', 'website', 'address', 'city',
                'county', 'country', 'postal_code'
            )
        }),
        (_('Business Registration'), {
            'fields': ('registration_number', 'tax_id', 'business_license')
        }),
        (_('Financial Settings'), {
            'fields': ('currency', 'timezone', 'payment_methods')
        }),
        (_('M-Pesa Configuration'), {
            'fields': ('mpesa_paybill', 'mpesa_till_number'),
            'classes': ('collapse',)
        }),
        (_('Status & Settings'), {
            'fields': (
                'status', 'is_verified', 'is_active', 'settings', 'metadata'
            )
        }),
        (_('Subscription'), {
            'fields': (
                'subscription_plan', 'subscription_status',
                'subscription_expiry'
            )
        }),
        (_('Limits'), {
            'fields': (
                'max_users', 'max_customers', 'monthly_transaction_limit'
            ),
            'classes': ('collapse',)
        }),
        (_('Statistics'), {
            'fields': (
                'member_count', 'customer_count', 'revenue_today',
                'revenue_this_month'
            ),
            'classes': ('collapse',)
        }),
        (_('Audit'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'activate_organizations', 'deactivate_organizations',
        'verify_organizations', 'upgrade_to_premium', 'downgrade_to_basic'
    ]
    
    def member_count(self, obj):
        """Display member count"""
        return obj.members.count()
    member_count.short_description = 'Members'
    
    def customer_count(self, obj):
        """Display customer count"""
        from customers.models import Customer
        return Customer.objects.filter(organization=obj).count()
    customer_count.short_description = 'Customers'
    
    def revenue_today(self, obj):
        """Display today's revenue"""
        from django.utils import timezone
        from django.db.models import Sum
        from payments.models import Payment
        
        today = timezone.now().date()
        revenue = Payment.objects.filter(
            organization=obj,
            status='completed',
            completed_at__date=today
        ).aggregate(total=Sum('amount'))['total']
        
        return f"KES {revenue or 0:,.2f}"
    revenue_today.short_description = "Today's Revenue"
    
    def revenue_this_month(self, obj):
        """Display this month's revenue"""
        from django.utils import timezone
        from django.db.models import Sum
        from payments.models import Payment
        
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        revenue = Payment.objects.filter(
            organization=obj,
            status='completed',
            completed_at__date__gte=month_start
        ).aggregate(total=Sum('amount'))['total']
        
        return f"KES {revenue or 0:,.2f}"
    revenue_this_month.short_description = "This Month's Revenue"
    
    def activate_organizations(self, request, queryset):
        """Activate selected organizations"""
        updated = queryset.update(is_active=True, status='active')
        self.message_user(request, f'{updated} organizations were activated.')
    activate_organizations.short_description = "Activate selected organizations"
    
    def deactivate_organizations(self, request, queryset):
        """Deactivate selected organizations"""
        updated = queryset.update(is_active=False, status='inactive')
        self.message_user(request, f'{updated} organizations were deactivated.')
    deactivate_organizations.short_description = "Deactivate selected organizations"
    
    def verify_organizations(self, request, queryset):
        """Verify selected organizations"""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} organizations were verified.')
    verify_organizations.short_description = "Verify selected organizations"
    
    def upgrade_to_premium(self, request, queryset):
        """Upgrade selected organizations to premium"""
        updated = queryset.update(
            subscription_plan='premium',
            subscription_status='active',
            max_users=50,
            max_customers=10000,
            monthly_transaction_limit=10000000
        )
        self.message_user(request, f'{updated} organizations were upgraded to premium.')
    upgrade_to_premium.short_description = "Upgrade to premium plan"
    
    def downgrade_to_basic(self, request, queryset):
        """Downgrade selected organizations to basic"""
        updated = queryset.update(
            subscription_plan='basic',
            max_users=5,
            max_customers=100,
            monthly_transaction_limit=1000000
        )
        self.message_user(request, f'{updated} organizations were downgraded to basic.')
    downgrade_to_basic.short_description = "Downgrade to basic plan"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('organization_type', 'created_by')
        return qs


class OrganizationMemberInline(admin.TabularInline):
    """Inline admin for OrganizationMember"""
    model = OrganizationMember
    extra = 1
    readonly_fields = ['joined_at', 'updated_at']
    fields = [
        'user', 'role', 'can_manage_payments', 'can_manage_customers',
        'can_manage_staff', 'can_view_reports', 'is_active',
        'invitation_accepted', 'joined_at'
    ]
    raw_id_fields = ['user', 'invited_by']


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    """Admin configuration for OrganizationMember model"""
    
    list_display = [
        'organization', 'user', 'role', 'is_active', 'invitation_accepted',
        'joined_at', 'has_full_permissions'
    ]
    
    list_filter = [
        'role', 'is_active', 'invitation_accepted', 'organization',
        'joined_at'
    ]
    
    search_fields = [
        'organization__name', 'user__email', 'user__first_name',
        'user__last_name', 'user__phone_number'
    ]
    
    readonly_fields = ['joined_at', 'updated_at']
    
    fieldsets = (
        (_('Membership'), {
            'fields': ('organization', 'user', 'invited_by')
        }),
        (_('Role & Permissions'), {
            'fields': (
                'role', 'can_manage_payments', 'can_manage_customers',
                'can_manage_staff', 'can_view_reports'
            )
        }),
        (_('Status'), {
            'fields': ('is_active', 'invitation_accepted')
        }),
        (_('Audit'), {
            'fields': ('joined_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ['organization', 'user', 'invited_by']
    
    actions = ['activate_members', 'deactivate_members', 'grant_admin_permissions']
    
    def has_full_permissions(self, obj):
        """Check if member has all permissions"""
        return all([
            obj.can_manage_payments,
            obj.can_manage_customers,
            obj.can_manage_staff,
            obj.can_view_reports
        ])
    has_full_permissions.boolean = True
    has_full_permissions.short_description = 'Full Permissions'
    
    def activate_members(self, request, queryset):
        """Activate selected members"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} members were activated.')
    activate_members.short_description = "Activate selected members"
    
    def deactivate_members(self, request, queryset):
        """Deactivate selected members"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} members were deactivated.')
    deactivate_members.short_description = "Deactivate selected members"
    
    def grant_admin_permissions(self, request, queryset):
        """Grant admin permissions to selected members"""
        updated = queryset.update(
            role='admin',
            can_manage_payments=True,
            can_manage_customers=True,
            can_manage_staff=True,
            can_view_reports=True
        )
        self.message_user(request, f'{updated} members were granted admin permissions.')
    grant_admin_permissions.short_description = "Grant admin permissions"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('organization', 'user', 'invited_by')
        return qs