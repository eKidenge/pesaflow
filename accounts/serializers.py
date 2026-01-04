from rest_framework import serializers
from django.contrib.auth import authenticate
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from .models import (
    User, 
    UserProfile, 
    Organization,
    LoginHistory,
    VerificationCode,
    UserSession
)


# ==============================================
# ORGANIZATION SERIALIZERS
# ==============================================

class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for Organization model"""
    
    total_users = serializers.IntegerField(read_only=True)
    active_users = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'email', 'phone', 'country', 'address',
            'registration_number', 'business_type', 'is_verified',
            'verification_document', 'currency', 'timezone',
            'settings', 'metadata', 'total_users', 'active_users',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'is_verified', 'total_users', 'active_users',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'phone': {'required': True},
            'name': {'required': True}
        }
    
    def validate_email(self, value):
        """Validate organization email"""
        if self.instance and Organization.objects.filter(email=value).exclude(id=self.instance.id).exists():
            raise serializers.ValidationError('An organization with this email already exists.')
        elif not self.instance and Organization.objects.filter(email=value).exists():
            raise serializers.ValidationError('An organization with this email already exists.')
        return value


# ==============================================
# USER PROFILE SERIALIZERS
# ==============================================

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model"""
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'national_id', 'date_of_birth', 'gender',
            'address', 'city', 'country', 'designation', 'department',
            'bio', 'emergency_contact_name', 'emergency_contact_phone',
            'website', 'twitter', 'linkedin', 'timezone', 'language',
            'currency', 'email_notifications', 'sms_notifications',
            'push_notifications', 'marketing_emails', 'preferences',
            'metadata', 'login_attempts', 'last_login_attempt',
            'account_locked', 'account_locked_until',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'login_attempts', 'last_login_attempt',
            'account_locked', 'account_locked_until',
            'created_at', 'updated_at'
        ]


# ==============================================
# USER SERIALIZERS
# ==============================================

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model - INTEGRATED WITH TEMPLATES"""
    
    profile = UserProfileSerializer(read_only=True)
    organization_detail = OrganizationSerializer(source='organization', read_only=True)
    template_role = serializers.CharField(read_only=True)
    dashboard_url = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            # Basic information
            'id', 'email', 'first_name', 'last_name', 'phone',
            'full_name', 'profile_picture',
            
            # Role and type
            'user_type', 'template_role', 'is_system_admin',
            'is_business_owner', 'is_business_staff', 'is_client',
            
            # Organization
            'organization', 'organization_detail',
            'position', 'department',
            
            # Address
            'address', 'city', 'country', 'id_number',
            
            # Verification
            'email_verified', 'phone_verified',
            'verification_code', 'verification_code_expiry',
            
            # Preferences
            'receive_email_notifications', 'receive_sms_notifications',
            'two_factor_enabled',
            
            # Profile
            'profile',
            
            # System fields
            'is_active', 'is_staff', 'is_superuser',
            'last_login', 'date_joined', 'date_of_birth',
            
            # Dashboard and redirect
            'dashboard_url', 'get_dashboard_url',
            
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'email_verified', 'phone_verified', 'is_staff',
            'is_superuser', 'last_login', 'date_joined',
            'verification_code', 'verification_code_expiry',
            'template_role', 'dashboard_url', 'get_dashboard_url',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'password': {'write_only': True, 'min_length': 8}
        }
    
    def to_representation(self, instance):
        """Custom representation to include computed properties"""
        representation = super().to_representation(instance)
        
        # Add template role mapping
        representation['template_role'] = instance.template_role
        
        # Add dashboard URL
        representation['dashboard_url'] = instance.get_dashboard_url()
        
        # Add computed properties
        representation['is_system_admin'] = instance.is_system_admin
        representation['is_business_owner'] = instance.is_business_owner
        representation['is_business_staff'] = instance.is_business_staff
        representation['is_client'] = instance.is_client
        
        # Remove sensitive fields
        if 'verification_code' in representation:
            representation.pop('verification_code')
        if 'verification_code_expiry' in representation:
            representation.pop('verification_code_expiry')
        
        return representation


# ==============================================
# REGISTRATION SERIALIZERS - FOR TEMPLATE INTEGRATION
# ==============================================

class BaseRegistrationSerializer(serializers.ModelSerializer):
    """Base registration serializer with common fields"""
    
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        min_length=8,
        style={'input_type': 'password'},
        help_text="Minimum 8 characters with letters and numbers"
    )
    confirm_password = serializers.CharField(
        write_only=True, 
        required=True,
        style={'input_type': 'password'}
    )
    phone = serializers.CharField(required=True) 
    # country = serializers.CharField(required=True, default='Kenya')      Open accounts/serializers.py and change this line:
    country = serializers.CharField(default='Kenya')

    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'phone',
            'country', 'password', 'confirm_password'
        ]
    
    def validate_email(self, value):
        """Validate email"""
        try:
            validate_email(value)
        except ValidationError:
            raise serializers.ValidationError('Enter a valid email address.')
        
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        
        return value
    
    def validate_password(self, value):
        """Validate password strength"""
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, data):
        """Validate registration data"""
        # Check if passwords match
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })
        
        # Check if phone number already exists
        if User.objects.filter(phone=data['phone']).exists():
            raise serializers.ValidationError({
                'phone': 'A user with this phone number already exists.'
            })
        
        return data
    
    def create(self, validated_data):
        """Create user - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement create method")


