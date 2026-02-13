"""
Service Layer for JustIRC Client

Business logic separated from UI concerns.
All services are async-first and can be easily tested.
"""

import asyncio
import json
import os
from typing import Optional, Dict, Set, Callable, Any, List
from datetime import datetime

from models import (
    User, Channel, Message, ClientState, ConnectionConfig,
    UserStatus, MessageType as ModelMessageType, ImageTransferState,
    NotificationEvent
)
from protocol import Protocol, MessageType
from crypto_layer import CryptoLayer
from image_transfer import ImageTransfer


class NetworkService:
    """
    Handles all network communication with the server.
    Responsible for connecting, sending, and receiving messages.
    """
    
    def __init__(self, crypto: CryptoLayer):
        self.crypto = crypto
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self._message_handlers: List[Callable] = []
        self._receive_task: Optional[asyncio.Task] = None
    
    def add_message_handler(self, handler: Callable):
        """Add a handler for incoming messages"""
        self._message_handlers.append(handler)
    
    def remove_message_handler(self, handler: Callable):
        """Remove a message handler"""
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)
    
    async def connect(self, config: ConnectionConfig) -> tuple[bool, str]:
        """
        Connect to IRC server
        
        Returns:
            tuple[bool, str]: (success, error_message or "")
        """
        try:
            self.reader, self.writer = await asyncio.open_connection(
                config.host, config.port
            )
            self.connected = True
            
            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # Send registration
            reg_message = Protocol.register(
                nickname=config.nickname,
                public_key=self.crypto.get_public_key_b64(),
                password=config.password,
                session_token=config.session_token
            )
            await self.send(reg_message)
            
            return True, ""
        
        except ConnectionRefusedError:
            return False, "Connection refused. Make sure the server is running."
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    async def disconnect(self):
        """Disconnect from server"""
        self.connected = False
        
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass
        
        self.reader = None
        self.writer = None
    
    async def send(self, message: str):
        """Send a message to the server"""
        if not self.connected or not self.writer:
            raise ConnectionError("Not connected to server")
        
        try:
            self.writer.write(message.encode('utf-8') + b'\n')
            await self.writer.drain()
        except Exception as e:
            self.connected = False
            raise ConnectionError(f"Send failed: {e}")
    
    async def _receive_loop(self):
        """Receive messages from server"""
        while self.connected and self.reader:
            try:
                data = await self.reader.readline()
                if not data:
                    # Connection closed
                    self.connected = False
                    await self._notify_handlers({
                        'type': 'connection_closed',
                        'reason': 'Server closed connection'
                    })
                    break
                
                message_str = data.decode('utf-8').strip()
                if message_str:
                    try:
                        message = Protocol.parse_message(message_str)
                        await self._notify_handlers(message)
                    except ValueError as e:
                        print(f"Invalid message: {e}")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Receive error: {e}")
                self.connected = False
                await self._notify_handlers({
                    'type': 'connection_error',
                    'error': str(e)
                })
                break
    
    async def _notify_handlers(self, message: dict):
        """Notify all registered message handlers"""
        for handler in self._message_handlers:
            try:
                await handler(message)
            except Exception as e:
                print(f"Handler error: {e}")
    
    def is_connected(self) -> bool:
        """Check if connected to server"""
        return self.connected


