from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count
from .models import Customer, CustomerGroup


class PaymentInline(admin.TabularInline):
    """Inline admin for Payment"""
    model = 'payments.Payment'
    extra = 0
    readonly_fields = ['payment_reference', 'amount', 'status', 'created_at']
    fields = ['payment_reference', 'amount', 'status', 'created_at']
    can_delete = False
    max_num = 10
    
    def has_add_permission(self, request, obj):
        return False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Admin configuration for Customer model"""
    
    list_display = [
        'customer_code', 'full_name', 'phone_number', 'organization',
        'customer_type', 'status', 'account_balance', 'last_payment_date',
        'created_at', 'payment_count', 'total_paid'
    ]
    
    list_filter = [
        'status', 'customer_type', 'organization', 'gender',
        'receive_sms', 'receive_email', 'receive_whatsapp',
        'created_at', 'last_payment_date'
    ]
    
    search_fields = [
        'customer_code', 'first_name', 'last_name', 'middle_name',
        'phone_number', 'email', 'national_id', 'registration_number',
        'organization__name'
    ]
    
    readonly_fields = [
        'customer_code', 'created_at', 'updated_at', 'last_payment_date',
        'payment_count', 'total_paid', 'groups_list'
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'customer_code', 'organization', 'first_name', 'middle_name',
                'last_name', 'gender', 'date_of_birth', 'nationality'
            )
        }),
        (_('Contact Information'), {
            'fields': (
                'email', 'phone_number', 'alternate_phone', 'address',
                'city', 'county', 'postal_code'
            )
        }),
        (_('Identification'), {
            'fields': ('national_id', 'passport_number'),
            'classes': ('collapse',)
        }),
        (_('Customer Details'), {
            'fields': (
                'customer_type', 'registration_number', 'account_balance',
                'credit_limit', 'discount_rate', 'status', 'tags'
            )
        }),
        (_('Guardian/Next of Kin'), {
            'fields': (
                'guardian_name', 'guardian_phone', 'guardian_relationship'
            ),
            'classes': ('collapse',)
        }),
        (_('Employment/Education'), {
            'fields': (
                'employer_name', 'employer_address', 'school_name',
                'course', 'year_of_study'
            ),
            'classes': ('collapse',)
        }),
        (_('Communication Preferences'), {
            'fields': (
                'receive_sms', 'receive_email', 'receive_whatsapp',
                'preferred_language'
            )
        }),
        (_('Groups'), {
            'fields': ('groups_list',),
            'classes': ('collapse',)
        }),
        (_('Custom Fields & Notes'), {
            'fields': ('custom_fields', 'notes'),
            'classes': ('collapse',)
        }),
        (_('Statistics'), {
            'fields': ('payment_count', 'total_paid', 'last_payment_date'),
            'classes': ('collapse',)
        }),
        (_('Audit'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ['organization', 'created_by']
    filter_horizontal = ['groups']
    
    inlines = [PaymentInline]
    
    actions = [
        'activate_customers', 'deactivate_customers',
        'export_selected_customers', 'add_to_group', 'remove_from_group',
        'send_bulk_sms', 'send_bulk_email'
    ]
    
    def full_name(self, obj):
        """Display full name"""
        names = [obj.first_name]
        if obj.middle_name:
            names.append(obj.middle_name)
        names.append(obj.last_name)
        return ' '.join(names)
    full_name.short_description = 'Full Name'
    full_name.admin_order_field = 'first_name'
    
    def payment_count(self, obj):
        """Display payment count"""
        return obj.payments.count()
    payment_count.short_description = 'Payments'
    
    def total_paid(self, obj):
        """Display total amount paid"""
        from django.db.models import Sum
        total = obj.payments.filter(status='completed').aggregate(
            total=Sum('amount')
        )['total']
        return f"KES {total or 0:,.2f}"
    total_paid.short_description = 'Total Paid'
    
    def groups_list(self, obj):
        """Display groups as links"""
        groups = obj.groups.all()
        if not groups:
            return "No groups"
        
        links = []
        for group in groups:
            url = reverse('admin:customers_customergroup_change', args=[group.id])
            links.append(f'<a href="{url}">{group.name}</a>')
        
        return format_html(', '.join(links))
    groups_list.short_description = 'Groups'
    
    def activate_customers(self, request, queryset):
        """Activate selected customers"""
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} customers were activated.')
    activate_customers.short_description = "Activate selected customers"
    
    def deactivate_customers(self, request, queryset):
        """Deactivate selected customers"""
        updated = queryset.update(status='inactive')
        self.message_user(request, f'{updated} customers were deactivated.')
    deactivate_customers.short_description = "Deactivate selected customers"
    
    def export_selected_customers(self, request, queryset):
        """Export selected customers to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="customers_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Customer Code', 'First Name', 'Last Name', 'Email',
            'Phone Number', 'Customer Type', 'Status', 'Account Balance',
            'Created At', 'Organization'
        ])
        
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
                customer.organization.name if customer.organization else ''
            ])
        
        return response
    export_selected_customers.short_description = "Export selected customers to CSV"
    
    def add_to_group(self, request, queryset):
        """Add selected customers to a group"""
        from django import forms
        
        class GroupForm(forms.Form):
            group = forms.ModelChoiceField(
                queryset=CustomerGroup.objects.all(),
                label="Select Group"
            )
        
        if 'apply' in request.POST:
            form = GroupForm(request.POST)
            if form.is_valid():
                group = form.cleaned_data['group']
                for customer in queryset:
                    customer.groups.add(group)
                
                self.message_user(
                    request,
                    f'{queryset.count()} customers were added to {group.name}.'
                )
                return
        else:
            form = GroupForm()
        
        return admin.helpers.action_form(
            self, request, queryset, 'add_to_group',
            'Add selected customers to group',
            form
        )
    add_to_group.short_description = "Add to group"
    
    def remove_from_group(self, request, queryset):
        """Remove selected customers from a group"""
        from django import forms
        
        class GroupForm(forms.Form):
            group = forms.ModelChoiceField(
                queryset=CustomerGroup.objects.all(),
                label="Select Group"
            )
        
        if 'apply' in request.POST:
            form = GroupForm(request.POST)
            if form.is_valid():
                group = form.cleaned_data['group']
                for customer in queryset:
                    customer.groups.remove(group)
                
                self.message_user(
                    request,
                    f'{queryset.count()} customers were removed from {group.name}.'
                )
                return
        else:
            form = GroupForm()
        
        return admin.helpers.action_form(
            self, request, queryset, 'remove_from_group',
            'Remove selected customers from group',
            form
        )
    remove_from_group.short_description = "Remove from group"
    
    def send_bulk_sms(self, request, queryset):
        """Send bulk SMS to selected customers"""
        customers_with_phone = queryset.filter(
            phone_number__isnull=False,
            receive_sms=True
        )
        
        self.message_user(
            request,
            f'Ready to send SMS to {customers_with_phone.count()} customers.'
        )
        
        # In production, this would redirect to a custom view for composing the message
    send_bulk_sms.short_description = "Send bulk SMS"
    
    def send_bulk_email(self, request, queryset):
        """Send bulk email to selected customers"""
        customers_with_email = queryset.filter(
            email__isnull=False,
            receive_email=True
        )
        
        self.message_user(
            request,
            f'Ready to send email to {customers_with_email.count()} customers.'
        )
    send_bulk_email.short_description = "Send bulk email"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('organization', 'created_by')
        qs = qs.prefetch_related('groups', 'payments')
        return qs


