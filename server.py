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
import time
from typing import Dict, Set, Optional
from protocol import Protocol, MessageType
from rate_limiter import RateLimiter, ConnectionRateLimiter
from auth_manager import AuthenticationManager
from profile_manager import ProfileManager
from input_validator import InputValidator
from ip_filter import IPFilter
from message_queue import MessageQueue, MessageBatcher
from performance_monitor import PerformanceMonitor, ConnectionManager, RoutingOptimizer
from crypto_layer import CryptoLayer


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
        self.status: str = "online"  # online, away, busy, dnd
        self.status_message: str = ""
        
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
        
        # Initialize profile manager
        profiles_file = os.path.join(data_dir, 'user_profiles.json')
        self.profile_manager = ProfileManager(profiles_file=profiles_file)
        
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
        self.channel_banned: Dict[str, Dict[str, dict]] = {}  # channel -> {user_id -> {banned_by, reason, timestamp, expires_at}}
        self.channel_topics: Dict[str, str] = {}  # channel -> topic string
        self.channel_modes: Dict[str, Set[str]] = {}  # channel -> set of active modes (e.g., {'m', 's', 'i'})
        self.channel_keys: Dict[str, str] = {}  # channel -> base64 encryption key
        self.nicknames: Dict[str, str] = {}  # nickname -> user_id
        self.pending_op_auth: Dict[str, tuple] = {}  # user_id -> (channel, should_be_op)
        self.pending_op_grant: Dict[str, dict] = {}  # user_id -> {channel, granted_by, granted_by_id, is_mod}
        
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
        
        # Performance & Scalability Features
        max_connections = self.config.get('max_connections', 1000)
        self.connection_manager = ConnectionManager(
            max_connections=max_connections,
            idle_timeout=self.connection_timeout,
            cleanup_interval=60
        )
        
        self.performance_monitor = PerformanceMonitor(history_size=60)
        self.routing_optimizer = RoutingOptimizer(cache_size=100)
        
        # Message queue for offline users
        message_queue_dir = os.path.join(data_dir, 'message_queue')
        max_queued_per_user = self.config.get('max_queued_messages_per_user', 1000)
        self.message_queue = MessageQueue(
            storage_dir=message_queue_dir,
            max_messages_per_user=max_queued_per_user,
            default_ttl=604800  # 7 days
        )
        
        # Message batcher for efficient transmission
        self.message_batcher = MessageBatcher(batch_size=10, batch_timeout=0.1)
        
        # Background tasks
        self.background_tasks = []
        
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
                # Support both old format (dict of hashes) and new format (dict with role)
                operator_passwords_data = data.get('operator_passwords', {})
                self.operator_passwords = {}
                for channel, users in operator_passwords_data.items():
                    self.operator_passwords[channel] = {}
                    for user_id, password_info in users.items():
                        if isinstance(password_info, str):
                            # Old format: just the password hash, default to operator
                            self.operator_passwords[channel][user_id] = {
                                'password': password_info,
                                'role': 'operator'
                            }
                        else:
                            # New format: dict with password and role
                            self.operator_passwords[channel][user_id] = password_info
                
                # Load channel owners
                self.channel_owners = data.get('channel_owners', {})
                
                # Load banned users
                # Support both old format (list) and new format (dict with metadata)
                banned_data = data.get('channel_banned', {})
                for channel, banned_info in banned_data.items():
                    if isinstance(banned_info, list):
                        # Old format: convert to new format with no expiration
                        self.channel_banned[channel] = {}
                        for user_id in banned_info:
                            self.channel_banned[channel][user_id] = {
                                'banned_by': 'SYSTEM',
                                'reason': 'Legacy ban',
                                'timestamp': time.time(),
                                'expires_at': None
                            }
                    else:
                        # New format: already has metadata
                        self.channel_banned[channel] = banned_info
                
                # Load channel topics
                self.channel_topics = data.get('channel_topics', {})
                
                # Load channel modes
                modes_data = data.get('channel_modes', {})
                for channel, mode_list in modes_data.items():
                    self.channel_modes[channel] = set(mode_list)
                
                # Load channel encryption keys
                self.channel_keys = data.get('channel_keys', {})
                
                # Initialize empty operator and mod sets for existing channels
                for channel in self.channel_passwords.keys():
                    self.channel_operators[channel] = set()
                    self.channel_mods[channel] = set()
                    self.channels[channel] = set()
                    if channel not in self.channel_modes:
                        self.channel_modes[channel] = set()
                
                logger.info(f"Loaded {len(self.channel_passwords)} persistent channels from {self.channels_file}")
            except Exception as e:
                logger.error(f"Error loading channels: {e}")
        else:
            logger.info("No existing channel data found, starting fresh")
    
    def save_channels(self):
        """Save persistent channel data to file"""
        try:
            # Convert channel_modes sets to lists for JSON serialization
            modes_data = {}
            for channel, mode_set in self.channel_modes.items():
                modes_data[channel] = list(mode_set)
            
            # channel_banned is already JSON-serializable (dict of dicts)
            data = {
                'channel_passwords': self.channel_passwords,
                'channel_creator_passwords': self.channel_creator_passwords,
                'operator_passwords': self.operator_passwords,
                'channel_owners': self.channel_owners,
                'channel_banned': self.channel_banned,
                'channel_topics': self.channel_topics,
                'channel_modes': modes_data,
                'channel_keys': self.channel_keys
            }
            with open(self.channels_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved channel data to {self.channels_file}")
        except Exception as e:
            logger.error(f"Error saving channels: {e}")
            logger.error(f"Error saving channels: {e}")
    
    async def start(self):
        """Start the server"""
        # Start background tasks
        self.background_tasks.append(
            asyncio.create_task(self.check_expired_bans())
        )
        self.background_tasks.append(
            asyncio.create_task(self.periodic_performance_logging())
        )
        self.background_tasks.append(
            asyncio.create_task(self.periodic_queue_save())
        )
        
        # Start connection manager cleanup task
        self.connection_manager.start_cleanup_task(
            lambda user_id: self.disconnect_by_user_id(user_id)
        )
        
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        
        addr = server.sockets[0].getsockname()
        logger.info(f'Server started on {addr[0]}:{addr[1]}')
        logger.info('Server is running in ROUTING-ONLY mode - cannot decrypt messages')
        logger.info('Press Ctrl+C to stop')
        
        async with server:
            try:
                await server.serve_forever()
            except asyncio.CancelledError:
                pass
            finally:
                await self.shutdown()
    
    async def check_expired_bans(self):
        """Background task to check and remove expired bans"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = time.time()
                expired_bans = []
                
                # Find all expired bans
                for channel, banned_users in self.channel_banned.items():
                    for user_id, ban_info in list(banned_users.items()):
                        expires_at = ban_info.get('expires_at')
                        if expires_at and current_time >= expires_at:
                            expired_bans.append((channel, user_id))
                
                # Remove expired bans
                if expired_bans:
                    for channel, user_id in expired_bans:
                        del self.channel_banned[channel][user_id]
                        logger.info(f"Auto-removed expired ban for user {user_id} in {channel}")
                    
                    # Save changes if any bans were removed
                    self.save_channels()
                    
            except Exception as e:
                logger.error(f"Error in check_expired_bans: {e}")
    
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
        
        # Check connection manager limits
        if not self.connection_manager.can_accept_connection():
            logger.warning(f"Connection from {ip_address} rejected: server at capacity")
            try:
                error_msg = Protocol.error("Server at maximum capacity, please try again later")
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
                
                # Update connection activity
                if client.user_id:
                    self.connection_manager.update_activity(client.user_id)
                    self.performance_monitor.record_message(
                        client.user_id,
                        len(data),
                        direction='received'
                    )
                
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
        
        elif msg_type == MessageType.INVITE_USER.value:
            await self.handle_invite_user(client, message)
        
        elif msg_type == MessageType.INVITE_RESPONSE.value:
            await self.handle_invite_response(client, message)
        
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
        
        elif msg_type == MessageType.SET_MODE.value:
            await self.handle_set_mode(client, message)
        
        elif msg_type == MessageType.SET_STATUS.value:
            await self.handle_set_status(client, message)
        
        elif msg_type == MessageType.REGISTER_NICKNAME.value:
            await self.handle_register_nickname(client, message)
        
        elif msg_type == MessageType.UPDATE_PROFILE.value:
            await self.handle_update_profile(client, message)
        
        elif msg_type == MessageType.GET_PROFILE.value:
            await self.handle_get_profile(client, message)
        
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
        
        # Generate unique user_id based on nickname (stable across reconnections)
        user_id = f"user_{nickname}"
        logger.debug(f"Registering {nickname} with user_id: {user_id}")
        
        # Check connection manager capacity
        if not self.connection_manager.register_connection(user_id):
            await client.send(Protocol.error("Server at maximum capacity"))
            return
        
        # Register client
        client.user_id = user_id
        client.nickname = nickname
        client.public_key = public_key
        
        self.clients[user_id] = client
        self.nicknames[nickname] = user_id
        
        # Register with performance monitor
        self.performance_monitor.register_connection(user_id)
        
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
        
        # Deliver any queued offline messages
        await self.deliver_queued_messages(client)
        
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
        
        # Check if recipient is online
        if to_id not in self.clients:
            # Queue message for offline user
            logger.info(f"Queuing message from {client.nickname} to offline user {to_id}")
            
            self.message_queue.enqueue(
                recipient_id=to_id,
                sender_id=client.user_id,
                sender_nickname=client.nickname,
                message_type=MessageType.PRIVATE_MESSAGE.value,
                encrypted_content=json.dumps(message),
                ttl=604800,  # 7 days
                metadata={'queued_at': time.time()}
            )
            
            # Acknowledge to sender
            await client.send(Protocol.ack(
                success=True,
                message=f"User {to_id} is offline. Message queued for delivery."
            ))
            return
        
        target = self.clients[to_id]
        
        # Add sender nickname to message before forwarding
        message['from_nickname'] = client.nickname
        message_str = json.dumps(message)
        await target.send(message_str)
        
        # Track performance
        self.performance_monitor.record_message(
            to_id,
            len(message_str),
            direction='sent'
        )
        
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
        
        # Check moderated mode (+m) - only ops and mods can speak
        if 'm' in self.channel_modes.get(channel, set()):
            is_op = client.user_id in self.channel_operators.get(channel, set())
            is_mod = client.user_id in self.channel_mods.get(channel, set())
            is_owner = self.channel_owners.get(channel) == client.user_id
            
            if not (is_op or is_mod or is_owner):
                await client.send(Protocol.error("Channel is moderated - only operators and mods can speak"))
                return
        
        # Get channel members (use cache if available)
        members = self.routing_optimizer.get_cached_channel_members(channel)
        if members is None:
            members = self.channels[channel]
            self.routing_optimizer.cache_channel_members(channel, members)
        
        # Add sender nickname to message before forwarding
        message['from_nickname'] = client.nickname
        message_str = json.dumps(message)
        
        # Route to all channel members except sender
        sent_count = 0
        for user_id in members:
            if user_id != client.user_id and user_id in self.clients:
                await self.clients[user_id].send(message_str)
                
                # Track performance
                self.performance_monitor.record_message(
                    user_id,
                    len(message_str),
                    direction='sent'
                )
                sent_count += 1
        
        # Record channel activity
        self.performance_monitor.record_channel_message(channel, len(members))
        
        logger.debug(f"Routed channel message from {client.nickname} to {channel} ({sent_count} recipients)")
    
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
            ban_info = self.channel_banned[channel][client.user_id]
            expires_at = ban_info.get('expires_at')
            
            # Check if ban has expired
            if expires_at and time.time() >= expires_at:
                # Ban expired, remove it
                del self.channel_banned[channel][client.user_id]
                self.save_channels()
                logger.info(f"Ban expired for {client.nickname} in {channel}")
            else:
                # Ban is still active
                reason = ban_info.get('reason', 'No reason given')
                await client.send(Protocol.error(f"You are banned from {channel}: {reason}"))
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
            self.channel_banned[channel] = {}
            
            # Create encryption key for the channel
            crypto = CryptoLayer()
            channel_key = crypto.create_channel_key(channel)
            self.channel_keys[channel] = channel_key
            
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
                self.channel_banned[channel] = {}
            
            # Ensure encryption key exists
            if channel not in self.channel_keys:
                crypto = CryptoLayer()
                channel_key = crypto.create_channel_key(channel)
                self.channel_keys[channel] = channel_key
                self.save_channels()
            
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
            
            # Check join password if set (skip if user authenticated as operator)
            if channel in self.channel_passwords and not should_be_operator:
                if not password or self.hash_password(password) != self.channel_passwords[channel]:
                    await client.send(Protocol.error("Incorrect channel password"))
                    return
        
        # Scenario 3: Channel is currently active
        elif channel_active:
            # Ensure encryption key exists (in case of legacy channels)
            if channel not in self.channel_keys:
                crypto = CryptoLayer()
                channel_key = crypto.create_channel_key(channel)
                self.channel_keys[channel] = channel_key
                self.save_channels()
            
            # Check if user should regain operator/owner status
            if creator_password and channel in self.channel_creator_passwords:
                if self.hash_password(creator_password) == self.channel_creator_passwords[channel]:
                    should_be_operator = True
                    # Check if they're the original owner
                    if channel in self.channel_owners and self.channel_owners[channel] == client.user_id:
                        is_owner = True
                    logger.info(f"{client.nickname} regaining operator status in {channel}")
            
            # Check join password if set (skip if user authenticated as operator)
            if channel in self.channel_passwords and not should_be_operator:
                if not password or self.hash_password(password) != self.channel_passwords[channel]:
                    await client.send(Protocol.error("Incorrect channel password"))
                    return
        
        # Check if user has an existing operator password for this channel BEFORE adding to channel
        # (i.e., they had operator/mod/owner permission previously)
        # If so, they must verify their password even without providing creator_password
        has_operator_password = (channel in self.operator_passwords and 
                                 client.user_id in self.operator_passwords[channel])
        
        # Get the stored role for this user (if any)
        stored_role = None
        is_stored_mod = False
        if has_operator_password:
            password_info = self.operator_passwords[channel][client.user_id]
            stored_role = password_info.get('role', 'operator')
            is_stored_mod = (stored_role == 'mod')
        
        # Track if user authenticated via creator_password (skip operator password prompt)
        authenticated_via_creator_password = (
            creator_password and 
            channel in self.channel_creator_passwords and
            self.hash_password(creator_password) == self.channel_creator_passwords[channel]
        )
        
        # Debug logging for reconnection troubleshooting
        logger.debug(f"Join attempt by {client.nickname} ({client.user_id}) to {channel}:")
        logger.debug(f"  - has_operator_password: {has_operator_password}")
        logger.debug(f"  - stored_role: {stored_role}")
        logger.debug(f"  - should_be_operator: {should_be_operator}")
        logger.debug(f"  - authenticated_via_creator_password: {authenticated_via_creator_password}")
        logger.debug(f"  - operator_passwords for channel: {list(self.operator_passwords.get(channel, {}).keys())}")
        
        # If user has operator password set, they need to authenticate BEFORE joining
        # UNLESS they already authenticated with creator_password
        if has_operator_password and not should_be_operator and not authenticated_via_creator_password:
            # User previously had operator/mod status, must verify password
            # Check if they're the owner to maintain that status
            if channel in self.channel_owners and self.channel_owners[channel] == client.user_id:
                is_owner = True
            
            # Don't add to channel yet - do it in complete_join after authentication
            # Store role info (True for operator, False for mod based on stored_role)
            should_be_operator_role = not is_stored_mod
            self.pending_op_auth[client.user_id] = (channel, should_be_operator_role, is_owner, is_stored_mod)
            logger.debug(f"Stored pending_op_auth for {client.nickname}: {self.pending_op_auth[client.user_id]}")
            request_msg = Protocol.build_message(
                MessageType.OP_PASSWORD_REQUEST,
                channel=channel,
                action="verify"
            )
            await client.send(request_msg)
            logger.info(f"Requesting operator password from {client.nickname} for {channel} (existing {stored_role} permissions)")
            return  # Don't add to channel yet - wait for authentication
        
        # Add client to channel NOW (after password check)
        self.channels[channel].add(client.user_id)
        client.channels.add(channel)
        
        # Invalidate routing cache since membership changed
        self.routing_optimizer.invalidate_channel_cache(channel)
        
        # If user should be operator, request password verification
        # UNLESS they already authenticated with creator_password
        if should_be_operator and not authenticated_via_creator_password:
            # Check if they already have an operator password set
            if channel in self.operator_passwords and client.user_id in self.operator_passwords[channel]:
                # Ask for password
                self.pending_op_auth[client.user_id] = (channel, True, is_owner, False)
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
                self.pending_op_auth[client.user_id] = (channel, True, is_owner, False)
                request_msg = Protocol.build_message(
                    MessageType.OP_PASSWORD_REQUEST,
                    channel=channel,
                    action="set"
                )
                await client.send(request_msg)
                logger.info(f"Requesting new operator password from {client.nickname} for {channel}")
                return  # Don't complete join yet
        
        # Complete the join process
        await self.complete_join(client, channel, should_be_operator, is_owner)
    
    async def complete_join(self, client: Client, channel: str, is_operator: bool, is_owner: bool, is_mod: bool = False):
        """Complete the join process after authentication"""
        # Add client to channel if not already added (happens during operator auth flow)
        if client.user_id not in self.channels[channel]:
            self.channels[channel].add(client.user_id)
            client.channels.add(channel)
            # Invalidate routing cache since membership changed
            self.routing_optimizer.invalidate_channel_cache(channel)
        
        # Grant operator or mod status if needed
        if is_mod:
            self.channel_mods[channel].add(client.user_id)
            logger.info(f"{client.nickname} joined {channel} as mod")
        elif is_operator:
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
            is_owner=is_owner,
            topic=self.channel_topics.get(channel, ""),
            channel_key=self.channel_keys.get(channel, "")
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
            is_mod=is_mod,
            is_owner=is_owner
        )
        
        for user_id in self.channels[channel]:
            if user_id != client.user_id and user_id in self.clients:
                await self.clients[user_id].send(join_notification)
    
    async def handle_op_password_response(self, client: Client, message: dict):
        """Handle operator password response"""
        password = message.get('password')
        channel = message.get('channel')
        
        logger.debug(f"Received OP_PASSWORD_RESPONSE from {client.nickname} for {channel}")
        logger.debug(f"  - pending_op_auth: {client.user_id in self.pending_op_auth}")
        logger.debug(f"  - pending_op_grant: {client.user_id in self.pending_op_grant}")
        
        if not password:
            await client.send(Protocol.error("Password required"))
            # Only disconnect if this was for auth, not for grant
            if client.user_id in self.pending_op_auth:
                await self.disconnect_client(client)
            return
        
        # Check if this is for a role grant (someone granting op/mod to this user)
        if client.user_id in self.pending_op_grant:
            grant_info = self.pending_op_grant[client.user_id]
            expected_channel = grant_info['channel']
            granted_by = grant_info['granted_by']
            granted_by_id = grant_info['granted_by_id']
            is_mod = grant_info['is_mod']
            
            if channel != expected_channel:
                await client.send(Protocol.error("Channel mismatch"))
                del self.pending_op_grant[client.user_id]
                return
            
            # Validate password
            if len(password) < 4:
                await client.send(Protocol.error("Password must be at least 4 characters"))
                del self.pending_op_grant[client.user_id]
                return
            
            # Store the password with role
            if channel not in self.operator_passwords:
                self.operator_passwords[channel] = {}
            self.operator_passwords[channel][client.user_id] = {
                'password': self.hash_password(password),
                'role': 'mod' if is_mod else 'operator'
            }
            self.save_channels()
            
            # Grant the role
            if is_mod:
                # Grant mod status
                if channel not in self.channel_mods:
                    self.channel_mods[channel] = set()
                self.channel_mods[channel].add(client.user_id)
                
                logger.info(f"{granted_by} granted mod status to {client.nickname} in {channel}")
                
                # Notify all channel members (including granter and target)
                notification = Protocol.build_message(
                    MessageType.MOD_USER,
                    channel=channel,
                    user_id=client.user_id,
                    nickname=client.nickname,
                    granted_by=granted_by
                )
                for user_id in self.channels[channel]:
                    if user_id in self.clients:
                        await self.clients[user_id].send(notification)
            else:
                # Grant operator status
                if channel not in self.channel_operators:
                    self.channel_operators[channel] = set()
                self.channel_operators[channel].add(client.user_id)
                
                logger.info(f"{granted_by} granted operator status to {client.nickname} in {channel}")
                
                # Notify all channel members (including granter and target)
                notification = Protocol.build_message(
                    MessageType.OP_USER,
                    channel=channel,
                    user_id=client.user_id,
                    nickname=client.nickname,
                    granted_by=granted_by
                )
                for user_id in self.channels[channel]:
                    if user_id in self.clients:
                        await self.clients[user_id].send(notification)
            
            del self.pending_op_grant[client.user_id]
            return
        
        # Otherwise, this is for authentication (rejoining with op/mod privileges)
        if client.user_id not in self.pending_op_auth:
            await client.send(Protocol.error("Unexpected password response"))
            return
        
        expected_channel, should_be_op, is_owner, is_mod = self.pending_op_auth[client.user_id]
        
        if channel != expected_channel:
            await client.send(Protocol.error("Channel mismatch"))
            await self.disconnect_client(client)
            return
        
        # Check if this is a new password (set) or verification
        if channel not in self.operator_passwords:
            self.operator_passwords[channel] = {}
        
        if client.user_id in self.operator_passwords[channel]:
            # Verify existing password
            stored_password_info = self.operator_passwords[channel][client.user_id]
            stored_password = stored_password_info.get('password') if isinstance(stored_password_info, dict) else stored_password_info
            if self.hash_password(password) != stored_password:
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
            self.operator_passwords[channel][client.user_id] = {
                'password': self.hash_password(password),
                'role': 'mod' if is_mod else 'operator'
            }
            self.save_channels()
            logger.info(f"Set {'mod' if is_mod else 'operator'} password for {client.nickname} in {channel}")
        
        # Authentication successful
        del self.pending_op_auth[client.user_id]
        await self.complete_join(client, channel, should_be_op, is_owner, is_mod)
    
    async def handle_leave_channel(self, client: Client, message: dict):
        """Handle channel leave request"""
        channel = message.get('channel')
        
        if channel not in self.channels or client.user_id not in self.channels[channel]:
            await client.send(Protocol.error(f"You are not in channel {channel}"))
            return
        
        # Remove from channel
        self.channels[channel].remove(client.user_id)
        client.channels.discard(channel)
        
        # Invalidate routing cache since membership changed
        self.routing_optimizer.invalidate_channel_cache(channel)
        
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
        
        # Check if target is online
        if target_id not in self.clients:
            await client.send(Protocol.error(f"{target_nickname} is not currently connected"))
            return
        
        # Store pending operator grant (will be completed when target sets password)
        self.pending_op_grant[target_id] = {
            'channel': channel,
            'granted_by': client.nickname,
            'granted_by_id': client.user_id,
            'is_mod': False
        }
        
        # Request the target user to set their operator password
        request_msg = Protocol.build_message(
            MessageType.OP_PASSWORD_REQUEST,
            channel=channel,
            action="set",
            granted_by=client.nickname
        )
        await self.clients[target_id].send(request_msg)
        
        # Notify the granter
        await client.send(Protocol.ack(True, f"Password request sent to {target_nickname}"))
        
        logger.info(f"{client.nickname} initiated operator grant to {target_nickname} in {channel}")
    
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
            
            # Notify ALL channel members (including remover and target)
            notification = Protocol.build_message(
                MessageType.UNOP_USER,
                channel=channel,
                user_id=target_id,
                nickname=target_nickname,
                removed_by=client.nickname
            )
            for user_id in self.channels[channel]:
                if user_id in self.clients:
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
        
        # Check if target is online
        if target_id not in self.clients:
            await client.send(Protocol.error(f"{target_nickname} is not currently connected"))
            return
        
        # Store pending mod grant (will be completed when target sets password)
        self.pending_op_grant[target_id] = {
            'channel': channel,
            'granted_by': client.nickname,
            'granted_by_id': client.user_id,
            'is_mod': True
        }
        
        # Request the target user to set their mod password
        request_msg = Protocol.build_message(
            MessageType.OP_PASSWORD_REQUEST,
            channel=channel,
            action="set",
            granted_by=client.nickname,
            is_mod=True
        )
        await self.clients[target_id].send(request_msg)
        
        # Notify the granter
        await client.send(Protocol.ack(True, f"Password request sent to {target_nickname}"))
        
        logger.info(f"{client.nickname} initiated mod grant to {target_nickname} in {channel}")
    
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
            # Also remove their operator password (mods use the same password system)
            if channel in self.operator_passwords and target_id in self.operator_passwords[channel]:
                del self.operator_passwords[channel][target_id]
                self.save_channels()
            
            logger.info(f"{client.nickname} removed mod status from {target_nickname} in {channel}")
            await client.send(Protocol.ack(True, f"{target_nickname} is no longer a mod"))
            
            # Notify target
            if target_id in self.clients:
                await self.clients[target_id].send(Protocol.ack(True, f"You are no longer a mod in {channel}"))
            
            # Notify ALL channel members (including remover and target)
            notification = Protocol.build_message(
                MessageType.UNMOD_USER,
                channel=channel,
                user_id=target_id,
                nickname=target_nickname,
                removed_by=client.nickname
            )
            for user_id in self.channels[channel]:
                if user_id in self.clients:
                    await self.clients[user_id].send(notification)
        else:
            await client.send(Protocol.error(f"{target_nickname} is not a mod"))
    
    async def handle_ban_user(self, client: Client, message: dict):
        """Handle banning a user from a channel"""
        channel = message.get('channel')
        target_nickname = message.get('target_nickname')
        reason = message.get('reason', 'No reason given')
        duration = message.get('duration')  # Optional: duration in seconds for timed ban
        
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
        
        # Calculate expiration time if duration provided
        expires_at = None
        if duration and duration > 0:
            expires_at = time.time() + duration
        
        # Add to ban list with metadata
        if channel not in self.channel_banned:
            self.channel_banned[channel] = {}
        self.channel_banned[channel][target_id] = {
            'banned_by': client.user_id,
            'banned_by_nickname': client.nickname,
            'reason': reason,
            'timestamp': time.time(),
            'expires_at': expires_at
        }
        self.save_channels()
        
        # Build response message
        ban_msg = f"{target_nickname} has been banned from {channel}"
        if duration:
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            if hours > 0:
                ban_msg += f" for {hours}h {minutes}m"
            else:
                ban_msg += f" for {minutes}m"
        
        logger.info(f"{client.nickname} banned {target_nickname} from {channel}: {reason} (duration: {duration})")
        await client.send(Protocol.ack(True, ban_msg))
        
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
        del self.channel_banned[channel][target_id]
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
    
    async def handle_invite_user(self, client: Client, message: dict):
        """Handle inviting a user to a channel"""
        channel = message.get('channel')
        target_nickname = message.get('target_nickname')
        
        if not channel or not target_nickname:
            await client.send(Protocol.error("Missing channel or target_nickname"))
            return
        
        # Check if inviter is in the channel
        if channel not in self.channels or client.user_id not in self.channels[channel]:
            await client.send(Protocol.error("You must be in the channel to invite users"))
            return
        
        # Only operators and owners can send invites
        is_op = client.user_id in self.channel_operators.get(channel, set())
        is_owner = self.channel_owners.get(channel) == client.user_id
        
        if not (is_op or is_owner):
            await client.send(Protocol.error("Only operators can invite users"))
            return
        
        # Find target user
        if target_nickname not in self.nicknames:
            await client.send(Protocol.error(f"User {target_nickname} not found"))
            return
        
        target_id = self.nicknames[target_nickname]
        
        # Check if target is already in channel
        if target_id in self.channels.get(channel, set()):
            await client.send(Protocol.error(f"{target_nickname} is already in {channel}"))
            return
        
        # Send invite to target user
        if target_id in self.clients:
            invite_msg = Protocol.build_message(
                MessageType.INVITE_USER,
                channel=channel,
                inviter_nickname=client.nickname,
                inviter_id=client.user_id
            )
            await self.clients[target_id].send(invite_msg)
            
            logger.info(f"{client.nickname} invited {target_nickname} to {channel}")
            await client.send(Protocol.ack(True, f"Invited {target_nickname} to {channel}"))
        else:
            await client.send(Protocol.error(f"{target_nickname} is not online"))
    
    async def handle_invite_response(self, client: Client, message: dict):
        """Handle user's response to a channel invite"""
        channel = message.get('channel')
        inviter_nickname = message.get('inviter_nickname')
        accepted = message.get('accepted', False)
        
        if not channel or not inviter_nickname:
            await client.send(Protocol.error("Missing channel or inviter_nickname"))
            return
        
        if accepted:
            # User accepted, join them to the channel
            # Reuse the join channel logic
            join_msg = {
                'type': MessageType.JOIN_CHANNEL.value,
                'channel': channel
            }
            await self.handle_join_channel(client, join_msg)
            
            # Notify the inviter if online
            if inviter_nickname in self.nicknames:
                inviter_id = self.nicknames[inviter_nickname]
                if inviter_id in self.clients:
                    notification = Protocol.build_message(
                        MessageType.CHANNEL_MESSAGE,
                        channel=channel,
                        sender="SERVER",
                        text=f"{client.nickname} accepted your invite"
                    )
                    await self.clients[inviter_id].send(notification)
        else:
            # User declined
            logger.info(f"{client.nickname} declined invite to {channel} from {inviter_nickname}")
            
            # Notify the inviter if online
            if inviter_nickname in self.nicknames:
                inviter_id = self.nicknames[inviter_nickname]
                if inviter_id in self.clients and inviter_id in self.channels.get(channel, set()):
                    notification = Protocol.build_message(
                        MessageType.CHANNEL_MESSAGE,
                        channel=channel,
                        sender="SERVER",
                        text=f"{client.nickname} declined your invite"
                    )
                    await self.clients[inviter_id].send(notification)
    
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
    
    async def handle_set_status(self, client: Client, message: dict):
        """Handle user status change"""
        status = message.get('status', 'online')
        custom_message = message.get('custom_message', '')
        
        # Validate status
        valid_statuses = ['online', 'away', 'busy', 'dnd']
        if status not in valid_statuses:
            await client.send(Protocol.error(f"Invalid status. Must be one of: {', '.join(valid_statuses)}"))
            return
        
        # Update client status
        client.status = status
        client.status_message = custom_message[:100]  # Limit to 100 chars
        
        logger.info(f"{client.nickname} set status to {status}: {custom_message}")
        
        # Send acknowledgment
        await client.send(Protocol.ack(True, f"Status set to {status}"))
        
        # Broadcast status update to all users who share a channel with this user
        notified_users = set()
        for channel in client.channels:
            if channel in self.channels:
                for user_id in self.channels[channel]:
                    if user_id != client.user_id and user_id not in notified_users:
                        notified_users.add(user_id)
                        if user_id in self.clients:
                            status_update = Protocol.build_message(
                                MessageType.STATUS_UPDATE,
                                user_id=client.user_id,
                                nickname=client.nickname,
                                status=status,
                                custom_message=custom_message
                            )
                            await self.clients[user_id].send(status_update)
    
    async def handle_register_nickname(self, client: Client, message: dict):
        """Handle nickname registration"""
        if not client.nickname:
            await client.send(Protocol.error("You must be connected to register a nickname"))
            return
        
        nickname = message.get('nickname')
        password = message.get('password')
        
        if not nickname or not password:
            await client.send(Protocol.error("Missing nickname or password"))
            return
        
        # Verify that the nickname matches the client's current nickname
        if nickname != client.nickname:
            await client.send(Protocol.error("You can only register your current nickname"))
            return
        
        # Attempt to register the nickname
        success, msg = self.profile_manager.register_nickname(nickname, password)
        
        if success:
            logger.info(f"Nickname registered: {nickname}")
            await client.send(Protocol.ack(True, msg))
        else:
            await client.send(Protocol.error(msg))
    
    async def handle_update_profile(self, client: Client, message: dict):
        """Handle profile update"""
        if not client.nickname:
            await client.send(Protocol.error("You must be connected to update your profile"))
            return
        
        bio = message.get('bio')
        status_message = message.get('status_message')
        avatar = message.get('avatar')
        
        # Update profile
        success, msg = self.profile_manager.update_profile(
            client.nickname,
            bio=bio,
            status_message=status_message,
            avatar=avatar
        )
        
        if success:
            logger.info(f"Profile updated for {client.nickname}")
            await client.send(Protocol.ack(True, msg))
        else:
            await client.send(Protocol.error(msg))
    
    async def handle_get_profile(self, client: Client, message: dict):
        """Handle profile request"""
        target_nickname = message.get('target_nickname')
        
        if not target_nickname:
            await client.send(Protocol.error("Missing target nickname"))
            return
        
        # Get profile from profile manager
        profile = self.profile_manager.get_profile(target_nickname)
        
        if profile:
            # Send profile response
            response = Protocol.profile_response(
                nickname=target_nickname,
                bio=profile.get('bio'),
                status_message=profile.get('status_message'),
                avatar=profile.get('avatar'),
                registered=profile.get('registered', False),
                registration_date=profile.get('registration_date')
            )
            await client.send(response)
        else:
            await client.send(Protocol.error(f"Profile not found for {target_nickname}"))
    
    async def handle_set_mode(self, client: Client, message: dict):
        """Handle setting channel modes"""
        channel = message.get('channel')
        mode = message.get('mode')
        enable = message.get('enable', True)
        
        if not channel or not mode:
            await client.send(Protocol.error("Missing channel or mode"))
            return
        
        # Only operators and owners can set modes
        is_op = client.user_id in self.channel_operators.get(channel, set())
        is_owner = self.channel_owners.get(channel) == client.user_id
        
        if not (is_op or is_owner):
            await client.send(Protocol.error("Only operators can set channel modes"))
            return
        
        # Validate mode
        valid_modes = {'m', 's', 'i', 'n', 'p'}  # moderated, secret, invite-only, no external messages, private
        if mode not in valid_modes:
            await client.send(Protocol.error(f"Unknown mode: {mode}. Valid modes: {', '.join(valid_modes)}"))
            return
        
        # Initialize modes for channel if needed
        if channel not in self.channel_modes:
            self.channel_modes[channel] = set()
        
        # Apply mode
        mode_changed = False
        if enable:
            if mode not in self.channel_modes[channel]:
                self.channel_modes[channel].add(mode)
                mode_changed = True
        else:
            if mode in self.channel_modes[channel]:
                self.channel_modes[channel].discard(mode)
                mode_changed = True
        
        if not mode_changed:
            mode_status = "enabled" if enable else "disabled"
            await client.send(Protocol.ack(True, f"Mode {mode} is already {mode_status}"))
            return
        
        # Save changes
        self.save_channels()
        
        # Mode descriptions
        mode_names = {
            'm': 'moderated (only ops/mods can speak)',
            's': 'secret (hidden from channel list)',
            'i': 'invite-only',
            'n': 'no external messages',
            'p': 'private (hide user list from non-members)'
        }
        
        mode_action = "enabled" if enable else "disabled"
        mode_desc = mode_names.get(mode, mode)
        
        logger.info(f"{client.nickname} {mode_action} mode +{mode} in {channel}")
        await client.send(Protocol.ack(True, f"Mode +{mode} ({mode_desc}) {mode_action}"))
        
        # Notify all channel members
        notification = Protocol.mode_change(channel, mode, enable, client.nickname)
        for user_id in self.channels.get(channel, set()):
            if user_id in self.clients and user_id != client.user_id:
                await self.clients[user_id].send(notification)
    
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
                "public_key": c.public_key,
                "status": c.status,
                "status_message": c.status_message
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
                "public_key": new_client.public_key,
                "status": new_client.status,
                "status_message": new_client.status_message
            }]
        )
        
        for user_id, client in self.clients.items():
            if user_id != new_client.user_id:
                await client.send(user_info)
    
    async def disconnect_client(self, client: Client):
        """Disconnect a client and clean up"""
        if client.user_id:
            logger.info(f"Client {client.nickname} ({client.user_id}) disconnected")
            
            # Debug: Show operator_passwords state before cleanup
            for channel in list(client.channels):
                if channel in self.operator_passwords and client.user_id in self.operator_passwords[channel]:
                    password_info = self.operator_passwords[channel][client.user_id]
                    role = password_info.get('role', 'operator') if isinstance(password_info, dict) else 'operator'
                    logger.debug(f"  - {client.nickname} has {role} password for {channel} (will persist)")
            
            # Clean up pending operator authentication/grant states
            if client.user_id in self.pending_op_auth:
                del self.pending_op_auth[client.user_id]
                logger.debug(f"Cleaned up pending_op_auth for {client.nickname}")
            if client.user_id in self.pending_op_grant:
                del self.pending_op_grant[client.user_id]
                logger.debug(f"Cleaned up pending_op_grant for {client.nickname}")
            
            # Unregister from managers
            self.connection_manager.unregister_connection(client.user_id)
            self.performance_monitor.unregister_connection(client.user_id)
            
            # Remove from all channels
            for channel in list(client.channels):
                if channel in self.channels:
                    self.channels[channel].discard(client.user_id)
                    
                    # Invalidate routing cache
                    self.routing_optimizer.invalidate_channel_cache(channel)
                    
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


    async def deliver_queued_messages(self, client: Client):
        """Deliver any queued messages to a client upon reconnection"""
        if not client.user_id:
            return
        
        queued_messages = self.message_queue.dequeue_all(client.user_id)
        
        if not queued_messages:
            return
        
        logger.info(f"Delivering {len(queued_messages)} queued messages to {client.nickname}")
        
        for queued_msg in queued_messages:
            try:
                # Send the queued encrypted message
                await client.send(queued_msg.encrypted_content)
                
                # Track performance
                self.performance_monitor.record_message(
                    client.user_id,
                    len(queued_msg.encrypted_content),
                    direction='sent'
                )
            except Exception as e:
                logger.error(f"Error delivering queued message to {client.nickname}: {e}")
        
        # Notify client about delivered messages
        notification = Protocol.build_message(
            MessageType.ACK,
            success=True,
            message=f"Delivered {len(queued_messages)} queued message(s)"
        )
        await client.send(notification)
    
    async def disconnect_by_user_id(self, user_id: str):
        """Disconnect a client by user_id (for idle timeout)"""
        if user_id in self.clients:
            client = self.clients[user_id]
            logger.info(f"Disconnecting idle client: {client.nickname}")
            await self.disconnect_client(client)
    
    async def periodic_performance_logging(self):
        """Background task to log performance statistics"""
        while True:
            try:
                await asyncio.sleep(300)  # Log every 5 minutes
                self.performance_monitor.log_summary()
                
                # Log queue stats
                queue_stats = self.message_queue.get_stats()
                if queue_stats['total_messages_waiting'] > 0:
                    logger.info(
                        f"Message Queue: {queue_stats['active_queues']} queues, "
                        f"{queue_stats['total_messages_waiting']} messages waiting"
                    )
                
                # Log connection manager stats
                conn_stats = self.connection_manager.get_stats()
                logger.info(
                    f"Connections: {conn_stats['active_connections']}/{conn_stats['max_connections']} "
                    f"({conn_stats['utilization']:.1f}% utilization)"
                )
                
                # Log routing cache stats
                cache_stats = self.routing_optimizer.get_cache_stats()
                if cache_stats['cache_hits'] + cache_stats['cache_misses'] > 0:
                    logger.info(
                        f"Routing Cache: {cache_stats['hit_rate']:.1f}% hit rate, "
                        f"{cache_stats['cached_channels']} channels cached"
                    )
                
                # Take performance snapshot
                self.performance_monitor.take_snapshot()
                
            except asyncio.CancelledError:
                logger.info("Performance logging task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in performance logging: {e}")
    
    async def periodic_queue_save(self):
        """Background task to periodically save message queue to disk"""
        while True:
            try:
                await asyncio.sleep(60)  # Save every minute
                self.message_queue.save_to_disk()
                
                # Cleanup expired messages
                self.message_queue.cleanup_expired()
                
            except asyncio.CancelledError:
                logger.info("Queue save task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in queue save task: {e}")
    
    async def shutdown(self):
        """Shutdown server gracefully"""
        logger.info("Starting server shutdown...")
        
        # Cancel all background tasks
        for task in self.background_tasks:
            task.cancel()
        
        # Stop connection manager cleanup
        self.connection_manager.stop_cleanup_task()
        
        # Wait for background tasks to finish
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        # Save message queue
        self.message_queue.shutdown()
        
        # Save channels
        self.save_channels()
        
        # Log final statistics
        logger.info("=== Final Server Statistics ===")
        self.performance_monitor.log_summary()
        
        queue_stats = self.message_queue.get_stats()
        logger.info(f"Message Queue: {queue_stats['total_queued']} queued, "
                   f"{queue_stats['total_delivered']} delivered, "
                   f"{queue_stats['total_expired']} expired")
        
        conn_stats = self.connection_manager.get_stats()
        logger.info(f"Connections: {conn_stats['total_accepted']} accepted, "
                   f"{conn_stats['total_rejected']} rejected, "
                   f"{conn_stats['total_idle_timeouts']} idle timeouts")
        
        logger.info("Server shutdown complete")


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