class StateManager:
    """
    Manages the client state.
    Provides a single source of truth for application state.
    """
    
    def __init__(self):
        self._state = ClientState()
        self._state_listeners: List[Callable] = []
    
    def add_listener(self, listener: Callable[[ClientState], None]):
        """Add a listener for state changes"""
        self._state_listeners.append(listener)
    
    def remove_listener(self, listener: Callable):
        """Remove a state listener"""
        if listener in self._state_listeners:
            self._state_listeners.remove(listener)
    
    # Aliases for observer pattern
    def add_observer(self, observer: Callable[[ClientState], None]):
        """Add an observer for state changes (alias for add_listener)"""
        self.add_listener(observer)
    
    def remove_observer(self, observer: Callable):
        """Remove a state observer (alias for remove_listener)"""
        self.remove_listener(observer)
    
    def get_state(self) -> ClientState:
        """Get current state (read-only copy)"""
        return self._state.copy()
    
    def update_state(self, **kwargs):
        """Update state and notify listeners"""
        for key, value in kwargs.items():
            if hasattr(self._state, key):
                setattr(self._state, key, value)
        
        self._notify_listeners()
    
    def _notify_listeners(self):
        """Notify all state listeners"""
        state_copy = self._state.copy()
        for listener in self._state_listeners:
            try:
                listener(state_copy)
            except Exception as e:
                print(f"State listener error: {e}")
    
    # User management
    def add_user(self, user: User):
        """Add or update a user"""
        self._state.users[user.user_id] = user
        self._notify_listeners()
    
    def remove_user(self, user_id: str):
        """Remove a user"""
        if user_id in self._state.users:
            del self._state.users[user_id]
            self._notify_listeners()
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self._state.users.get(user_id)
    
    def get_user_by_nickname(self, nickname: str) -> Optional[User]:
        """Get user by nickname"""
        for user in self._state.users.values():
            if user.nickname == nickname:
                return user
        return None
    
    # Channel management
    def add_channel(self, channel: Channel):
        """Add or update a channel"""
        self._state.channels[channel.name] = channel
        self._notify_listeners()
    
    def remove_channel(self, channel_name: str):
        """Remove a channel"""
        if channel_name in self._state.channels:
            del self._state.channels[channel_name]
            self._state.joined_channels.discard(channel_name)
            self._notify_listeners()
    
    def get_channel(self, channel_name: str) -> Optional[Channel]:
        """Get channel by name"""
        return self._state.channels.get(channel_name)
    
    def join_channel(self, channel_name: str):
        """Mark channel as joined"""
        self._state.joined_channels.add(channel_name)
        self._notify_listeners()
    
    def leave_channel(self, channel_name: str):
        """Mark channel as left"""
        self._state.joined_channels.discard(channel_name)
        self._notify_listeners()
    
    # Blocked users
    def block_user(self, user_id: str):
        """Block a user"""
        self._state.blocked_users.add(user_id)
        self._notify_listeners()
    
    def unblock_user(self, user_id: str):
        """Unblock a user"""
        self._state.blocked_users.discard(user_id)
        self._notify_listeners()
    
    def is_user_blocked(self, user_id: str) -> bool:
        """Check if user is blocked"""
        return user_id in self._state.blocked_users
    
    # Current channel management
    def set_current_channel(self, channel_name: str):
        """Set the current active channel"""
        self._state.current_channel = channel_name
        self._notify_listeners()


class MessageService:
    """
    Handles message sending and receiving logic.
    Manages encryption, formatting, and routing of messages.
    """
    
    def __init__(
        self,
        network: NetworkService,
        state: StateManager,
        crypto: CryptoLayer,
        image_transfer: ImageTransfer
    ):
        self.network = network
        self.state = state
        self.crypto = crypto
        self.image_transfer = image_transfer
        self._message_listeners: List[Callable] = []
    
    def add_message_listener(self, listener: Callable[[Message], None]):
        """Add a listener for incoming messages"""
        self._message_listeners.append(listener)
    
    async def send_private_message(self, recipient_nickname: str, content: str):
        """Send a private message"""
        recipient = self.state.get_user_by_nickname(recipient_nickname)
        if not recipient:
            raise ValueError(f"User {recipient_nickname} not found")
        
        # Encrypt message
        encrypted_data, nonce = self.crypto.encrypt(recipient.user_id, content)
        
        # Send to server
        msg = Protocol.encrypted_message(
            self.state.get_state().user_id,
            recipient.user_id,
            encrypted_data,
            nonce,
            is_channel=False
        )
        await self.network.send(msg)
        
        # Notify listeners (for local display)
        message = Message(
            message_type=ModelMessageType.PRIVATE,
            sender=self.state.get_state().nickname,
            content=content,
            recipient=recipient_nickname,
            encrypted=True,
            metadata={'from_id': self.state.get_state().user_id}
        )
        await self._notify_listeners(message)
    
    async def send_channel_message(self, channel_name: str, content: str):
        """Send a message to a channel"""
        channel = self.state.get_channel(channel_name)
        if not channel:
            raise ValueError(f"Channel {channel_name} not found")
        
        # Encrypt message for channel
        encrypted_data, nonce = self.crypto.encrypt_for_channel(channel_name, content)
        
        # Send to server
        msg = Protocol.encrypted_message(
            self.state.get_state().user_id,
            channel_name,
            encrypted_data,
            nonce,
            is_channel=True
        )
        await self.network.send(msg)
        
        # Notify listeners (for local display)
        message = Message(
            message_type=ModelMessageType.CHANNEL,
            sender=self.state.get_state().nickname,
            content=content,
            recipient=channel_name,
            encrypted=True,
            metadata={'from_id': self.state.get_state().user_id, 'channel': channel_name}
        )
        await self._notify_listeners(message)
    
    async def handle_incoming_message(self, protocol_message: dict):
        """Handle an incoming message from the server"""
        msg_type = protocol_message.get('type')
        
        # Private message
        if msg_type == MessageType.PRIVATE_MESSAGE.value:
            await self._handle_private_message(protocol_message)
        
        # Channel message
        elif msg_type == MessageType.CHANNEL_MESSAGE.value:
            await self._handle_channel_message(protocol_message)
        
        # System messages
        elif msg_type in [MessageType.ERROR.value, MessageType.ACK.value]:
            message = Message(
                message_type=ModelMessageType.SYSTEM,
                sender="SYSTEM",
                content=protocol_message.get('message', ''),
                metadata=protocol_message
            )
            await self._notify_listeners(message)
    
    async def _handle_private_message(self, protocol_message: dict):
        """Handle incoming private message"""
        from_id = protocol_message.get('from_id')
        from_nickname = protocol_message.get('from_nickname')
        encrypted_data = protocol_message.get('encrypted_data')
        nonce = protocol_message.get('nonce')
        
        # Check if user is blocked
        if self.state.is_user_blocked(from_id):
            return
        
        # Decrypt message
        try:
            decrypted = self.crypto.decrypt(from_id, encrypted_data, nonce)
            
            message = Message(
                message_type=ModelMessageType.PRIVATE,
                sender=from_nickname,
                content=decrypted,
                encrypted=True,
                metadata={'from_id': from_id}
            )
            await self._notify_listeners(message)
        
        except Exception as e:
            print(f"Failed to decrypt private message: {e}")
    
    async def _handle_channel_message(self, protocol_message: dict):
        """Handle incoming channel message"""
        from_id = protocol_message.get('from_id')
        from_nickname = protocol_message.get('from_nickname')
        channel = protocol_message.get('to_id')  # Channel name is in to_id
        encrypted_data = protocol_message.get('encrypted_data')
        nonce = protocol_message.get('nonce')
        
        # Check if user is blocked
        if self.state.is_user_blocked(from_id):
            return
        
        # Decrypt message
        try:
            decrypted = self.crypto.decrypt_from_channel(channel, encrypted_data, nonce)
            
            message = Message(
                message_type=ModelMessageType.CHANNEL,
                sender=from_nickname,
                content=decrypted,
                recipient=channel,
                encrypted=True,
                metadata={'from_id': from_id, 'channel': channel}
            )
            await self._notify_listeners(message)
        
        except Exception as e:
            print(f"Failed to decrypt channel message: {e}")
    
    async def _notify_listeners(self, message: Message):
        """Notify all message listeners"""
        for listener in self._message_listeners:
            try:
                await listener(message)
            except Exception as e:
                print(f"Message listener error: {e}")