class CustomerInline(admin.TabularInline):
    """Inline admin for Customer in CustomerGroup"""
    model = Customer.groups.through
    extra = 1
    verbose_name = 'Customer'
    verbose_name_plural = 'Customers'
    raw_id_fields = ['customer']


@admin.register(CustomerGroup)
class CustomerGroupAdmin(admin.ModelAdmin):
    """Admin configuration for CustomerGroup model"""
    
    list_display = [
        'name', 'organization', 'group_type', 'is_active',
        'customer_count', 'default_payment_amount', 'created_at'
    ]
    
    list_filter = [
        'group_type', 'is_active', 'organization', 'created_at'
    ]
    
    search_fields = [
        'name', 'description', 'organization__name'
    ]
    
    readonly_fields = ['created_at', 'updated_at', 'customer_count']
    
    fieldsets = (
        (_('Group Information'), {
            'fields': (
                'organization', 'name', 'description', 'group_type',
                'is_active'
            )
        }),
        (_('Payment Settings'), {
            'fields': ('default_payment_amount', 'payment_frequency')
        }),
        (_('Statistics'), {
            'fields': ('customer_count',),
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
    
    filter_horizontal = ['customers']
    
    inlines = [CustomerInline]
    
    actions = ['activate_groups', 'deactivate_groups', 'send_group_notification']
    
    def customer_count(self, obj):
        """Display customer count"""
        return obj.customers.count()
    customer_count.short_description = 'Customers'
    
    def activate_groups(self, request, queryset):
        """Activate selected groups"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} groups were activated.')
    activate_groups.short_description = "Activate selected groups"
    
    def deactivate_groups(self, request, queryset):
        """Deactivate selected groups"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} groups were deactivated.')
    deactivate_groups.short_description = "Deactivate selected groups"
    
    def send_group_notification(self, request, queryset):
        """Send notification to all customers in selected groups"""
        total_customers = 0
        for group in queryset:
            total_customers += group.customers.count()
        
        self.message_user(
            request,
            f'Ready to send notification to {total_customers} customers across {queryset.count()} groups.'
        )
    send_group_notification.short_description = "Send group notification"
    
    def get_queryset(self, request):
        """Custom queryset for admin"""
        qs = super().get_queryset(request)
        qs = qs.select_related('organization')
        qs = qs.annotate(customer_count=Count('customers'))
        return qs