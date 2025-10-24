"""
Authentication Logging System
Provides comprehensive logging for authentication events including
login, logout, registration, and security events.
"""

import logging
from django.utils import timezone
from django.contrib.auth.models import User
from .models import UserAuditLog, SecurityLog
from typing import Optional, Dict, Any

# Configure logger
logger = logging.getLogger('meat_trace.auth')


class AuthLogger:
    """
    Centralized authentication logging service
    Logs authentication events to both Django logging and database
    """
    
    @staticmethod
    def _get_client_ip(request) -> Optional[str]:
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def _get_user_agent(request) -> str:
        """Extract user agent from request"""
        return request.META.get('HTTP_USER_AGENT', '')
    
    @staticmethod
    def log_login_success(user: User, request, **kwargs):
        """
        Log successful login attempt
        
        Args:
            user: The user who logged in
            request: The HTTP request object
            **kwargs: Additional metadata
        """
        ip_address = AuthLogger._get_client_ip(request)
        user_agent = AuthLogger._get_user_agent(request)
        
        # Log to Django logger
        logger.info(
            f"LOGIN_SUCCESS: User '{user.username}' (ID: {user.id}) logged in successfully "
            f"from IP {ip_address}"
        )
        
        # Log to database - UserAuditLog
        try:
            UserAuditLog.objects.create(
                performed_by=user,
                affected_user=user,
                action='user_login',
                description=f"User {user.username} logged in successfully",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    'success': True,
                    'timestamp': timezone.now().isoformat(),
                    **kwargs
                }
            )
        except Exception as e:
            logger.error(f"Failed to create UserAuditLog for login: {e}")
        
        # Log to database - SecurityLog
        try:
            SecurityLog.objects.create(
                user=user,
                event_type='login',
                severity='low',
                description=f"Successful login for user {user.username}",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    'success': True,
                    'username': user.username,
                    **kwargs
                }
            )
        except Exception as e:
            logger.error(f"Failed to create SecurityLog for login: {e}")
    
    @staticmethod
    def log_login_failure(username: str, request, reason: str = "Invalid credentials", **kwargs):
        """
        Log failed login attempt
        
        Args:
            username: The username that was attempted
            request: The HTTP request object
            reason: Reason for failure
            **kwargs: Additional metadata
        """
        ip_address = AuthLogger._get_client_ip(request)
        user_agent = AuthLogger._get_user_agent(request)
        
        # Log to Django logger
        logger.warning(
            f"LOGIN_FAILURE: Failed login attempt for username '{username}' "
            f"from IP {ip_address}. Reason: {reason}"
        )
        
        # Try to find user for database logging
        try:
            user = User.objects.filter(username=username).first()
        except Exception:
            user = None
        
        # Log to database - SecurityLog
        try:
            SecurityLog.objects.create(
                user=user,
                event_type='failed_login',
                severity='medium',
                description=f"Failed login attempt for username '{username}'. Reason: {reason}",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    'success': False,
                    'username': username,
                    'reason': reason,
                    **kwargs
                }
            )
        except Exception as e:
            logger.error(f"Failed to create SecurityLog for failed login: {e}")
    
    @staticmethod
    def log_logout(user: User, request, **kwargs):
        """
        Log user logout
        
        Args:
            user: The user who logged out
            request: The HTTP request object
            **kwargs: Additional metadata
        """
        ip_address = AuthLogger._get_client_ip(request)
        user_agent = AuthLogger._get_user_agent(request)
        
        # Log to Django logger
        logger.info(
            f"LOGOUT: User '{user.username}' (ID: {user.id}) logged out "
            f"from IP {ip_address}"
        )
        
        # Log to database - UserAuditLog
        try:
            UserAuditLog.objects.create(
                performed_by=user,
                affected_user=user,
                action='user_logout',
                description=f"User {user.username} logged out",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    'timestamp': timezone.now().isoformat(),
                    **kwargs
                }
            )
        except Exception as e:
            logger.error(f"Failed to create UserAuditLog for logout: {e}")
        
        # Log to database - SecurityLog
        try:
            SecurityLog.objects.create(
                user=user,
                event_type='logout',
                severity='low',
                description=f"User {user.username} logged out",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    'username': user.username,
                    **kwargs
                }
            )
        except Exception as e:
            logger.error(f"Failed to create SecurityLog for logout: {e}")
    
    @staticmethod
    def log_registration_success(user: User, request, role: str, **kwargs):
        """
        Log successful user registration
        
        Args:
            user: The newly created user
            request: The HTTP request object
            role: The role assigned to the user
            **kwargs: Additional metadata
        """
        ip_address = AuthLogger._get_client_ip(request)
        user_agent = AuthLogger._get_user_agent(request)
        
        # Log to Django logger
        logger.info(
            f"REGISTRATION_SUCCESS: New user '{user.username}' (ID: {user.id}) "
            f"registered with role '{role}' from IP {ip_address}"
        )
        
        # Log to database - UserAuditLog
        try:
            UserAuditLog.objects.create(
                performed_by=user,
                affected_user=user,
                action='user_joined',
                description=f"New user {user.username} registered with role {role}",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    'success': True,
                    'role': role,
                    'email': user.email,
                    'timestamp': timezone.now().isoformat(),
                    **kwargs
                }
            )
        except Exception as e:
            logger.error(f"Failed to create UserAuditLog for registration: {e}")
        
        # Log to database - SecurityLog
        try:
            SecurityLog.objects.create(
                user=user,
                event_type='login',  # First login after registration
                severity='low',
                description=f"New user {user.username} registered and logged in",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    'success': True,
                    'registration': True,
                    'role': role,
                    'username': user.username,
                    'email': user.email,
                    **kwargs
                }
            )
        except Exception as e:
            logger.error(f"Failed to create SecurityLog for registration: {e}")
    
    @staticmethod
    def log_registration_failure(username: str, email: str, request, reason: str, **kwargs):
        """
        Log failed registration attempt
        
        Args:
            username: The attempted username
            email: The attempted email
            request: The HTTP request object
            reason: Reason for failure
            **kwargs: Additional metadata
        """
        ip_address = AuthLogger._get_client_ip(request)
        user_agent = AuthLogger._get_user_agent(request)
        
        # Log to Django logger
        logger.warning(
            f"REGISTRATION_FAILURE: Failed registration attempt for username '{username}', "
            f"email '{email}' from IP {ip_address}. Reason: {reason}"
        )
        
        # Log to database - SecurityLog
        try:
            SecurityLog.objects.create(
                user=None,
                event_type='suspicious_activity',
                severity='medium',
                description=f"Failed registration attempt. Reason: {reason}",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    'success': False,
                    'username': username,
                    'email': email,
                    'reason': reason,
                    **kwargs
                }
            )
        except Exception as e:
            logger.error(f"Failed to create SecurityLog for failed registration: {e}")
    
    @staticmethod
    def log_password_change(user: User, request, **kwargs):
        """
        Log password change event
        
        Args:
            user: The user who changed their password
            request: The HTTP request object
            **kwargs: Additional metadata
        """
        ip_address = AuthLogger._get_client_ip(request)
        user_agent = AuthLogger._get_user_agent(request)
        
        # Log to Django logger
        logger.info(
            f"PASSWORD_CHANGE: User '{user.username}' (ID: {user.id}) "
            f"changed password from IP {ip_address}"
        )
        
        # Log to database - UserAuditLog
        try:
            UserAuditLog.objects.create(
                performed_by=user,
                affected_user=user,
                action='password_changed',
                description=f"User {user.username} changed their password",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    'timestamp': timezone.now().isoformat(),
                    **kwargs
                }
            )
        except Exception as e:
            logger.error(f"Failed to create UserAuditLog for password change: {e}")
        
        # Log to database - SecurityLog
        try:
            SecurityLog.objects.create(
                user=user,
                event_type='password_change',
                severity='medium',
                description=f"User {user.username} changed their password",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    'username': user.username,
                    **kwargs
                }
            )
        except Exception as e:
            logger.error(f"Failed to create SecurityLog for password change: {e}")
    
    @staticmethod
    def log_suspicious_activity(request, description: str, severity: str = 'high', **kwargs):
        """
        Log suspicious activity
        
        Args:
            request: The HTTP request object
            description: Description of the suspicious activity
            severity: Severity level (low, medium, high, critical)
            **kwargs: Additional metadata
        """
        ip_address = AuthLogger._get_client_ip(request)
        user_agent = AuthLogger._get_user_agent(request)
        
        # Log to Django logger
        logger.warning(
            f"SUSPICIOUS_ACTIVITY: {description} from IP {ip_address}"
        )
        
        # Try to get user from request
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            user_obj = user
        else:
            user_obj = None
        
        # Log to database - SecurityLog
        try:
            SecurityLog.objects.create(
                user=user_obj,
                event_type='suspicious_activity',
                severity=severity,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=kwargs
            )
        except Exception as e:
            logger.error(f"Failed to create SecurityLog for suspicious activity: {e}")
    
    @staticmethod
    def log_session_expired(user: User, **kwargs):
        """
        Log session expiration
        
        Args:
            user: The user whose session expired
            **kwargs: Additional metadata
        """
        # Log to Django logger
        logger.info(
            f"SESSION_EXPIRED: Session expired for user '{user.username}' (ID: {user.id})"
        )
        
        # Log to database - SecurityLog
        try:
            SecurityLog.objects.create(
                user=user,
                event_type='logout',
                severity='low',
                description=f"Session expired for user {user.username}",
                metadata={
                    'reason': 'session_expired',
                    'username': user.username,
                    **kwargs
                }
            )
        except Exception as e:
            logger.error(f"Failed to create SecurityLog for session expiration: {e}")


