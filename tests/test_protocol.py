#!/usr/bin/env python3
"""
Comprehensive tests for protocol.py
Tests message building and parsing
"""

import unittest
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protocol import Protocol, MessageType


class TestProtocol(unittest.TestCase):
    """Test protocol message building and parsing"""
    
    def test_register_message(self):
        """Test registration message"""
        msg = Protocol.register("alice", "public_key_data")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.REGISTER.value)
        self.assertEqual(parsed['nickname'], "alice")
        self.assertEqual(parsed['public_key'], "public_key_data")
    
    def test_private_message(self):
        """Test private encrypted message"""
        msg = Protocol.encrypted_message(
            "alice", "bob", "encrypted_data", "nonce", is_channel=False
        )
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.PRIVATE_MESSAGE.value)
        self.assertEqual(parsed['from_id'], "alice")
        self.assertEqual(parsed['to_id'], "bob")
        self.assertEqual(parsed['encrypted_data'], "encrypted_data")
        self.assertEqual(parsed['nonce'], "nonce")
    
    def test_channel_message(self):
        """Test channel message"""
        msg = Protocol.encrypted_message(
            "alice", "#test", "encrypted_data", "nonce", is_channel=True
        )
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.CHANNEL_MESSAGE.value)
        self.assertEqual(parsed['from_id'], "alice")
        self.assertEqual(parsed['to_id'], "#test")
    
    def test_join_channel(self):
        """Test join channel message"""
        msg = Protocol.join_channel("user123", "#test", "password123")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.JOIN_CHANNEL.value)
        self.assertEqual(parsed['channel'], "#test")
        self.assertEqual(parsed['password'], "password123")
    
    def test_join_channel_no_password(self):
        """Test join channel without password"""
        msg = Protocol.join_channel("user123", "#public")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.JOIN_CHANNEL.value)
        self.assertEqual(parsed['channel'], "#public")
        self.assertIsNone(parsed.get('password'))
    
    def test_leave_channel(self):
        """Test leave channel message"""
        msg = Protocol.leave_channel("user123", "#test")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.LEAVE_CHANNEL.value)
        self.assertEqual(parsed['channel'], "#test")
    
    def test_ack_success(self):
        """Test success acknowledgment"""
        msg = Protocol.ack(True, "Operation successful")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.ACK.value)
        self.assertTrue(parsed['success'])
        self.assertEqual(parsed['message'], "Operation successful")
    
    def test_ack_failure(self):
        """Test failure acknowledgment"""
        msg = Protocol.ack(False, "Operation failed")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.ACK.value)
        self.assertFalse(parsed['success'])
        self.assertEqual(parsed['message'], "Operation failed")
    
    def test_error_message(self):
        """Test error message"""
        msg = Protocol.error("Something went wrong")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.ERROR.value)
        self.assertEqual(parsed['error'], "Something went wrong")
    
    def test_user_list(self):
        """Test user list message"""
        users = [
            {"user_id": "1", "nickname": "alice", "public_key": "key1"},
            {"user_id": "2", "nickname": "bob", "public_key": "key2"}
        ]
        msg = Protocol.user_list(users)
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.USER_LIST.value)
        self.assertEqual(len(parsed['users']), 2)
        self.assertEqual(parsed['users'][0]['nickname'], "alice")
    
    def test_image_start(self):
        """Test image transfer start message"""
        msg = Protocol.image_start("alice", "bob", "img123", 10, "encrypted_meta", "nonce123")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.IMAGE_START.value)
        self.assertEqual(parsed['image_id'], "img123")
        self.assertEqual(parsed['from_id'], "alice")
        self.assertEqual(parsed['total_chunks'], 10)
    
    def test_image_chunk(self):
        """Test image chunk message"""
        msg = Protocol.image_chunk("alice", "bob", "img123", 1, "encrypted_chunk", "nonce")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.IMAGE_CHUNK.value)
        self.assertEqual(parsed['image_id'], "img123")
        self.assertEqual(parsed['chunk_number'], 1)
    
    def test_invalid_json(self):
        """Test that invalid JSON raises error"""
        with self.assertRaises(ValueError):
            Protocol.parse_message("not json")
    
    def test_missing_type(self):
        """Test that message without type raises error"""
        with self.assertRaises(ValueError):
            Protocol.parse_message('{"data": "test"}')
    
    def test_empty_message(self):
        """Test that empty message raises error"""
        with self.assertRaises(ValueError):
            Protocol.parse_message("")
    
    def test_json_encoding(self):
        """Test that messages are valid JSON"""
        messages = [
            Protocol.register("test", "key"),
            Protocol.join_channel("user123", "#test"),
            Protocol.error("test error"),
            Protocol.ack(True, "success")
        ]
        
        for msg in messages:
            # Should not raise exception
            json.loads(msg)
    
    def test_special_characters_in_message(self):
        """Test handling of special characters"""
        msg = Protocol.register("test\n\r\t", "key\"'\\")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['nickname'], "test\n\r\t")
        self.assertEqual(parsed['public_key'], "key\"'\\")
    
    def test_unicode_in_message(self):
        """Test handling of Unicode characters"""
        msg = Protocol.register("用户名", "🔑")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['nickname'], "用户名")
        self.assertEqual(parsed['public_key'], "🔑")
    
    def test_large_message(self):
        """Test handling of large messages"""
        large_data = "A" * 10000
        msg = Protocol.error(large_data)
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['error'], large_data)


class TestMessageTypes(unittest.TestCase):
    """Test MessageType enum"""
    
    def test_all_types_unique(self):
        """Test that all message types have unique values"""
        values = [t.value for t in MessageType]
        self.assertEqual(len(values), len(set(values)))
    
    def test_type_values_are_strings(self):
        """Test that all message type values are strings"""
        for msg_type in MessageType:
            self.assertIsInstance(msg_type.value, str)


if __name__ == '__main__':
    unittest.main()
