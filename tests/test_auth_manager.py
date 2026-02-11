#!/usr/bin/env python3
"""
Tests for authentication module
"""

import unittest
import tempfile
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth_manager import AuthenticationManager


class TestAuthenticationManager(unittest.TestCase):
    """Test authentication functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary file for accounts
        self.temp_dir = tempfile.mkdtemp()
        self.accounts_file = os.path.join(self.temp_dir, 'test_accounts.json')
        self.auth = AuthenticationManager(
            accounts_file=self.accounts_file,
            enable_accounts=True,
            require_authentication=False
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.accounts_file):
            os.remove(self.accounts_file)
        os.rmdir(self.temp_dir)
    
    def test_create_account(self):
        """Test account creation"""
        result = self.auth.create_account('testuser', 'password123')
        self.assertTrue(result)
        self.assertTrue(self.auth.account_exists('testuser'))
    
    def test_duplicate_account(self):
        """Test that duplicate accounts are rejected"""
        self.auth.create_account('testuser', 'password123')
        result = self.auth.create_account('testuser', 'different_password')
        self.assertFalse(result)
    
    def test_password_verification(self):
        """Test password verification"""
        self.auth.create_account('testuser', 'password123')
        self.assertTrue(self.auth.verify_password('testuser', 'password123'))
        self.assertFalse(self.auth.verify_password('testuser', 'wrongpassword'))
    
    def test_authentication(self):
        """Test authentication"""
        self.auth.create_account('testuser', 'password123')
        token = self.auth.authenticate('testuser', 'password123')
        self.assertIsNotNone(token)
        
        # Verify token
        username = self.auth.verify_session(token)
        self.assertEqual(username, 'testuser')
    
    def test_authentication_failure(self):
        """Test authentication with wrong password"""
        self.auth.create_account('testuser', 'password123')
        token = self.auth.authenticate('testuser', 'wrongpassword')
        self.assertIsNone(token)
    
    def test_logout(self):
        """Test logout"""
        self.auth.create_account('testuser', 'password123')
        token = self.auth.authenticate('testuser', 'password123')
        
        # Logout
        result = self.auth.logout(token)
        self.assertTrue(result)
        
        # Token should no longer be valid
        username = self.auth.verify_session(token)
        self.assertIsNone(username)
    
    def test_change_password(self):
        """Test password change"""
        self.auth.create_account('testuser', 'oldpassword')
        
        # Change password
        result = self.auth.change_password('testuser', 'oldpassword', 'newpassword')
        self.assertTrue(result)
        
        # Old password should not work
        self.assertFalse(self.auth.verify_password('testuser', 'oldpassword'))
        
        # New password should work
        self.assertTrue(self.auth.verify_password('testuser', 'newpassword'))
    
    def test_change_password_wrong_old(self):
        """Test password change with wrong old password"""
        self.auth.create_account('testuser', 'password123')
        result = self.auth.change_password('testuser', 'wrongold', 'newpassword')
        self.assertFalse(result)
    
    def test_account_lockout(self):
        """Test account lockout after failed attempts"""
        self.auth.create_account('testuser', 'password123')
        
        # Make 5 failed attempts
        for _ in range(5):
            self.auth.authenticate('testuser', 'wrongpassword')
        
        # Account should be locked
        self.assertTrue(self.auth.is_account_locked('testuser'))
        
        # Even correct password should fail
        token = self.auth.authenticate('testuser', 'password123')
        self.assertIsNone(token)
    
    def test_disable_enable_account(self):
        """Test disabling and enabling accounts"""
        self.auth.create_account('testuser', 'password123')
        
        # Disable account
        result = self.auth.disable_account('testuser')
        self.assertTrue(result)
        self.assertTrue(self.auth.is_account_disabled('testuser'))
        
        # Enable account
        result = self.auth.enable_account('testuser')
        self.assertTrue(result)
        self.assertFalse(self.auth.is_account_disabled('testuser'))
    
    def test_account_persistence(self):
        """Test that accounts persist to file"""
        self.auth.create_account('testuser', 'password123')
        
        # Create new auth manager with same file
        auth2 = AuthenticationManager(
            accounts_file=self.accounts_file,
            enable_accounts=True
        )
        
        # Account should exist
        self.assertTrue(auth2.account_exists('testuser'))
        self.assertTrue(auth2.verify_password('testuser', 'password123'))
    
    def test_get_account_info(self):
        """Test getting account info"""
        self.auth.create_account('testuser', 'password123', 'test@example.com')
        info = self.auth.get_account_info('testuser')
        
        self.assertIsNotNone(info)
        self.assertEqual(info['username'], 'testuser')
        self.assertEqual(info['email'], 'test@example.com')
        
        # Should not expose password hash
        self.assertNotIn('password_hash', info)
        self.assertNotIn('salt', info)
    
    def test_password_hash_uniqueness(self):
        """Test that same password produces unique hashes with different salts"""
        hash1, salt1 = self.auth.hash_password('password123')
        hash2, salt2 = self.auth.hash_password('password123')
        
        # Salts should be different
        self.assertNotEqual(salt1, salt2)
        
        # Hashes should be different
        self.assertNotEqual(hash1, hash2)


if __name__ == '__main__':
    unittest.main()