# Convenience functions for common operations
def log_login_success(user: User, request, **kwargs):
    """Convenience function to log successful login"""
    AuthLogger.log_login_success(user, request, **kwargs)


def log_login_failure(username: str, request, reason: str = "Invalid credentials", **kwargs):
    """Convenience function to log failed login"""
    AuthLogger.log_login_failure(username, request, reason, **kwargs)


def log_logout(user: User, request, **kwargs):
    """Convenience function to log logout"""
    AuthLogger.log_logout(user, request, **kwargs)


def log_registration_success(user: User, request, role: str, **kwargs):
    """Convenience function to log successful registration"""
    AuthLogger.log_registration_success(user, request, role, **kwargs)


def log_registration_failure(username: str, email: str, request, reason: str, **kwargs):
    """Convenience function to log failed registration"""
    AuthLogger.log_registration_failure(username, email, request, reason, **kwargs)


def log_password_change(user: User, request, **kwargs):
    """Convenience function to log password change"""
    AuthLogger.log_password_change(user, request, **kwargs)


def log_suspicious_activity(request, description: str, severity: str = 'high', **kwargs):
    """Convenience function to log suspicious activity"""
    AuthLogger.log_suspicious_activity(request, description, severity, **kwargs)


def log_session_expired(user: User, **kwargs):
    """Convenience function to log session expiration"""
    AuthLogger.log_session_expired(user, **kwargs)