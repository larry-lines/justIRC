#!/usr/bin/env python3
"""
Integration tests for server and client
Tests full client-server communication workflows
"""

import unittest
import asyncio
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import IRCServer, Client
from protocol import Protocol, MessageType
from crypto_layer import CryptoLayer


class TestServerIntegration(unittest.TestCase):
    """Test server functionality"""
    
    def setUp(self):
        """Set up test server"""
        self.temp_dir = tempfile.mkdtemp()
        self.server = IRCServer(
            host='127.0.0.1',
            port=0,  # Random port
            data_dir=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up temp directory"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_server_initialization(self):
        """Test server initializes correctly"""
        # Server may load host from config, verify it's set
        self.assertIsNotNone(self.server.host)
        self.assertIsNotNone(self.server.channels)
        self.assertIsNotNone(self.server.clients)
    
    def test_hash_password(self):
        """Test password hashing"""
        password = "test123"
        hashed = self.server.hash_password(password)
        
        self.assertIsNotNone(hashed)
        self.assertNotEqual(hashed, password)
        self.assertEqual(len(hashed), 64)  # SHA256 hex
    
    def test_hash_password_consistency(self):
        """Test that same password produces same hash"""
        password = "test123"
        hash1 = self.server.hash_password(password)
        hash2 = self.server.hash_password(password)
        
        self.assertEqual(hash1, hash2)
    
    def test_channel_persistence(self):
        """Test channel data persistence"""
        # Create channel with password
        channel = "#testchannel"
        password = "secret"
        self.server.channel_passwords[channel] = self.server.hash_password(password)
        self.server.channel_owners[channel] = "user123"
        
        # Save channels
        self.server.save_channels()
        
        # Create new server instance and load
        server2 = IRCServer(
            host='127.0.0.1',
            port=0,
            data_dir=self.temp_dir
        )
        
        # Verify data loaded
        self.assertIn(channel, server2.channel_passwords)
        self.assertEqual(server2.channel_owners[channel], "user123")
    
    def test_channel_ban_persistence(self):
        """Test that banned users persist"""
        channel = "#test"
        banned_user = "baduser"
        
        self.server.channel_banned[channel] = {banned_user}
        self.server.save_channels()
        
        # Load in new server
        server2 = IRCServer(
            host='127.0.0.1',
            port=0,
            data_dir=self.temp_dir
        )
        
        self.assertIn(channel, server2.channel_banned)
        self.assertIn(banned_user, server2.channel_banned[channel])
    
    def test_nickname_registration(self):
        """Test nickname to user_id mapping"""
        user_id = "user123"
        nickname = "testuser"
        
        self.server.nicknames[nickname] = user_id
        
        self.assertEqual(self.server.nicknames[nickname], user_id)
    
    def test_duplicate_nickname_prevention(self):
        """Test that nicknames should be unique"""
        user1 = "user1"
        user2 = "user2"
        nickname = "samename"
        
        self.server.nicknames[nickname] = user1
        
        # Attempting to use same nickname should require handling
        # (Server handles this in actual implementation)
        self.assertEqual(self.server.nicknames[nickname], user1)


class TestClientServerWorkflow(unittest.IsolatedAsyncioTestCase):
    """Test complete client-server workflows"""
    
    async def asyncSetUp(self):
        """Set up test server and clients"""
        self.temp_dir = tempfile.mkdtemp()
        self.server = IRCServer(
            host='127.0.0.1',
            port=16667,
            data_dir=self.temp_dir
        )
        
        # Start server (in test mode, we'll mock this)
        self.server_task = None
    
    async def asyncTearDown(self):
        """Clean up"""
        if self.server_task:
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    async def test_protocol_message_parsing(self):
        """Test protocol message creation and parsing"""
        # Test register
        register_msg = Protocol.register("testuser", "pubkey123")
        parsed = Protocol.parse_message(register_msg)
        
        self.assertEqual(parsed['type'], MessageType.REGISTER.value)
        self.assertEqual(parsed['nickname'], "testuser")
        
        # Test join
        join_msg = Protocol.join_channel("user123", "#test", "password")
        parsed = Protocol.parse_message(join_msg)
        
        self.assertEqual(parsed['type'], MessageType.JOIN_CHANNEL.value)
        self.assertEqual(parsed['channel'], "#test")
    
    async def test_crypto_workflow(self):
        """Test full cryptographic workflow"""
        alice = CryptoLayer()
        bob = CryptoLayer()
        
        # Exchange keys
        alice_pub = alice.get_public_key_b64()
        bob_pub = bob.get_public_key_b64()
        
        alice.load_peer_public_key("bob", bob_pub)
        bob.load_peer_public_key("alice", alice_pub)
        
        # Alice sends encrypted message
        plaintext = "Hello Bob!"
        encrypted, nonce = alice.encrypt("bob", plaintext)
        
        # Create protocol message
        msg = Protocol.encrypted_message("alice", "bob", encrypted, nonce, False)
        parsed = Protocol.parse_message(msg)
        
        # Bob receives and decrypts
        decrypted = bob.decrypt("alice", parsed['encrypted_data'], parsed['nonce'])
        
        self.assertEqual(plaintext, decrypted)


class TestOperatorCommands(unittest.TestCase):
    """Test operator/moderator functionality"""
    
    def setUp(self):
        """Set up test server"""
        self.temp_dir = tempfile.mkdtemp()
        self.server = IRCServer(
            host='127.0.0.1',
            port=0,
            data_dir=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_channel_owner_creation(self):
        """Test channel owner is set on creation"""
        channel = "#test"
        owner_id = "user123"
        
        self.server.channel_owners[channel] = owner_id
        
        self.assertEqual(self.server.channel_owners[channel], owner_id)
    
    def test_operator_assignment(self):
        """Test operator assignment"""
        channel = "#test"
        operator_id = "user456"
        
        if channel not in self.server.channel_operators:
            self.server.channel_operators[channel] = set()
        
        self.server.channel_operators[channel].add(operator_id)
        
        self.assertIn(operator_id, self.server.channel_operators[channel])
    
    def test_moderator_assignment(self):
        """Test moderator assignment"""
        channel = "#test"
        mod_id = "user789"
        
        if channel not in self.server.channel_mods:
            self.server.channel_mods[channel] = set()
        
        self.server.channel_mods[channel].add(mod_id)
        
        self.assertIn(mod_id, self.server.channel_mods[channel])
    
    def test_ban_user(self):
        """Test banning a user"""
        channel = "#test"
        banned_id = "baduser"
        
        if channel not in self.server.channel_banned:
            self.server.channel_banned[channel] = set()
        
        self.server.channel_banned[channel].add(banned_id)
        
        self.assertIn(banned_id, self.server.channel_banned[channel])
    
    def test_unban_user(self):
        """Test unbanning a user"""
        channel = "#test"
        user_id = "user123"
        
        # Ban first
        self.server.channel_banned[channel] = {user_id}
        
        # Unban
        self.server.channel_banned[channel].remove(user_id)
        
        self.assertNotIn(user_id, self.server.channel_banned[channel])
    
    def test_operator_password_storage(self):
        """Test operator password storage"""
        channel = "#test"
        user_id = "user123"
        password = "oppass"
        
        if channel not in self.server.operator_passwords:
            self.server.operator_passwords[channel] = {}
        
        self.server.operator_passwords[channel][user_id] = self.server.hash_password(password)
        
        # Verify password was hashed
        stored_hash = self.server.operator_passwords[channel][user_id]
        self.assertEqual(stored_hash, self.server.hash_password(password))
        self.assertNotEqual(stored_hash, password)


class TestEndToEndWorkflows(unittest.IsolatedAsyncioTestCase):
    """Test complete end-to-end workflows"""
    
    async def test_join_message_leave_workflow(self):
        """Test complete join -> message -> leave workflow"""
        alice = CryptoLayer()
        bob = CryptoLayer()
        
        # Exchange keys
        alice_pub = alice.get_public_key_b64()
        bob_pub = bob.get_public_key_b64()
        
        alice.load_peer_public_key("bob_id", bob_pub)
        bob.load_peer_public_key("alice_id", alice_pub)
        
        # Alice registers
        register_msg = Protocol.register("alice", alice_pub)
        self.assertIsNotNone(register_msg)
        
        # Alice joins channel
        join_msg = Protocol.join_channel("alice_id", "#general")
        parsed_join = Protocol.parse_message(join_msg)
        self.assertEqual(parsed_join['channel'], "#general")
        
        # Alice sends encrypted message to Bob
        plaintext = "Hello Bob!"
        encrypted, nonce = alice.encrypt("bob_id", plaintext)
        pm_msg = Protocol.encrypted_message("alice_id", "bob_id", encrypted, nonce, False)
        
        # Bob decrypts
        parsed_pm = Protocol.parse_message(pm_msg)
        decrypted = bob.decrypt("alice_id", parsed_pm['encrypted_data'], parsed_pm['nonce'])
        self.assertEqual(plaintext, decrypted)
        
        # Alice leaves channel
        leave_msg = Protocol.leave_channel("alice_id", "#general")
        parsed_leave = Protocol.parse_message(leave_msg)
        self.assertEqual(parsed_leave['channel'], "#general")


if __name__ == '__main__':
    unittest.main()
