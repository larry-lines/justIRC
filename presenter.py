"""
Presenter Layer for JustIRC Client (MVP Pattern)

The Presenter acts as a mediator between the View (UI) and the Services (business logic).
It orchestrates all operations, keeping the View purely focused on display concerns.
"""

import asyncio
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime

from models import (
    User, Channel, Message, ClientState, ConnectionConfig,
    UserStatus, MessageType, NotificationEvent
)
from services import (
    NetworkService, StateManager, MessageService,
    ChannelService, NotificationService
)
from protocol import Protocol, MessageType as ProtocolMessageType


class ClientPresenter:
    """
    Main presenter for the IRC client.
    Coordinates all business logic and updates the view.
    """
    
    def __init__(
        self,
        network_service: NetworkService,
        state_manager: StateManager,
        message_service: MessageService,
        channel_service: ChannelService,
        notification_service: NotificationService
    ):
        self.network = network_service
        self.state = state_manager
        self.messages = message_service
        self.channels = channel_service
        self.notifications = notification_service
        
        # View callbacks - set by the View
        self.on_connection_changed: Optional[Callable[[bool, str], None]] = None
        self.on_message_received: Optional[Callable[[Message], None]] = None
        self.on_user_list_updated: Optional[Callable[[List[User]], None]] = None
        self.on_channel_joined: Optional[Callable[[Channel], None]] = None
        self.on_channel_left: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_state_changed: Optional[Callable[[ClientState], None]] = None
        
        # Register handlers
        self.network.add_message_handler(self._handle_protocol_message)
        self.messages.add_message_listener(self._handle_application_message)
        self.state.add_listener(self._handle_state_change)
    
    # Connection Management
    
    async def connect(self, config: ConnectionConfig):
        """Connect to IRC server"""
        success, error = await self.network.connect(config)
        
        if success:
            self.state.update_state(
                connected=True,
                nickname=config.nickname
            )
        
        if self.on_connection_changed:
            self.on_connection_changed(success, error)
    
    async def disconnect(self):
        """Disconnect from server"""
        await self.network.disconnect()
        
        self.state.update_state(
            connected=False,
            user_id=None,
            current_channel=None,
            current_recipient=None
        )
        
        if self.on_connection_changed:
            self.on_connection_changed(False, "Disconnected")
    
    # Message Handling
    
    async def send_message(self, content: str) -> bool:
        """
        Send a message to the current channel or recipient
        
        Returns:
            bool: True if successful
        """
        try:
            state = self.state.get_state()
            
            if state.current_channel:
                # Send to channel
                await self.messages.send_channel_message(state.current_channel, content)
                return True
            
            elif state.current_recipient:
                # Send private message
                await self.messages.send_private_message(state.current_recipient, content)
                return True
            
            else:
                if self.on_error:
                    self.on_error("No channel or recipient selected")
                return False
        
        except Exception as e:
            if self.on_error:
                self.on_error(f"Failed to send message: {e}")
            return False
    
    async def send_private_message_to(self, nickname: str, content: str) -> bool:
        """Send a private message to a specific user"""
        try:
            await self.messages.send_private_message(nickname, content)
            return True
        except Exception as e:
            if self.on_error:
                self.on_error(f"Failed to send private message: {e}")
            return False
    
    # Channel Management
    
    async def join_channel(
        self,
        channel_name: str,
        password: Optional[str] = None,
        creator_password: Optional[str] = None
    ):
        """Join a channel"""
        try:
            await self.channels.join_channel(channel_name, password, creator_password)
        except Exception as e:
            if self.on_error:
                self.on_error(f"Failed to join channel: {e}")
    
    async def leave_channel(self, channel_name: str):
        """Leave a channel"""
        try:
            await self.channels.leave_channel(channel_name)
            
            # Switch to another channel if available
            state = self.state.get_state()
            if state.current_channel == channel_name:
                if state.joined_channels:
                    next_channel = list(state.joined_channels)[0]
                    self.switch_to_channel(next_channel)
                else:
                    self.state.update_state(current_channel=None)
            
            if self.on_channel_left:
                self.on_channel_left(channel_name)
        
        except Exception as e:
            if self.on_error:
                self.on_error(f"Failed to leave channel: {e}")
    
    def switch_to_channel(self, channel_name: str):
        """Switch the current view to a channel"""
        channel = self.state.get_channel(channel_name)
        if channel:
            self.state.update_state(
                current_channel=channel_name,
                current_recipient=None
            )
    
    def switch_to_private_chat(self, nickname: str):
        """Switch the current view to a private chat"""
        user = self.state.get_user_by_nickname(nickname)
        if user:
            self.state.update_state(
                current_channel=None,
                current_recipient=nickname
            )
    
    # User Management
    
    async def set_status(self, status: UserStatus, message: str = ""):
        """Set user status"""
        self.state.update_state(
            status=status,
            status_message=message
        )
        
        # Send to server
        try:
            msg = Protocol.set_status(status.value, message)
            await self.network.send(msg)
        except Exception as e:
            if self.on_error:
                self.on_error(f"Failed to set status: {e}")
    
    def block_user(self, user_id: str):
        """Block a user"""
        self.state.block_user(user_id)
    
    def unblock_user(self, user_id: str):
        """Unblock a user"""
        self.state.unblock_user(user_id)
    
    def is_user_blocked(self, user_id: str) -> bool:
        """Check if user is blocked"""
        return self.state.is_user_blocked(user_id)
    
    # State Queries
    
    def get_state(self) -> ClientState:
        """Get current application state"""
        return self.state.get_state()
    
    def get_users(self) -> List[User]:
        """Get list of all users"""
        state = self.state.get_state()
        return list(state.users.values())
    
    def get_channels(self) -> List[Channel]:
        """Get list of all channels"""
        state = self.state.get_state()
        return list(state.channels.values())
    
    def get_joined_channels(self) -> List[Channel]:
        """Get list of joined channels"""
        state = self.state.get_state()
        return [
            channel for channel in state.channels.values()
            if channel.name in state.joined_channels
        ]
    
    def get_channel_members(self, channel_name: str) -> List[User]:
        """Get list of users in a channel"""
        channel = self.state.get_channel(channel_name)
        if not channel:
            return []
        
        state = self.state.get_state()
        return [
            state.users[user_id]
            for user_id in channel.members
            if user_id in state.users
        ]
    
    # Protocol Message Handlers
    
    async def _handle_protocol_message(self, message: dict):
        """Handle incoming protocol messages from server"""
        msg_type = message.get('type')
        
        if msg_type == ProtocolMessageType.ACK.value:
            await self._handle_ack(message)
        
        elif msg_type == ProtocolMessageType.ERROR.value:
            await self._handle_error(message)
        
        elif msg_type == ProtocolMessageType.USER_LIST.value:
            await self._handle_user_list(message)
        
        elif msg_type == ProtocolMessageType.JOIN_CHANNEL.value:
            await self._handle_join_channel_response(message)
        
        elif msg_type == ProtocolMessageType.LEAVE_CHANNEL.value:
            await self._handle_leave_channel_notification(message)
        
        elif msg_type == ProtocolMessageType.DISCONNECT.value:
            await self._handle_user_disconnect(message)
        
        elif msg_type in [
            ProtocolMessageType.PRIVATE_MESSAGE.value,
            ProtocolMessageType.CHANNEL_MESSAGE.value
        ]:
            # Delegate to message service
            await self.messages.handle_incoming_message(message)
        
        # Handle other message types as needed
    
    async def _handle_ack(self, message: dict):
        """Handle acknowledgment messages"""
        success = message.get('success', False)
        msg_text = message.get('message', '')
        
        # Check for registration success
        if success and 'user_id' in message:
            self.state.update_state(
                connected=True,
                user_id=message['user_id']
            )
        
        # Check for channel join success (server sends ACK with channel info)
        elif success and 'channel' in message:
            # This is a join channel response - delegate to the channel join handler
            await self._handle_join_channel_response(message)
        
        # System message
        if msg_text:
            sys_msg = Message(
                message_type=MessageType.SYSTEM,
                sender="SYSTEM",
                content=msg_text
            )
            if self.on_message_received:
                self.on_message_received(sys_msg)
    
    async def _handle_error(self, message: dict):
        """Handle error messages"""
        error_text = message.get('error', 'Unknown error')
        
        # Check if this is a "new channel requires creator password" error
        if error_text and 'creator password' in error_text.lower() and 'new channel' in error_text.lower():
            # Trigger special handling for creator password - the GUI will show a dialog
            # We'll add a special error type for this
            if self.on_error:
                self.on_error(f"CREATOR_PASSWORD_REQUIRED:{error_text}")
        else:
            # Regular error
            if self.on_error:
                self.on_error(error_text)
    
    async def _handle_user_list(self, message: dict):
        """Handle user list updates"""
        users_data = message.get('users', [])
        
        for user_data in users_data:
            user = User(
                user_id=user_data['user_id'],
                nickname=user_data['nickname'],
                public_key=user_data.get('public_key'),
                status=UserStatus(user_data.get('status', 'online')),
                status_message=user_data.get('status_message', '')
            )
            self.state.add_user(user)
        
        if self.on_user_list_updated:
            self.on_user_list_updated(self.get_users())
    
    async def _handle_join_channel_response(self, message: dict):
        """Handle successful channel join"""
        channel_name = message.get('channel')
        members_data = message.get('members', [])
        
        if not channel_name:
            return
        
        # Get crypto layer for key management
        crypto = self.network.crypto
        
        # Load channel key if provided (for encryption)
        channel_key = message.get('channel_key')
        if channel_key:
            crypto.load_channel_key(channel_name, channel_key)
        
        # Create or update channel
        channel = Channel(
            name=channel_name,
            password_protected=message.get('is_protected', False),
            topic=message.get('topic', '')
        )
        
        # Add members and update user state
        for member_data in members_data:
            user_id = member_data['user_id']
            nickname = member_data.get('nickname', '')
            public_key = member_data.get('public_key', '')
            
            # Add to channel
            channel.add_member(user_id)
            
            if member_data.get('is_operator'):
                channel.operators.add(user_id)
            if member_data.get('is_mod'):
                channel.mods.add(user_id)
            if member_data.get('is_owner'):
                channel.owner = user_id
            
            # Add/update user in state manager if not already there
            existing_user = self.state.get_user(user_id)
            if not existing_user:
                from models import User, UserStatus
                user = User(
                    user_id=user_id,
                    nickname=nickname,
                    public_key=public_key,
                    status=UserStatus.ONLINE
                )
                self.state.add_user(user)
                
                # Load peer public key for encryption
                if public_key and user_id != self.state.get_state().user_id:
                    crypto.load_peer_public_key(user_id, public_key)
        
        self.state.add_channel(channel)
        self.state.join_channel(channel_name)
        self.state.update_state(current_channel=channel_name)
        
        if self.on_channel_joined:
            self.on_channel_joined(channel)
    
    async def _handle_leave_channel_notification(self, message: dict):
        """Handle notification that a user left a channel"""
        user_id = message.get('user_id')
        nickname = message.get('nickname')
        channel_name = message.get('channel')
        
        if channel_name:
            channel = self.state.get_channel(channel_name)
            if channel:
                channel.remove_member(user_id)
                self.state.add_channel(channel)  # Update
            
            # System message
            sys_msg = Message(
                message_type=MessageType.SYSTEM,
                sender="SYSTEM",
                content=f"{nickname} left {channel_name}",
                recipient=channel_name
            )
            if self.on_message_received:
                self.on_message_received(sys_msg)
    
    async def _handle_user_disconnect(self, message: dict):
        """Handle user disconnect notification"""
        user_id = message.get('user_id')
        nickname = message.get('nickname')
        
        if user_id:
            self.state.remove_user(user_id)
        
        # System message
        sys_msg = Message(
            message_type=MessageType.SYSTEM,
            sender="SYSTEM",
            content=f"{nickname} disconnected"
        )
        if self.on_message_received:
            self.on_message_received(sys_msg)
    
    # Application Message Handlers
    
    async def _handle_application_message(self, message: Message):
        """Handle application-level messages (after processing)"""
        # Check for mentions and notifications
        state = self.state.get_state()
        
        if message.sender != state.nickname:
            # Check for mention
            if state.nickname and state.nickname.lower() in message.content.lower():
                # Send notification
                window_focused = False  # View should set this
                await self.notifications.notify_message(
                    message.sender,
                    message.content,
                    message.is_private(),
                    window_focused
                )
        
        # Forward to view
        if self.on_message_received:
            self.on_message_received(message)
    
    # State Change Handler
    
    def _handle_state_change(self, state: ClientState):
        """Handle state changes"""
        if self.on_state_changed:
            self.on_state_changed(state)
