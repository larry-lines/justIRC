#!/usr/bin/env python3
"""
Comprehensive tests for crypto_layer.py
Tests all cryptographic operations
"""

import unittest
import base64
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_layer import CryptoLayer, ChannelCrypto


class TestCryptoLayer(unittest.TestCase):
    """Test cryptographic functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.alice = CryptoLayer()
        self.bob = CryptoLayer()
        self.charlie = CryptoLayer()
    
    def test_key_generation(self):
        """Test that keys are generated correctly"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.assertIsNotNone(alice_pub)
        self.assertIsNotNone(bob_pub)
        self.assertNotEqual(alice_pub, bob_pub)
        self.assertEqual(len(alice_pub), 44)  # Base64 of 32 bytes
    
    def test_public_key_bytes(self):
        """Test public key as bytes"""
        pub_bytes = self.alice.get_public_key_bytes()
        self.assertIsInstance(pub_bytes, bytes)
        self.assertEqual(len(pub_bytes), 32)  # X25519 key size
    
    def test_key_exchange(self):
        """Test key exchange between two parties"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.bob.load_peer_public_key("alice", alice_pub)
        
        self.assertTrue(self.alice.has_peer_key("bob"))
        self.assertTrue(self.bob.has_peer_key("alice"))
    
    def test_invalid_public_key(self):
        """Test that invalid public key raises error"""
        with self.assertRaises(ValueError):
            self.alice.load_peer_public_key("invalid", "not_a_valid_key")
    
    def test_encryption_decryption(self):
        """Test message encryption and decryption"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.bob.load_peer_public_key("alice", alice_pub)
        
        plaintext = "Hello Bob, this is a secret message!"
        encrypted, nonce = self.alice.encrypt("bob", plaintext)
        decrypted = self.bob.decrypt("alice", encrypted, nonce)
        
        self.assertEqual(plaintext, decrypted)
    
    def test_encryption_empty_message(self):
        """Test encryption of empty message"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.bob.load_peer_public_key("alice", alice_pub)
        
        plaintext = ""
        encrypted, nonce = self.alice.encrypt("bob", plaintext)
        decrypted = self.bob.decrypt("alice", encrypted, nonce)
        
        self.assertEqual(plaintext, decrypted)
    
    def test_encryption_unicode(self):
        """Test encryption with unicode characters"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.bob.load_peer_public_key("alice", alice_pub)
        
        plaintext = "Hello 🌍! Testing 日本語 and العربية"
        encrypted, nonce = self.alice.encrypt("bob", plaintext)
        decrypted = self.bob.decrypt("alice", encrypted, nonce)
        
        self.assertEqual(plaintext, decrypted)
    
    def test_encryption_large_message(self):
        """Test encryption of large message"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.bob.load_peer_public_key("alice", alice_pub)
        
        plaintext = "A" * 10000  # 10KB message
        encrypted, nonce = self.alice.encrypt("bob", plaintext)
        decrypted = self.bob.decrypt("alice", encrypted, nonce)
        
        self.assertEqual(plaintext, decrypted)
    
    def test_encryption_different_peers(self):
        """Test that encryption is different for different peers"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        charlie_pub = self.charlie.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.alice.load_peer_public_key("charlie", charlie_pub)
        
        plaintext = "Same message to both"
        encrypted_bob, nonce_bob = self.alice.encrypt("bob", plaintext)
        encrypted_charlie, nonce_charlie = self.alice.encrypt("charlie", plaintext)
        
        self.assertNotEqual(encrypted_bob, encrypted_charlie)
    
    def test_tampering_detection(self):
        """Test that tampering is detected"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.bob.load_peer_public_key("alice", alice_pub)
        
        plaintext = "Important message"
        encrypted, nonce = self.alice.encrypt("bob", plaintext)
        
        # Tamper with the ciphertext
        encrypted_bytes = base64.b64decode(encrypted)
        tampered_bytes = bytes([b ^ 1 for b in encrypted_bytes])
        tampered_encrypted = base64.b64encode(tampered_bytes).decode('utf-8')
        
        with self.assertRaises(ValueError):
            self.bob.decrypt("alice", tampered_encrypted, nonce)
    
    def test_wrong_nonce(self):
        """Test that wrong nonce fails decryption"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.bob.load_peer_public_key("alice", alice_pub)
        
        plaintext = "Test message"
        encrypted, _ = self.alice.encrypt("bob", plaintext)
        wrong_nonce = base64.b64encode(os.urandom(12)).decode('utf-8')
        
        with self.assertRaises(ValueError):
            self.bob.decrypt("alice", encrypted, wrong_nonce)
    
    def test_encrypt_without_peer_key(self):
        """Test that encrypting without peer key raises error"""
        with self.assertRaises(ValueError):
            self.alice.encrypt("unknown", "test")
    
    def test_decrypt_without_peer_key(self):
        """Test that decrypting without peer key raises error"""
        with self.assertRaises(ValueError):
            self.alice.decrypt("unknown", "encrypted", "nonce")
    
    def test_image_encryption(self):
        """Test image encryption and decryption"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.bob.load_peer_public_key("alice", alice_pub)
        
        # Simulate image data
        image_data = b'\x89PNG\r\n\x1a\n' + os.urandom(1000)
        
        encrypted, nonce = self.alice.encrypt_image("bob", image_data)
        decrypted = self.bob.decrypt_image("alice", encrypted, nonce)
        
        self.assertEqual(image_data, decrypted)
    
    def test_image_encryption_large(self):
        """Test encryption of large image (1MB)"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.bob.load_peer_public_key("alice", alice_pub)
        
        image_data = os.urandom(1024 * 1024)  # 1MB
        encrypted, nonce = self.alice.encrypt_image("bob", image_data)
        decrypted = self.bob.decrypt_image("alice", encrypted, nonce)
        
        self.assertEqual(image_data, decrypted)
    
    def test_nonce_uniqueness(self):
        """Test that nonces are unique for each encryption"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        
        nonces = set()
        for _ in range(100):
            _, nonce = self.alice.encrypt("bob", "test")
            nonces.add(nonce)
        
        self.assertEqual(len(nonces), 100)  # All nonces should be unique


class TestChannelCrypto(unittest.TestCase):
    """Test channel (group) encryption"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.crypto = ChannelCrypto()
        self.crypto2 = ChannelCrypto()
    
    def test_channel_key_creation(self):
        """Test channel key creation"""
        key = self.crypto.create_channel_key("#test")
        self.assertIsNotNone(key)
        self.assertEqual(len(key), 44)  # Base64 of 32 bytes
    
    def test_channel_encryption(self):
        """Test channel message encryption"""
        channel = "#test"
        self.crypto.create_channel_key(channel)
        
        plaintext = "Hello channel!"
        encrypted, nonce = self.crypto.encrypt_for_channel(channel, plaintext)
        decrypted = self.crypto.decrypt_from_channel(channel, encrypted, nonce)
        
        self.assertEqual(plaintext, decrypted)
    
    def test_shared_channel_key(self):
        """Test that same key works for multiple users"""
        channel = "#test"
        key = self.crypto.create_channel_key(channel)
        
        # Second user loads the same key
        self.crypto2.load_channel_key(channel, key)
        
        # First user encrypts
        plaintext = "Message to channel"
        encrypted, nonce = self.crypto.encrypt_for_channel(channel, plaintext)
        
        # Second user decrypts
        decrypted = self.crypto2.decrypt_from_channel(channel, encrypted, nonce)
        
        self.assertEqual(plaintext, decrypted)
    
    def test_multiple_channels(self):
        """Test encryption for multiple channels"""
        channels = ["#test1", "#test2", "#test3"]
        
        for channel in channels:
            self.crypto.create_channel_key(channel)
        
        # Encrypt same message to all channels
        plaintext = "Multi-channel message"
        encrypted_messages = []
        
        for channel in channels:
            encrypted, nonce = self.crypto.encrypt_for_channel(channel, plaintext)
            encrypted_messages.append((encrypted, nonce))
        
        # All encryptions should be different
        encrypted_list = [e for e, n in encrypted_messages]
        self.assertEqual(len(encrypted_list), len(set(encrypted_list)))
        
        # All should decrypt correctly
        for i, channel in enumerate(channels):
            encrypted, nonce = encrypted_messages[i]
            decrypted = self.crypto.decrypt_from_channel(channel, encrypted, nonce)
            self.assertEqual(plaintext, decrypted)
    
    def test_channel_key_export_import(self):
        """Test that channel keys can be exported and imported"""
        channel = "#test"
        key = self.crypto.create_channel_key(channel)
        
        # Export and import
        self.crypto2.load_channel_key(channel, key)
        
        # Verify they work the same
        plaintext = "Test message"
        encrypted, nonce = self.crypto.encrypt_for_channel(channel, plaintext)
        decrypted = self.crypto2.decrypt_from_channel(channel, encrypted, nonce)
        
        self.assertEqual(plaintext, decrypted)
    
    def test_channel_without_key(self):
        """Test that operations without key raise error"""
        with self.assertRaises(ValueError):
            self.crypto.encrypt_for_channel("#nokey", "test")
        
        with self.assertRaises(ValueError):
            self.crypto.decrypt_from_channel("#nokey", "encrypted", "nonce")
    
    def test_invalid_channel_key(self):
        """Test that invalid key raises error"""
        with self.assertRaises(ValueError):
            self.crypto.load_channel_key("#test", "invalid_key")
    
    def test_channel_tampering_detection(self):
        """Test that tampering is detected in channel messages"""
        channel = "#test"
        self.crypto.create_channel_key(channel)
        
        plaintext = "Important channel message"
        encrypted, nonce = self.crypto.encrypt_for_channel(channel, plaintext)
        
        # Tamper with the ciphertext
        encrypted_bytes = base64.b64decode(encrypted)
        tampered_bytes = bytes([b ^ 1 for b in encrypted_bytes])
        tampered_encrypted = base64.b64encode(tampered_bytes).decode('utf-8')
        
        with self.assertRaises(ValueError):
            self.crypto.decrypt_from_channel(channel, tampered_encrypted, nonce)


if __name__ == '__main__':
    unittest.main()
