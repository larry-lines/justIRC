#!/usr/bin/env python3
"""
Tests for key rotation functionality
"""

import unittest
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_layer import CryptoLayer


class TestKeyRotation(unittest.TestCase):
    """Test key rotation functionality"""
    
    def test_key_rotation_initialization(self):
        """Test that rotation tracking is initialized"""
        alice = CryptoLayer(key_rotation_interval=60.0, max_messages_per_key=100)
        bob = CryptoLayer()
        
        alice_pub = alice.get_public_key_b64()
        bob_pub = bob.get_public_key_b64()
        
        alice.load_peer_public_key("bob", bob_pub)
        
        # Should have timestamp and message count
        self.assertIn("bob", alice.peer_key_timestamp)
        self.assertIn("bob", alice.peer_message_count)
        self.assertEqual(alice.peer_message_count["bob"], 0)
    
    def test_message_count_increments(self):
        """Test that message count increments on encryption"""
        alice = CryptoLayer()
        bob = CryptoLayer()
        
        alice_pub = alice.get_public_key_b64()
        bob_pub = bob.get_public_key_b64()
        
        alice.load_peer_public_key("bob", bob_pub)
        bob.load_peer_public_key("alice", alice_pub)
        
        # Send messages
        for i in range(5):
            alice.encrypt("bob", f"message {i}")
        
        self.assertEqual(alice.peer_message_count["bob"], 5)
    
    def test_should_rotate_message_limit(self):
        """Test that rotation is needed after message limit"""
        alice = CryptoLayer(max_messages_per_key=3)
        bob = CryptoLayer()
        
        alice_pub = alice.get_public_key_b64()
        bob_pub = bob.get_public_key_b64()
        
        alice.load_peer_public_key("bob", bob_pub)
        
        # Should not need rotation initially
        self.assertFalse(alice.should_rotate_key("bob"))
        
        # Send messages up to limit
        for i in range(3):
            alice.encrypt("bob", f"message {i}")
        
        # Should need rotation now
        self.assertTrue(alice.should_rotate_key("bob"))
    
    def test_should_rotate_time_limit(self):
        """Test that rotation is needed after time limit"""
        alice = CryptoLayer(key_rotation_interval=0.1)  # 100ms
        bob = CryptoLayer()
        
        alice_pub = alice.get_public_key_b64()
        bob_pub = bob.get_public_key_b64()
        
        alice.load_peer_public_key("bob", bob_pub)
        
        # Should not need rotation initially
        self.assertFalse(alice.should_rotate_key("bob"))
        
        # Wait for time limit
        time.sleep(0.15)
        
        # Should need rotation now
        self.assertTrue(alice.should_rotate_key("bob"))
    
    def test_get_rotation_reason(self):
        """Test getting rotation reason"""
        alice = CryptoLayer(max_messages_per_key=2)
        bob = CryptoLayer()
        
        alice_pub = alice.get_public_key_b64()
        bob_pub = bob.get_public_key_b64()
        
        alice.load_peer_public_key("bob", bob_pub)
        
        # No rotation needed initially
        self.assertIsNone(alice.get_rotation_reason("bob"))
        
        # Hit message limit
        alice.encrypt("bob", "msg1")
        alice.encrypt("bob", "msg2")
        
        # Should have reason
        reason = alice.get_rotation_reason("bob")
        self.assertIsNotNone(reason)
        self.assertIn("message", reason.lower())
    
    def test_get_key_stats(self):
        """Test getting key statistics"""
        alice = CryptoLayer(max_messages_per_key=10)
        bob = CryptoLayer()
        
        alice_pub = alice.get_public_key_b64()
        bob_pub = bob.get_public_key_b64()
        
        alice.load_peer_public_key("bob", bob_pub)
        
        # Send some messages
        for i in range(3):
            alice.encrypt("bob", f"message {i}")
        
        stats = alice.get_key_stats("bob")
        
        self.assertIn("peer_id", stats)
        self.assertEqual(stats["peer_id"], "bob")
        self.assertIn("message_count", stats)
        self.assertEqual(stats["message_count"], 3)
        self.assertIn("should_rotate", stats)
        self.assertIn("key_age_seconds", stats)
        self.assertIn("messages_until_rotation", stats)
    
    def test_rotate_key_for_peer(self):
        """Test key rotation"""
        alice = CryptoLayer()
        bob = CryptoLayer()
        
        alice_pub = alice.get_public_key_b64()
        bob_pub = bob.get_public_key_b64()
        
        alice.load_peer_public_key("bob", bob_pub)
        bob.load_peer_public_key("alice", alice_pub)
        
        # Send messages
        for i in range(5):
            alice.encrypt("bob", f"message {i}")
        
        # Check message count
        self.assertEqual(alice.peer_message_count["bob"], 5)
        
        # Rotate key
        old_public_key = alice.get_public_key_b64()
        alice.rotate_key_for_peer("bob")
        
        # Public key should change
        new_public_key = alice.get_public_key_b64()
        self.assertNotEqual(old_public_key, new_public_key)
        
        # Message count should reset
        self.assertEqual(alice.peer_message_count["bob"], 0)
    
    def test_encryption_after_rotation(self):
        """Test that encryption still works after rotation"""
        alice = CryptoLayer()
        bob = CryptoLayer()
        
        alice_pub = alice.get_public_key_b64()
        bob_pub = bob.get_public_key_b64()
        
        alice.load_peer_public_key("bob", bob_pub)
        bob.load_peer_public_key("alice", alice_pub)
        
        # Rotate key
        alice.rotate_key_for_peer("bob")
        
        # Bob needs new public key
        new_alice_pub = alice.get_public_key_b64()
        bob.load_peer_public_key("alice", new_alice_pub)
        
        # Should still work
        plaintext = "Test after rotation"
        encrypted, nonce = alice.encrypt("bob", plaintext)
        decrypted = bob.decrypt("alice", encrypted, nonce)
        
        self.assertEqual(plaintext, decrypted)


if __name__ == '__main__':
    unittest.main()