class ChannelService:
    """
    Manages channel operations (join, leave, permissions, etc.)
    """
    
    def __init__(self, network: NetworkService, state: StateManager, crypto: CryptoLayer):
        self.network = network
        self.state = state
        self.crypto = crypto
    
    async def join_channel(
        self,
        channel_name: str,
        password: Optional[str] = None,
        creator_password: Optional[str] = None
    ):
        """Join a channel"""
        user_id = self.state.get_state().user_id
        msg = Protocol.join_channel(user_id, channel_name, password, creator_password)
        await self.network.send(msg)
    
    async def leave_channel(self, channel_name: str):
        """Leave a channel"""
        user_id = self.state.get_state().user_id
        msg = Protocol.leave_channel(user_id, channel_name)
        await self.network.send(msg)
        
        # Update state
        self.state.leave_channel(channel_name)
    
    async def set_topic(self, channel_name: str, topic: str):
        """Set channel topic"""
        msg = Protocol.set_topic(channel_name, topic)
        await self.network.send(msg)
    
    async def set_mode(self, channel_name: str, mode: str, enable: bool):
        """Set channel mode"""
        msg = Protocol.set_mode(channel_name, mode, enable)
        await self.network.send(msg)
    
    async def invite_user(self, channel_name: str, nickname: str):
        """Invite a user to a channel"""
        msg = Protocol.invite_user(channel_name, nickname)
        await self.network.send(msg)
    
    async def kick_user(self, channel_name: str, nickname: str, reason: str = ""):
        """Kick a user from a channel"""
        msg = Protocol.kick_user(channel_name, nickname, reason)
        await self.network.send(msg)
    
    async def ban_user(self, channel_name: str, nickname: str, reason: str = "", duration: int = 0):
        """Ban a user from a channel"""
        msg = Protocol.ban_user(channel_name, nickname, reason, duration)
        await self.network.send(msg)


class NotificationService:
    """
    Handles notifications (desktop, sound, etc.)
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._notification_handlers: List[Callable] = []
    
    def add_handler(self, handler: Callable[[NotificationEvent], None]):
        """Add a notification handler"""
        self._notification_handlers.append(handler)
    
    async def notify(self, event: NotificationEvent, window_focused: bool):
        """Send a notification"""
        settings = self.config.get("notifications", {})
        
        if not event.should_show(window_focused, settings):
            return
        
        for handler in self._notification_handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"Notification handler error: {e}")
    
    async def notify_message(
        self,
        sender: str,
        message_preview: str,
        is_private: bool,
        window_focused: bool
    ):
        """Notify about a new message"""
        title = f"Private message from {sender}" if is_private else f"{sender} in channel"
        
        event = NotificationEvent(
            title=title,
            message=message_preview[:100],  # Limit preview length
            priority="high" if is_private else "normal"
        )
        
        await self.notify(event, window_focused)
