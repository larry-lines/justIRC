"""
Protocol definitions for JustIRC
Defines message types and structures
"""

import json
import time
from typing import Dict, Any, Optional
from enum import Enum


class MessageType(Enum):
    """Message types in the protocol"""
    # Connection management
    REGISTER = "register"
    DISCONNECT = "disconnect"
    
    # Key exchange
    KEY_EXCHANGE = "key_exchange"
    PUBLIC_KEY_REQUEST = "public_key_request"
    PUBLIC_KEY_RESPONSE = "public_key_response"
    
    # Messaging
    PRIVATE_MESSAGE = "private_message"
    CHANNEL_MESSAGE = "channel_message"
    
    # Channel management
    JOIN_CHANNEL = "join_channel"
    LEAVE_CHANNEL = "leave_channel"
    OP_USER = "op_user"
    UNOP_USER = "unop_user"
    MOD_USER = "mod_user"
    UNMOD_USER = "unmod_user"
    KICK_USER = "kick_user"
    BAN_USER = "ban_user"
    UNBAN_USER = "unban_user"
    KICKBAN_USER = "kickban_user"
    SET_TOPIC = "set_topic"
    TRANSFER_OWNERSHIP = "transfer_ownership"
    OP_PASSWORD_REQUEST = "op_password_request"
    OP_PASSWORD_RESPONSE = "op_password_response"
    
    # Information requests
    WHOIS = "whois"
    LIST_CHANNELS = "list_channels"
    WHOIS_RESPONSE = "whois_response"
    CHANNEL_LIST_RESPONSE = "channel_list_response"
    
    # File transfer
    IMAGE_START = "image_start"
    IMAGE_CHUNK = "image_chunk"
    IMAGE_END = "image_end"
    
    # Server responses
    ACK = "ack"
    ERROR = "error"
    USER_LIST = "user_list"
    CHANNEL_LIST = "channel_list"


class Protocol:
    """Protocol message builder and parser"""
    
    VERSION = "1.0"
    
    @staticmethod
    def build_message(msg_type: MessageType, **kwargs) -> str:
        """Build a protocol message"""
        message = {
            "version": Protocol.VERSION,
            "type": msg_type.value,
            "timestamp": time.time(),
            **kwargs
        }
        return json.dumps(message)
    
    @staticmethod
    def parse_message(data: str) -> Dict[str, Any]:
        """Parse a protocol message"""
        try:
            message = json.loads(data)
            if "type" not in message:
                raise ValueError("Message missing type field")
            return message
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON message: {e}")
    
    @staticmethod
    def register(nickname: str, public_key: str) -> str:
        """Create a registration message"""
        return Protocol.build_message(
            MessageType.REGISTER,
            nickname=nickname,
            public_key=public_key
        )
    
    @staticmethod
    def key_exchange(from_id: str, to_id: str, public_key: str) -> str:
        """Create a key exchange message"""
        return Protocol.build_message(
            MessageType.KEY_EXCHANGE,
            from_id=from_id,
            to_id=to_id,
            public_key=public_key
        )
    
    @staticmethod
    def encrypted_message(from_id: str, to_id: str, 
                         encrypted_data: str, nonce: str,
                         is_channel: bool = False) -> str:
        """Create an encrypted message"""
        msg_type = MessageType.CHANNEL_MESSAGE if is_channel else MessageType.PRIVATE_MESSAGE
        return Protocol.build_message(
            msg_type,
            from_id=from_id,
            to_id=to_id,
            encrypted_data=encrypted_data,
            nonce=nonce
        )
    
    @staticmethod
    def join_channel(user_id: str, channel: str, password: str = None, creator_password: str = None) -> str:
        """Create a join channel message"""
        msg_data = {
            "user_id": user_id,
            "channel": channel
        }
        if password:
            msg_data["password"] = password
        if creator_password:
            msg_data["creator_password"] = creator_password
        return Protocol.build_message(
            MessageType.JOIN_CHANNEL,
            **msg_data
        )
    
    @staticmethod
    def leave_channel(user_id: str, channel: str) -> str:
        """Create a leave channel message"""
        return Protocol.build_message(
            MessageType.LEAVE_CHANNEL,
            user_id=user_id,
            channel=channel
        )
    
    @staticmethod
    def image_start(from_id: str, to_id: str, image_id: str, 
                   total_chunks: int, encrypted_metadata: str, nonce: str) -> str:
        """Create an image start message"""
        return Protocol.build_message(
            MessageType.IMAGE_START,
            from_id=from_id,
            to_id=to_id,
            image_id=image_id,
            total_chunks=total_chunks,
            encrypted_metadata=encrypted_metadata,
            nonce=nonce
        )
    
    @staticmethod
    def image_chunk(from_id: str, to_id: str, image_id: str,
                   chunk_number: int, encrypted_data: str, nonce: str) -> str:
        """Create an image chunk message"""
        return Protocol.build_message(
            MessageType.IMAGE_CHUNK,
            from_id=from_id,
            to_id=to_id,
            image_id=image_id,
            chunk_number=chunk_number,
            encrypted_data=encrypted_data,
            nonce=nonce
        )
    
    @staticmethod
    def image_end(from_id: str, to_id: str, image_id: str) -> str:
        """Create an image end message"""
        return Protocol.build_message(
            MessageType.IMAGE_END,
            from_id=from_id,
            to_id=to_id,
            image_id=image_id
        )
    
    @staticmethod
    def ack(success: bool, message: str = "") -> str:
        """Create an acknowledgment message"""
        return Protocol.build_message(
            MessageType.ACK,
            success=success,
            message=message
        )
    
    @staticmethod
    def error(error_message: str) -> str:
        """Create an error message"""
        return Protocol.build_message(
            MessageType.ERROR,
            error=error_message
        )
    
    @staticmethod
    def user_list(users: list) -> str:
        """Create a user list message"""
        return Protocol.build_message(
            MessageType.USER_LIST,
            users=users
        )
    
    @staticmethod
    def channel_list(channels: list) -> str:
        """Create a channel list message"""
        return Protocol.build_message(
            MessageType.CHANNEL_LIST,
            channels=channels
        )
    
    @staticmethod
    def op_user(channel: str, target_nickname: str, password: str) -> str:
        """Create an op user message"""
        return Protocol.build_message(
            MessageType.OP_USER,
            channel=channel,
            target_nickname=target_nickname,
            op_password=password
        )
    
    @staticmethod
    def whois(target_nickname: str) -> str:
        """Create a whois request message"""
        return Protocol.build_message(
            MessageType.WHOIS,
            target_nickname=target_nickname
        )
    
    @staticmethod
    def list_channels() -> str:
        """Create a list channels request message"""
        return Protocol.build_message(
            MessageType.LIST_CHANNELS
        )
    
    @staticmethod
    def kick_user(channel: str, target_nickname: str, reason: str = "") -> str:
        """Create a kick user message"""
        return Protocol.build_message(
            MessageType.KICK_USER,
            channel=channel,
            target_nickname=target_nickname,
            reason=reason
        )
    
    @staticmethod
    def set_topic(channel: str, topic: str) -> str:
        """Create a set topic message"""
        return Protocol.build_message(
            MessageType.SET_TOPIC,
            channel=channel,
            topic=topic
        )
