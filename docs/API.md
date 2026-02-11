# JustIRC API Reference

## Protocol Message Formats

### Message Structure

All messages in JustIRC follow a JSON-based protocol:

```json
{
  "version": "1.0",
  "type": "message_type",
  "timestamp": 1234567890.123,
  ... additional fields ...
}
```

**Common Fields:**
- `version` (string): Protocol version
- `type` (string): Message type identifier
- `timestamp` (float): Unix timestamp when message was created

### Message Types

#### Connection Management

**REGISTER** - Register a new client
```json
{
  "type": "register",
  "nickname": "alice",
  "public_key": "base64_encoded_public_key",
  "password": "optional_password",
  "session_token": "optional_session_token"
}
```

**DISCONNECT** - Disconnect from server
```json
{
  "type": "disconnect"
}
```

#### Authentication

**AUTH_REQUEST** - Authenticate with server
```json
{
  "type": "auth_request",
  "username": "alice",
  "password": "password123"
}
```

**AUTH_RESPONSE** - Authentication result
```json
{
  "type": "auth_response",
  "success": true,
  "session_token": "token_string",
  "message": "Authenticated as alice"
}
```

**CREATE_ACCOUNT** - Create new account
```json
{
  "type": "create_account",
  "username": "alice",
  "password": "password123",
  "email": "alice@example.com"
}
```

**CHANGE_PASSWORD** - Change account password
```json
{
  "type": "change_password",
  "old_password": "oldpass",
  "new_password": "newpass"
}
```

#### Key Exchange

**KEY_EXCHANGE** - Exchange public keys
```json
{
  "type": "key_exchange",
  "from_id": "user_0_alice",
  "to_id": "user_1_bob",
  "public_key": "base64_encoded_key"
}
```

**PUBLIC_KEY_REQUEST** - Request a user's public key
```json
{
  "type": "public_key_request",
  "target_nickname": "bob"
}
```

**PUBLIC_KEY_RESPONSE** - Response with user's public key
```json
{
  "type": "public_key_response",
  "user_id": "user_1_bob",
  "nickname": "bob",
  "public_key": "base64_encoded_key"
}
```

**REKEY_REQUEST** - Request key rotation
```json
{
  "type": "rekey_request",
  "from_id": "user_0_alice",
  "to_id": "user_1_bob",
  "new_public_key": "base64_encoded_new_key"
}
```

**REKEY_RESPONSE** - Respond to key rotation
```json
{
  "type": "rekey_response",
  "from_id": "user_1_bob",
  "to_id": "user_0_alice",
  "new_public_key": "base64_encoded_new_key"
}
```

#### Messaging

**PRIVATE_MESSAGE** - End-to-end encrypted private message
```json
{
  "type": "private_message",
  "from_id": "user_0_alice",
  "to_id": "user_1_bob",
  "encrypted_data": "base64_encrypted_message",
  "nonce": "base64_nonce"
}
```

**CHANNEL_MESSAGE** - End-to-end encrypted channel message
```json
{
  "type": "channel_message",
  "from_id": "user_0_alice",
  "to_id": "#lobby",
  "encrypted_data": "base64_encrypted_message",
  "nonce": "base64_nonce"
}
```

#### Channel Management

**JOIN_CHANNEL** - Join a channel
```json
{
  "type": "join_channel",
  "user_id": "user_0_alice",
  "channel": "#lobby",
  "password": "optional_channel_password",
  "creator_password": "optional_creator_password"
}
```

**LEAVE_CHANNEL** - Leave a channel
```json
{
  "type": "leave_channel",
  "user_id": "user_0_alice",
  "channel": "#lobby"
}
```

**OP_USER** - Grant operator status
```json
{
  "type": "op_user",
  "channel": "#lobby",
  "target_nickname": "bob",
  "password": ""
}
```

**KICK_USER** - Kick user from channel
```json
{
  "type": "kick_user",
  "channel": "#lobby",
  "target_nickname": "bob",
  "reason": "Optional kick reason"
}
```

**BAN_USER** - Ban user from channel
```json
{
  "type": "ban_user",
  "channel": "#lobby",
  "target_nickname": "bob"
}
```