class AdminRegistrationSerializer(BaseRegistrationSerializer):
    """Serializer for admin registration - FROM TEMPLATE"""
    
    admin_key = serializers.CharField(
        write_only=True, 
        required=False,
        help_text="Admin authorization key (optional)"
    )
    
    class Meta(BaseRegistrationSerializer.Meta):
        fields = BaseRegistrationSerializer.Meta.fields + ['admin_key']
    
    def create(self, validated_data):
        """Create admin user"""
        admin_key = validated_data.pop('admin_key', None)
        confirm_password = validated_data.pop('confirm_password')
        
        # In production, validate admin_key against a secret
        # For demo, we'll accept any admin_key or none
        
        # Create user
        user = User.objects.create_superuser(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone=validated_data['phone'],
            user_type='system_admin',
            country=validated_data.get('country', 'Kenya')
        )
        
        return user


class BusinessRegistrationSerializer(BaseRegistrationSerializer):
    """Serializer for business registration - FROM TEMPLATE"""
    
    business_name = serializers.CharField(required=True)
    business_type = serializers.CharField(required=True)
    business_address = serializers.CharField(required=False, allow_blank=True)
    
    class Meta(BaseRegistrationSerializer.Meta):
        fields = BaseRegistrationSerializer.Meta.fields + [
            'business_name', 'business_type', 'business_address'
        ]
    
    def create(self, validated_data):
        """Create business user with organization"""
        business_name = validated_data.pop('business_name')
        business_type = validated_data.pop('business_type')
        business_address = validated_data.pop('business_address', '')
        confirm_password = validated_data.pop('confirm_password')
        
        # Create organization first
        organization = Organization.objects.create(
            name=business_name,
            email=validated_data['email'],
            phone=validated_data['phone'],
            country=validated_data.get('country', 'Kenya'),
            business_type=business_type,
            address=business_address
        )
        
        # Create business owner user
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone=validated_data['phone'],
            user_type='business_owner',
            country=validated_data.get('country', 'Kenya'),
            organization=organization
        )
        
        return user


class ClientRegistrationSerializer(BaseRegistrationSerializer):
    """Serializer for client registration - FROM TEMPLATE"""
    
    id_number = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    
    class Meta(BaseRegistrationSerializer.Meta):
        fields = BaseRegistrationSerializer.Meta.fields + ['id_number', 'address']
    
    def create(self, validated_data):
        """Create client user"""
        id_number = validated_data.pop('id_number', '')
        address = validated_data.pop('address', '')
        confirm_password = validated_data.pop('confirm_password')
        
        # Create client user
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone=validated_data['phone'],
            user_type='client',
            country=validated_data.get('country', 'Kenya'),
            id_number=id_number,
            address=address
        )
        
        return user


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Generic user registration serializer for API"""
    
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=True)
    role = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'phone',
            'password', 'confirm_password', 'role',
            'country', 'id_number', 'address'
        ]
        extra_kwargs = {
            'id_number': {'required': False},
            'address': {'required': False}
        }
    
    def validate(self, data):
        """Validate registration data"""
        # Password validation
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        
        # Email validation
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({'email': 'Email already registered.'})
        
        # Phone validation
        if data.get('phone') and User.objects.filter(phone=data['phone']).exists():
            raise serializers.ValidationError({'phone': 'Phone number already registered.'})
        
        # Role validation
        valid_roles = ['admin', 'business', 'client']
        if data['role'] not in valid_roles:
            raise serializers.ValidationError({'role': f'Role must be one of: {", ".join(valid_roles)}'})
        
        return data
    
    def create(self, validated_data):
        """Create user based on role"""
        role = validated_data.pop('role')
        confirm_password = validated_data.pop('confirm_password')
        
        # Map role to user_type
        role_mapping = {
            'admin': 'system_admin',
            'business': 'business_owner',
            'client': 'client'
        }
        
        # Extract user data
        user_data = {
            'email': validated_data['email'],
            'password': validated_data['password'],
            'first_name': validated_data['first_name'],
            'last_name': validated_data['last_name'],
            'phone': validated_data.get('phone', ''),
            'user_type': role_mapping[role],
            'country': validated_data.get('country', 'Kenya'),
        }
        
        # Add client-specific fields
        if role == 'client':
            user_data['id_number'] = validated_data.get('id_number', '')
            user_data['address'] = validated_data.get('address', '')
        
        # Create user
        user = User.objects.create_user(**user_data)
        
        return user


# ==============================================
# AUTHENTICATION SERIALIZERS
# ==============================================

class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login - INTEGRATED WITH TEMPLATE"""
    
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    role = serializers.CharField(required=False, default='business')
    remember_me = serializers.BooleanField(default=False, required=False)
    
    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'business')
        
        # Try to authenticate with email or username
        user = None
        
        # Check if input is email
        try:
            validate_email(username)
            # It's an email
            user = authenticate(username=username, password=password)
        except ValidationError:
            # It's a username (though we use email as username)
            user = authenticate(username=username, password=password)
        
        if not user:
            raise serializers.ValidationError('Invalid username or password.')
        
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled.')
        
        # Check role compatibility
        role_mapping = {
            'admin': 'system_admin',
            'business': ['business_owner', 'business_staff'],
            'client': 'client'
        }
        
        expected_types = role_mapping.get(role, [])
        
        if isinstance(expected_types, str):
            expected_types = [expected_types]
        
        if user.user_type not in expected_types:
            raise serializers.ValidationError(
                f'Invalid role selection. This account is a {user.get_user_type_display()}.'
            )
        
        data['user'] = user
        return data


