#!/usr/bin/env python3
"""
Test suite for JustIRC
Tests crypto layer, protocol, and basic functionality
"""

import unittest
import asyncio
import json
from crypto_layer import CryptoLayer, ChannelCrypto
from protocol import Protocol, MessageType


class TestCryptoLayer(unittest.TestCase):
    """Test cryptographic functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.alice = CryptoLayer()
        self.bob = CryptoLayer()
    
    def test_key_generation(self):
        """Test that keys are generated correctly"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.assertIsNotNone(alice_pub)
        self.assertIsNotNone(bob_pub)
        self.assertNotEqual(alice_pub, bob_pub)
        self.assertEqual(len(alice_pub), 44)  # Base64 of 32 bytes
    
    def test_key_exchange(self):
        """Test key exchange between two parties"""
        # Exchange public keys
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.bob.load_peer_public_key("alice", alice_pub)
        
        # Verify shared secrets exist
        self.assertTrue(self.alice.has_peer_key("bob"))
        self.assertTrue(self.bob.has_peer_key("alice"))
    
    def test_encryption_decryption(self):
        """Test message encryption and decryption"""
        # Exchange keys
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.bob.load_peer_public_key("alice", alice_pub)
        
        # Alice encrypts message to Bob
        plaintext = "Hello Bob, this is a secret message!"
        encrypted, nonce = self.alice.encrypt("bob", plaintext)
        
        # Bob decrypts message from Alice
        decrypted = self.bob.decrypt("alice", encrypted, nonce)
        
        self.assertEqual(plaintext, decrypted)
    
    def test_encryption_different_peers(self):
        """Test that encryption is different for different peers"""
        charlie = CryptoLayer()
        
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        charlie_pub = charlie.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.alice.load_peer_public_key("charlie", charlie_pub)
        
        plaintext = "Same message to both"
        
        encrypted_bob, nonce_bob = self.alice.encrypt("bob", plaintext)
        encrypted_charlie, nonce_charlie = self.alice.encrypt("charlie", plaintext)
        
        # Encrypted messages should be different
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
        import base64
        encrypted_bytes = base64.b64decode(encrypted)
        tampered_bytes = bytes([b ^ 1 for b in encrypted_bytes])
        tampered_encrypted = base64.b64encode(tampered_bytes).decode('utf-8')
        
        # Decryption should fail
        with self.assertRaises(ValueError):
            self.bob.decrypt("alice", tampered_encrypted, nonce)
    
    def test_image_encryption(self):
        """Test image encryption and decryption"""
        alice_pub = self.alice.get_public_key_b64()
        bob_pub = self.bob.get_public_key_b64()
        
        self.alice.load_peer_public_key("bob", bob_pub)
        self.bob.load_peer_public_key("alice", alice_pub)
        
        # Simulate image data
        image_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 1000  # Fake PNG header + data
        
        # Encrypt
        encrypted, nonce = self.alice.encrypt_image("bob", image_data)
        
        # Decrypt
        decrypted = self.bob.decrypt_image("alice", encrypted, nonce)
        
        self.assertEqual(image_data, decrypted)


class TestChannelCrypto(unittest.TestCase):
    """Test channel (group) encryption"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.crypto = ChannelCrypto()
    
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
        crypto2 = ChannelCrypto()
        crypto2.load_channel_key(channel, key)
        
        # First user encrypts
        plaintext = "Message to channel"
        encrypted, nonce = self.crypto.encrypt_for_channel(channel, plaintext)
        
        # Second user decrypts
        decrypted = crypto2.decrypt_from_channel(channel, encrypted, nonce)
        
        self.assertEqual(plaintext, decrypted)


class TestProtocol(unittest.TestCase):
    """Test protocol message building and parsing"""
    
    def test_register_message(self):
        """Test registration message"""
        msg = Protocol.register("alice", "public_key_data")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.REGISTER.value)
        self.assertEqual(parsed['nickname'], "alice")
        self.assertEqual(parsed['public_key'], "public_key_data")
    
    def test_encrypted_message(self):
        """Test encrypted message"""
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
    
    def test_ack_message(self):
        """Test acknowledgment message"""
        msg = Protocol.ack(True, "Success")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.ACK.value)
        self.assertTrue(parsed['success'])
        self.assertEqual(parsed['message'], "Success")
    
    def test_error_message(self):
        """Test error message"""
        msg = Protocol.error("Something went wrong")
        parsed = Protocol.parse_message(msg)
        
        self.assertEqual(parsed['type'], MessageType.ERROR.value)
        self.assertEqual(parsed['error'], "Something went wrong")
    
    def test_invalid_json(self):
        """Test that invalid JSON raises error"""
        with self.assertRaises(ValueError):
            Protocol.parse_message("not json")
    
    def test_missing_type(self):
        """Test that message without type raises error"""
        with self.assertRaises(ValueError):
            Protocol.parse_message('{"data": "test"}')


class TestEndToEnd(unittest.TestCase):
    """End-to-end encryption tests"""
    
    def test_full_conversation(self):
        """Test a full encrypted conversation"""
        # Create two users
        alice = CryptoLayer()
        bob = CryptoLayer()
        
        # Exchange keys
        alice_pub = alice.get_public_key_b64()
        bob_pub = bob.get_public_key_b64()
        
        alice.load_peer_public_key("bob", bob_pub)
        bob.load_peer_public_key("alice", alice_pub)
        
        # Alice sends message to Bob
        msg1 = "Hello Bob!"
        encrypted1, nonce1 = alice.encrypt("bob", msg1)
        protocol_msg1 = Protocol.encrypted_message("alice", "bob", encrypted1, nonce1)
        
        # Bob receives and decrypts
        parsed1 = Protocol.parse_message(protocol_msg1)
        decrypted1 = bob.decrypt(
            parsed1['from_id'],
            parsed1['encrypted_data'],
            parsed1['nonce']
        )
        self.assertEqual(msg1, decrypted1)
        
        # Bob replies
        msg2 = "Hi Alice, nice to hear from you!"
        encrypted2, nonce2 = bob.encrypt("alice", msg2)
        protocol_msg2 = Protocol.encrypted_message("bob", "alice", encrypted2, nonce2)
        
        # Alice receives and decrypts
        parsed2 = Protocol.parse_message(protocol_msg2)
        decrypted2 = alice.decrypt(
            parsed2['from_id'],
            parsed2['encrypted_data'],
            parsed2['nonce']
        )
        self.assertEqual(msg2, decrypted2)


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestCryptoLayer))
    suite.addTests(loader.loadTestsFromTestCase(TestChannelCrypto))
    suite.addTests(loader.loadTestsFromTestCase(TestProtocol))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEnd))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success status
    return result.wasSuccessful()


if __name__ == '__main__':
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
