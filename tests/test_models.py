"""
Tests for data models (models.py)

Tests the domain models with no external dependencies.
"""

import unittest
from datetime import datetime
from models import (
    User, Channel, Message, ClientState, UserStatus,
    ConnectionConfig, ImageTransferState, NotificationEvent
)


class TestUser(unittest.TestCase):
    """Test User model"""
    
    def test_create_user(self):
        """Test creating a user"""
        user = User(
            user_id="user123",
            nickname="TestUser",
            public_key="key123"
        )
        
        self.assertEqual(user.user_id, "user123")
        self.assertEqual(user.nickname, "TestUser")
        self.assertEqual(user.public_key, "key123")
        self.assertEqual(user.status, UserStatus.ONLINE)
        self.assertEqual(user.status_message, "")
    
    def test_user_with_status(self):
        """Test user with custom status"""
        user = User(
            user_id="user123",
            nickname="TestUser",
            public_key="key123",
            status=UserStatus.AWAY,
            status_message="Out for lunch"
        )
        
        self.assertEqual(user.status, UserStatus.AWAY)
        self.assertEqual(user.status_message, "Out for lunch")
    
    def test_is_online(self):
        """Test is_online method"""
        user_online = User("1", "User1", "key1", status=UserStatus.ONLINE)
        user_offline = User("2", "User2", "key2", status=UserStatus.OFFLINE)
        user_away = User("3", "User3", "key3", status=UserStatus.AWAY)
        
        self.assertTrue(user_online.is_online())
        self.assertFalse(user_offline.is_online())
        self.assertTrue(user_away.is_online())  # Away is still "online"
    
    def test_update_status(self):
        """Test updating user status"""
        user = User("1", "User1", "key1")
        
        user.update_status(UserStatus.BUSY, "In a meeting")
        
        self.assertEqual(user.status, UserStatus.BUSY)
        self.assertEqual(user.status_message, "In a meeting")


class TestChannel(unittest.TestCase):
    """Test Channel model"""
    
    def test_create_channel(self):
        """Test creating a channel"""
        channel = Channel(name="#general")
        
        self.assertEqual(channel.name, "#general")
        self.assertFalse(channel.password_protected)
        self.assertEqual(channel.topic, "")
        self.assertEqual(len(channel.members), 0)
        self.assertEqual(len(channel.operators), 0)
    
    def test_channel_with_properties(self):
        """Test channel with custom properties"""
        channel = Channel(
            name="#private",
            password_protected=True,
            topic="Private channel",
            modes={'m': True, 't': True}
        )
        
        self.assertTrue(channel.password_protected)
        self.assertEqual(channel.topic, "Private channel")
        self.assertTrue(channel.modes['m'])
        self.assertTrue(channel.modes['t'])
    
    def test_add_member(self):
        """Test adding members to channel"""
        channel = Channel(name="#test")
        
        channel.add_member("User1")
        channel.add_member("User2")
        
        self.assertEqual(len(channel.members), 2)
        self.assertIn("User1", channel.members)
        self.assertIn("User2", channel.members)
    
    def test_remove_member(self):
        """Test removing members from channel"""
        channel = Channel(name="#test")
        channel.add_member("User1")
        channel.add_member("User2")
        
        channel.remove_member("User1")
        
        self.assertEqual(len(channel.members), 1)
        self.assertNotIn("User1", channel.members)
        self.assertIn("User2", channel.members)
    
    def test_is_operator(self):
        """Test operator checking"""
        channel = Channel(name="#test")
        channel.operators.add("Operator1")
        
        self.assertTrue(channel.is_operator("Operator1"))
        self.assertFalse(channel.is_operator("User1"))
    
    def test_member_count(self):
        """Test member count"""
        channel = Channel(name="#test")
        
        self.assertEqual(channel.member_count(), 0)
        
        channel.add_member("User1")
        channel.add_member("User2")
        channel.add_member("User3")
        
        self.assertEqual(channel.member_count(), 3)


class TestMessage(unittest.TestCase):
    """Test Message model"""
    
    def test_create_message(self):
        """Test creating a message"""
        msg = Message(
            message_type="PRIVMSG",
            sender="User1",
            content="Hello, world!"
        )
        
        self.assertEqual(msg.message_type, "PRIVMSG")
        self.assertEqual(msg.sender, "User1")
        self.assertEqual(msg.content, "Hello, world!")
        self.assertIsInstance(msg.timestamp, datetime)
        self.assertFalse(msg.encrypted)
    
    def test_channel_message(self):
        """Test channel message"""
        msg = Message(
            message_type="CHANNEL",
            sender="User1",
            content="Hello channel!",
            recipient="#general"
        )
        
        self.assertEqual(msg.message_type, "CHANNEL")
        self.assertEqual(msg.recipient, "#general")
    
    def test_encrypted_message(self):
        """Test encrypted message"""
        msg = Message(
            message_type="PRIVMSG",
            sender="User1",
            content="Secret message",
            encrypted=True
        )
        
        self.assertTrue(msg.encrypted)
    
    def test_message_with_metadata(self):
        """Test message with metadata"""
        msg = Message(
            message_type="PRIVMSG",
            sender="User1",
            content="Test",
            metadata={"priority": "high", "read": False}
        )
        
        self.assertEqual(msg.metadata["priority"], "high")
        self.assertFalse(msg.metadata["read"])