# ==============================================
# PASSWORD MANAGEMENT SERIALIZERS
# ==============================================

class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password"""
    
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=True)
    
    def validate(self, data):
        # Check if passwords match
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'New passwords do not match.'
            })
        
        # Check if new password is different from old
        if data['old_password'] == data['new_password']:
            raise serializers.ValidationError({
                'new_password': 'New password must be different from old password.'
            })
        
        # Validate password strength
        try:
            validate_password(data['new_password'])
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': list(e.messages)})
        
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        # Don't reveal if email exists (security)
        try:
            validate_email(value)
        except ValidationError:
            raise serializers.ValidationError('Enter a valid email address.')
        
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""
    
    token = serializers.CharField(required=True)
    uid = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=True)
    
    def validate(self, data):
        # Check if passwords match
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })
        
        # Validate password strength
        try:
            validate_password(data['new_password'])
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': list(e.messages)})
        
        return data


# ==============================================
# VERIFICATION SERIALIZERS
# ==============================================

class VerificationRequestSerializer(serializers.Serializer):
    """Serializer for requesting verification"""
    
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False)
    
    def validate(self, data):
        if not data.get('email') and not data.get('phone'):
            raise serializers.ValidationError('Either email or phone must be provided.')
        return data


class VerifyCodeSerializer(serializers.Serializer):
    """Serializer for verifying code"""
    
    code = serializers.CharField(required=True, max_length=6)
    purpose = serializers.ChoiceField(
        choices=[
            ('email_verification', 'Email Verification'),
            ('phone_verification', 'Phone Verification'),
            ('password_reset', 'Password Reset')
        ],
        required=True
    )


# ==============================================
# UPDATE SERIALIZERS
# ==============================================

class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone', 'profile_picture',
            'address', 'city', 'country', 'date_of_birth',
            'receive_email_notifications', 'receive_sms_notifications',
            'two_factor_enabled'
        ]
    
    def validate_phone(self, value):
        user = self.context['request'].user
        
        if value and value != user.phone:
            if User.objects.filter(phone=value).exclude(id=user.id).exists():
                raise serializers.ValidationError('This phone number is already registered.')
        
        return value


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile details"""
    
    class Meta:
        model = UserProfile
        fields = [
            'national_id', 'gender', 'bio', 'website',
            'twitter', 'linkedin', 'timezone', 'language',
            'currency', 'email_notifications', 'sms_notifications',
            'push_notifications', 'marketing_emails'
        ]


# ==============================================
# HISTORY AND SESSION SERIALIZERS
# ==============================================

class LoginHistorySerializer(serializers.ModelSerializer):
    """Serializer for login history"""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = LoginHistory
        fields = [
            'id', 'user_email', 'ip_address', 'user_agent',
            'location', 'device_type', 'browser', 'os',
            'success', 'failure_reason', 'login_time',
            'logout_time', 'session_duration'
        ]
        read_only_fields = fields


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer for user sessions"""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = UserSession
        fields = [
            'id', 'user_email', 'session_key', 'ip_address',
            'user_agent', 'location', 'is_active', 'is_mobile',
            'created_at', 'last_activity', 'expires_at'
        ]
        read_only_fields = fields


# ==============================================
# DASHBOARD SERIALIZERS
# ==============================================

class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""
    
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    new_users_today = serializers.IntegerField()
    verified_emails = serializers.IntegerField()
    verified_phones = serializers.IntegerField()
    by_user_type = serializers.DictField(child=serializers.IntegerField())


class BusinessDashboardSerializer(serializers.Serializer):
    """Serializer for business dashboard"""
    
    organization = OrganizationSerializer()
    total_staff = serializers.IntegerField()
    active_staff = serializers.IntegerField()
    recent_activity = LoginHistorySerializer(many=True)
    upcoming_payments = serializers.ListField(child=serializers.DictField())


# ==============================================
# UTILITY SERIALIZERS
# ==============================================

class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification"""
    
    email = serializers.EmailField(required=True)


class PhoneVerificationSerializer(serializers.Serializer):
    """Serializer for phone verification"""
    
    phone = serializers.CharField(required=True)


class SimpleResponseSerializer(serializers.Serializer):
    """Simple response serializer"""
    
    message = serializers.CharField()
    status = serializers.CharField()
    data = serializers.DictField(required=False)