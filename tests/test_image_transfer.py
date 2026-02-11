#!/usr/bin/env python3
"""
Tests for image_transfer.py
Tests image chunking, encryption, and transfer
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_layer import CryptoLayer
from image_transfer import ImageTransfer


class TestImageTransfer(unittest.TestCase):
    """Test image transfer functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.alice_crypto = CryptoLayer()
        self.bob_crypto = CryptoLayer()
        
        # Exchange keys
        alice_pub = self.alice_crypto.get_public_key_b64()
        bob_pub = self.bob_crypto.get_public_key_b64()
        
        self.alice_crypto.load_peer_public_key("bob", bob_pub)
        self.bob_crypto.load_peer_public_key("alice", alice_pub)
        
        self.alice_transfer = ImageTransfer(self.alice_crypto)
        self.bob_transfer = ImageTransfer(self.bob_crypto)
    
    def test_image_chunking_small(self):
        """Test chunking of small image"""
        image_data = b"Small image data"
        chunks = self.alice_transfer.chunk_image(image_data)
        
        self.assertGreater(len(chunks), 0)
        
        # Reassemble
        reassembled = b''.join(chunks)
        self.assertEqual(image_data, reassembled)
    
    def test_image_chunking_large(self):
        """Test chunking of large image (1MB)"""
        image_data = os.urandom(1024 * 1024)
        chunks = self.alice_transfer.chunk_image(image_data)
        
        self.assertGreater(len(chunks), 1)
        
        # Reassemble
        reassembled = b''.join(chunks)
        self.assertEqual(image_data, reassembled)
    
    def test_image_encryption_decryption(self):
        """Test full image encryption and decryption"""
        image_data = os.urandom(50000)  # 50KB image
        
        # Encrypt chunks
        encrypted_chunks = []
        nonces = []
        
        for chunk in self.alice_transfer.chunk_image(image_data):
            encrypted, nonce = self.alice_crypto.encrypt_image("bob", chunk)
            encrypted_chunks.append(encrypted)
            nonces.append(nonce)
        
        # Decrypt chunks
        decrypted_chunks = []
        for encrypted, nonce in zip(encrypted_chunks, nonces):
            decrypted = self.bob_crypto.decrypt_image("alice", encrypted, nonce)
            decrypted_chunks.append(decrypted)
        
        # Reassemble
        reassembled = b''.join(decrypted_chunks)
        self.assertEqual(image_data, reassembled)
    
    def test_chunk_size_consistency(self):
        """Test that all chunks except last are same size"""
        image_data = os.urandom(100000)  # 100KB
        chunks = self.alice_transfer.chunk_image(image_data)
        
        # All chunks except last should be same size
        chunk_size = len(chunks[0])
        for i in range(len(chunks) - 1):
            self.assertEqual(len(chunks[i]), chunk_size)
        
        # Last chunk can be smaller or equal
        self.assertLessEqual(len(chunks[-1]), chunk_size)
    
    def test_empty_image(self):
        """Test handling of empty image"""
        image_data = b""
        chunks = self.alice_transfer.chunk_image(image_data)
        
        # Should have at least one chunk (even if empty)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], b"")
    
    def test_single_byte_image(self):
        """Test handling of single byte image"""
        image_data = b"A"
        chunks = self.alice_transfer.chunk_image(image_data)
        
        reassembled = b''.join(chunks)
        self.assertEqual(image_data, reassembled)
    
    def test_exact_chunk_size(self):
        """Test image that exactly matches chunk size"""
        chunk_size = self.alice_transfer.CHUNK_SIZE
        image_data = os.urandom(chunk_size)
        chunks = self.alice_transfer.chunk_image(image_data)
        
        # Should have 1 or 2 chunks (implementation specific)
        self.assertGreaterEqual(len(chunks), 1)
        reassembled = b''.join(chunks)
        self.assertEqual(image_data, reassembled)
    
    def test_multiple_of_chunk_size(self):
        """Test image that is multiple of chunk size"""
        chunk_size = self.alice_transfer.CHUNK_SIZE
        image_data = os.urandom(chunk_size * 3)
        chunks = self.alice_transfer.chunk_image(image_data)
        
        # Should have at least 3 chunks
        self.assertGreaterEqual(len(chunks), 3)
        reassembled = b''.join(chunks)
        self.assertEqual(image_data, reassembled)


if __name__ == '__main__':
    unittest.main()
