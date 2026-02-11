"""
JustIRC Server - Secure Routing-Only IRC Server
This server CANNOT decrypt messages - it only routes them
"""

import asyncio
import logging
import argparse
import json
import hashlib
import os
from typing import Dict, Set
from protocol import Protocol, MessageType


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('JustIRC-Server')


class Client:
    """Represents a connected client"""
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.user_id: str = None
        self.nickname: str = None
        self.public_key: str = None
        self.channels: Set[str] = set()
        
        # Get client address (but don't expose it to other clients)
        peername = writer.get_extra_info('peername')
        self.address = f"{peername[0]}:{peername[1]}" if peername else "unknown"
    
    async def send(self, message: str):
        """Send a message to this client"""
        try:
            self.writer.write(message.encode('utf-8') + b'\n')
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error sending to {self.nickname}: {e}")
    
    def __repr__(self):
        return f"Client({self.nickname or 'unregistered'})"


class IRCServer:
    """Main IRC server class - routes messages without decrypting"""
    
    def __init__(self, host='0.0.0.0', port=6667, data_dir='./server_data', config_file='server_config.json'):
        self.data_dir = data_dir
        self.channels_file = os.path.join(data_dir, 'channels.json')
        self.config_file = config_file
        
        # Load server configuration
        self.config = self.load_config()
        self.host = self.config.get('host', host)
        self.port = self.config.get('port', port)
        self.server_name = self.config.get('server_name', 'JustIRC Server')
        self.description = self.config.get('description', 'Welcome to JustIRC!')
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        self.clients: Dict[str, Client] = {}  # user_id -> Client
        self.channels: Dict[str, Set[str]] = {}  # channel -> set of user_ids
        self.channel_passwords: Dict[str, str] = {}  # channel -> hashed password
        self.channel_operators: Dict[str, Set[str]] = {}  # channel -> set of operator user_ids
        self.channel_creator_passwords: Dict[str, str] = {}  # channel -> hashed creator password
        self.channel_topics: Dict[str, str] = {}  # channel -> topic string
        self.nicknames: Dict[str, str] = {}  # nickname -> user_id
        
        # Load persistent channel data
        self.load_channels()
    
    def load_config(self):
        """Load server configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    logger.info(f"Loaded server config from {self.config_file}")
                    return config
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                return {}
        else:
            logger.info("No server config found, using defaults")
            return {}
    
    def hash_password(self, password: str) -> str:
        """Hash a password using SHA256"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    def load_channels(self):
        """Load persistent channel data from file"""
        if os.path.exists(self.channels_file):
            try:
                with open(self.channels_file, 'r') as f:
                    data = json.load(f)
                    
                # Load channel passwords (already hashed)
                self.channel_passwords = data.get('channel_passwords', {})
                
                # Load channel creator passwords (already hashed)
                self.channel_creator_passwords = data.get('channel_creator_passwords', {})
                
                # Initialize empty operator sets for existing channels
                for channel in self.channel_passwords.keys():
                    self.channel_operators[channel] = set()
                    self.channels[channel] = set()
                
                logger.info(f"Loaded {len(self.channel_passwords)} persistent channels from {self.channels_file}")
            except Exception as e:
                logger.error(f"Error loading channels: {e}")
        else:
            logger.info("No existing channel data found, starting fresh")
    
    def save_channels(self):
        """Save persistent channel data to file"""
        try:
            data = {
                'channel_passwords': self.channel_passwords,
                'channel_creator_passwords': self.channel_creator_passwords
            }
            with open(self.channels_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved channel data to {self.channels_file}")
        except Exception as e:
            logger.error(f"Error saving channels: {e}")
    
    async def start(self):
        """Start the server"""
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        
        addr = server.sockets[0].getsockname()
        logger.info(f'Server started on {addr[0]}:{addr[1]}')
        logger.info('Server is running in ROUTING-ONLY mode - cannot decrypt messages')
        logger.info('Press Ctrl+C to stop')
        
        async with server:
            await server.serve_forever()
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a new client connection"""
        client = Client(reader, writer)
        logger.info(f"New connection from {client.address}")
        
        try:
            while True:
                # Read message (newline delimited)
                data = await reader.readline()
                if not data:
                    break
                
                message_str = data.decode('utf-8').strip()
                if not message_str:
                    continue
                
                try:
                    message = Protocol.parse_message(message_str)
                    await self.handle_message(client, message)
                except ValueError as e:
                    logger.warning(f"Invalid message from {client.nickname}: {e}")
                    await client.send(Protocol.error(str(e)))
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error handling client {client.nickname}: {e}")
        finally:
            await self.disconnect_client(client)
    
    async def handle_message(self, client: Client, message: dict):
        """Route message based on type"""
        msg_type = message.get('type')
        
        if msg_type == MessageType.REGISTER.value:
            await self.handle_register(client, message)
        
        elif msg_type == MessageType.PUBLIC_KEY_REQUEST.value:
            await self.handle_public_key_request(client, message)
        
        elif msg_type == MessageType.PRIVATE_MESSAGE.value:
            await self.route_private_message(client, message)
        
        elif msg_type == MessageType.CHANNEL_MESSAGE.value:
            await self.route_channel_message(client, message)
        
        elif msg_type == MessageType.JOIN_CHANNEL.value:
            await self.handle_join_channel(client, message)
        
        elif msg_type == MessageType.LEAVE_CHANNEL.value:
            await self.handle_leave_channel(client, message)
        
        elif msg_type == MessageType.OP_USER.value:
            await self.handle_op_user(client, message)
        
        elif msg_type == MessageType.WHOIS.value:
            await self.handle_whois(client, message)
        
        elif msg_type == MessageType.LIST_CHANNELS.value:
            await self.handle_list_channels(client, message)
        
        elif msg_type == MessageType.KICK_USER.value:
            await self.handle_kick_user(client, message)
        
        elif msg_type == MessageType.SET_TOPIC.value:
            await self.handle_set_topic(client, message)
        
        elif msg_type in [MessageType.IMAGE_START.value, 
                         MessageType.IMAGE_CHUNK.value,
                         MessageType.IMAGE_END.value]:
            await self.route_image_message(client, message)
        
        elif msg_type == MessageType.DISCONNECT.value:
            await self.disconnect_client(client)
        
        else:
            await client.send(Protocol.error(f"Unknown message type: {msg_type}"))
    
    async def handle_register(self, client: Client, message: dict):
        """Register a new client"""
        nickname = message.get('nickname')
        public_key = message.get('public_key')
        
        if not nickname or not public_key:
            await client.send(Protocol.error("Missing nickname or public_key"))
            return
        
        # Check if nickname is taken
        if nickname in self.nicknames:
            await client.send(Protocol.error(f"Nickname {nickname} already taken"))
            return
        
        # Generate unique user_id
        user_id = f"user_{len(self.clients)}_{nickname}"
        
        # Register client
        client.user_id = user_id
        client.nickname = nickname
        client.public_key = public_key
        
        self.clients[user_id] = client
        self.nicknames[nickname] = user_id
        
        logger.info(f"Registered {nickname} with ID {user_id}")
        
        # Send acknowledgment with user_id and server description
        response = Protocol.build_message(
            MessageType.ACK,
            success=True,
            user_id=user_id,
            message=f"Welcome {nickname}!",
            description=self.description
        )
        await client.send(response)
        
        # Send list of online users
        await self.send_user_list(client)
        
        # Broadcast to all other users that a new user joined
        await self.broadcast_new_user(client)
    
    async def handle_public_key_request(self, client: Client, message: dict):
        """Send a peer's public key"""
        target_nickname = message.get('target_nickname')
        
        if target_nickname not in self.nicknames:
            await client.send(Protocol.error(f"User {target_nickname} not found"))
            return
        
        target_id = self.nicknames[target_nickname]
        target_client = self.clients[target_id]
        
        response = Protocol.build_message(
            MessageType.PUBLIC_KEY_RESPONSE,
            user_id=target_id,
            nickname=target_nickname,
            public_key=target_client.public_key
        )
        await client.send(response)
    
    async def route_private_message(self, client: Client, message: dict):
        """Route encrypted private message (server cannot decrypt)"""
        to_id = message.get('to_id')
        
        if to_id not in self.clients:
            await client.send(Protocol.error(f"User {to_id} not found"))
            return
        
        target = self.clients[to_id]
        
        # Just forward the encrypted message as-is
        await target.send(json.dumps(message))
        logger.debug(f"Routed encrypted message from {client.nickname} to {target.nickname}")
    
    async def route_channel_message(self, client: Client, message: dict):
        """Route encrypted channel message to all members"""
        channel = message.get('to_id')
        
        if channel not in self.channels:
            await client.send(Protocol.error(f"Channel {channel} not found"))
            return
        
        if client.user_id not in self.channels[channel]:
            await client.send(Protocol.error(f"You are not in channel {channel}"))
            return
        
        # Route to all channel members except sender
        for user_id in self.channels[channel]:
            if user_id != client.user_id and user_id in self.clients:
                await self.clients[user_id].send(json.dumps(message))
        
        logger.debug(f"Routed channel message from {client.nickname} to {channel}")
    
    async def handle_join_channel(self, client: Client, message: dict):
        """Handle channel join request"""
        channel = message.get('channel')
        password = message.get('password')
        creator_password = message.get('creator_password')  # For regaining operator status
        
        if not channel:
            await client.send(Protocol.error("Missing channel name"))
            return
        
        # Normalize channel name: lowercase and replace spaces with hyphens
        channel = channel.lower().replace(' ', '-')
        
        # Check if this is a persistent channel (exists in storage)
        channel_exists = channel in self.channel_passwords or channel in self.channel_creator_passwords
        
        # Check if channel is currently active
        channel_active = channel in self.channels
        
        # Scenario 1: Brand new channel (not in persistent storage)
        if not channel_exists and not channel_active:
            # User is creating this channel for the first time
            if not creator_password or len(creator_password) < 4:
                await client.send(Protocol.error(
                    "Creating new channel requires a creator password (4+ characters) to regain operator status later.\\n"
                    "Usage: /join #channel <join_password> <creator_password>\\n"
                    "Or just: /join #channel <password> (uses same password for both)"
                ))
                return
            
            # Create new persistent channel
            self.channels[channel] = set()
            self.channel_operators[channel] = set()
            self.channel_operators[channel].add(client.user_id)
            
            # Save passwords (hashed)
            if password:
                self.channel_passwords[channel] = self.hash_password(password)
            self.channel_creator_passwords[channel] = self.hash_password(creator_password)
            
            # Save to disk
            self.save_channels()
            
            logger.info(f"Created new persistent channel {channel} with {client.nickname} as operator")
        
        # Scenario 2: Persistent channel exists (in storage) but not currently active
        elif channel_exists and not channel_active:
            # Re-initialize the channel
            self.channels[channel] = set()
            self.channel_operators[channel] = set()
            
            # Check if user should regain operator status
            if creator_password and channel in self.channel_creator_passwords:
                if self.hash_password(creator_password) == self.channel_creator_passwords[channel]:
                    self.channel_operators[channel].add(client.user_id)
                    logger.info(f"{client.nickname} regained operator status in {channel}")
                else:
                    await client.send(Protocol.error("Incorrect creator password"))
                    return
            
            # Check join password if set
            if channel in self.channel_passwords:
                if not password or self.hash_password(password) != self.channel_passwords[channel]:
                    await client.send(Protocol.error("Incorrect channel password"))
                    return
        
        # Scenario 3: Channel is currently active
        elif channel_active:
            # Check if user should regain operator status
            if creator_password and channel in self.channel_creator_passwords:
                if self.hash_password(creator_password) == self.channel_creator_passwords[channel]:
                    self.channel_operators[channel].add(client.user_id)
                    logger.info(f"{client.nickname} regained operator status in {channel}")
            
            # Check join password if set
            if channel in self.channel_passwords:
                if not password or self.hash_password(password) != self.channel_passwords[channel]:
                    await client.send(Protocol.error("Incorrect channel password"))
                    return
        
        # Add client to channel
        self.channels[channel].add(client.user_id)
        client.channels.add(channel)
        
        logger.info(f"{client.nickname} joined {channel}")
        
        # Send acknowledgment with channel member list
        members = [
            {
                "user_id": uid,
                "nickname": self.clients[uid].nickname,
                "public_key": self.clients[uid].public_key,
                "is_operator": uid in self.channel_operators.get(channel, set())
            }
            for uid in self.channels[channel] if uid in self.clients
        ]
        
        response = Protocol.build_message(
            MessageType.ACK,
            success=True,
            channel=channel,
            members=members,
            is_protected=channel in self.channel_passwords
        )
        await client.send(response)
        
        # Notify other channel members
        join_notification = Protocol.build_message(
            MessageType.JOIN_CHANNEL,
            user_id=client.user_id,
            nickname=client.nickname,
            channel=channel,
            public_key=client.public_key
        )
        
        for user_id in self.channels[channel]:
            if user_id != client.user_id and user_id in self.clients:
                await self.clients[user_id].send(join_notification)
    
    async def handle_leave_channel(self, client: Client, message: dict):
        """Handle channel leave request"""
        channel = message.get('channel')
        
        if channel not in self.channels or client.user_id not in self.channels[channel]:
            await client.send(Protocol.error(f"You are not in channel {channel}"))
            return
        
        # Remove from channel
        self.channels[channel].remove(client.user_id)
        client.channels.discard(channel)
        
        # Remove from operators if they were one
        if channel in self.channel_operators:
            self.channel_operators[channel].discard(client.user_id)
        
        # Channels are now persistent - don't delete when empty
        # if not self.channels[channel]:
        #     del self.channels[channel]
        #     logger.info(f"Deleted empty channel {channel}")
        
        logger.info(f"{client.nickname} left {channel}")
        
        await client.send(Protocol.ack(True, f"Left channel {channel}"))
        
        # Notify remaining members
        if channel in self.channels:
            leave_notification = Protocol.build_message(
                MessageType.LEAVE_CHANNEL,
                user_id=client.user_id,
                nickname=client.nickname,
                channel=channel
            )
            
            for user_id in self.channels[channel]:
                if user_id in self.clients:
                    await self.clients[user_id].send(leave_notification)
    
    async def route_image_message(self, client: Client, message: dict):
        """Route encrypted image messages"""
        to_id = message.get('to_id')
        
        if to_id not in self.clients:
            await client.send(Protocol.error(f"User {to_id} not found"))
            return
        
        target = self.clients[to_id]
        
        # Forward encrypted image data as-is
        await target.send(json.dumps(message))
        logger.debug(f"Routed encrypted image from {client.nickname} to {target.nickname}")
    
    async def handle_op_user(self, client: Client, message: dict):
        """Handle granting operator status to a user"""
        channel = message.get('channel')
        target_nickname = message.get('target_nickname')
        
        if not channel or not target_nickname:
            await client.send(Protocol.error("Missing channel or target_nickname"))
            return
        
        # Check if channel exists
        if channel not in self.channels:
            await client.send(Protocol.error(f"Channel {channel} does not exist"))
            return
        
        # Check if requester is in the channel
        if client.user_id not in self.channels[channel]:
            await client.send(Protocol.error(f"You are not in channel {channel}"))
            return
        
        # Check if requester is an operator (this is the only authorization needed)
        if client.user_id not in self.channel_operators.get(channel, set()):
            await client.send(Protocol.error("You are not an operator in this channel"))
            return
        
        # Find target user
        if target_nickname not in self.nicknames:
            await client.send(Protocol.error(f"User {target_nickname} not found"))
            return
        
        target_id = self.nicknames[target_nickname]
        
        # Check if target is in the channel
        if target_id not in self.channels[channel]:
            await client.send(Protocol.error(f"{target_nickname} is not in channel {channel}"))
            return
        
        # Grant operator status
        if channel not in self.channel_operators:
            self.channel_operators[channel] = set()
        self.channel_operators[channel].add(target_id)
        
        logger.info(f"{client.nickname} granted operator status to {target_nickname} in {channel}")
        
        # Send acknowledgment
        await client.send(Protocol.ack(True, f"{target_nickname} is now an operator in {channel}"))
        
        # Notify the target user
        if target_id in self.clients:
            notification = Protocol.build_message(
                MessageType.ACK,
                success=True,
                message=f"You are now an operator in {channel}",
                channel=channel,
                is_operator=True
            )
            await self.clients[target_id].send(notification)
        
        # Notify all channel members
        op_notification = Protocol.build_message(
            MessageType.OP_USER,
            channel=channel,
            user_id=target_id,
            nickname=target_nickname,
            granted_by=client.nickname
        )
        for user_id in self.channels[channel]:
            if user_id in self.clients and user_id != client.user_id and user_id != target_id:
                await self.clients[user_id].send(op_notification)
    
    async def handle_kick_user(self, client: Client, message: dict):
        """Handle kicking a user from a channel"""
        channel = message.get('channel')
        target_nickname = message.get('target_nickname')
        reason = message.get('reason', 'No reason given')
        
        if not channel or not target_nickname:
            await client.send(Protocol.error("Missing channel or target_nickname"))
            return
        
        # Check if channel exists
        if channel not in self.channels:
            await client.send(Protocol.error(f"Channel {channel} does not exist"))
            return
        
        # Check if requester is in the channel
        if client.user_id not in self.channels[channel]:
            await client.send(Protocol.error(f"You are not in channel {channel}"))
            return
        
        # Check if requester is an operator
        if client.user_id not in self.channel_operators.get(channel, set()):
            await client.send(Protocol.error("You are not an operator in this channel"))
            return
        
        # Find target user
        if target_nickname not in self.nicknames:
            await client.send(Protocol.error(f"User {target_nickname} not found"))
            return
        
        target_id = self.nicknames[target_nickname]
        
        # Check if target is in the channel
        if target_id not in self.channels[channel]:
            await client.send(Protocol.error(f"{target_nickname} is not in channel {channel}"))
            return
        
        # Can't kick yourself
        if target_id == client.user_id:
            await client.send(Protocol.error("You cannot kick yourself"))
            return
        
        # Remove user from channel
        self.channels[channel].remove(target_id)
        if target_id in self.clients:
            self.clients[target_id].channels.discard(channel)
        
        # Remove operator status if they had it
        if channel in self.channel_operators and target_id in self.channel_operators[channel]:
            self.channel_operators[channel].remove(target_id)
        
        logger.info(f"{client.nickname} kicked {target_nickname} from {channel}: {reason}")
        
        # Send acknowledgment to kicker
        await client.send(Protocol.ack(True, f"{target_nickname} has been kicked from {channel}"))
        
        # Notify the kicked user
        if target_id in self.clients:
            kick_notification = Protocol.build_message(
                MessageType.KICK_USER,
                channel=channel,
                kicked_by=client.nickname,
                reason=reason
            )
            await self.clients[target_id].send(kick_notification)
        
        # Notify all remaining channel members
        kick_announcement = Protocol.build_message(
            MessageType.CHANNEL_MESSAGE,
            channel=channel,
            sender="SERVER",
            text=f"{target_nickname} was kicked by {client.nickname}: {reason}"
        )
        for user_id in self.channels[channel]:
            if user_id in self.clients and user_id != client.user_id:
                await self.clients[user_id].send(kick_announcement)
    
    async def handle_set_topic(self, client: Client, message: dict):
        """Handle setting channel topic"""
        channel = message.get('channel')
        topic = message.get('topic', '')
        
        if not channel:
            await client.send(Protocol.error("Missing channel"))
            return
        
        # Check if channel exists
        if channel not in self.channels:
            await client.send(Protocol.error(f"Channel {channel} does not exist"))
            return
        
        # Check if requester is in the channel
        if client.user_id not in self.channels[channel]:
            await client.send(Protocol.error(f"You are not in channel {channel}"))
            return
        
        # Check if requester is an operator
        if client.user_id not in self.channel_operators.get(channel, set()):
            await client.send(Protocol.error("You are not an operator in this channel"))
            return
        
        # Set the topic
        self.channel_topics[channel] = topic
        
        logger.info(f"{client.nickname} set topic in {channel}: {topic}")
        
        # Send acknowledgment to setter
        await client.send(Protocol.ack(True, f"Topic set for {channel}"))
        
        # Notify all channel members
        topic_notification = Protocol.build_message(
            MessageType.SET_TOPIC,
            channel=channel,
            topic=topic,
            set_by=client.nickname
        )
        for user_id in self.channels[channel]:
            if user_id in self.clients and user_id != client.user_id:
                await self.clients[user_id].send(topic_notification)
    
    async def handle_whois(self, client: Client, message: dict):
        """Handle whois request"""
        target_nickname = message.get('target_nickname')
        
        if not target_nickname:
            await client.send(Protocol.error("Missing target nickname"))
            return
        
        # Find user
        target_id = self.nicknames.get(target_nickname)
        if not target_id or target_id not in self.clients:
            await client.send(Protocol.error(f"User {target_nickname} not found"))
            return
        
        target_client = self.clients[target_id]
        
        # Get channels the user is in
        user_channels = list(target_client.channels)
        
        # Send whois response
        response = Protocol.build_message(
            MessageType.WHOIS_RESPONSE,
            nickname=target_nickname,
            user_id=target_id,
            channels=user_channels,
            online=True
        )
        await client.send(response)
    
    async def handle_list_channels(self, client: Client, message: dict):
        """Handle list channels request"""
        # Build channel list with info
        channel_list = []
        for channel_name, members in self.channels.items():
            channel_info = {
                'name': channel_name,
                'users': len(members),
                'protected': channel_name in self.channel_passwords,
                'topic': self.channel_topics.get(channel_name, '')
            }
            channel_list.append(channel_info)
        
        # Sort by name
        channel_list.sort(key=lambda x: x['name'])
        
        # Send response
        response = Protocol.build_message(
            MessageType.CHANNEL_LIST_RESPONSE,
            channels=channel_list
        )
        await client.send(response)
    
    async def send_user_list(self, client: Client):
        """Send list of online users to a client (including self)"""
        users = [
            {
                "user_id": uid,
                "nickname": c.nickname,
                "public_key": c.public_key
            }
            for uid, c in self.clients.items()
        ]
        
        await client.send(Protocol.user_list(users))
    
    async def broadcast_new_user(self, new_client: Client):
        """Broadcast new user to all existing users"""
        user_info = Protocol.build_message(
            MessageType.USER_LIST,
            users=[{
                "user_id": new_client.user_id,
                "nickname": new_client.nickname,
                "public_key": new_client.public_key
            }]
        )
        
        for user_id, client in self.clients.items():
            if user_id != new_client.user_id:
                await client.send(user_info)
    
    async def disconnect_client(self, client: Client):
        """Disconnect a client and clean up"""
        if client.user_id:
            logger.info(f"Client {client.nickname} disconnected")
            
            # Remove from all channels
            for channel in list(client.channels):
                if channel in self.channels:
                    self.channels[channel].discard(client.user_id)
                    # Remove from operators
                    if channel in self.channel_operators:
                        self.channel_operators[channel].discard(client.user_id)
                    # Channels are persistent, don't delete
                    # Notify channel members
                    leave_msg = Protocol.build_message(
                        MessageType.LEAVE_CHANNEL,
                        user_id=client.user_id,
                        nickname=client.nickname,
                        channel=channel
                    )
                    for user_id in self.channels[channel]:
                        if user_id in self.clients:
                            await self.clients[user_id].send(leave_msg)
            
            # Remove from client list
            if client.user_id in self.clients:
                del self.clients[client.user_id]
            
            if client.nickname in self.nicknames:
                del self.nicknames[client.nickname]
        
        # Close connection
        try:
            client.writer.close()
            await client.writer.wait_closed()
        except:
            pass


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='JustIRC Secure Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=6667, help='Port to bind to')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    server = IRCServer(host=args.host, port=args.port)
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")


if __name__ == '__main__':
    main()
