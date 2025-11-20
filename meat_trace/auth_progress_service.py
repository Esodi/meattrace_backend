"""
Service for sending real-time authentication progress updates via WebSocket.
Provides user-friendly status messages during login and signup processes.
"""

import json
from datetime import datetime
from asgiref.sync import async_to_sync

try:
    from channels.layers import get_channel_layer
    CHANNELS_AVAILABLE = True
except ImportError:
    CHANNELS_AVAILABLE = False
    get_channel_layer = None


class AuthProgressService:
    """
    Service to send authentication progress updates to clients via WebSocket.
    """
    
    @staticmethod
    def _send_to_channel(session_id, event_type, data):
        """Send message to a specific auth session channel"""
        if not CHANNELS_AVAILABLE or not get_channel_layer:
            return  # Silently fail if channels not available
        
        try:
            channel_layer = get_channel_layer()
            group_name = f'auth_progress_{session_id}'
            
            # Add timestamp
            data['timestamp'] = datetime.now().isoformat()
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': event_type,
                    'data': data
                }
            )
        except Exception as e:
            # Log error but don't break the auth flow
            print(f"Warning: Failed to send auth progress update: {e}")
    
    @staticmethod
    def send_progress(session_id, step, message, status='info', details=None):
        """
        Send a progress update to the client.
        
        Args:
            session_id: Unique session identifier
            step: The current step in the auth process (e.g., 'validating', 'creating_user')
            message: User-friendly message to display
            status: 'info', 'success', 'warning', or 'error'
            details: Optional dict with additional information
        """
        AuthProgressService._send_to_channel(
            session_id,
            'auth_progress',
            {
                'step': step,
                'message': message,
                'status': status,
                'details': details or {}
            }
        )
    
    @staticmethod
    def send_complete(session_id, success, message, user_data=None):
        """
        Send authentication completion notification.
        
        Args:
            session_id: Unique session identifier
            success: Boolean indicating if auth was successful
            message: Final message to display
            user_data: Optional dict with user information (sanitized)
        """
        AuthProgressService._send_to_channel(
            session_id,
            'auth_complete',
            {
                'success': success,
                'message': message,
                'user': user_data or {}
            }
        )
    
    @staticmethod
    def send_error(session_id, message, code='unknown'):
        """
        Send authentication error notification.
        
        Args:
            session_id: Unique session identifier
            message: User-friendly error message
            code: Error code for client-side handling
        """
        AuthProgressService._send_to_channel(
            session_id,
            'auth_error',
            {
                'message': message,
                'code': code
            }
        )
    
    # Pre-defined messages for common auth steps
    
    @staticmethod
    def login_started(session_id, username):
        """Notify that login process has started"""
        AuthProgressService.send_progress(
            session_id,
            'started',
            f'Authenticating user {username}...',
            'info'
        )
    
    @staticmethod
    def login_validating_credentials(session_id):
        """Notify that credentials are being validated"""
        AuthProgressService.send_progress(
            session_id,
            'validating',
            'Verifying your credentials...',
            'info'
        )
    
    @staticmethod
    def login_checking_account(session_id):
        """Notify that account status is being checked"""
        AuthProgressService.send_progress(
            session_id,
            'checking_account',
            'Checking account status...',
            'info'
        )
    
    @staticmethod
    def login_loading_profile(session_id):
        """Notify that user profile is being loaded"""
        AuthProgressService.send_progress(
            session_id,
            'loading_profile',
            'Loading your profile...',
            'info'
        )
    
    @staticmethod
    def login_generating_tokens(session_id):
        """Notify that authentication tokens are being generated"""
        AuthProgressService.send_progress(
            session_id,
            'generating_tokens',
            'Generating secure session...',
            'info'
        )
    
    @staticmethod
    def login_success(session_id, username, role):
        """Notify successful login"""
        AuthProgressService.send_complete(
            session_id,
            True,
            f'Welcome back! Redirecting to your {role} dashboard...',
            {'username': username, 'role': role}
        )
    
    @staticmethod
    def login_failed_invalid_credentials(session_id):
        """Notify login failed due to invalid credentials"""
        AuthProgressService.send_error(
            session_id,
            'Invalid username or password. Please check your credentials and try again.',
            'invalid_credentials'
        )
    
    @staticmethod
    def login_failed_account_disabled(session_id):
        """Notify login failed due to disabled account"""
        AuthProgressService.send_error(
            session_id,
            'Your account has been disabled. Please contact support for assistance.',
            'account_disabled'
        )
    
    @staticmethod
    def login_failed_network_error(session_id):
        """Notify login failed due to network error"""
        AuthProgressService.send_error(
            session_id,
            'Unable to connect to the server. Please check your internet connection.',
            'network_error'
        )
    
    # Signup flow messages
    
    @staticmethod
    def signup_started(session_id, username):
        """Notify that signup process has started"""
        AuthProgressService.send_progress(
            session_id,
            'started',
            f'Creating account for {username}...',
            'info'
        )
    
    @staticmethod
    def signup_validating_data(session_id):
        """Notify that registration data is being validated"""
        AuthProgressService.send_progress(
            session_id,
            'validating',
            'Validating registration information...',
            'info'
        )
    
    @staticmethod
    def signup_checking_availability(session_id):
        """Notify that username/email availability is being checked"""
        AuthProgressService.send_progress(
            session_id,
            'checking_availability',
            'Checking username and email availability...',
            'info'
        )
    
    @staticmethod
    def signup_creating_account(session_id):
        """Notify that user account is being created"""
        AuthProgressService.send_progress(
            session_id,
            'creating_account',
            'Creating your account...',
            'info'
        )
    
    @staticmethod
    def signup_creating_profile(session_id, role):
        """Notify that user profile is being created"""
        AuthProgressService.send_progress(
            session_id,
            'creating_profile',
            f'Setting up your {role} profile...',
            'info'
        )
    
    @staticmethod
    def signup_configuring_permissions(session_id):
        """Notify that permissions are being configured"""
        AuthProgressService.send_progress(
            session_id,
            'configuring_permissions',
            'Configuring access permissions...',
            'info'
        )
    
    @staticmethod
    def signup_finalizing(session_id):
        """Notify that signup is being finalized"""
        AuthProgressService.send_progress(
            session_id,
            'finalizing',
            'Finalizing registration...',
            'info'
        )
    
    @staticmethod
    def signup_success(session_id, username, role):
        """Notify successful signup"""
        AuthProgressService.send_complete(
            session_id,
            True,
            f'Account created successfully! Welcome to MeatTrace Pro, {username}!',
            {'username': username, 'role': role}
        )
    
    @staticmethod
    def signup_failed_username_exists(session_id):
        """Notify signup failed due to existing username"""
        AuthProgressService.send_error(
            session_id,
            'This username is already taken. Please choose a different username.',
            'username_exists'
        )
    
    @staticmethod
    def signup_failed_email_exists(session_id):
        """Notify signup failed due to existing email"""
        AuthProgressService.send_error(
            session_id,
            'This email address is already registered. Please use a different email or try logging in.',
            'email_exists'
        )
    
    @staticmethod
    def signup_failed_validation(session_id, field):
        """Notify signup failed due to validation error"""
        AuthProgressService.send_error(
            session_id,
            f'Invalid {field}. Please check your information and try again.',
            'validation_error'
        )