**SET_TOPIC** - Set channel topic
```json
{
  "type": "set_topic",
  "channel": "#lobby",
  "topic": "Welcome to the lobby!"
}
```

#### File Transfer

**IMAGE_START** - Begin image transfer
```json
{
  "type": "image_start",
  "from_id": "user_0_alice",
  "to_id": "user_1_bob",
  "filename": "photo.jpg",
  "total_chunks": 15,
  "file_size": 48000
}
```

**IMAGE_CHUNK** - Transfer image chunk
```json
{
  "type": "image_chunk",
  "from_id": "user_0_alice",
  "to_id": "user_1_bob",
  "chunk_number": 5,
  "encrypted_data": "base64_encrypted_chunk",
  "nonce": "base64_nonce"
}
```

**IMAGE_END** - Complete image transfer
```json
{
  "type": "image_end",
  "from_id": "user_0_alice",
  "to_id": "user_1_bob"
}
```

#### Server Responses

**ACK** - Acknowledge success
```json
{
  "type": "ack",
  "success": true,
  "message": "Action completed",
  "user_id": "optional_user_id",
  "channel": "optional_channel"
}
```

**ERROR** - Error response
```json
{
  "type": "error",
  "error": "Error message description"
}
```

**USER_LIST** - List of online users
```json
{
  "type": "user_list",
  "users": [
    {
      "user_id": "user_0_alice",
      "nickname": "alice",
      "public_key": "base64_key"
    }
  ]
}
```

---

## Core Modules

### crypto_layer.py

**CryptoLayer** - Handles all cryptographic operations

```python
class CryptoLayer:
    def __init__(self, key_rotation_interval=3600.0, max_messages_per_key=10000):
        """
        Initialize crypto layer with key rotation settings
        
        Args:
            key_rotation_interval: Time in seconds before rotating keys (default 1 hour)
            max_messages_per_key: Max messages before rotating (default 10,000)
        """
```

**Key Methods:**

```python
def get_public_key_b64() -> str:
    """Get public key as base64 string"""

def load_peer_public_key(peer_id: str, public_key_b64: str):
    """Load a peer's public key from base64"""

def encrypt(peer_id: str, plaintext: str) -> Tuple[str, str]:
    """
    Encrypt data for a specific peer
    Returns: (encrypted_data_b64, nonce_b64)
    """

def decrypt(peer_id: str, encrypted_data_b64: str, nonce_b64: str) -> str:
    """
    Decrypt data from a specific peer
    Returns: decrypted plaintext
    """

def should_rotate_key(peer_id: str) -> bool:
    """Check if key rotation is needed for a peer"""

def rotate_key_for_peer(peer_id: str):
    """Rotate encryption key for a peer"""

def get_key_stats(peer_id: str) -> dict:
    """Get key rotation statistics for a peer"""
```

**ChannelCrypto** - Handles channel (group) encryption

```python
class ChannelCrypto:
    def create_channel_key(channel: str) -> str:
        """Create a new channel key and return it as base64"""
    
    def load_channel_key(channel: str, key_b64: str):
        """Load a channel key from base64"""
    
    def encrypt_for_channel(channel: str, plaintext: str) -> Tuple[str, str]:
        """Encrypt message for channel"""
    
    def decrypt_from_channel(channel: str, encrypted_b64: str, nonce_b64: str) -> str:
        """Decrypt message from channel"""
```

### protocol.py

**Protocol** - Message builder and parser

```python
class Protocol:
    VERSION = "1.0"
    
    @staticmethod
    def build_message(msg_type: MessageType, **kwargs) -> str:
        """Build a protocol message"""
    
    @staticmethod
    def parse_message(data: str) -> Dict[str, Any]:
        """Parse a protocol message"""
    
    # Message builders for each message type
    @staticmethod
    def register(nickname: str, public_key: str, ...) -> str:
        """Create a registration message"""
    
    @staticmethod
    def encrypted_message(from_id: str, to_id: str, 
                         encrypted_data: str, nonce: str,
                         is_channel: bool = False) -> str:
        """Create an encrypted message"""
```

