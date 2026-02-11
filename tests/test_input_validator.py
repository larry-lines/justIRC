#!/usr/bin/env python3
"""
Tests for input validation
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from input_validator import InputValidator


class TestInputValidator(unittest.TestCase):
    """Test input validation functionality"""
    
    def test_valid_nickname(self):
        """Test valid nickname"""
        is_valid, error = InputValidator.validate_nickname("alice123")
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_nickname_too_short(self):
        """Test nickname too short"""
        is_valid, error = InputValidator.validate_nickname("ab")
        self.assertFalse(is_valid)
        self.assertIn("at least 3", error)
    
    def test_nickname_too_long(self):
        """Test nickname too long"""
        is_valid, error = InputValidator.validate_nickname("a" * 21)
        self.assertFalse(is_valid)
        self.assertIn("at most 20", error)
    
    def test_nickname_invalid_chars(self):
        """Test nickname with invalid characters"""
        is_valid, error = InputValidator.validate_nickname("alice@bob")
        self.assertFalse(is_valid)
        self.assertIn("only contain", error)
    
    def test_nickname_reserved(self):
        """Test reserved nickname"""
        is_valid, error = InputValidator.validate_nickname("server")
        self.assertFalse(is_valid)
        self.assertIn("reserved", error)
    
    def test_valid_channel_name(self):
        """Test valid channel name"""
        is_valid, error = InputValidator.validate_channel_name("#lobby")
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_channel_missing_hash(self):
        """Test channel name without #"""
        is_valid, error = InputValidator.validate_channel_name("lobby")
        self.assertFalse(is_valid)
        self.assertIn("must start with #", error)
    
    def test_channel_too_short(self):
        """Test channel name too short"""
        is_valid, error = InputValidator.validate_channel_name("#")
        self.assertFalse(is_valid)
        self.assertIn("at least 2", error)
    
    def test_channel_too_long(self):
        """Test channel name too long"""
        is_valid, error = InputValidator.validate_channel_name("#" + "a" * 51)
        self.assertFalse(is_valid)
        self.assertIn("at most 50", error)
    
    def test_channel_invalid_chars(self):
        """Test channel with invalid characters"""
        is_valid, error = InputValidator.validate_channel_name("#lobby@room")
        self.assertFalse(is_valid)
        self.assertIn("only contain", error)
    
    def test_valid_email(self):
        """Test valid email"""
        is_valid, error = InputValidator.validate_email("alice@example.com")
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_email_optional(self):
        """Test that email is optional"""
        is_valid, error = InputValidator.validate_email(None)
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_email_invalid_format(self):
        """Test invalid email format"""
        is_valid, error = InputValidator.validate_email("notanemail")
        self.assertFalse(is_valid)
        self.assertIn("Invalid email", error)
    
    def test_valid_password(self):
        """Test valid password"""
        is_valid, error = InputValidator.validate_password("password123")
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_password_too_short(self):
        """Test password too short"""
        is_valid, error = InputValidator.validate_password("pass")
        self.assertFalse(is_valid)
        self.assertIn("at least", error)
    
    def test_password_too_long(self):
        """Test password too long"""
        long_pass = "a" * 300
        is_valid, error = InputValidator.validate_password(long_pass)
        self.assertFalse(is_valid)
        self.assertIn("at most", error)
    
    def test_valid_message(self):
        """Test valid message"""
        is_valid, error = InputValidator.validate_message("Hello world!")
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_message_empty(self):
        """Test empty message"""
        is_valid, error = InputValidator.validate_message("")
        self.assertFalse(is_valid)
        self.assertIn("cannot be empty", error)
    
    def test_message_too_long(self):
        """Test message too long"""
        long_msg = "a" * 5000
        is_valid, error = InputValidator.validate_message(long_msg)
        self.assertFalse(is_valid)
        self.assertIn("exceeds maximum", error)
    
    def test_message_null_byte(self):
        """Test message with null byte"""
        is_valid, error = InputValidator.validate_message("hello\x00world")
        self.assertFalse(is_valid)
        self.assertIn("invalid characters", error)
    
    def test_sanitize_string(self):
        """Test string sanitization"""
        sanitized = InputValidator.sanitize_string("hello\x00world\x01test")
        self.assertNotIn("\x00", sanitized)
        self.assertNotIn("\x01", sanitized)
    
    def test_sanitize_with_max_length(self):
        """Test sanitization with max length"""
        sanitized = InputValidator.sanitize_string("hello world", max_length=5)
        self.assertEqual(len(sanitized), 5)
        self.assertEqual(sanitized, "hello")
    
    def test_valid_user_id(self):
        """Test valid user ID"""
        is_valid, error = InputValidator.validate_user_id("user_123_alice")
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_user_id_invalid_format(self):
        """Test invalid user ID format"""
        is_valid, error = InputValidator.validate_user_id("invalid_format")
        self.assertFalse(is_valid)
        self.assertIn("Invalid user ID", error)


if __name__ == '__main__':
    unittest.main()
