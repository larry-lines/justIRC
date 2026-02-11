"""
Authentication module for JustIRC
Handles user accounts, password authentication, and credentials storage
"""

import hashlib
import hmac
import secrets
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


class AuthenticationManager:
    """Manages user authentication and credentials"""
    
    def __init__(self, accounts_file: str = "accounts.json", 
                 enable_accounts: bool = False,
                 require_authentication: bool = False):
        """
        Initialize authentication manager
        
        Args:
            accounts_file: Path to persistent accounts storage
            enable_accounts: Enable persistent user accounts
            require_authentication: Require authentication for all users
        """
        self.accounts_file = accounts_file
        self.enable_accounts = enable_accounts
        self.require_authentication = require_authentication
        self.accounts: Dict[str, Dict[str, Any]] = {}
        self.active_sessions: Dict[str, str] = {}  # session_token -> username
        self.failed_attempts: Dict[str, list] = {}  # username -> [timestamps]
        
        if self.enable_accounts:
            self.load_accounts()
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> tuple:
        """
        Hash password using PBKDF2-HMAC-SHA256
        
        Args:
            password: Plain text password
            salt: Optional salt (generated if not provided)
            
        Returns:
            (hashed_password, salt) tuple
        """
        if salt is None:
            salt = secrets.token_bytes(32)
        
        # Use PBKDF2 with 100,000 iterations
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        
        return (hashed, salt)
    
    def verify_password(self, username: str, password: str) -> bool:
        """
        Verify password for a user
        
        Args:
            username: Username to verify
            password: Plain text password
            
        Returns:
            True if password matches, False otherwise
        """
        if username not in self.accounts:
            return False
        
        account = self.accounts[username]
        stored_hash = bytes.fromhex(account['password_hash'])
        salt = bytes.fromhex(account['salt'])
        
        hashed, _ = self.hash_password(password, salt)
        
        return hmac.compare_digest(hashed, stored_hash)
    
    def create_account(self, username: str, password: str, 
                      email: Optional[str] = None) -> bool:
        """
        Create a new user account
        
        Args:
            username: Desired username
            password: Plain text password
            email: Optional email address
            
        Returns:
            True if account created, False if username exists
        """
        if username in self.accounts:
            return False
        
        hashed, salt = self.hash_password(password)
        
        self.accounts[username] = {
            'username': username,
            'password_hash': hashed.hex(),
            'salt': salt.hex(),
            'email': email,
            'created_at': datetime.utcnow().isoformat(),
            'last_login': None,
            'disabled': False
        }
        
        if self.enable_accounts:
            self.save_accounts()
        
        return True
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate a user and create a session
        
        Args:
            username: Username
            password: Plain text password
            
        Returns:
            Session token if successful, None otherwise
        """
        # Check if account is locked due to failed attempts
        if self.is_account_locked(username):
            return None
        
        # Verify password
        if not self.verify_password(username, password):
            self.record_failed_attempt(username)
            return None
        
        # Clear failed attempts on successful login
        if username in self.failed_attempts:
            del self.failed_attempts[username]
        
        # Update last login
        if username in self.accounts:
            self.accounts[username]['last_login'] = datetime.utcnow().isoformat()
            if self.enable_accounts:
                self.save_accounts()
        
        # Generate session token
        session_token = secrets.token_urlsafe(32)
        self.active_sessions[session_token] = username
        
        return session_token
    
    def verify_session(self, session_token: str) -> Optional[str]:
        """
        Verify a session token
        
        Args:
            session_token: Session token to verify
            
        Returns:
            Username if valid, None otherwise
        """
        return self.active_sessions.get(session_token)
    
    def logout(self, session_token: str) -> bool:
        """
        Logout a session
        
        Args:
            session_token: Session token
            
        Returns:
            True if successful
        """
        if session_token in self.active_sessions:
            del self.active_sessions[session_token]
            return True
        return False
    
    def record_failed_attempt(self, username: str):
        """Record a failed login attempt"""
        now = datetime.utcnow()
        
        if username not in self.failed_attempts:
            self.failed_attempts[username] = []
        
        self.failed_attempts[username].append(now)
        
        # Keep only recent attempts (last hour)
        cutoff = now - timedelta(hours=1)
        self.failed_attempts[username] = [
            t for t in self.failed_attempts[username] if t > cutoff
        ]
    
    def is_account_locked(self, username: str, max_attempts: int = 5) -> bool:
        """
        Check if account is locked due to failed attempts
        
        Args:
            username: Username to check
            max_attempts: Maximum attempts before lockout (default 5)
            
        Returns:
            True if locked, False otherwise
        """
        if username not in self.failed_attempts:
            return False
        
        # Clean old attempts
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=15)  # 15 minute lockout window
        
        self.failed_attempts[username] = [
            t for t in self.failed_attempts[username] if t > cutoff
        ]
        
        return len(self.failed_attempts[username]) >= max_attempts
    
    def change_password(self, username: str, old_password: str, 
                       new_password: str) -> bool:
        """
        Change user password
        
        Args:
            username: Username
            old_password: Current password
            new_password: New password
            
        Returns:
            True if successful, False otherwise
        """
        if not self.verify_password(username, old_password):
            return False
        
        hashed, salt = self.hash_password(new_password)
        
        self.accounts[username]['password_hash'] = hashed.hex()
        self.accounts[username]['salt'] = salt.hex()
        
        if self.enable_accounts:
            self.save_accounts()
        
        return True
    
    def disable_account(self, username: str) -> bool:
        """Disable a user account"""
        if username not in self.accounts:
            return False
        
        self.accounts[username]['disabled'] = True
        
        if self.enable_accounts:
            self.save_accounts()
        
        return True
    
    def enable_account(self, username: str) -> bool:
        """Enable a user account"""
        if username not in self.accounts:
            return False
        
        self.accounts[username]['disabled'] = False
        
        if self.enable_accounts:
            self.save_accounts()
        
        return True
    
    def is_account_disabled(self, username: str) -> bool:
        """Check if account is disabled"""
        if username not in self.accounts:
            return False
        
        return self.accounts[username].get('disabled', False)
    
    def account_exists(self, username: str) -> bool:
        """Check if account exists"""
        return username in self.accounts
    
    def load_accounts(self):
        """Load accounts from file"""
        if not os.path.exists(self.accounts_file):
            return
        
        try:
            with open(self.accounts_file, 'r') as f:
                self.accounts = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load accounts: {e}")
    
    def save_accounts(self):
        """Save accounts to file"""
        try:
            with open(self.accounts_file, 'w') as f:
                json.dump(self.accounts, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save accounts: {e}")
    
    def get_account_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get account information (excluding password)
        
        Args:
            username: Username
            
        Returns:
            Account info dict or None
        """
        if username not in self.accounts:
            return None
        
        account = self.accounts[username].copy()
        # Don't expose password hash and salt
        account.pop('password_hash', None)
        account.pop('salt', None)
        
        return account
