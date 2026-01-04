from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.auth.models import Group
from django.db.models import Count
from django.utils import timezone

from .models import (
    User, 
    UserProfile, 
    Organization, 
    LoginHistory, 
    VerificationCode,
    UserSession
)


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile"""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile Details'
    fieldsets = [
        ('Personal Information', {
            'fields': ['gender', 'date_of_birth', 'national_id']
        }),
        ('Contact Information', {
            'fields': ['address', 'city', 'country', 'website']
        }),
        ('Professional Information', {
            'fields': ['designation', 'department', 'bio']
        }),
        ('Emergency Contact', {
            'fields': ['emergency_contact_name', 'emergency_contact_phone']
        }),
        ('Social Media', {
            'fields': ['twitter', 'linkedin'],
            'classes': ['collapse']
        }),
        ('Preferences', {
            'fields': [
                'timezone', 'language', 'currency',
                'email_notifications', 'sms_notifications',
                'push_notifications', 'marketing_emails'
            ],
            'classes': ['collapse']
        }),
        ('Security', {
            'fields': ['login_attempts', 'last_login_attempt', 'account_locked'],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': ['preferences', 'metadata'],
            'classes': ['collapse']
        }),
    ]
    readonly_fields = ['created_at', 'updated_at', 'login_attempts', 'last_login_attempt']


class LoginHistoryInline(admin.TabularInline):
    """Inline admin for LoginHistory"""
    model = LoginHistory
    extra = 0
    max_num = 5
    can_delete = False
    readonly_fields = [
        'ip_address', 'user_agent', 'location', 'device_type',
        'browser', 'os', 'success', 'failure_reason', 'login_time'
    ]
    
    def has_add_permission(self, request, obj):
        return False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for User model - UPDATED FOR NEW MODELS"""
    
    list_display = [
        'email', 'full_name', 'phone', 'user_type_display', 
        'organization_link', 'is_active', 'email_verified', 
        'phone_verified', 'created_at_short'
    ]
    
    list_filter = [
        'user_type', 'is_active', 'is_staff', 'is_superuser',
        'email_verified', 'phone_verified', 'organization',
        'country', 'created_at', 'updated_at'
    ]
    
    search_fields = [
        'email', 'first_name', 'last_name', 'phone',
        'organization__name', 'id_number'
    ]
    
    ordering = ['-created_at']
    
    fieldsets = (
        (_('Login Credentials'), {
            'fields': ('email', 'password')
        }),
        (_('Personal Information'), {
            'fields': (
                'first_name', 'last_name', 'phone', 
                'profile_picture', 'date_of_birth'
            )
        }),
        (_('Address Information'), {
            'fields': ('address', 'city', 'country')
        }),
        (_('User Type & Role'), {
            'fields': ('user_type', 'id_number', 'position', 'department')
        }),
        (_('Organization'), {
            'fields': ('organization',)
        }),
        (_('Permissions'), {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            )
        }),
        (_('Verification Status'), {
            'fields': (
                'email_verified', 'phone_verified',
                'verification_code', 'verification_code_expiry'
            ),
            'classes': ('collapse',)
        }),
        (_('Password Management'), {
            'fields': (
                'password_reset_token', 'password_reset_token_expiry',
                'last_password_change', 'must_change_password'
            ),
            'classes': ('collapse',)
        }),
        (_('Preferences'), {
            'fields': (
                'receive_email_notifications', 'receive_sms_notifications',
                'two_factor_enabled'
            )
        }),
        (_('Security & Tracking'), {
            'fields': (
                'last_login_ip', 'last_login_location',
                'last_login', 'date_joined'
            ),
            'classes': ('collapse',)
        }),
        (_('System Information'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'first_name', 'last_name', 'phone',
                'password1', 'password2', 'user_type', 'country',
                'organization', 'is_active', 'is_staff', 'is_superuser'
            ),
        }),
    )
    
    readonly_fields = [
        'last_login', 'date_joined', 'created_at', 'updated_at',
        'password_reset_token', 'last_password_change',
        'last_login_ip', 'last_login_location'
    ]
    
    inlines = [UserProfileInline, LoginHistoryInline]
    
    actions = [
        'make_active', 'make_inactive', 
        'verify_email', 'verify_phone',
        'send_welcome_email', 'reset_password',
        'export_users_csv'
    ]
    
    # Custom display methods
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = 'Full Name'
    full_name.admin_order_field = 'first_name'
    
    def user_type_display(self, obj):
        colors = {
            'system_admin': 'red',
            'business_owner': 'blue',
            'business_staff': 'green',
            'client': 'gray'
        }
        color = colors.get(obj.user_type, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_user_type_display()
        )
    user_type_display.short_description = 'User Type'
    
    def organization_link(self, obj):
        if obj.organization:
            url = reverse('admin:accounts_organization_change', args=[obj.organization.id])
            return format_html('<a href="{}">{}</a>', url, obj.organization.name)
        return '-'
    organization_link.short_description = 'Organization'
    organization_link.admin_order_field = 'organization__name'
    
    def created_at_short(self, obj):
        return obj.created_at.strftime('%Y-%m-%d')
    created_at_short.short_description = 'Created'
    created_at_short.admin_order_field = 'created_at'
    
    # Admin actions
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users were marked as active.')
    make_active.short_description = "✅ Mark selected users as active"
    
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users were marked as inactive.')
    make_inactive.short_description = "❌ Mark selected users as inactive"
    
    def verify_email(self, request, queryset):
        updated = queryset.update(email_verified=True)
        self.message_user(request, f'{updated} users had their email verified.')
    verify_email.short_description = "📧 Verify email for selected users"
    
    def verify_phone(self, request, queryset):
        updated = queryset.update(phone_verified=True)
        self.message_user(request, f'{updated} users had their phone verified.')
    verify_phone.short_description = "📱 Verify phone for selected users"
    
    def send_welcome_email(self, request, queryset):
        from django.core.mail import send_mail
        from django.conf import settings
        
        count = 0
        for user in queryset:
            try:
                send_mail(
                    subject='Welcome to PesaFlow - Admin Resend',
                    message=f'Hello {user.first_name},\n\nWelcome to PesaFlow! Your account is active.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                count += 1
            except Exception as e:
                self.message_user(request, f'Failed to send to {user.email}: {str(e)}', level='error')
        
        self.message_user(request, f'Welcome emails sent to {count} users.')
    send_welcome_email.short_description = "📨 Send welcome email to selected users"
    
    def reset_password(self, request, queryset):
        import uuid
        for user in queryset:
            temp_password = str(uuid.uuid4())[:8]
            user.set_password(temp_password)
            user.must_change_password = True
            user.save()
            
            self.message_user(
                request, 
                f'Password reset for {user.email}. Temporary password: {temp_password}',
                level='info'
            )
    reset_password.short_description = "🔑 Reset password for selected users"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('organization', 'user_profile')
        return qs
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields read-only for existing users"""
        readonly_fields = list(self.readonly_fields)
        if obj:  # Editing an existing object
            readonly_fields.append('email')
            readonly_fields.append('user_type')
        return readonly_fields
    
    # Change list customizations
    def changelist_view(self, request, extra_context=None):
        # Add stats to the changelist view
        stats = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'admins': User.objects.filter(user_type='system_admin').count(),
            'business_users': User.objects.filter(user_type__in=['business_owner', 'business_staff']).count(),
            'clients': User.objects.filter(user_type='client').count(),
            'verified_emails': User.objects.filter(email_verified=True).count(),
        }
        
        extra_context = extra_context or {}
        extra_context['stats'] = stats
        
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Admin configuration for Organization model"""
    
    list_display = [
        'name', 'email', 'phone', 'country', 'business_type',
        'is_verified', 'total_users', 'created_at_short'
    ]
    
    list_filter = [
        'business_type', 'country', 'is_verified',
        'created_at', 'updated_at'
    ]
    
    search_fields = [
        'name', 'email', 'phone', 'registration_number'
    ]
    
    readonly_fields = [
        'total_users', 'active_users', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'name', 'email', 'phone', 'country', 'address'
            )
        }),
        (_('Business Details'), {
            'fields': (
                'registration_number', 'business_type',
                'verification_document', 'is_verified'
            )
        }),
        (_('Settings'), {
            'fields': ('currency', 'timezone', 'settings'),
            'classes': ('collapse',)
        }),
        (_('Statistics'), {
            'fields': ('total_users', 'active_users'),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['verify_organization', 'unverify_organization']
    
    def total_users(self, obj):
        return obj.users.count()
    total_users.short_description = 'Total Users'
    
    def active_users(self, obj):
        return obj.users.filter(is_active=True).count()
    active_users.short_description = 'Active Users'
    
    def created_at_short(self, obj):
        return obj.created_at.strftime('%Y-%m-%d')
    created_at_short.short_description = 'Created'
    
    def verify_organization(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} organizations were verified.')
    verify_organization.short_description = "✅ Verify selected organizations"
    
    def unverify_organization(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} organizations were unverified.')
    unverify_organization.short_description = "❌ Unverify selected organizations"
    
    inlines = []
    
    def get_inlines(self, request, obj):
        if obj:
            from django.contrib import admin
            class OrganizationUsersInline(admin.TabularInline):
                model = User
                extra = 0
                max_num = 10
                fields = ['email', 'first_name', 'last_name', 'user_type', 'is_active']
                readonly_fields = fields
                can_delete = False
                
                def has_add_permission(self, request, obj):
                    return False
            return [OrganizationUsersInline]
        return []
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.annotate(user_count=Count('users'))
        return qs


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin configuration for UserProfile model"""
    
    list_display = [
        'user_email', 'user_full_name', 'national_id', 
        'gender', 'city', 'country', 'designation',
        'account_status', 'created_at_short'
    ]
    
    list_filter = [
        'gender', 'country', 'city', 
        'account_locked', 'created_at', 'updated_at'
    ]
    
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name',
        'national_id', 'city', 'country', 'designation'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'login_attempts',
        'last_login_attempt', 'account_locked', 'account_locked_until'
    ]
    
    fieldsets = (
        (_('User Account'), {
            'fields': ('user',)
        }),
        (_('Personal Information'), {
            'fields': (
                'national_id', 'date_of_birth', 'gender'
            )
        }),
        (_('Contact Information'), {
            'fields': ('address', 'city', 'country')
        }),
        (_('Professional Information'), {
            'fields': ('designation', 'department', 'bio')
        }),
        (_('Emergency Contact'), {
            'fields': ('emergency_contact_name', 'emergency_contact_phone'),
            'classes': ('collapse',)
        }),
        (_('Social Media'), {
            'fields': ('website', 'twitter', 'linkedin'),
            'classes': ('collapse',)
        }),
        (_('Preferences'), {
            'fields': (
                'timezone', 'language', 'currency',
                'email_notifications', 'sms_notifications',
                'push_notifications', 'marketing_emails'
            ),
            'classes': ('collapse',)
        }),
        (_('Security Status'), {
            'fields': (
                'login_attempts', 'last_login_attempt',
                'account_locked', 'account_locked_until'
            ),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('preferences', 'metadata'),
            'classes': ('collapse',)
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['unlock_accounts', 'reset_login_attempts']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email'
    
    def user_full_name(self, obj):
        return obj.user.full_name
    user_full_name.short_description = 'Full Name'
    user_full_name.admin_order_field = 'user__first_name'
    
    def account_status(self, obj):
        if obj.account_locked:
            return format_html(
                '<span style="color: red; font-weight: bold;">🔒 Locked</span>'
            )
        return format_html(
            '<span style="color: green; font-weight: bold;">✅ Active</span>'
        )
    account_status.short_description = 'Status'
    
    def created_at_short(self, obj):
        return obj.created_at.strftime('%Y-%m-%d')
    created_at_short.short_description = 'Created'
    
    def unlock_accounts(self, request, queryset):
        for profile in queryset:
            profile.reset_login_attempts()
        self.message_user(request, f'{queryset.count()} accounts were unlocked.')
    unlock_accounts.short_description = "🔓 Unlock selected accounts"
    
    def reset_login_attempts(self, request, queryset):
        for profile in queryset:
            profile.login_attempts = 0
            profile.save()
        self.message_user(request, f'Login attempts reset for {queryset.count()} accounts.')
    reset_login_attempts.short_description = "🔄 Reset login attempts"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('user')
        return qs


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    """Admin configuration for LoginHistory model"""
    
    list_display = [
        'user_email', 'ip_address', 'location',
        'device_type', 'browser', 'success_badge',
        'login_time_short', 'session_duration_display'
    ]
    
    list_filter = [
        'success', 'device_type', 'browser', 'os',
        'login_time', 'user__user_type'
    ]
    
    search_fields = [
        'user__email', 'ip_address', 'location',
        'user_agent'
    ]
    
    readonly_fields = [
        'user', 'ip_address', 'user_agent', 'location',
        'device_type', 'browser', 'os', 'success',
        'failure_reason', 'login_time', 'logout_time',
        'session_duration'
    ]
    
    fieldsets = (
        (_('User Information'), {
            'fields': ('user',)
        }),
        (_('Login Details'), {
            'fields': (
                'ip_address', 'location', 'user_agent'
            )
        }),
        (_('Device Information'), {
            'fields': ('device_type', 'browser', 'os'),
            'classes': ('collapse',)
        }),
        (_('Login Result'), {
            'fields': ('success', 'failure_reason')
        }),
        (_('Timestamps'), {
            'fields': ('login_time', 'logout_time', 'session_duration'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['export_login_history']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def success_badge(self, obj):
        if obj.success:
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Success</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ Failed</span>'
            )
    success_badge.short_description = 'Status'
    
    def login_time_short(self, obj):
        return obj.login_time.strftime('%Y-%m-%d %H:%M')
    login_time_short.short_description = 'Login Time'
    
    def session_duration_display(self, obj):
        if obj.session_duration:
            total_seconds = int(obj.session_duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours}h {minutes}m"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return '-'
    session_duration_display.short_description = 'Duration'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('user')
        return qs


@admin.register(VerificationCode)
class VerificationCodeAdmin(admin.ModelAdmin):
    """Admin configuration for VerificationCode model"""
    
    list_display = [
        'user_email', 'code', 'purpose_display',
        'is_valid_badge', 'used_badge', 'created_at_short',
        'expires_at_short'
    ]
    
    list_filter = [
        'purpose', 'used', 'created_at'
    ]
    
    search_fields = [
        'user__email', 'code', 'ip_address'
    ]
    
    readonly_fields = [
        'user', 'code', 'purpose', 'created_at',
        'expires_at', 'used', 'used_at', 'ip_address',
        'metadata'
    ]
    
    fieldsets = (
        (_('Verification Information'), {
            'fields': ('user', 'code', 'purpose')
        }),
        (_('Validity'), {
            'fields': ('created_at', 'expires_at', 'used', 'used_at')
        }),
        (_('Additional Data'), {
            'fields': ('ip_address', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def purpose_display(self, obj):
        return obj.get_purpose_display()
    purpose_display.short_description = 'Purpose'
    
    def is_valid_badge(self, obj):
        if obj.is_valid():
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Valid</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">❌ Expired</span>'
        )
    is_valid_badge.short_description = 'Valid'
    
    def used_badge(self, obj):
        if obj.used:
            return format_html(
                '<span style="color: blue; font-weight: bold;">✅ Used</span>'
            )
        return format_html(
            '<span style="color: orange; font-weight: bold;">⏳ Unused</span>'
        )
    used_badge.short_description = 'Used'
    
    def created_at_short(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_short.short_description = 'Created'
    
    def expires_at_short(self, obj):
        return obj.expires_at.strftime('%Y-%m-%d %H:%M')
    expires_at_short.short_description = 'Expires'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('user')
        return qs


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Admin configuration for UserSession model"""
    
    list_display = [
        'user_email', 'session_short', 'ip_address',
        'is_active_badge', 'is_mobile_badge', 'created_at_short',
        'last_activity_short', 'is_expired_badge'
    ]
    
    list_filter = [
        'is_active', 'is_mobile', 'created_at', 'last_activity'
    ]
    
    search_fields = [
        'user__email', 'session_key', 'ip_address'
    ]
    
    readonly_fields = [
        'user', 'session_key', 'ip_address', 'user_agent',
        'location', 'is_active', 'is_mobile', 'created_at',
        'last_activity', 'expires_at'
    ]
    
    fieldsets = (
        (_('Session Information'), {
            'fields': ('user', 'session_key', 'is_active')
        }),
        (_('Connection Details'), {
            'fields': ('ip_address', 'user_agent', 'location')
        }),
        (_('Device Information'), {
            'fields': ('is_mobile',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'last_activity', 'expires_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['terminate_sessions']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def session_short(self, obj):
        return obj.session_key[:20] + '...'
    session_short.short_description = 'Session Key'
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Active</span>'
            )
        return format_html(
            '<span style="color: gray; font-weight: bold;">💤 Inactive</span>'
        )
    is_active_badge.short_description = 'Active'
    
    def is_mobile_badge(self, obj):
        if obj.is_mobile:
            return format_html('📱 Mobile')
        return format_html('💻 Desktop')
    is_mobile_badge.short_description = 'Device'
    
    def created_at_short(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_short.short_description = 'Created'
    
    def last_activity_short(self, obj):
        return obj.last_activity.strftime('%Y-%m-%d %H:%M')
    last_activity_short.short_description = 'Last Activity'
    
    def is_expired_badge(self, obj):
        if obj.is_expired():
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ Expired</span>'
            )
        return format_html(
            '<span style="color: green; font-weight: bold;">✅ Valid</span>'
        )
    is_expired_badge.short_description = 'Expired'
    
    def terminate_sessions(self, request, queryset):
        terminated = queryset.update(is_active=False)
        self.message_user(request, f'{terminated} sessions were terminated.')
    terminate_sessions.short_description = "🚫 Terminate selected sessions"
    
    def has_add_permission(self, request):
        return False
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('user')
        return qs


# Unregister default Group admin if not needed
# admin.site.unregister(Group)

# Custom admin site header and title
admin.site.site_header = "PesaFlow Administration"
admin.site.site_title = "PesaFlow Admin Portal"
admin.site.index_title = "Welcome to PesaFlow Admin Portal"