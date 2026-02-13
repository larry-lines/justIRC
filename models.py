"""
Data Models for JustIRC Client

Represents domain objects and state in a clean, testable way.
These models are independent of UI and can be easily tested.
"""

from dataclasses import dataclass, field
from typing import Optional, Set, Dict, Any
from datetime import datetime
from enum import Enum


class UserStatus(Enum):
    """User presence status"""
    ONLINE = "online"
    AWAY = "away"
    BUSY = "busy"
    DND = "dnd"  # Do Not Disturb
    OFFLINE = "offline"


@dataclass
class User:
    """Represents a user in the IRC system"""
    user_id: str
    nickname: str
    public_key: Optional[str] = None
    status: UserStatus = UserStatus.ONLINE
    status_message: str = ""
    
    def __hash__(self):
        return hash(self.user_id)
    
    def __eq__(self, other):
        if not isinstance(other, User):
            return False
        return self.user_id == other.user_id
    
    def is_online(self) -> bool:
        """Check if user is online"""
        return self.status != UserStatus.OFFLINE
    
    def update_status(self, status: UserStatus, message: str = ""):
        """Update user status"""
        self.status = status
        self.status_message = message


@dataclass
class Channel:
    """Represents a chat channel"""
    name: str
    password_protected: bool = False
    topic: str = ""
    modes: Set[str] = field(default_factory=set)
    members: Set[str] = field(default_factory=set)  # user_ids
    operators: Set[str] = field(default_factory=set)  # user_ids
    mods: Set[str] = field(default_factory=set)  # user_ids
    owner: Optional[str] = None  # user_id
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if not isinstance(other, Channel):
            return False
        return self.name == other.name
    
    def add_member(self, user_id: str):
        """Add a member to the channel"""
        self.members.add(user_id)
    
    def remove_member(self, user_id: str):
        """Remove a member from the channel"""
        self.members.discard(user_id)
        self.operators.discard(user_id)
        self.mods.discard(user_id)
    
    def is_operator(self, user_id: str) -> bool:
        """Check if user is an operator"""
        return user_id in self.operators or user_id == self.owner
    
    def is_mod(self, user_id: str) -> bool:
        """Check if user is a moderator"""
        return user_id in self.mods or self.is_operator(user_id)
    
    def is_owner(self, user_id: str) -> bool:
        """Check if user is the channel owner"""
        return user_id == self.owner
    
    def member_count(self) -> int:
        """Get number of members"""
        return len(self.members)
    
    def has_mode(self, mode: str) -> bool:
        """Check if channel has a specific mode"""
        return mode in self.modes


class MessageType(Enum):
    """Type of message"""
    PRIVATE = "private"
    CHANNEL = "channel"
    SYSTEM = "system"
    ERROR = "error"
    INFO = "info"


@dataclass
class Message:
    """Represents a chat message"""
    message_type: MessageType
    sender: str  # nickname or "SYSTEM"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    recipient: Optional[str] = None  # For private messages (nickname or channel)
    encrypted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_private(self) -> bool:
        """Check if this is a private message"""
        return self.message_type == MessageType.PRIVATE
    
    def is_channel(self) -> bool:
        """Check if this is a channel message"""
        return self.message_type == MessageType.CHANNEL
    
    def is_system(self) -> bool:
        """Check if this is a system message"""
        return self.message_type == MessageType.SYSTEM
    
    def format_timestamp(self) -> str:
        """Format timestamp for display"""
        return self.timestamp.strftime("%H:%M:%S")


@dataclass
class ConnectionConfig:
    """Connection configuration"""
    host: str
    port: int
    nickname: str
    use_auth: bool = False
    username: Optional[str] = None
    password: Optional[str] = None
    session_token: Optional[str] = None
    auto_reconnect: bool = False
    reconnect_delay: int = 5


@dataclass
class ClientState:
    """
    Represents the current state of the IRC client
    Immutable snapshot for easy testing and state management
    """
    connected: bool = False
    user_id: Optional[str] = None
    nickname: Optional[str] = None
    current_channel: Optional[str] = None
    current_recipient: Optional[str] = None  # For private messages
    status: UserStatus = UserStatus.ONLINE
    status_message: str = ""
    
    users: Dict[str, User] = field(default_factory=dict)
    channels: Dict[str, Channel] = field(default_factory=dict)
    joined_channels: Set[str] = field(default_factory=set)
    blocked_users: Set[str] = field(default_factory=set)
    
    def is_in_channel(self, channel_name: str) -> bool:
        """Check if user is in a channel"""
        return channel_name in self.joined_channels
    
    def is_user_blocked(self, user_id: str) -> bool:
        """Check if a user is blocked"""
        return user_id in self.blocked_users
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.users.get(user_id)
    
    def get_channel(self, channel_name: str) -> Optional[Channel]:
        """Get channel by name"""
        return self.channels.get(channel_name)
    
    def copy(self) -> 'ClientState':
        """Create a copy of the current state"""
        import copy
        return copy.deepcopy(self)


@dataclass
class ImageTransferState:
    """Represents an image transfer in progress"""
    image_id: str
    from_user_id: str
    from_nickname: str
    filename: str
    file_size: int
    mime_type: str
    total_chunks: int
    received_chunks: int = 0
    chunks_data: Dict[int, bytes] = field(default_factory=dict)
    accepted: bool = False
    completed: bool = False
    
    def progress_percentage(self) -> float:
        """Calculate transfer progress percentage"""
        if self.total_chunks == 0:
            return 0.0
        return (self.received_chunks / self.total_chunks) * 100.0
    
    def is_complete(self) -> bool:
        """Check if transfer is complete"""
        return self.received_chunks == self.total_chunks


@dataclass
class NotificationEvent:
    """Represents a notification to be shown to the user"""
    title: str
    message: str
    priority: str = "normal"  # normal, high, urgent
    play_sound: bool = True
    
    def should_show(self, window_focused: bool, settings: Dict[str, Any]) -> bool:
        """Determine if notification should be shown based on settings"""
        if not settings.get("enabled", True):
            return False
        
        if settings.get("only_when_inactive", True) and window_focused:
            return False
        
        return True