### auth_manager.py

**AuthenticationManager** - User account management

```python
class AuthenticationManager:
    def __init__(self, accounts_file: str, 
                 enable_accounts: bool,
                 require_authentication: bool):
        """Initialize authentication manager"""
    
    def create_account(username: str, password: str, 
                      email: Optional[str] = None) -> bool:
        """Create a new user account"""
    
    def authenticate(username: str, password: str) -> Optional[str]:
        """Authenticate a user and create a session. Returns session token"""
    
    def verify_session(session_token: str) -> Optional[str]:
        """Verify a session token. Returns username if valid"""
    
    def change_password(username: str, old_password: str, 
                       new_password: str) -> bool:
        """Change user password"""
    
    def is_account_locked(username: str, max_attempts: int = 5) -> bool:
        """Check if account is locked due to failed attempts"""
```

### rate_limiter.py

**RateLimiter** - Token bucket rate limiting

```python
class RateLimiter:
    def __init__(self, max_requests: int, time_window: float):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
    
    def is_allowed(client_id: str) -> bool:
        """Check if request is allowed for client"""
    
    def get_remaining(client_id: str) -> int:
        """Get remaining requests for client"""
    
    def get_retry_after(client_id: str) -> float:
        """Get seconds until client can retry"""
```

**ConnectionRateLimiter** - Connection rate limiting with bans

```python
class ConnectionRateLimiter:
    def __init__(self, max_connections: int, time_window: float, 
                 ban_threshold: int = 10):
        """Initialize connection rate limiter"""
    
    def is_allowed(ip: str) -> Tuple[bool, str]:
        """
        Check if connection is allowed
        Returns: (allowed, reason_if_denied)
        """
```

### input_validator.py

**InputValidator** - Input validation and sanitization

```python
class InputValidator:
    @staticmethod
    def validate_nickname(nickname: str) -> Tuple[bool, Optional[str]]:
        """Validate nickname. Returns (is_valid, error_message)"""
    
    @staticmethod
    def validate_channel_name(channel: str) -> Tuple[bool, Optional[str]]:
        """Validate channel name"""
    
    @staticmethod
    def validate_email(email: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Validate email address"""
    
    @staticmethod
    def validate_password(password: str, min_length: int = 8) -> Tuple[bool, Optional[str]]:
        """Validate password strength"""
    
    @staticmethod
    def sanitize_string(text: str, max_length: Optional[int] = None) -> str:
        """Sanitize a string by removing control characters"""
```

### ip_filter.py

**IPFilter** - IP blacklist/whitelist management

```python
class IPFilter:
    def __init__(self, blacklist_file: str, whitelist_file: str, 
                 enable_whitelist: bool = False):
        """Initialize IP filter"""
    
    def is_allowed(ip: str) -> bool:
        """Check if an IP is allowed to connect"""
    
    def add_to_blacklist(ip_or_network: str, save: bool = True) -> bool:
        """Add IP or network to blacklist (supports CIDR notation)"""
    
    def add_to_whitelist(ip_or_network: str, save: bool = True) -> bool:
        """Add IP or network to whitelist"""
    
    def temp_ban(ip: str, duration_minutes: int = 15):
        """Temporarily ban an IP address"""
```

### image_transfer.py

**ImageTransfer** - Encrypted image transfer

```python
class ImageTransfer:
    def __init__(self, crypto: CryptoLayer, chunk_size: int = 32768):
        """
        Initialize image transfer
        
        Args:
            crypto: CryptoLayer instance for encryption
            chunk_size: Size of each chunk in bytes (default 32KB)
        """
    
    def chunk_image(image_data: bytes) -> List[bytes]:
        """Split image into chunks"""
    
    def reassemble_image(chunks: List[bytes]) -> bytes:
        """Reassemble image from chunks"""
```

---

## Server Configuration

**server_config.json** - Server configuration file

```json
{
  "server_name": "JustIRC Server",
  "description": "Welcome message",
  "host": "0.0.0.0",
  "port": 6667,
  "max_channels": 1000,
  "max_users": 10000,
  "enable_authentication": false,
  "require_authentication": false,
  "enable_ip_whitelist": false,
  "connection_timeout": 300,
  "read_timeout": 60,
  "max_message_size": 65536
}
```

