"""
Cryptographic layer for JustIRC
Handles all encryption, decryption, and key management
Uses X25519 for key exchange and ChaCha20-Poly1305 for encryption
"""

import os
import base64
import json
import time
from typing import Tuple, Dict, Optional
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class CryptoLayer:
    """Handles all cryptographic operations"""
    
    def __init__(self, key_rotation_interval: float = 3600.0, max_messages_per_key: int = 10000):
        """
        Initialize crypto layer with new key pair
        
        Args:
            key_rotation_interval: Time in seconds before key rotation is recommended
            max_messages_per_key: Max messages before key rotation is forced
        """
        # Generate long-term identity key pair
        self.private_key = X25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        
        # Store shared secrets for different peers
        self.shared_secrets: Dict[str, bytes] = {}
        
        # Store public keys of peers
        self.peer_public_keys: Dict[str, X25519PublicKey] = {}
        
        # Key rotation tracking
        self.key_rotation_interval = key_rotation_interval
        self.max_messages_per_key = max_messages_per_key
        self.peer_key_timestamp: Dict[str, float] = {}  # peer_id -> timestamp
        self.peer_message_count: Dict[str, int] = {}  # peer_id -> message count
        
        # Channel (group) encryption keys
        self.channel_keys: Dict[str, bytes] = {}
    
    def get_public_key_bytes(self) -> bytes:
        """Get public key as bytes"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def get_public_key_b64(self) -> str:
        """Get public key as base64 string"""
        return base64.b64encode(self.get_public_key_bytes()).decode('utf-8')
    
    def load_peer_public_key(self, peer_id: str, public_key_b64: str):
        """Load a peer's public key from base64"""
        try:
            public_key_bytes = base64.b64decode(public_key_b64)
            peer_public_key = X25519PublicKey.from_public_bytes(public_key_bytes)
            self.peer_public_keys[peer_id] = peer_public_key
            
            # Initialize rotation tracking
            self.peer_key_timestamp[peer_id] = time.time()
            self.peer_message_count[peer_id] = 0
            
            # Immediately compute shared secret
            self._compute_shared_secret(peer_id)
        except Exception as e:
            raise ValueError(f"Failed to load peer public key: {e}")
    
    def _compute_shared_secret(self, peer_id: str):
        """Compute shared secret with a peer using ECDH"""
        if peer_id not in self.peer_public_keys:
            raise ValueError(f"Public key for {peer_id} not found")
        
        peer_public_key = self.peer_public_keys[peer_id]
        
        # Perform ECDH key exchange
        shared_key = self.private_key.exchange(peer_public_key)
        
        # Derive a proper encryption key using HKDF
        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'JustIRC-E2E-Encryption'
        ).derive(shared_key)
        
        self.shared_secrets[peer_id] = derived_key
    
    def encrypt(self, peer_id: str, plaintext: str) -> Tuple[str, str]:
        """
        Encrypt data for a specific peer
        Returns: (encrypted_data_b64, nonce_b64)
        """
        # Increment message count for potential rotation
        if peer_id in self.peer_message_count:
            self.peer_message_count[peer_id] += 1
        
        if peer_id not in self.shared_secrets:
            raise ValueError(f"No shared secret with {peer_id}. Exchange keys first.")
        
        # Generate random nonce
        nonce = os.urandom(12)  # 96-bit nonce for ChaCha20Poly1305
        
        # Encrypt with ChaCha20Poly1305
        cipher = ChaCha20Poly1305(self.shared_secrets[peer_id])
        ciphertext = cipher.encrypt(nonce, plaintext.encode('utf-8'), None)
        
        # Return base64 encoded
        return (
            base64.b64encode(ciphertext).decode('utf-8'),
            base64.b64encode(nonce).decode('utf-8')
        )
    
    def decrypt(self, peer_id: str, encrypted_data_b64: str, nonce_b64: str) -> str:
        """
        Decrypt data from a specific peer
        Returns: decrypted plaintext
        """
        if peer_id not in self.shared_secrets:
            raise ValueError(f"No shared secret with {peer_id}. Exchange keys first.")
        
        # Decode from base64
        ciphertext = base64.b64decode(encrypted_data_b64)
        nonce = base64.b64decode(nonce_b64)
        
        # Decrypt with ChaCha20Poly1305
        cipher = ChaCha20Poly1305(self.shared_secrets[peer_id])
        try:
            plaintext = cipher.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")
    
    def encrypt_image(self, peer_id: str, image_data: bytes) -> Tuple[bytes, str]:
        """
        Encrypt image data for a specific peer
        Returns: (encrypted_data, nonce_b64)
        """
        if peer_id not in self.shared_secrets:
            raise ValueError(f"No shared secret with {peer_id}. Exchange keys first.")
        
        # Generate random nonce
        nonce = os.urandom(12)
        
        # Encrypt with ChaCha20Poly1305
        cipher = ChaCha20Poly1305(self.shared_secrets[peer_id])
        ciphertext = cipher.encrypt(nonce, image_data, None)
        
        return (ciphertext, base64.b64encode(nonce).decode('utf-8'))
    
    def decrypt_image(self, peer_id: str, encrypted_data: bytes, nonce_b64: str) -> bytes:
        """
        Decrypt image data from a specific peer
        Returns: decrypted image data
        """
        if peer_id not in self.shared_secrets:
            raise ValueError(f"No shared secret with {peer_id}. Exchange keys first.")
        
        nonce = base64.b64decode(nonce_b64)
        
        # Decrypt with ChaCha20Poly1305
        cipher = ChaCha20Poly1305(self.shared_secrets[peer_id])
        try:
            plaintext = cipher.decrypt(nonce, encrypted_data, None)
            return plaintext
        except Exception as e:
            raise ValueError(f"Image decryption failed: {e}")
    
    def has_peer_key(self, peer_id: str) -> bool:
        """Check if we have a peer's public key"""
        return peer_id in self.peer_public_keys
    
    def should_rotate_key(self, peer_id: str) -> bool:
        """
        Check if key rotation is needed for a peer
        
        Args:
            peer_id: Peer to check
            
        Returns:
            True if key should be rotated
        """
        if peer_id not in self.peer_key_timestamp:
            return False
        
        # Check time-based rotation
        time_elapsed = time.time() - self.peer_key_timestamp[peer_id]
        if time_elapsed >= self.key_rotation_interval:
            return True
        
        # Check message-count-based rotation
        if peer_id in self.peer_message_count:
            if self.peer_message_count[peer_id] >= self.max_messages_per_key:
                return True
        
        return False
    
    def get_rotation_reason(self, peer_id: str) -> Optional[str]:
        """
        Get human-readable reason for key rotation
        
        Args:
            peer_id: Peer to check
            
        Returns:
            Reason string or None if no rotation needed
        """
        if not self.should_rotate_key(peer_id):
            return None
        
        if peer_id not in self.peer_key_timestamp:
            return None
        
        time_elapsed = time.time() - self.peer_key_timestamp[peer_id]
        if time_elapsed >= self.key_rotation_interval:
            return f"Time limit reached ({time_elapsed/60:.1f} minutes)"
        
        if peer_id in self.peer_message_count:
            if self.peer_message_count[peer_id] >= self.max_messages_per_key:
                return f"Message limit reached ({self.peer_message_count[peer_id]} messages)"
        
        return "Unknown reason"
    
    def rotate_key_for_peer(self, peer_id: str):
        """
        Rotate encryption key for a peer (reinitialize with new ephemeral key)
        This maintains the same public key exchange but derives a new shared secret
        
        Args:
            peer_id: Peer to rotate key for
        """
        if peer_id not in self.peer_public_keys:
            raise ValueError(f"No public key for {peer_id}")
        
        # Recompute shared secret (in practice, would generate new ephemeral key)
        # For simplicity, we'll regenerate the entire key pair
        self.private_key = X25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        
        # Recompute all shared secrets with new key
        for pid in list(self.peer_public_keys.keys()):
            self._compute_shared_secret(pid)
            self.peer_key_timestamp[pid] = time.time()
            self.peer_message_count[pid] = 0
    
    def get_key_stats(self, peer_id: str) -> Dict[str, any]:
        """
        Get statistics about a peer's key
        
        Args:
            peer_id: Peer to get stats for
            
        Returns:
            Dictionary with key statistics
        """
        if peer_id not in self.peer_key_timestamp:
            return {}
        
        time_elapsed = time.time() - self.peer_key_timestamp[peer_id]
        message_count = self.peer_message_count.get(peer_id, 0)
        
        return {
            "peer_id": peer_id,
            "key_age_seconds": time_elapsed,
            "key_age_minutes": time_elapsed / 60,
            "message_count": message_count,
            "should_rotate": self.should_rotate_key(peer_id),
            "rotation_reason": self.get_rotation_reason(peer_id),
            "time_until_rotation": max(0, self.key_rotation_interval - time_elapsed),
            "messages_until_rotation": max(0, self.max_messages_per_key - message_count)
        }
    
    def remove_peer(self, peer_id: str):
        """Remove peer's keys and secrets (for perfect forward secrecy)"""
        if peer_id in self.shared_secrets:
            del self.shared_secrets[peer_id]
        if peer_id in self.peer_public_keys:
            del self.peer_public_keys[peer_id]
        # Also clean up rotation tracking
        if peer_id in self.peer_key_timestamp:
            del self.peer_key_timestamp[peer_id]
        if peer_id in self.peer_message_count:
            del self.peer_message_count[peer_id]
    
    def create_channel_key(self, channel: str) -> str:
        """Create a new channel key and return it as base64"""
        key = ChaCha20Poly1305.generate_key()
        self.channel_keys[channel] = key
        return base64.b64encode(key).decode('utf-8')
    
    def load_channel_key(self, channel: str, key_b64: str):
        """Load a channel key from base64"""
        key = base64.b64decode(key_b64)
        self.channel_keys[channel] = key
    
    def encrypt_for_channel(self, channel: str, plaintext: str) -> Tuple[str, str]:
        """Encrypt message for a channel"""
        if channel not in self.channel_keys:
            raise ValueError(f"No key for channel {channel}")
        
        nonce = os.urandom(12)
        cipher = ChaCha20Poly1305(self.channel_keys[channel])
        ciphertext = cipher.encrypt(nonce, plaintext.encode('utf-8'), None)
        
        return (
            base64.b64encode(ciphertext).decode('utf-8'),
            base64.b64encode(nonce).decode('utf-8')
        )
    
    def decrypt_from_channel(self, channel: str, encrypted_data_b64: str, nonce_b64: str) -> str:
        """Decrypt message from a channel"""
        if channel not in self.channel_keys:
            raise ValueError(f"No key for channel {channel}")
        
        ciphertext = base64.b64decode(encrypted_data_b64)
        nonce = base64.b64decode(nonce_b64)
        
        cipher = ChaCha20Poly1305(self.channel_keys[channel])
        try:
            plaintext = cipher.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Channel decryption failed: {e}")


