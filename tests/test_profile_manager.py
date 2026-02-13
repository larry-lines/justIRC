"""
Tests for Profile Manager
"""

import unittest
import os
import sys
import tempfile
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from profile_manager import ProfileManager


class TestProfileManager(unittest.TestCase):
    """Test profile management functionality"""
    
    def setUp(self):
        """Set up temp profiles file"""
        self.temp_fd, self.temp_file = tempfile.mkstemp(suffix='.json')
        os.close(self.temp_fd)
        self.profile_mgr = ProfileManager(self.temp_file)
    
    def tearDown(self):
        """Clean up temp file"""
        if os.path.exists(self.temp_file):
            os.unlink(self.temp_file)
    
    def test_register_nickname(self):
        """Test nickname registration"""
        success, msg = self.profile_mgr.register_nickname('testuser', 'password123')
        self.assertTrue(success)
        self.assertIn('success', msg.lower())
        
        # Verify profile was created
        profile = self.profile_mgr.get_profile('testuser')
        self.assertIsNotNone(profile)
        self.assertTrue(profile['registered'])
        self.assertEqual(profile['nickname'], 'testuser')
    
    def test_register_duplicate_nickname(self):
        """Test registering an already registered nickname"""
        self.profile_mgr.register_nickname('testuser', 'password123')
        success, msg = self.profile_mgr.register_nickname('testuser', 'newpassword')
        
        self.assertFalse(success)
        self.assertIn('already registered', msg.lower())
    
    def test_register_short_password(self):
        """Test registering with short password"""
        success, msg = self.profile_mgr.register_nickname('testuser', 'short')
        
        self.assertFalse(success)
        self.assertIn('at least 6', msg.lower())
    
    def test_verify_password(self):
        """Test password verification"""
        self.profile_mgr.register_nickname('testuser', 'password123')
        
        # Correct password
        self.assertTrue(self.profile_mgr.verify_password('testuser', 'password123'))
        
        # Incorrect password
        self.assertFalse(self.profile_mgr.verify_password('testuser', 'wrongpassword'))
    
    def test_is_registered(self):
        """Test checking if nickname is registered"""
        self.assertFalse(self.profile_mgr.is_registered('testuser'))
        
        self.profile_mgr.register_nickname('testuser', 'password123')
        self.assertTrue(self.profile_mgr.is_registered('testuser'))
    
    def test_update_profile_bio(self):
        """Test updating profile bio"""
        self.profile_mgr.register_nickname('testuser', 'password123')
        
        success, msg = self.profile_mgr.update_profile('testuser', bio='This is my bio')
        self.assertTrue(success)
        
        profile = self.profile_mgr.get_profile('testuser')
        self.assertEqual(profile['bio'], 'This is my bio')
    
    def test_update_profile_status(self):
        """Test updating profile status message"""
        self.profile_mgr.register_nickname('testuser', 'password123')
        
        success, msg = self.profile_mgr.update_profile('testuser', status_message='Away')
        self.assertTrue(success)
        
        profile = self.profile_mgr.get_profile('testuser')
        self.assertEqual(profile['status_message'], 'Away')
    
    def test_update_profile_avatar(self):
        """Test updating profile avatar"""
        self.profile_mgr.register_nickname('testuser', 'password123')
        
        avatar_data = 'base64encodedimagedata'
        success, msg = self.profile_mgr.update_profile('testuser', avatar=avatar_data)
        self.assertTrue(success)
        
        profile = self.profile_mgr.get_profile('testuser')
        self.assertEqual(profile['avatar'], avatar_data)
    
    def test_update_profile_bio_too_long(self):
        """Test updating bio with text that's too long"""
        self.profile_mgr.register_nickname('testuser', 'password123')
        
        long_bio = 'x' * 501  # Over 500 char limit
        success, msg = self.profile_mgr.update_profile('testuser', bio=long_bio)
        
        self.assertFalse(success)
        self.assertIn('500', msg)
    
    def test_update_profile_status_too_long(self):
        """Test updating status with text that's too long"""
        self.profile_mgr.register_nickname('testuser', 'password123')
        
        long_status = 'x' * 101  # Over 100 char limit
        success, msg = self.profile_mgr.update_profile('testuser', status_message=long_status)
        
        self.assertFalse(success)
        self.assertIn('100', msg)
    
    def test_update_profile_avatar_too_large(self):
        """Test updating avatar with data that's too large"""
        self.profile_mgr.register_nickname('testuser', 'password123')
        
        large_avatar = 'x' * 150001  # Over 150KB limit
        success, msg = self.profile_mgr.update_profile('testuser', avatar=large_avatar)
        
        self.assertFalse(success)
        self.assertIn('large', msg.lower())
    
    def test_update_profile_creates_if_not_exists(self):
        """Test that update_profile creates profile if it doesn't exist"""
        success, msg = self.profile_mgr.update_profile('newuser', bio='New user bio')
        self.assertTrue(success)
        
        profile = self.profile_mgr.get_profile('newuser')
        self.assertIsNotNone(profile)
        self.assertEqual(profile['bio'], 'New user bio')
        self.assertFalse(profile['registered'])
    
    def test_get_profile_nonexistent(self):
        """Test getting profile for non-existent user"""
        profile = self.profile_mgr.get_profile('nonexistent')
        self.assertIsNone(profile)
    
    def test_get_profile_does_not_expose_password(self):
        """Test that get_profile doesn't expose password data"""
        self.profile_mgr.register_nickname('testuser', 'password123')
        
        profile = self.profile_mgr.get_profile('testuser')
        self.assertNotIn('password_hash', profile)
        self.assertNotIn('salt', profile)
    
    def test_delete_profile_registered(self):
        """Test deleting a registered profile with password"""
        self.profile_mgr.register_nickname('testuser', 'password123')
        
        # Wrong password
        success, msg = self.profile_mgr.delete_profile('testuser', 'wrongpassword')
        self.assertFalse(success)
        
        # Correct password
        success, msg = self.profile_mgr.delete_profile('testuser', 'password123')
        self.assertTrue(success)
        
        # Verify profile is gone
        profile = self.profile_mgr.get_profile('testuser')
        self.assertIsNone(profile)
    
    def test_delete_profile_unregistered(self):
        """Test deleting an unregistered profile"""
        self.profile_mgr.update_profile('testuser', bio='Test bio')
        
        # No password needed for unregistered
        success, msg = self.profile_mgr.delete_profile('testuser')
        self.assertTrue(success)
        
        profile = self.profile_mgr.get_profile('testuser')
        self.assertIsNone(profile)
    
    def test_delete_profile_nonexistent(self):
        """Test deleting non-existent profile"""
        success, msg = self.profile_mgr.delete_profile('nonexistent')
        self.assertFalse(success)
    
    def test_get_all_registered_nicknames(self):
        """Test getting list of all registered nicknames"""
        self.profile_mgr.register_nickname('user1', 'password123')
        self.profile_mgr.register_nickname('user2', 'password123')
        self.profile_mgr.update_profile('user3', bio='Unregistered')
        
        registered = self.profile_mgr.get_all_registered_nicknames()
        
        self.assertEqual(len(registered), 2)
        self.assertIn('user1', registered)
        self.assertIn('user2', registered)
        self.assertNotIn('user3', registered)
    
    def test_search_profiles_by_nickname(self):
        """Test searching profiles by nickname"""
        self.profile_mgr.register_nickname('alice', 'password123')
        self.profile_mgr.register_nickname('bob', 'password123')
        self.profile_mgr.update_profile('alice', bio='Developer')
        
        results = self.profile_mgr.search_profiles('ali')
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['nickname'], 'alice')
    
    def test_search_profiles_by_bio(self):
        """Test searching profiles by bio content"""
        self.profile_mgr.update_profile('alice', bio='Python developer')
        self.profile_mgr.update_profile('bob', bio='JavaScript developer')
        
        results = self.profile_mgr.search_profiles('python')
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['nickname'], 'alice')
    
    def test_search_profiles_max_results(self):
        """Test search respects max_results limit"""
        for i in range(15):
            self.profile_mgr.update_profile(f'user{i}', bio='Test user')
        
        results = self.profile_mgr.search_profiles('user', max_results=5)
        
        self.assertEqual(len(results), 5)
    
    def test_update_last_seen(self):
        """Test updating last seen timestamp"""
        self.profile_mgr.register_nickname('testuser', 'password123')
        
        profile_before = self.profile_mgr.get_profile('testuser')
        last_seen_before = profile_before.get('last_seen')
        
        # Wait a tiny bit
        import time
        time.sleep(0.01)
        
        self.profile_mgr.update_last_seen('testuser')
        
        profile_after = self.profile_mgr.get_profile('testuser')
        last_seen_after = profile_after.get('last_seen')
        
        # Last seen should be updated
        self.assertNotEqual(last_seen_before, last_seen_after)
    
    def test_persistence(self):
        """Test that profiles persist to disk"""
        self.profile_mgr.register_nickname('testuser', 'password123')
        self.profile_mgr.update_profile('testuser', bio='Test bio')
        
        # Create new profile manager with same file
        profile_mgr2 = ProfileManager(self.temp_file)
        
        profile = profile_mgr2.get_profile('testuser')
        self.assertIsNotNone(profile)
        self.assertEqual(profile['nickname'], 'testuser')
        self.assertEqual(profile['bio'], 'Test bio')
        self.assertTrue(profile['registered'])


if __name__ == '__main__':
    unittest.main()