**Configuration Options:**

- `server_name`: Server display name
- `description`: Welcome message shown to clients
- `host`: Bind address (0.0.0.0 for all interfaces)
- `port`: Port number (default 6667)
- `enable_authentication`: Enable user accounts (default false)
- `require_authentication`: Require authentication for all users (default false)
- `enable_ip_whitelist`: Enable whitelist-only mode (default false)
- `connection_timeout`: Max idle time in seconds (default 300)
- `read_timeout`: Max time to read a message in seconds (default 60)
- `max_message_size`: Max message size in bytes (default 64KB)

---

## Client Examples

### Basic Client Connection

```python
import asyncio
from client import IRCClient

async def main():
    client = IRCClient("localhost", 6667, "alice")
    await client.connect()
    await client.run()

asyncio.run(main())
```

### Sending Encrypted Messages

```python
# Private message
await client.send_private_message("bob", "Hello Bob!")

# Channel message
await client.join_channel("#lobby")
await client.send_channel_message("#lobby", "Hello everyone!")
```

### Key Rotation

```python
# Manual key rotation
await client.initiate_key_rotation("bob")

# Check if rotation is needed
if client.crypto.should_rotate_key("user_1_bob"):
    reason = client.crypto.get_rotation_reason("user_1_bob")
    print(f"Key rotation recommended: {reason}")
```

### Authentication

```python
# Create account
from protocol import Protocol
msg = Protocol.create_account("alice", "password123", "alice@example.com")
await client.send(msg)

# Authenticate
msg = Protocol.auth_request("alice", "password123")
await client.send(msg)

# Register with session token
msg = Protocol.register("alice", public_key, session_token=token)
await client.send(msg)
```

---

## Error Handling

### Common Error Codes

- `"Missing nickname or public_key"`: Registration incomplete
- `"Nickname {nickname} already taken"`: Nickname in use
- `"Authentication required"`: Server requires authentication
- `"Invalid username or password"`: Authentication failed
- `"Account temporarily locked"`: Too many failed login attempts
- `"Access denied"`: IP blocked by filter
- `"Rate limit exceeded"`: Too many requests
- `"Message too large"`: Message exceeds max size
- `"Read timeout"`: Client took too long to send message
- `"No encryption key for {user}"`: Key exchange not complete
- `"Failed to decrypt message"`: Decryption failed
- `"You are banned from {channel}"`: User banned from channel

### Error Response Format

```json
{
  "type": "error",
  "error": "Error message description"
}
```

---

## Best Practices

### Security

1. **Always validate inputs**: Use InputValidator for all user inputs
2. **Implement rate limiting**: Prevent abuse with RateLimiter
3. **Use strong passwords**: Minimum 8 characters for authentication
4. **Enable key rotation**: Automatic or manual rotation for PFS
5. **Filter IPs**: Use IPFilter to block malicious sources
6. **Timeout connections**: Prevent resource exhaustion

### Performance

1. **Chunk large data**: Use ImageTransfer for files
2. **Batch operations**: Combine multiple operations when possible
3. **Clean up resources**: Remove old clients and sessions
4. **Monitor limits**: Track rate limits and resource usage

### Development

1. **Test thoroughly**: Use provided test suite
2. **Log appropriately**: Log important events, not content
3. **Handle errors gracefully**: Always send error responses
4. **Document changes**: Update protocol docs for new features
5. **Follow standards**: Use type hints and docstrings

---

## Version Compatibility

**Current Protocol Version: 1.0**

All messages include a `version` field. Future versions will maintain backward compatibility where possible. Breaking changes will increment the version number.

**Supported Python Versions:** 3.9 - 3.13

**Dependencies:**
- cryptography >= 41.0.0
- Pillow >= 10.0.0 (for GUI and image transfer)

---

## Support

For issues, questions, or contributions, see:
- [SECURITY.md](SECURITY.md) - Security documentation
- [FEATURES.md](FEATURES.md) - User feature guide  
- [README.md](README.md) - Quick start guide
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