class TestClientState(unittest.TestCase):
    """Test ClientState model"""
    
    def test_create_state(self):
        """Test creating client state"""
        state = ClientState()
        
        self.assertFalse(state.connected)
        self.assertIsNone(state.user_id)
        self.assertIsNone(state.nickname)
        self.assertIsNone(state.current_channel)
        self.assertEqual(len(state.users), 0)
        self.assertEqual(len(state.channels), 0)
    
    def test_connected_state(self):
        """Test connected state"""
        state = ClientState(
            connected=True,
            user_id="user123",
            nickname="TestUser"
        )
        
        self.assertTrue(state.connected)
        self.assertEqual(state.user_id, "user123")
        self.assertEqual(state.nickname, "TestUser")
    
    def test_state_with_users_and_channels(self):
        """Test state with users and channels"""
        user1 = User("1", "User1", "key1")
        user2 = User("2", "User2", "key2")
        channel = Channel("#general")
        
        state = ClientState(
            connected=True,
            users={"User1": user1, "User2": user2},
            channels={"#general": channel}
        )
        
        self.assertEqual(len(state.users), 2)
        self.assertEqual(len(state.channels), 1)
        self.assertIn("User1", state.users)
        self.assertIn("#general", state.channels)
    
    def test_joined_channels(self):
        """Test joined channels tracking"""
        state = ClientState(
            joined_channels={"#general", "#random"}
        )
        
        self.assertEqual(len(state.joined_channels), 2)
        self.assertIn("#general", state.joined_channels)
        self.assertIn("#random", state.joined_channels)
    
    def test_blocked_users(self):
        """Test blocked users tracking"""
        state = ClientState(
            blocked_users={"BadUser1", "BadUser2"}
        )
        
        self.assertEqual(len(state.blocked_users), 2)
        self.assertIn("BadUser1", state.blocked_users)
        self.assertIn("BadUser2", state.blocked_users)


class TestConnectionConfig(unittest.TestCase):
    """Test ConnectionConfig model"""
    
    def test_create_config(self):
        """Test creating connection config"""
        config = ConnectionConfig(
            host="localhost",
            port=6667,
            nickname="TestUser"
        )
        
        self.assertEqual(config.host, "localhost")
        self.assertEqual(config.port, 6667)
        self.assertEqual(config.nickname, "TestUser")
        self.assertFalse(config.use_auth)
        self.assertIsNone(config.password)
    
    def test_config_with_auth(self):
        """Test config with authentication enabled"""
        config = ConnectionConfig(
            host="irc.example.com",
            port=6697,
            nickname="SecureUser",
            use_auth=True,
            password="secret123"
        )
        
        self.assertTrue(config.use_auth)
        self.assertEqual(config.password, "secret123")


class TestImageTransferState(unittest.TestCase):
    """Test ImageTransferState model"""
    
    def test_create_transfer_state(self):
        """Test creating transfer state"""
        state = ImageTransferState(
            image_id="img123",
            from_user_id="user1",
            from_nickname="User1",
            filename="image.png",
            file_size=1024,
            mime_type="image/png",
            total_chunks=10
        )
        
        self.assertEqual(state.image_id, "img123")
        self.assertEqual(state.total_chunks, 10)
        self.assertEqual(state.from_nickname, "User1")
        self.assertEqual(state.received_chunks, 0)
    
    def test_transfer_progress(self):
        """Test transfer progress calculation"""
        state = ImageTransferState(
            image_id="img123",
            from_user_id="user1",
            from_nickname="User1",
            filename="image.png",
            file_size=1024,
            mime_type="image/png",
            total_chunks=10,
            received_chunks=5
        )
        
        # Progress should be 50%
        expected_progress = 50.0
        self.assertEqual(state.progress_percentage(), expected_progress)
    
    def test_transfer_complete(self):
        """Test transfer completion check"""
        state = ImageTransferState(
            image_id="img123",
            from_user_id="user1",
            from_nickname="User1",
            filename="image.png",
            file_size=1024,
            mime_type="image/png",
            total_chunks=3,
            received_chunks=3
        )
        
        self.assertTrue(state.is_complete())
    
    def test_transfer_incomplete(self):
        """Test incomplete transfer"""
        state = ImageTransferState(
            image_id="img123",
            from_user_id="user1",
            from_nickname="User1",
            filename="image.png",
            file_size=1024,
            mime_type="image/png",
            total_chunks=5,
            received_chunks=3
        )
        
        self.assertFalse(state.is_complete())
        self.assertEqual(state.progress_percentage(), 60.0)


class TestNotificationEvent(unittest.TestCase):
    """Test NotificationEvent model"""
    
    def test_create_notification(self):
        """Test creating notification"""
        notification = NotificationEvent(
            title="New Message",
            message="You have a new message from User1"
        )
        
        self.assertEqual(notification.title, "New Message")
        self.assertEqual(notification.message, "You have a new message from User1")
        self.assertEqual(notification.priority, "normal")
    
    def test_high_priority_notification(self):
        """Test high priority notification"""
        notification = NotificationEvent(
            title="Urgent",
            message="Server shutting down in 5 minutes",
            priority="high"
        )
        
        self.assertEqual(notification.priority, "high")


if __name__ == '__main__':
    unittest.main()
