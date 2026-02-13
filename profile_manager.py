"""
User Profile Manager for JustIRC
Handles nickname registration, user profiles, and profile data persistence
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path


class ProfileManager:
    """Manages user profiles and registered nicknames"""
    
    def __init__(self, profiles_file: str = "user_profiles.json"):
        """
        Initialize profile manager
        
        Args:
            profiles_file: Path to profiles database file
        """
        self.profiles_file = profiles_file
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.load_profiles()
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> tuple:
        """
        Hash a password using PBKDF2-HMAC-SHA256
        
        Args:
            password: Plain text password
            salt: Optional salt (will be generated if not provided)
            
        Returns:
            (hashed_password, salt) tuple
        """
        if salt is None:
            salt = hashlib.sha256(str(datetime.utcnow()).encode()).digest()[:16]
        
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return (hashed, salt)
    
    def verify_password(self, nickname: str, password: str) -> bool:
        """
        Verify a password for a registered nickname
        
        Args:
            nickname: Registered nickname
            password: Password to verify
            
        Returns:
            True if password matches, False otherwise
        """
        if nickname not in self.profiles or not self.profiles[nickname].get('registered'):
            return False
        
        stored_hash = bytes.fromhex(self.profiles[nickname]['password_hash'])
        stored_salt = bytes.fromhex(self.profiles[nickname]['salt'])
        
        hashed, _ = self.hash_password(password, stored_salt)
        return hashed == stored_hash
    
    def register_nickname(self, nickname: str, password: str) -> tuple[bool, str]:
        """
        Register a nickname with a password
        
        Args:
            nickname: Nickname to register
            password: Password for nickname protection
            
        Returns:
            (success, message) tuple
        """
        if nickname in self.profiles and self.profiles[nickname].get('registered'):
            return (False, "Nickname is already registered")
        
        if len(password) < 6:
            return (False, "Password must be at least 6 characters")
        
        hashed, salt = self.hash_password(password)
        
        # Create or update profile
        if nickname not in self.profiles:
            self.profiles[nickname] = {}
        
        self.profiles[nickname].update({
            'nickname': nickname,
            'registered': True,
            'password_hash': hashed.hex(),
            'salt': salt.hex(),
            'registration_date': datetime.utcnow().isoformat(),
            'bio': None,
            'status_message': None,
            'avatar': None,
            'last_seen': datetime.utcnow().isoformat()
        })
        
        self.save_profiles()
        return (True, "Nickname registered successfully")
    
    def is_registered(self, nickname: str) -> bool:
        """
        Check if a nickname is registered
        
        Args:
            nickname: Nickname to check
            
        Returns:
            True if registered, False otherwise
        """
        return nickname in self.profiles and self.profiles[nickname].get('registered', False)
    
    def update_profile(self, nickname: str, bio: Optional[str] = None,
                      status_message: Optional[str] = None,
                      avatar: Optional[str] = None) -> tuple[bool, str]:
        """
        Update user profile
        
        Args:
            nickname: Nickname to update
            bio: User bio/description (max 500 chars)
            status_message: Status message (max 100 chars)
            avatar: Avatar data (base64 encoded or URL)
            
        Returns:
            (success, message) tuple
        """
        # Create profile if it doesn't exist
        if nickname not in self.profiles:
            self.profiles[nickname] = {
                'nickname': nickname,
                'registered': False,
                'bio': None,
                'status_message': None,
                'avatar': None,
                'last_seen': datetime.utcnow().isoformat()
            }
        
        # Validate input lengths
        if bio is not None:
            if len(bio) > 500:
                return (False, "Bio must be 500 characters or less")
            self.profiles[nickname]['bio'] = bio
        
        if status_message is not None:
            if len(status_message) > 100:
                return (False, "Status message must be 100 characters or less")
            self.profiles[nickname]['status_message'] = status_message
        
        if avatar is not None:
            # Limit avatar size (base64 encoded ~100KB = ~75KB original)
            if len(avatar) > 150000:
                return (False, "Avatar data too large (max ~100KB)")
            self.profiles[nickname]['avatar'] = avatar
        
        self.profiles[nickname]['last_updated'] = datetime.utcnow().isoformat()
        self.save_profiles()
        
        return (True, "Profile updated successfully")
    
    def get_profile(self, nickname: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile
        
        Args:
            nickname: Nickname to get profile for
            
        Returns:
            Profile dict or None if not found
        """
        if nickname not in self.profiles:
            return None
        
        profile = self.profiles[nickname].copy()
        
        # Don't expose password data
        profile.pop('password_hash', None)
        profile.pop('salt', None)
        
        return profile
    
    def update_last_seen(self, nickname: str):
        """
        Update last seen timestamp
        
        Args:
            nickname: Nickname to update
        """
        if nickname in self.profiles:
            self.profiles[nickname]['last_seen'] = datetime.utcnow().isoformat()
            self.save_profiles()
    
    def delete_profile(self, nickname: str, password: Optional[str] = None) -> tuple[bool, str]:
        """
        Delete a user profile
        
        Args:
            nickname: Nickname to delete
            password: Password verification (required for registered nicknames)
            
        Returns:
            (success, message) tuple
        """
        if nickname not in self.profiles:
            return (False, "Profile not found")
        
        # Verify password for registered nicknames
        if self.profiles[nickname].get('registered'):
            if not password or not self.verify_password(nickname, password):
                return (False, "Invalid password")
        
        del self.profiles[nickname]
        self.save_profiles()
        
        return (True, "Profile deleted successfully")
    
    def load_profiles(self):
        """Load profiles from file"""
        try:
            path = Path(self.profiles_file)
            if path.exists():
                with open(self.profiles_file, 'r') as f:
                    self.profiles = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load profiles: {e}")
            self.profiles = {}
    
    def save_profiles(self):
        """Save profiles to file"""
        try:
            with open(self.profiles_file, 'w') as f:
                json.dump(self.profiles, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save profiles: {e}")
    
    def get_all_registered_nicknames(self) -> list[str]:
        """
        Get list of all registered nicknames
        
        Returns:
            List of registered nicknames
        """
        return [
            nick for nick, profile in self.profiles.items()
            if profile.get('registered', False)
        ]
    
    def search_profiles(self, query: str, max_results: int = 10) -> list[Dict[str, Any]]:
        """
        Search profiles by nickname or bio
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of matching profiles
        """
        query_lower = query.lower()
        results = []
        
        for nickname, profile in self.profiles.items():
            if len(results) >= max_results:
                break
            
            # Search in nickname
            if query_lower in nickname.lower():
                profile_copy = profile.copy()
                profile_copy.pop('password_hash', None)
                profile_copy.pop('salt', None)
                results.append(profile_copy)
                continue
            
            # Search in bio
            bio = profile.get('bio', '')
            if bio and query_lower in bio.lower():
                profile_copy = profile.copy()
                profile_copy.pop('password_hash', None)
                profile_copy.pop('salt', None)
                results.append(profile_copy)
        
        return results
