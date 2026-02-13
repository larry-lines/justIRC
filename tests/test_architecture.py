"""
Tests for service layer and presenter

Uses mocks to test business logic without external dependencies.
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
from datetime import datetime

from models import User, Channel, Message, ClientState, UserStatus
from services import StateManager, MessageService, ChannelService
from presenter import ClientPresenter


class TestStateManager(unittest.TestCase):
    """Test StateManager service"""
    
    def setUp(self):
        """Setup for each test"""
        self.state_manager = StateManager()
    
    def test_initial_state(self):
        """Test initial state is disconnected"""
        state = self.state_manager.get_state()
        
        self.assertFalse(state.connected)
        self.assertIsNone(state.user_id)
        self.assertEqual(len(state.users), 0)
    
    def test_update_state(self):
        """Test updating state"""
        self.state_manager.update_state(
            connected=True,
            user_id="user123",
            nickname="TestUser"
        )
        
        state = self.state_manager.get_state()
        self.assertTrue(state.connected)
        self.assertEqual(state.user_id, "user123")
        self.assertEqual(state.nickname, "TestUser")
    
    def test_add_user(self):
        """Test adding a user"""
        user = User("1", "User1", "key1")
        
        self.state_manager.add_user(user)
        
        state = self.state_manager.get_state()
        self.assertIn("1", state.users)  # users dict is keyed by user_id
        self.assertEqual(state.users["1"].nickname, "User1")
    
    def test_remove_user(self):
        """Test removing a user"""
        user = User("1", "User1", "key1")
        self.state_manager.add_user(user)
        
        self.state_manager.remove_user("User1")
        
        state = self.state_manager.get_state()
        self.assertNotIn("User1", state.users)
    
    def test_add_channel(self):
        """Test adding a channel"""
        channel = Channel("#general")
        
        self.state_manager.add_channel(channel)
        
        state = self.state_manager.get_state()
        self.assertIn("#general", state.channels)
    
    def test_remove_channel(self):
        """Test removing a channel"""
        channel = Channel("#general")
        self.state_manager.add_channel(channel)
        
        self.state_manager.remove_channel("#general")
        
        state = self.state_manager.get_state()
        self.assertNotIn("#general", state.channels)
    
    def test_join_channel(self):
        """Test marking channel as joined"""
        self.state_manager.join_channel("#general")
        
        state = self.state_manager.get_state()
        self.assertIn("#general", state.joined_channels)
    
    def test_leave_channel(self):
        """Test marking channel as left"""
        self.state_manager.join_channel("#general")
        self.state_manager.leave_channel("#general")
        
        state = self.state_manager.get_state()
        self.assertNotIn("#general", state.joined_channels)
    
    def test_block_user(self):
        """Test blocking a user"""
        self.state_manager.block_user("BadUser")
        
        state = self.state_manager.get_state()
        self.assertIn("BadUser", state.blocked_users)
    
    def test_unblock_user(self):
        """Test unblocking a user"""
        self.state_manager.block_user("User1")
        self.state_manager.unblock_user("User1")
        
        state = self.state_manager.get_state()
        self.assertNotIn("User1", state.blocked_users)
    
    def test_set_current_channel(self):
        """Test setting current channel"""
        self.state_manager.set_current_channel("#general")
        
        state = self.state_manager.get_state()
        self.assertEqual(state.current_channel, "#general")
    
    def test_observers(self):
        """Test observer pattern"""
        observer_called = False
        new_state = None
        
        def observer(state):
            nonlocal observer_called, new_state
            observer_called = True
            new_state = state
        
        self.state_manager.add_observer(observer)
        self.state_manager.update_state(connected=True)
        
        self.assertTrue(observer_called)
        self.assertIsNotNone(new_state)
        self.assertTrue(new_state.connected)
    
    def test_remove_observer(self):
        """Test removing observer"""
        call_count = 0
        
        def observer(state):
            nonlocal call_count
            call_count += 1
        
        self.state_manager.add_observer(observer)
        self.state_manager.update_state(connected=True)  # Should call observer
        
        self.state_manager.remove_observer(observer)
        self.state_manager.update_state(connected=False)  # Should not call observer
        
        self.assertEqual(call_count, 1)


class TestMessageService(unittest.IsolatedAsyncioTestCase):
    """Test MessageService"""
    
    async def asyncSetUp(self):
        """Setup for each test"""
        self.mock_network = AsyncMock()
        self.mock_state = Mock(spec=StateManager)
        self.mock_crypto = Mock()
        self.mock_image_transfer = Mock()
        
        # Setup mock state
        mock_state = ClientState(
            connected=True,
            user_id="user123",
            nickname="TestUser"
        )
        self.mock_state.get_state.return_value = mock_state
        
        # Mock get_user_by_nickname for tests
        from models import User
        mock_user = User(user_id="user2", nickname="User2", public_key="key2")
        self.mock_state.get_user_by_nickname.return_value = mock_user
        
        # Mock get_channel for tests
        from models import Channel
        mock_channel = Channel(name="#general", owner="user123", topic="Test topic")
        self.mock_state.get_channel.return_value = mock_channel
        
        # Mock state method for blocking
        self.mock_state.is_user_blocked.return_value = False
        
        # Mock crypto methods
        self.mock_crypto.encrypt.return_value = ("encrypted_data", "nonce")
        self.mock_crypto.encrypt_for_channel.return_value = ("encrypted_data", "nonce")
        self.mock_crypto.decrypt.return_value = "Decrypted message"
        
        self.message_service = MessageService(
            network=self.mock_network,
            state=self.mock_state,
            crypto=self.mock_crypto,
            image_transfer=self.mock_image_transfer
        )
    
    async def test_send_private_message(self):
        """Test sending private message"""
        await self.message_service.send_private_message("User2", "Hello!")
        
        # Verify crypto.encrypt was called
        self.mock_crypto.encrypt.assert_called_once_with("user2", "Hello!")
        
        # Verify network.send was called
        self.mock_network.send.assert_called_once()
        
        # Get the call arguments
        call_args = self.mock_network.send.call_args[0]
        self.assertIn("private_message", str(call_args))
        self.assertIn("user2", str(call_args))
    
    async def test_send_channel_message(self):
        """Test sending channel message"""
        await self.message_service.send_channel_message("#general", "Hello channel!")
        
        # Verify crypto.encrypt_for_channel was called
        self.mock_crypto.encrypt_for_channel.assert_called_once_with("#general", "Hello channel!")
        
        # Verify network.send was called
        self.mock_network.send.assert_called_once()
        
        call_args = self.mock_network.send.call_args[0]
        self.assertIn("channel_message", str(call_args))
        self.assertIn("#general", str(call_args))
    
    async def test_handle_incoming_message(self):
        """Test handling incoming message"""
        # Create a protocol message (dict), not a Message object
        protocol_message = {
            "type": "private_message",
            "from_id": "user2",
            "from_nickname": "User2",
            "to_id": "user123",
            "encrypted_data": "encrypted",
            "nonce": "nonce123"
        }
        
        # Mock decrypt to return the message content
        self.mock_crypto.decrypt.return_value = "Hello back!"
        
        handler_called = False
        
        def test_handler(msg):
            nonlocal handler_called
            handler_called = True
            # msg should be a Message object created from the protocol_message
        
        self.message_service.add_message_listener(test_handler)
        
        await self.message_service.handle_incoming_message(protocol_message)
        
        # Verify crypto.decrypt was called with correct arguments
        self.mock_crypto.decrypt.assert_called_once_with("user2", "encrypted", "nonce123")
        self.assertTrue(handler_called)


class TestChannelService(unittest.IsolatedAsyncioTestCase):
    """Test ChannelService"""
    
    async def asyncSetUp(self):
        """Setup for each test"""
        self.mock_network = AsyncMock()
        self.mock_state = Mock(spec=StateManager)
        self.mock_crypto = Mock()
        
        # Setup mock state
        mock_state = ClientState(
            connected=True,
            user_id="user123",
            nickname="TestUser"
        )
        self.mock_state.get_state.return_value = mock_state
        
        self.channel_service = ChannelService(
            network=self.mock_network,
            state=self.mock_state,
            crypto=self.mock_crypto
        )
    
    async def test_join_channel(self):
        """Test joining a channel"""
        await self.channel_service.join_channel("#general")
        
        # Verify network.send was called
        self.mock_network.send.assert_called_once()
        
        call_args = self.mock_network.send.call_args[0]
        self.assertIn("join_channel", str(call_args))
        self.assertIn("#general", str(call_args))
    
    async def test_leave_channel(self):
        """Test leaving a channel"""
        await self.channel_service.leave_channel("#general")
        
        # Verify network.send was called
        self.mock_network.send.assert_called_once()
        
        call_args = self.mock_network.send.call_args[0]
        self.assertIn("leave_channel", str(call_args))
        self.assertIn("#general", str(call_args))
    
    async def test_set_topic(self):
        """Test setting channel topic"""
        await self.channel_service.set_topic("#general", "New topic")
        
        self.mock_network.send.assert_called_once()
        
        call_args = self.mock_network.send.call_args[0]
        self.assertIn("set_topic", str(call_args))
        self.assertIn("New topic", str(call_args))


class TestClientPresenter(unittest.IsolatedAsyncioTestCase):
    """Test ClientPresenter"""
    
    async def asyncSetUp(self):
        """Setup for each test"""
        self.mock_network = AsyncMock()
        self.mock_network.add_message_handler = Mock()  # Sync method, not async
        self.mock_network.connect.return_value = (True, None)  # Return success tuple
        
        self.mock_state = Mock(spec=StateManager)
        
        self.mock_message = AsyncMock()
        self.mock_message.add_message_listener = Mock()  # Sync method, not async
        
        self.mock_channel = AsyncMock()
        self.mock_notification = Mock()
        
        # Setup mock state
        self.current_state = ClientState()
        self.mock_state.get_state.return_value = self.current_state
        self.mock_state.add_listener = Mock()  # Sync method, not async
        
        self.presenter = ClientPresenter(
            network_service=self.mock_network,
            state_manager=self.mock_state,
            message_service=self.mock_message,
            channel_service=self.mock_channel,
            notification_service=self.mock_notification
        )
    
    async def test_connect(self):
        """Test connecting to server"""
        from models import ConnectionConfig
        config = ConnectionConfig(host="localhost", port=6667, nickname="TestUser")
        await self.presenter.connect(config)
        
        # Verify network service was called
        self.mock_network.connect.assert_called_once_with(config)
    
    async def test_disconnect(self):
        """Test disconnecting from server"""
        await self.presenter.disconnect()
        
        self.mock_network.disconnect.assert_called_once()
    
    async def test_send_message_to_channel(self):
        """Test sending message to current channel"""
        self.current_state.current_channel = "#general"
        
        await self.presenter.send_message("Hello!")
        
        # Verify channel message was sent
        self.mock_message.send_channel_message.assert_called_once_with("#general", "Hello!")
    
    async def test_send_message_no_channel(self):
        """Test sending message with no current channel"""
        self.current_state.current_channel = None
        
        # Should call error callback
        error_called = False
        
        def error_handler(msg):
            nonlocal error_called
            error_called = True
        
        self.presenter.on_error = error_handler
        
        await self.presenter.send_message("Hello!")
        
        self.assertTrue(error_called)
    
    async def test_join_channel(self):
        """Test joining a channel"""
        await self.presenter.join_channel("#general")
        
        self.mock_channel.join_channel.assert_called_once_with("#general", None, None)
    
    async def test_leave_channel(self):
        """Test leaving a channel"""
        await self.presenter.leave_channel("#general")
        
        self.mock_channel.leave_channel.assert_called_once_with("#general")
    
    async def test_switch_to_channel(self):
        """Test switching to a channel"""
        channel = Channel("#general")
        self.current_state.channels["#general"] = channel
        self.current_state.joined_channels.add("#general")
        self.mock_state.get_channel.return_value = channel
        
        self.presenter.switch_to_channel("#general")  # Not async
        
        # Verify state was updated
        self.mock_state.update_state.assert_called_once()
    
    async def test_get_users(self):
        """Test getting user list"""
        user1 = User("1", "User1", "key1")
        user2 = User("2", "User2", "key2")
        self.current_state.users = {"User1": user1, "User2": user2}
        
        users = self.presenter.get_users()
        
        self.assertEqual(len(users), 2)
        self.assertIn(user1, users)
        self.assertIn(user2, users)
    
    async def test_get_channels(self):
        """Test getting channel list"""
        channel1 = Channel("#general")
        channel2 = Channel("#random")
        self.current_state.channels = {"#general": channel1, "#random": channel2}
        
        channels = self.presenter.get_channels()
        
        self.assertEqual(len(channels), 2)
        self.assertIn(channel1, channels)
        self.assertIn(channel2, channels)


class TestDependencyInjection(unittest.TestCase):
    """Test dependency injection container"""
    
    def test_create_container(self):
        """Test creating a container"""
        from dependency_container import DependencyContainer
        
        container = DependencyContainer()
        self.assertIsNotNone(container)
    
    def test_register_and_resolve_singleton(self):
        """Test registering and resolving singleton service"""
        from dependency_container import DependencyContainer
        
        container = DependencyContainer()
        
        # Register a simple service
        class TestService:
            def __init__(self):
                self.value = 42
        
        container.register_singleton(TestService, lambda: TestService())
        
        # Resolve twice
        service1 = container.resolve(TestService)
        service2 = container.resolve(TestService)
        
        # Should be the same instance
        self.assertIs(service1, service2)
        self.assertEqual(service1.value, 42)
    
    def test_register_and_resolve_transient(self):
        """Test registering and resolving transient service"""
        from dependency_container import DependencyContainer
        
        container = DependencyContainer()
        
        # Register a simple service
        class TestService:
            def __init__(self):
                self.value = 42
        
        container.register_transient(TestService, lambda: TestService())
        
        # Resolve twice
        service1 = container.resolve(TestService)
        service2 = container.resolve(TestService)
        
        # Should be different instances
        self.assertIsNot(service1, service2)
        self.assertEqual(service1.value, 42)
        self.assertEqual(service2.value, 42)
    
    def test_register_instance(self):
        """Test registering existing instance"""
        from dependency_container import DependencyContainer
        
        container = DependencyContainer()
        
        class TestService:
            def __init__(self, value):
                self.value = value
        
        instance = TestService(100)
        container.register_instance(TestService, instance)
        
        resolved = container.resolve(TestService)
        
        self.assertIs(resolved, instance)
        self.assertEqual(resolved.value, 100)
    
    def test_resolve_unregistered_service(self):
        """Test resolving unregistered service throws error"""
        from dependency_container import DependencyContainer
        
        container = DependencyContainer()
        
        class UnregisteredService:
            pass
        
        with self.assertRaises(KeyError):
            container.resolve(UnregisteredService)
    
    def test_try_resolve_returns_none(self):
        """Test try_resolve returns None for unregistered service"""
        from dependency_container import DependencyContainer
        
        container = DependencyContainer()
        
        class UnregisteredService:
            pass
        
        result = container.try_resolve(UnregisteredService)
        self.assertIsNone(result)
    
    def test_is_registered(self):
        """Test checking if service is registered"""
        from dependency_container import DependencyContainer
        
        container = DependencyContainer()
        
        class TestService:
            pass
        
        self.assertFalse(container.is_registered(TestService))
        
        container.register_singleton(TestService, lambda: TestService())
        
        self.assertTrue(container.is_registered(TestService))


if __name__ == '__main__':
    unittest.main()
