"""
Input validation and sanitization for JustIRC
Provides security validation for all user inputs
"""

import re
from typing import Optional, Tuple


class InputValidator:
    """Validates and sanitizes user inputs"""
    
    # Regex patterns for validation
    NICKNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{3,20}$')
    CHANNEL_PATTERN = re.compile(r'^#[a-zA-Z0-9_-]{1,50}$')
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    # Maximum lengths
    MAX_MESSAGE_LENGTH = 4096
    MAX_TOPIC_LENGTH = 256
    MAX_PASSWORD_LENGTH = 256
    MAX_REASON_LENGTH = 256
    
    @staticmethod
    def validate_nickname(nickname: str) -> Tuple[bool, Optional[str]]:
        """
        Validate nickname
        
        Args:
            nickname: Nickname to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        if not nickname:
            return (False, "Nickname cannot be empty")
        
        if len(nickname) < 3:
            return (False, "Nickname must be at least 3 characters")
        
        if len(nickname) > 20:
            return (False, "Nickname must be at most 20 characters")
        
        if not InputValidator.NICKNAME_PATTERN.match(nickname):
            return (False, "Nickname can only contain letters, numbers, _ and -")
        
        # Check for reserved names
        reserved = ['server', 'admin', 'root', 'system']
        if nickname.lower() in reserved:
            return (False, f"Nickname '{nickname}' is reserved")
        
        return (True, None)
    
    @staticmethod
    def validate_channel_name(channel: str) -> Tuple[bool, Optional[str]]:
        """
        Validate channel name
        
        Args:
            channel: Channel name to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        if not channel:
            return (False, "Channel name cannot be empty")
        
        if not channel.startswith('#'):
            return (False, "Channel name must start with #")
        
        if len(channel) < 2:
            return (False, "Channel name must be at least 2 characters (including #)")
        
        if len(channel) > 51:  # # + 50 chars
            return (False, "Channel name must be at most 50 characters (excluding #)")
        
        if not InputValidator.CHANNEL_PATTERN.match(channel):
            return (False, "Channel name can only contain letters, numbers, _ and -")
        
        return (True, None)
    
    @staticmethod
    def validate_email(email: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Validate email address
        
        Args:
            email: Email to validate (can be None)
            
        Returns:
            (is_valid, error_message) tuple
        """
        if email is None:
            return (True, None)  # Email is optional
        
        if not email:
            return (False, "Email cannot be empty string")
        
        if len(email) > 254:  # RFC 5321
            return (False, "Email address is too long")
        
        if not InputValidator.EMAIL_PATTERN.match(email):
            return (False, "Invalid email format")
        
        return (True, None)
    
    @staticmethod
    def validate_password(password: str, min_length: int = 8) -> Tuple[bool, Optional[str]]:
        """
        Validate password strength
        
        Args:
            password: Password to validate
            min_length: Minimum password length (default 8)
            
        Returns:
            (is_valid, error_message) tuple
        """
        if not password:
            return (False, "Password cannot be empty")
        
        if len(password) < min_length:
            return (False, f"Password must be at least {min_length} characters")
        
        if len(password) > InputValidator.MAX_PASSWORD_LENGTH:
            return (False, f"Password must be at most {InputValidator.MAX_PASSWORD_LENGTH} characters")
        
        return (True, None)
    
    @staticmethod
    def validate_message(message: str) -> Tuple[bool, Optional[str]]:
        """
        Validate message content
        
        Args:
            message: Message to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        if not message:
            return (False, "Message cannot be empty")
        
        if len(message) > InputValidator.MAX_MESSAGE_LENGTH:
            return (False, f"Message exceeds maximum length of {InputValidator.MAX_MESSAGE_LENGTH}")
        
        # Check for null bytes (potential injection)
        if '\x00' in message:
            return (False, "Message contains invalid characters")
        
        return (True, None)
    
    @staticmethod
    def validate_topic(topic: str) -> Tuple[bool, Optional[str]]:
        """
        Validate channel topic
        
        Args:
            topic: Topic to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        if not topic:
            return (False, "Topic cannot be empty")
        
        if len(topic) > InputValidator.MAX_TOPIC_LENGTH:
            return (False, f"Topic exceeds maximum length of {InputValidator.MAX_TOPIC_LENGTH}")
        
        # Check for null bytes
        if '\x00' in topic:
            return (False, "Topic contains invalid characters")
        
        return (True, None)
    
    @staticmethod
    def sanitize_string(text: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize a string by removing control characters
        
        Args:
            text: Text to sanitize
            max_length: Optional maximum length
            
        Returns:
            Sanitized string
        """
        if not text:
            return ""
        
        # Remove null bytes and other control characters (except newlines and tabs)
        sanitized = ''.join(char for char in text 
                          if char.isprintable() or char in '\n\t')
        
        # Truncate if needed
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    @staticmethod
    def validate_user_id(user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate user ID format
        
        Args:
            user_id: User ID to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        if not user_id:
            return (False, "User ID cannot be empty")
        
        # User IDs should start with "user_"
        if not user_id.startswith('user_'):
            return (False, "Invalid user ID format")
        
        if len(user_id) > 100:
            return (False, "User ID is too long")
        
        return (True, None)
    
    @staticmethod
    def validate_reason(reason: str) -> Tuple[bool, Optional[str]]:
        """
        Validate kick/ban reason
        
        Args:
            reason: Reason text to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        if not reason:
            return (True, None)  # Reason is optional
        
        if len(reason) > InputValidator.MAX_REASON_LENGTH:
            return (False, f"Reason exceeds maximum length of {InputValidator.MAX_REASON_LENGTH}")
        
        # Check for null bytes
        if '\x00' in reason:
            return (False, "Reason contains invalid characters")
        
        return (True, None)
