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
from typing import Dict, Set, Optional
from protocol import Protocol, MessageType
from rate_limiter import RateLimiter, ConnectionRateLimiter
from auth_manager import AuthenticationManager
from input_validator import InputValidator
from ip_filter import IPFilter


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
        
        # Authentication settings
        enable_auth = self.config.get('enable_authentication', False)
        require_auth = self.config.get('require_authentication', False)
        accounts_file = os.path.join(data_dir, 'accounts.json')
        
        # Initialize authentication manager
        self.auth_manager = AuthenticationManager(
            accounts_file=accounts_file,
            enable_accounts=enable_auth,
            require_authentication=require_auth
        )
        
        # Track authenticated sessions
        self.authenticated_users: Dict[str, str] = {}  # user_id -> username
        
        # IP filtering
        enable_whitelist = self.config.get('enable_ip_whitelist', False)
        blacklist_file = os.path.join(data_dir, 'ip_blacklist.json')
        whitelist_file = os.path.join(data_dir, 'ip_whitelist.json')
        
        self.ip_filter = IPFilter(
            blacklist_file=blacklist_file,
            whitelist_file=whitelist_file,
            enable_whitelist=enable_whitelist
        )
        
        # Connection timeout settings
        self.connection_timeout = self.config.get('connection_timeout', 300)  # 5 minutes
        self.read_timeout = self.config.get('read_timeout', 60)  # 1 minute
        self.max_message_size = self.config.get('max_message_size', 65536)  # 64KB
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        self.clients: Dict[str, Client] = {}  # user_id -> Client
        self.channels: Dict[str, Set[str]] = {}  # channel -> set of user_ids
        self.channel_passwords: Dict[str, str] = {}  # channel -> hashed password
        self.channel_operators: Dict[str, Set[str]] = {}  # channel -> set of operator user_ids
        self.channel_mods: Dict[str, Set[str]] = {}  # channel -> set of mod user_ids
        self.channel_owners: Dict[str, str] = {}  # channel -> owner user_id
        self.channel_creator_passwords: Dict[str, str] = {}  # channel -> hashed creator password
        self.operator_passwords: Dict[str, Dict[str, str]] = {}  # channel -> {user_id -> hashed_password}
        self.channel_banned: Dict[str, Set[str]] = {}  # channel -> set of banned user_ids
        self.channel_topics: Dict[str, str] = {}  # channel -> topic string
        self.nicknames: Dict[str, str] = {}  # nickname -> user_id
        self.pending_op_auth: Dict[str, tuple] = {}  # user_id -> (channel, should_be_op)
        
        # Rate limiting
        # Messages: 30 per 10 seconds per client
        self.message_limiter = RateLimiter(max_requests=30, time_window=10.0)
        # Image chunks: 100 per 10 seconds per client  
        self.image_limiter = RateLimiter(max_requests=100, time_window=10.0)
        # Connections: 5 per minute per IP, ban after 10 violations
        self.connection_limiter = ConnectionRateLimiter(
            max_connections=5, 
            time_window=60.0, 
            ban_threshold=10
        )
        
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
                
                # Load operator passwords (already hashed)
                self.operator_passwords = data.get('operator_passwords', {})
                
                # Load channel owners
                self.channel_owners = data.get('channel_owners', {})
                
                # Load banned users
                # Convert lists back to sets
                banned_data = data.get('channel_banned', {})
                for channel, banned_list in banned_data.items():
                    self.channel_banned[channel] = set(banned_list)
                
                # Initialize empty operator and mod sets for existing channels
                for channel in self.channel_passwords.keys():
                    self.channel_operators[channel] = set()
                    self.channel_mods[channel] = set()
                    self.channels[channel] = set()
                
                logger.info(f"Loaded {len(self.channel_passwords)} persistent channels from {self.channels_file}")
            except Exception as e:
                logger.error(f"Error loading channels: {e}")
        else:
            logger.info("No existing channel data found, starting fresh")
    
    def save_channels(self):
        """Save persistent channel data to file"""
        try:
            # Convert sets to lists for JSON serialization
            banned_data = {}
            for channel, banned_set in self.channel_banned.items():
                banned_data[channel] = list(banned_set)
            
            data = {
                'channel_passwords': self.channel_passwords,
                'channel_creator_passwords': self.channel_creator_passwords,
                'operator_passwords': self.operator_passwords,
                'channel_owners': self.channel_owners,
                'channel_banned': banned_data
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
        
        # Extract IP address for rate limiting and filtering
        peername = writer.get_extra_info('peername')
        ip_address = peername[0] if peername else "unknown"
        
        # Check IP filter first
        if not self.ip_filter.is_allowed(ip_address):
            logger.warning(f"Connection from {ip_address} blocked by IP filter")
            try:
                error_msg = Protocol.error("Access denied")
                writer.write(error_msg.encode('utf-8') + b'\n')
                await writer.drain()
                writer.close()
                await writer.wait_closed()
            except:
                pass
            return
        
        # Check connection rate limit
        allowed, reason = self.connection_limiter.is_allowed(ip_address)
        if not allowed:
            logger.warning(f"Connection from {ip_address} rate limited: {reason}")
            try:
                error_msg = Protocol.error(reason)
                writer.write(error_msg.encode('utf-8') + b'\n')
                await writer.drain()
                writer.close()
                await writer.wait_closed()
            except:
                pass
            return
        
        logger.info(f"New connection from {client.address}")
        
        try:
            while True:
                # Read message with timeout
                try:
                    data = await asyncio.wait_for(
                        reader.readline(),
                        timeout=self.read_timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Read timeout for {client.nickname or client.address}")
                    await client.send(Protocol.error("Read timeout"))
                    break
                
                if not data:
                    break
                
                # Check message size
                if len(data) > self.max_message_size:
                    logger.warning(f"Message too large from {client.nickname or client.address}")
                    await client.send(Protocol.error("Message too large"))
                    continue
                
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
        
        elif msg_type == MessageType.AUTH_REQUEST.value:
            await self.handle_auth_request(client, message)
        
        elif msg_type == MessageType.CREATE_ACCOUNT.value:
            await self.handle_create_account(client, message)
        
        elif msg_type == MessageType.CHANGE_PASSWORD.value:
            await self.handle_change_password(client, message)
        
        elif msg_type == MessageType.PUBLIC_KEY_REQUEST.value:
            await self.handle_public_key_request(client, message)
        
        elif msg_type == MessageType.REKEY_REQUEST.value:
            await self.handle_rekey_request(client, message)
        
        elif msg_type == MessageType.REKEY_RESPONSE.value:
            await self.handle_rekey_response(client, message)
        
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
        
        elif msg_type == MessageType.UNOP_USER.value:
            await self.handle_unop_user(client, message)
        
        elif msg_type == MessageType.MOD_USER.value:
            await self.handle_mod_user(client, message)
        
        elif msg_type == MessageType.UNMOD_USER.value:
            await self.handle_unmod_user(client, message)
        
        elif msg_type == MessageType.OP_PASSWORD_RESPONSE.value:
            await self.handle_op_password_response(client, message)
        
        elif msg_type == MessageType.BAN_USER.value:
            await self.handle_ban_user(client, message)
        
        elif msg_type == MessageType.UNBAN_USER.value:
            await self.handle_unban_user(client, message)
        
        elif msg_type == MessageType.KICKBAN_USER.value:
            await self.handle_kickban_user(client, message)
        
        elif msg_type == MessageType.TRANSFER_OWNERSHIP.value:
            await self.handle_transfer_ownership(client, message)
        
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
        password = message.get('password')
        session_token = message.get('session_token')
        
        if not nickname or not public_key:
            await client.send(Protocol.error("Missing nickname or public_key"))
            return
        
        # Validate nickname
        is_valid, error_msg = InputValidator.validate_nickname(nickname)
        if not is_valid:
            await client.send(Protocol.error(error_msg))
            return
        
        # Check authentication requirements
        if self.auth_manager.require_authentication:
            # Verify session token or password
            authenticated_username = None
            
            if session_token:
                authenticated_username = self.auth_manager.verify_session(session_token)
            elif password and self.auth_manager.account_exists(nickname):
                # Try to authenticate
                token = self.auth_manager.authenticate(nickname, password)
                if token:
                    authenticated_username = nickname
            
            if not authenticated_username:
                await client.send(Protocol.auth_required(
                    "Authentication required. Please login or create an account."
                ))
                return
            
            # Check if account is disabled
            if self.auth_manager.is_account_disabled(authenticated_username):
                await client.send(Protocol.error("Account is disabled"))
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
        
        # Track authentication
        if self.auth_manager.enable_accounts and password:
            username = self.auth_manager.verify_session(session_token) if session_token else nickname
            if username:
                self.authenticated_users[user_id] = username
        
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
    
    async def handle_auth_request(self, client: Client, message: dict):
        """Handle authentication request"""
        username = message.get('username')
        password = message.get('password')
        
        if not username or not password:
            await client.send(Protocol.auth_response(
                success=False,
                message="Missing username or password"
            ))
            return
        
        # Authenticate
        session_token = self.auth_manager.authenticate(username, password)
        
        if session_token:
            await client.send(Protocol.auth_response(
                success=True,
                session_token=session_token,
                message=f"Authenticated as {username}"
            ))
            logger.info(f"User {username} authenticated successfully")
        else:
            # Check if account is locked
            if self.auth_manager.is_account_locked(username):
                await client.send(Protocol.auth_response(
                    success=False,
                    message="Account temporarily locked due to failed login attempts"
                ))
            else:
                await client.send(Protocol.auth_response(
                    success=False,
                    message="Invalid username or password"
                ))
            logger.warning(f"Failed authentication attempt for {username}")
    
    async def handle_create_account(self, client: Client, message: dict):
        """Handle account creation request"""
        if not self.auth_manager.enable_accounts:
            await client.send(Protocol.error("Account creation is disabled"))
            return
        
        username = message.get('username')
        password = message.get('password')
        email = message.get('email')
        
        if not username or not password:
            await client.send(Protocol.error("Missing username or password"))
            return
        
        # Validate username (alphanumeric, 3-20 chars)
        if not username.isalnum() or len(username) < 3 or len(username) > 20:
            await client.send(Protocol.error(
                "Username must be 3-20 alphanumeric characters"
            ))
            return
        
        # Validate password length
        if len(password) < 8:
            await client.send(Protocol.error(
                "Password must be at least 8 characters"
            ))
            return
        
        # Create account
        if self.auth_manager.create_account(username, password, email):
            # Automatically authenticate the new user
            session_token = self.auth_manager.authenticate(username, password)
            
            await client.send(Protocol.build_message(
                MessageType.ACK,
                success=True,
                session_token=session_token,
                message=f"Account created for {username}"
            ))
            logger.info(f"New account created: {username}")
        else:
            await client.send(Protocol.error(
                f"Username {username} is already taken"
            ))
    
    async def handle_change_password(self, client: Client, message: dict):
        """Handle password change request"""
        if not self.auth_manager.enable_accounts:
            await client.send(Protocol.error("Authentication is disabled"))
            return
        
        if not client.user_id or client.user_id not in self.authenticated_users:
            await client.send(Protocol.error("You must be authenticated"))
            return
        
        old_password = message.get('old_password')
        new_password = message.get('new_password')
        
        if not old_password or not new_password:
            await client.send(Protocol.error("Missing old_password or new_password"))
            return
        
        # Validate new password length
        if len(new_password) < 8:
            await client.send(Protocol.error(
                "New password must be at least 8 characters"
            ))
            return
        
        username = self.authenticated_users[client.user_id]
        
        if self.auth_manager.change_password(username, old_password, new_password):
            await client.send(Protocol.build_message(
                MessageType.ACK,
                success=True,
                message="Password changed successfully"
            ))
            logger.info(f"Password changed for user {username}")
        else:
            await client.send(Protocol.error("Invalid old password"))
    
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
    
    async def handle_rekey_request(self, client: Client, message: dict):
        """Handle key rotation request"""
        to_id = message.get('to_id')
        new_public_key = message.get('new_public_key')
        
        if not to_id or not new_public_key:
            await client.send(Protocol.error("Missing to_id or new_public_key"))
            return
        
        if to_id not in self.clients:
            await client.send(Protocol.error(f"User {to_id} not found"))
            return
        
        # Forward the rekey request to the target user
        target = self.clients[to_id]
        rekey_msg = Protocol.build_message(
            MessageType.REKEY_REQUEST,
            from_id=client.user_id,
            from_nickname=client.nickname,
            new_public_key=new_public_key
        )
        await target.send(rekey_msg)
        logger.info(f"Key rotation request from {client.nickname} to {target.nickname}")
    
    async def handle_rekey_response(self, client: Client, message: dict):
        """Handle key rotation response"""
        to_id = message.get('to_id')
        new_public_key = message.get('new_public_key')
        
        if not to_id or not new_public_key:
            await client.send(Protocol.error("Missing to_id or new_public_key"))
            return
        
        if to_id not in self.clients:
            await client.send(Protocol.error(f"User {to_id} not found"))
            return
        
        # Forward the rekey response to the original requester
        target = self.clients[to_id]
        rekey_msg = Protocol.build_message(
            MessageType.REKEY_RESPONSE,
            from_id=client.user_id,
            from_nickname=client.nickname,
            new_public_key=new_public_key
        )
        await target.send(rekey_msg)
        logger.info(f"Key rotation response from {client.nickname} to {target.nickname}")
    
    async def route_private_message(self, client: Client, message: dict):
        """Route encrypted private message (server cannot decrypt)"""
        # Check rate limit
        if not self.message_limiter.is_allowed(client.user_id):
            retry_after = self.message_limiter.get_retry_after(client.user_id)
            await client.send(Protocol.error(
                f"Rate limit exceeded. Retry after {retry_after:.1f} seconds"
            ))
            logger.warning(f"Rate limited message from {client.nickname}")
            return
        
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
        # Check rate limit
        if not self.message_limiter.is_allowed(client.user_id):
            retry_after = self.message_limiter.get_retry_after(client.user_id)
            await client.send(Protocol.error(
                f"Rate limit exceeded. Retry after {retry_after:.1f} seconds"
            ))
            logger.warning(f"Rate limited channel message from {client.nickname}")
            return
        
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
        creator_password = message.get('creator_password')  # For regaining owner/operator status
        
        if not channel:
            await client.send(Protocol.error("Missing channel name"))
            return
        
        # Validate channel name
        is_valid, error_msg = InputValidator.validate_channel_name(channel)
        if not is_valid:
            await client.send(Protocol.error(error_msg))
            return
        
        # Normalize channel name: lowercase and replace spaces with hyphens
        channel = channel.lower().replace(' ', '-')
        
        # Check if user is banned from this channel
        if channel in self.channel_banned and client.user_id in self.channel_banned[channel]:
            await client.send(Protocol.error(f"You are banned from {channel}"))
            return
        
        # Check if this is a persistent channel (exists in storage)
        channel_exists = channel in self.channel_passwords or channel in self.channel_creator_passwords
        
        # Check if channel is currently active
        channel_active = channel in self.channels
        
        # Track if user should be operator (needs password)
        should_be_operator = False
        is_owner = False
        
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
            self.channel_mods[channel] = set()
            self.channel_banned[channel] = set()
            
            # Set user as channel owner
            self.channel_owners[channel] = client.user_id
            is_owner = True
            
            # Save passwords (hashed)
            if password:
                self.channel_passwords[channel] = self.hash_password(password)
            self.channel_creator_passwords[channel] = self.hash_password(creator_password)
            
            # Owner needs to set operator password
            should_be_operator = True
            
            # Save to disk
            self.save_channels()
            
            logger.info(f"Created new persistent channel {channel} with {client.nickname} as owner")
        
        # Scenario 2: Persistent channel exists (in storage) but not currently active
        elif channel_exists and not channel_active:
            # Re-initialize the channel
            self.channels[channel] = set()
            self.channel_operators[channel] = set()
            self.channel_mods[channel] = set()
            if channel not in self.channel_banned:
                self.channel_banned[channel] = set()
            
            # Check if user should regain operator/owner status
            if creator_password and channel in self.channel_creator_passwords:
                if self.hash_password(creator_password) == self.channel_creator_passwords[channel]:
                    should_be_operator = True
                    # Check if they're the original owner
                    if channel in self.channel_owners and self.channel_owners[channel] == client.user_id:
                        is_owner = True
                    logger.info(f"{client.nickname} regaining operator status in {channel}")
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
            # Check if user should regain operator/owner status
            if creator_password and channel in self.channel_creator_passwords:
                if self.hash_password(creator_password) == self.channel_creator_passwords[channel]:
                    should_be_operator = True
                    # Check if they're the original owner
                    if channel in self.channel_owners and self.channel_owners[channel] == client.user_id:
                        is_owner = True
                    logger.info(f"{client.nickname} regaining operator status in {channel}")
            
            # Check join password if set
            if channel in self.channel_passwords:
                if not password or self.hash_password(password) != self.channel_passwords[channel]:
                    await client.send(Protocol.error("Incorrect channel password"))
                    return
        
        # Add client to channel
        self.channels[channel].add(client.user_id)
        client.channels.add(channel)
        
        # If user should be operator, request password verification
        if should_be_operator:
            # Check if they already have an operator password set
            if channel in self.operator_passwords and client.user_id in self.operator_passwords[channel]:
                # Ask for password
                self.pending_op_auth[client.user_id] = (channel, True, is_owner)
                request_msg = Protocol.build_message(
                    MessageType.OP_PASSWORD_REQUEST,
                    channel=channel,
                    action="verify"
                )
                await client.send(request_msg)
                logger.info(f"Requesting operator password from {client.nickname} for {channel}")
                return  # Don't complete join yet
            else:
                # First time as operator - ask to set password
                self.pending_op_auth[client.user_id] = (channel, True, is_owner)
                request_msg = Protocol.build_message(
                    MessageType.OP_PASSWORD_REQUEST,
                    channel=channel,
                    action="set"
                )
                await client.send(request_msg)
                logger.info(f"Requesting new operator password from {client.nickname} for {channel}")
                return  # Don't complete join yet
        
        # Complete the join process
        await self.complete_join(client, channel, False, is_owner)
    
    async def complete_join(self, client: Client, channel: str, is_operator: bool, is_owner: bool):
        """Complete the join process after authentication"""
        # Grant operator status if needed
        if is_operator:
            self.channel_operators[channel].add(client.user_id)
            logger.info(f"{client.nickname} joined {channel} as operator")
        else:
            logger.info(f"{client.nickname} joined {channel}")
        
        # Send acknowledgment with channel member list
        members = [
            {
                "user_id": uid,
                "nickname": self.clients[uid].nickname,
                "public_key": self.clients[uid].public_key,
                "is_operator": uid in self.channel_operators.get(channel, set()),
                "is_mod": uid in self.channel_mods.get(channel, set()),
                "is_owner": self.channel_owners.get(channel) == uid
            }
            for uid in self.channels[channel] if uid in self.clients
        ]
        
        response = Protocol.build_message(
            MessageType.ACK,
            success=True,
            channel=channel,
            members=members,
            is_protected=channel in self.channel_passwords,
            is_operator=is_operator,
            is_owner=is_owner
        )
        await client.send(response)
        
        # Notify other channel members
        join_notification = Protocol.build_message(
            MessageType.JOIN_CHANNEL,
            user_id=client.user_id,
            nickname=client.nickname,
            channel=channel,
            public_key=client.public_key,
            is_operator=is_operator,
            is_mod=client.user_id in self.channel_mods.get(channel, set()),
            is_owner=is_owner
        )
        
        for user_id in self.channels[channel]:
            if user_id != client.user_id and user_id in self.clients:
                await self.clients[user_id].send(join_notification)
    
    async def handle_op_password_response(self, client: Client, message: dict):
        """Handle operator password response"""
        password = message.get('password')
        channel = message.get('channel')
        
        if not password:
            await client.send(Protocol.error("Password required"))
            # Disconnect user
            await self.disconnect_client(client)
            return
        
        # Check if we're expecting a response from this user
        if client.user_id not in self.pending_op_auth:
            await client.send(Protocol.error("Unexpected password response"))
            return
        
        expected_channel, should_be_op, is_owner = self.pending_op_auth[client.user_id]
        
        if channel != expected_channel:
            await client.send(Protocol.error("Channel mismatch"))
            await self.disconnect_client(client)
            return
        
        # Check if this is a new password (set) or verification
        if channel not in self.operator_passwords:
            self.operator_passwords[channel] = {}
        
        if client.user_id in self.operator_passwords[channel]:
            # Verify existing password
            if self.hash_password(password) != self.operator_passwords[channel][client.user_id]:
                await client.send(Protocol.error("Incorrect operator password"))
                await self.disconnect_client(client)
                del self.pending_op_auth[client.user_id]
                return
        else:
            # Set new password
            if len(password) < 4:
                await client.send(Protocol.error("Operator password must be at least 4 characters"))
                await self.disconnect_client(client)
                del self.pending_op_auth[client.user_id]
                return
            self.operator_passwords[channel][client.user_id] = self.hash_password(password)
            self.save_channels()
            logger.info(f"Set operator password for {client.nickname} in {channel}")
        
        # Authentication successful
        del self.pending_op_auth[client.user_id]
        await self.complete_join(client, channel, True, is_owner)
    
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
        
        # Remove from mods if they were one
        if channel in self.channel_mods:
            self.channel_mods[channel].discard(client.user_id)
        
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
        # Rate limit image chunks
        msg_type = message.get('type')
        if msg_type == MessageType.IMAGE_CHUNK.value:
            if not self.image_limiter.is_allowed(client.user_id):
                retry_after = self.image_limiter.get_retry_after(client.user_id)
                await client.send(Protocol.error(
                    f"Image transfer rate limit exceeded. Retry after {retry_after:.1f} seconds"
                ))
                logger.warning(f"Rate limited image chunk from {client.nickname}")
                return
        
        to_id = message.get('to_id')
        
        if to_id not in self.clients:
            await client.send(Protocol.error(f"User {to_id} not found"))
            return
        
        target = self.clients[to_id]
        
        # Forward encrypted image data as-is
        await target.send(json.dumps(message))
        logger.debug(f"Routed encrypted image from {client.nickname} to {target.nickname}")
    
    async def handle_op_user(self, client: Client, message: dict):
        """Handle granting operator status to a user - Only owners can do this"""
        channel = message.get('channel')
        target_nickname = message.get('target_nickname')
        op_password = message.get('op_password')
        
        if not channel or not target_nickname:
            await client.send(Protocol.error("Missing channel or target_nickname"))
            return
        
        if not op_password or len(op_password) < 4:
            await client.send(Protocol.error("Must provide an operator password (4+ chars) for the new operator"))
            return
        
        # Check if channel exists
        if channel not in self.channels:
            await client.send(Protocol.error(f"Channel {channel} does not exist"))
            return
        
        # Check if requester is in the channel
        if client.user_id not in self.channels[channel]:
            await client.send(Protocol.error(f"You are not in channel {channel}"))
            return
        
        # Only channel owner can grant operator status
        if self.channel_owners.get(channel) != client.user_id:
            await client.send(Protocol.error("Only the channel owner can grant operator status"))
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
        
        # Set their operator password
        if channel not in self.operator_passwords:
            self.operator_passwords[channel] = {}
        self.operator_passwords[channel][target_id] = self.hash_password(op_password)
        self.save_channels()
        
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
        
        # Check if requester is a mod or operator (either can kick)
        is_mod = client.user_id in self.channel_mods.get(channel, set())
        is_op = client.user_id in self.channel_operators.get(channel, set())
        is_owner = self.channel_owners.get(channel) == client.user_id
        
        if not (is_mod or is_op or is_owner):
            await client.send(Protocol.error("You must be a mod or operator to kick users"))
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
        
        # Check permissions - mods can't kick operators or owners, operators can kick anyone except owner
        target_is_op = target_id in self.channel_operators.get(channel, set())
        target_is_owner = self.channel_owners.get(channel) == target_id
        
        if target_is_owner:
            await client.send(Protocol.error("Cannot kick the channel owner"))
            return
        
        if is_mod and target_is_op:
            await client.send(Protocol.error("Mods cannot kick operators"))
            return
        
        # Remove user from channel
        self.channels[channel].remove(target_id)
        if target_id in self.clients:
            self.clients[target_id].channels.discard(channel)
        
        # Remove operator status if they had it
        if channel in self.channel_operators and target_id in self.channel_operators[channel]:
            self.channel_operators[channel].remove(target_id)
        
        # Remove mod status if they had it
        if channel in self.channel_mods and target_id in self.channel_mods[channel]:
            self.channel_mods[channel].remove(target_id)
        
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
    
    async def handle_unop_user(self, client: Client, message: dict):
        """Handle removing operator status from a user"""
        channel = message.get('channel')
        target_nickname = message.get('target_nickname')
        
        if not channel or not target_nickname:
            await client.send(Protocol.error("Missing channel or target_nickname"))
            return
        
        # Only owner can remove operator status
        if self.channel_owners.get(channel) != client.user_id:
            await client.send(Protocol.error("Only the channel owner can remove operator status"))
            return
        
        # Find target user
        if target_nickname not in self.nicknames:
            await client.send(Protocol.error(f"User {target_nickname} not found"))
            return
        
        target_id = self.nicknames[target_nickname]
        
        # Remove operator status
        if channel in self.channel_operators and target_id in self.channel_operators[channel]:
            self.channel_operators[channel].remove(target_id)
            # Also remove their operator password
            if channel in self.operator_passwords and target_id in self.operator_passwords[channel]:
                del self.operator_passwords[channel][target_id]
                self.save_channels()
            
            logger.info(f"{client.nickname} removed operator status from {target_nickname} in {channel}")
            await client.send(Protocol.ack(True, f"{target_nickname} is no longer an operator"))
            
            # Notify target
            if target_id in self.clients:
                await self.clients[target_id].send(Protocol.ack(True, f"You are no longer an operator in {channel}"))
            
            # Notify channel
            notification = Protocol.build_message(
                MessageType.UNOP_USER,
                channel=channel,
                user_id=target_id,
                nickname=target_nickname,
                removed_by=client.nickname
            )
            for user_id in self.channels[channel]:
                if user_id in self.clients and user_id != client.user_id and user_id != target_id:
                    await self.clients[user_id].send(notification)
        else:
            await client.send(Protocol.error(f"{target_nickname} is not an operator"))
    
    async def handle_mod_user(self, client: Client, message: dict):
        """Handle granting mod status to a user"""
        channel = message.get('channel')
        target_nickname = message.get('target_nickname')
        
        if not channel or not target_nickname:
            await client.send(Protocol.error("Missing channel or target_nickname"))
            return
        
        # Check if channel exists
        if channel not in self.channels:
            await client.send(Protocol.error(f"Channel {channel} does not exist"))
            return
        
        # Only operators and owners can grant mod status
        is_op = client.user_id in self.channel_operators.get(channel, set())
        is_owner = self.channel_owners.get(channel) == client.user_id
        
        if not (is_op or is_owner):
            await client.send(Protocol.error("Only operators can grant mod status"))
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
        
        # Grant mod status
        if channel not in self.channel_mods:
            self.channel_mods[channel] = set()
        self.channel_mods[channel].add(target_id)
        
        logger.info(f"{client.nickname} granted mod status to {target_nickname} in {channel}")
        await client.send(Protocol.ack(True, f"{target_nickname} is now a mod in {channel}"))
        
        # Notify target
        if target_id in self.clients:
            await self.clients[target_id].send(Protocol.ack(True, f"You are now a mod in {channel}"))
        
        # Notify channel
        notification = Protocol.build_message(
            MessageType.MOD_USER,
            channel=channel,
            user_id=target_id,
            nickname=target_nickname,
            granted_by=client.nickname
        )
        for user_id in self.channels[channel]:
            if user_id in self.clients and user_id != client.user_id and user_id != target_id:
                await self.clients[user_id].send(notification)
    
    async def handle_unmod_user(self, client: Client, message: dict):
        """Handle removing mod status from a user"""
        channel = message.get('channel')
        target_nickname = message.get('target_nickname')
        
        if not channel or not target_nickname:
            await client.send(Protocol.error("Missing channel or target_nickname"))
            return
        
        # Only operators and owners can remove mod status
        is_op = client.user_id in self.channel_operators.get(channel, set())
        is_owner = self.channel_owners.get(channel) == client.user_id
        
        if not (is_op or is_owner):
            await client.send(Protocol.error("Only operators can remove mod status"))
            return
        
        # Find target user
        if target_nickname not in self.nicknames:
            await client.send(Protocol.error(f"User {target_nickname} not found"))
            return
        
        target_id = self.nicknames[target_nickname]
        
        # Remove mod status
        if channel in self.channel_mods and target_id in self.channel_mods[channel]:
            self.channel_mods[channel].remove(target_id)
            logger.info(f"{client.nickname} removed mod status from {target_nickname} in {channel}")
            await client.send(Protocol.ack(True, f"{target_nickname} is no longer a mod"))
            
            # Notify target
            if target_id in self.clients:
                await self.clients[target_id].send(Protocol.ack(True, f"You are no longer a mod in {channel}"))
            
            # Notify channel
            notification = Protocol.build_message(
                MessageType.UNMOD_USER,
                channel=channel,
                user_id=target_id,
                nickname=target_nickname,
                removed_by=client.nickname
            )
            for user_id in self.channels[channel]:
                if user_id in self.clients and user_id != client.user_id and user_id != target_id:
                    await self.clients[user_id].send(notification)
        else:
            await client.send(Protocol.error(f"{target_nickname} is not a mod"))
    
    async def handle_ban_user(self, client: Client, message: dict):
        """Handle banning a user from a channel"""
        channel = message.get('channel')
        target_nickname = message.get('target_nickname')
        reason = message.get('reason', 'No reason given')
        
        if not channel or not target_nickname:
            await client.send(Protocol.error("Missing channel or target_nickname"))
            return
        
        # Only operators and owners can ban
        is_op = client.user_id in self.channel_operators.get(channel, set())
        is_owner = self.channel_owners.get(channel) == client.user_id
        
        if not (is_op or is_owner):
            await client.send(Protocol.error("Only operators can ban users"))
            return
        
        # Find target user
        if target_nickname not in self.nicknames:
            await client.send(Protocol.error(f"User {target_nickname} not found"))
            return
        
        target_id = self.nicknames[target_nickname]
        
        # Can't ban owner
        if self.channel_owners.get(channel) == target_id:
            await client.send(Protocol.error("Cannot ban the channel owner"))
            return
        
        # Can't ban yourself
        if target_id == client.user_id:
            await client.send(Protocol.error("Cannot ban yourself"))
            return
        
        # Add to ban list
        if channel not in self.channel_banned:
            self.channel_banned[channel] = set()
        self.channel_banned[channel].add(target_id)
        self.save_channels()
        
        logger.info(f"{client.nickname} banned {target_nickname} from {channel}: {reason}")
        await client.send(Protocol.ack(True, f"{target_nickname} has been banned from {channel}"))
        
        # If user is in channel, kick them
        if target_id in self.channels.get(channel, set()):
            self.channels[channel].remove(target_id)
            if target_id in self.clients:
                self.clients[target_id].channels.discard(channel)
            
            # Remove operator/mod status
            if channel in self.channel_operators:
                self.channel_operators[channel].discard(target_id)
            if channel in self.channel_mods:
                self.channel_mods[channel].discard(target_id)
            
            # Notify banned user
            if target_id in self.clients:
                ban_msg = Protocol.build_message(
                    MessageType.BAN_USER,
                    channel=channel,
                    banned_by=client.nickname,
                    reason=reason
                )
                await self.clients[target_id].send(ban_msg)
        
        # Notify channel
        announcement = Protocol.build_message(
            MessageType.CHANNEL_MESSAGE,
            channel=channel,
            sender="SERVER",
            text=f"{target_nickname} was banned by {client.nickname}: {reason}"
        )
        for user_id in self.channels.get(channel, set()):
            if user_id in self.clients:
                await self.clients[user_id].send(announcement)
    
    async def handle_kickban_user(self, client: Client, message: dict):
        """Handle kicking and banning a user in one action"""
        # Just call ban (which also kicks if needed)
        await self.handle_ban_user(client, message)
    
    async def handle_unban_user(self, client: Client, message: dict):
        """Handle unbanning a user from a channel"""
        channel = message.get('channel')
        target_nickname = message.get('target_nickname')
        
        if not channel or not target_nickname:
            await client.send(Protocol.error("Missing channel or target_nickname"))
            return
        
        # Only operators and owners can unban
        is_op = client.user_id in self.channel_operators.get(channel, set())
        is_owner = self.channel_owners.get(channel) == client.user_id
        
        if not (is_op or is_owner):
            await client.send(Protocol.error("Only operators can unban users"))
            return
        
        # Find target user
        if target_nickname not in self.nicknames:
            await client.send(Protocol.error(f"User {target_nickname} not found"))
            return
        
        target_id = self.nicknames[target_nickname]
        
        # Check if user is actually banned
        if channel not in self.channel_banned or target_id not in self.channel_banned[channel]:
            await client.send(Protocol.error(f"{target_nickname} is not banned from {channel}"))
            return
        
        # Remove from ban list
        self.channel_banned[channel].discard(target_id)
        self.save_channels()
        
        logger.info(f"{client.nickname} unbanned {target_nickname} from {channel}")
        await client.send(Protocol.ack(True, f"{target_nickname} has been unbanned from {channel}"))
        
        # Notify the unbanned user if online
        if target_id in self.clients:
            unban_msg = Protocol.build_message(
                MessageType.UNBAN_USER,
                channel=channel,
                unbanned_by=client.nickname
            )
            await self.clients[target_id].send(unban_msg)
        
        # Notify channel
        announcement = Protocol.build_message(
            MessageType.CHANNEL_MESSAGE,
            channel=channel,
            sender="SERVER",
            text=f"{target_nickname} was unbanned by {client.nickname}"
        )
        for user_id in self.channels.get(channel, set()):
            if user_id in self.clients:
                await self.clients[user_id].send(announcement)
    
    async def handle_transfer_ownership(self, client: Client, message: dict):
        """Handle transferring channel ownership"""
        channel = message.get('channel')
        target_nickname = message.get('target_nickname')
        
        if not channel or not target_nickname:
            await client.send(Protocol.error("Missing channel or target_nickname"))
            return
        
        # Only current owner can transfer
        if self.channel_owners.get(channel) != client.user_id:
            await client.send(Protocol.error("Only the channel owner can transfer ownership"))
            return
        
        # Find target user
        if target_nickname not in self.nicknames:
            await client.send(Protocol.error(f"User {target_nickname} not found"))
            return
        
        target_id = self.nicknames[target_nickname]
        
        # Target must be in the channel
        if target_id not in self.channels.get(channel, set()):
            await client.send(Protocol.error(f"{target_nickname} is not in channel {channel}"))
            return
        
        # Target must be an operator
        if target_id not in self.channel_operators.get(channel, set()):
            await client.send(Protocol.error("Can only transfer ownership to an operator"))
            return
        
        # Transfer ownership
        self.channel_owners[channel] = target_id
        self.save_channels()
        
        logger.info(f"{client.nickname} transferred ownership of {channel} to {target_nickname}")
        await client.send(Protocol.ack(True, f"Transferred ownership of {channel} to {target_nickname}"))
        
        # Notify new owner
        if target_id in self.clients:
            await self.clients[target_id].send(Protocol.ack(True, f"You are now the owner of {channel}"))
        
        # Notify channel
        announcement = Protocol.build_message(
            MessageType.CHANNEL_MESSAGE,
            channel=channel,
            sender="SERVER",
            text=f"{client.nickname} transferred channel ownership to {target_nickname}"
        )
        for user_id in self.channels.get(channel, set()):
            if user_id in self.clients and user_id != client.user_id and user_id != target_id:
                await self.clients[user_id].send(announcement)
    
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
                    # Remove from mods
                    if channel in self.channel_mods:
                        self.channel_mods[channel].discard(client.user_id)
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
            
            # Broadcast user disconnect to all remaining clients for global user list update
            disconnect_msg = Protocol.build_message(
                MessageType.DISCONNECT,
                user_id=client.user_id,
                nickname=client.nickname
            )
            for uid, c in self.clients.items():
                if uid != client.user_id:
                    await c.send(disconnect_msg)
            
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