class ChannelCrypto:
    """Handles channel (group) encryption with a shared key"""
    
    def __init__(self):
        self.channel_keys: Dict[str, bytes] = {}
    
    def create_channel_key(self, channel: str) -> str:
        """Create a new channel key and return it as base64"""
        key = ChaCha20Poly1305.generate_key()
        self.channel_keys[channel] = key
        return base64.b64encode(key).decode('utf-8')
    
    def load_channel_key(self, channel: str, key_b64: str):
        """Load a channel key from base64"""
        key = base64.b64decode(key_b64)
        self.channel_keys[channel] = key
    
    def encrypt_for_channel(self, channel: str, plaintext: str) -> Tuple[str, str]:
        """Encrypt message for a channel"""
        if channel not in self.channel_keys:
            raise ValueError(f"No key for channel {channel}")
        
        nonce = os.urandom(12)
        cipher = ChaCha20Poly1305(self.channel_keys[channel])
        ciphertext = cipher.encrypt(nonce, plaintext.encode('utf-8'), None)
        
        return (
            base64.b64encode(ciphertext).decode('utf-8'),
            base64.b64encode(nonce).decode('utf-8')
        )
    
    def decrypt_from_channel(self, channel: str, encrypted_data_b64: str, nonce_b64: str) -> str:
        """Decrypt message from a channel"""
        if channel not in self.channel_keys:
            raise ValueError(f"No key for channel {channel}")
        
        ciphertext = base64.b64decode(encrypted_data_b64)
        nonce = base64.b64decode(nonce_b64)
        
        cipher = ChaCha20Poly1305(self.channel_keys[channel])
        try:
            plaintext = cipher.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Channel decryption failed: {e}")
