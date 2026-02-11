# JustIRC Developer Guide

Welcome to the JustIRC development guide! This document provides everything you need to understand, extend, and contribute to the JustIRC project.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Getting Started](#getting-started)
3. [Code Organization](#code-organization)
4. [Development Workflow](#development-workflow)
5. [Testing](#testing)
6. [Adding New Features](#adding-new-features)
7. [Debugging](#debugging)
8. [Performance Optimization](#performance-optimization)
9. [Common Patterns](#common-patterns)

---

## Architecture Overview

### High-Level Design

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Client    │◄───────►│    Server    │◄───────►│   Client    │
│             │         │  (Routing)   │         │             │
│  Crypto     │         │              │         │  Crypto     │
│  Protocol   │         │  No decrypt  │         │  Protocol   │
└─────────────┘         └──────────────┘         └─────────────┘
       │                                                 │
       │                                                 │
       └─────────────── E2E Encrypted ─────────────────┘
```

**Key Principles:**
- **Zero-knowledge server**: Server routes encrypted messages, cannot read content
- **Client-side encryption**: All crypto operations happen on clients
- **Asynchronous I/O**: Built on Python asyncio for scalability
- **Stateful connections**: Clients maintain persistent TCP connections

### Component Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Application Layer                    │
├─────────────────┬───────────────────┬───────────────────┤
│   client.py     │   client_gui.py   │   server.py       │
│   (CLI client)  │   (GUI client)    │   (IRC server)    │
└────────┬────────┴──────────┬────────┴──────────┬────────┘
         │                   │                   │
         └───────────────────┴───────────────────┘
                             │
         ┌───────────────────┴───────────────────┐
         │          Protocol & Crypto Layer       │
         ├───────────────┬───────────────────────┤
         │  protocol.py  │   crypto_layer.py     │
         │  (Messages)   │   (Encryption)        │
         └───────┬───────┴──────────┬────────────┘
                 │                  │
         ┌───────┴──────────────────┴────────┐
         │      Supporting Modules           │
         ├───────────────┬───────────────────┤
         │ auth_manager  │  rate_limiter     │
         │ input_validator│  ip_filter       │
         │ image_transfer │  config_manager   │
         └───────────────┴───────────────────┘
```

### Data Flow

**Sending an Encrypted Message:**
```
1. User types message → client.py
2. Encrypt with recipient's key → crypto_layer.py
3. Build protocol message → protocol.py
4. Send to server → asyncio transport
5. Server routes to recipient → server.py
6. Recipient decrypts → crypto_layer.py
7. Display to user → client.py / client_gui.py
```

---

## Getting Started

### Prerequisites

- Python 3.9 - 3.13
- Basic understanding of asyncio
- Familiarity with cryptography concepts

### Development Setup

1. **Clone the repository:**
```bash
git clone <repository_url>
cd justIRC
```

2. **Create virtual environment:**
```bash
python3 -m venv build-env
source build-env/bin/activate  # Linux/Mac
# or
build-env\Scripts\activate  # Windows
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Install development tools:**
```bash
pip install black flake8 mypy pylint pytest pytest-asyncio pytest-cov pre-commit
```

5. **Set up pre-commit hooks:**
```bash
pre-commit install
```

6. **Run tests:**
```bash
python run_tests.py
```

### Project Structure

```
justIRC/
├── server.py                 # Main IRC server
├── client.py                 # CLI client
├── client_gui.py             # GUI client (Tkinter)
├── protocol.py               # Protocol message definitions
├── crypto_layer.py           # Cryptographic operations
├── auth_manager.py           # User authentication
├── rate_limiter.py           # Rate limiting
├── input_validator.py        # Input validation
├── ip_filter.py              # IP filtering
├── image_transfer.py         # Image transfer
├── config_manager.py         # Configuration management
├── tests/                    # Test suite
│   ├── test_crypto_layer.py
│   ├── test_protocol.py
│   ├── test_integration.py
│   └── ...
├── docs/                     # Documentation
│   ├── API.md
│   ├── PROTOCOL.md
│   ├── DEVELOPER.md (this file)
│   └── ...
├── pyproject.toml            # Tool configuration
├── requirements.txt          # Dependencies
└── README.md                 # Quick start guide
```

---

## Code Organization

### Core Modules

#### server.py (1728 lines)

**Purpose:** Main IRC routing server

**Key Classes:**
- `IRCServer`: Main server class, handles client connections
- `Channel`: Represents a chat channel with members and permissions

**Key Methods:**
- `start()`: Start the server
- `handle_client(reader, writer)`: Handle individual client connection
- `handle_register()`: Register a new client
- `handle_private_message()`: Route private messages
- `handle_channel_message()`: Route channel messages
- `handle_auth_request()`: Authenticate users

**Async Design:**
- Uses `asyncio.start_server()` for TCP server
- Each client has a dedicated `handle_client()` coroutine
- Non-blocking message processing

#### client.py (920+ lines)

**Purpose:** Command-line IRC client

**Key Classes:**
- `IRCClient`: Main client class

**Key Methods:**
- `connect()`: Establish server connection
- `send_private_message()`: Send encrypted PM
- `send_channel_message()`: Send encrypted channel message
- `handle_incoming()`: Process incoming messages
- `initiate_key_rotation()`: Perform key rotation

**Features:**
- Async read loop for incoming messages
- Command parser for `/` commands
- Automatic key rotation detection

#### crypto_layer.py (335 lines)

**Purpose:** All cryptographic operations

**Key Classes:**
- `CryptoLayer`: Peer-to-peer encryption
- `ChannelCrypto`: Channel (group) encryption

**Cryptographic Primitives:**
- X25519: Key exchange
- ChaCha20-Poly1305: AEAD encryption
- HKDF-SHA256: Key derivation
- os.urandom(): Nonce generation

**Key Methods:**
- `encrypt(peer_id, plaintext)`: Encrypt for peer
- `decrypt(peer_id, ciphertext, nonce)`: Decrypt from peer
- `should_rotate_key(peer_id)`: Check rotation needed
- `rotate_key_for_peer(peer_id)`: Perform rotation

#### protocol.py (289+ lines)

**Purpose:** Protocol message construction and parsing

**Key Classes:**
- `MessageType`: Enum of all message types
- `Protocol`: Static methods for building/parsing messages

**Message Builders:**
- `Protocol.register()`: Build REGISTER message
- `Protocol.encrypted_message()`: Build encrypted message
- `Protocol.auth_request()`: Build AUTH_REQUEST
- `Protocol.rekey_request()`: Build REKEY_REQUEST

**Parsing:**
- `Protocol.parse_message()`: Parse JSON message
- Validates `version` and `type` fields
- Returns dict with message data

### Supporting Modules

#### auth_manager.py (335 lines)

**Purpose:** User account management and authentication

**Key Features:**
- PBKDF2-HMAC-SHA256 password hashing
- Session token management
- Account lockout after failed attempts
- Persistent storage in accounts.json

**Key Methods:**
- `create_account(username, password, email)`
- `authenticate(username, password)` → session_token
- `verify_session(session_token)` → username
- `change_password(username, old_pass, new_pass)`

#### rate_limiter.py

**Purpose:** Token bucket rate limiting

**Key Classes:**
- `RateLimiter`: Per-client rate limiting
- `ConnectionRateLimiter`: Connection-level limiting with bans

**Algorithm:** Token bucket
- Tokens refill over time
- Each request consumes tokens
- Requests denied when bucket empty

#### input_validator.py (243 lines)

**Purpose:** Input validation and sanitization

**Key Methods:**
- `validate_nickname()`: Check nickname format
- `validate_channel_name()`: Check channel format
- `validate_email()`: RFC-compliant email validation
- `validate_password()`: Password strength check
- `sanitize_string()`: Remove control characters

**Patterns:**
- Regex patterns for validation
- Whitelist approach (only valid characters allowed)
- Length limits enforced

#### ip_filter.py (299 lines)

**Purpose:** IP blacklist/whitelist with CIDR support

**Key Features:**
- Blacklist mode (block specific IPs)
- Whitelist mode (allow only specific IPs)
- CIDR network notation support
- Temporary bans with expiration
- Persistent storage

**Key Methods:**
- `is_allowed(ip)`: Check if IP can connect
- `add_to_blacklist(ip_or_network)`
- `temp_ban(ip, duration_minutes)`

#### image_transfer.py

**Purpose:** Encrypted image chunking and transfer

**Key Features:**
- Chunks images into 32KB pieces
- Encrypts each chunk individually
- Reassembles on receiver
- Progress tracking

---

## Development Workflow

### Code Style

JustIRC follows **PEP 8** style guidelines with some modifications:

**Line Length:**
- Maximum 100 characters (configured in `.flake8`)
- Break long lines logically

**Naming Conventions:**
- Classes: `PascalCase` (e.g., `IRCServer`)
- Functions/methods: `snake_case` (e.g., `handle_message`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_MESSAGE_SIZE`)
- Private: `_leading_underscore` (e.g., `_internal_method`)

**Type Hints:**
```python
def encrypt(self, peer_id: str, plaintext: str) -> Tuple[str, str]:
    """Encrypt data for a specific peer"""
    ...
```

**Docstrings:**
```python
def create_account(self, username: str, password: str, 
                  email: Optional[str] = None) -> bool:
    """
    Create a new user account.
    
    Args:
        username: Unique username (3-50 characters)
        password: Password (8-256 characters)
        email: Optional email address
        
    Returns:
        True if account created successfully, False otherwise
        
    Raises:
        ValueError: If username or password invalid
    """
```

### Running Quality Checks

**Format code:**
```bash
black .
```

**Run linters:**
```bash
flake8 .
pylint *.py
```

**Type checking:**
```bash
mypy *.py
```

**Run all checks:**
```bash
./quality_check.sh
```

### Git Workflow

1. **Create feature branch:**
```bash
git checkout -b feature/your-feature-name
```

2. **Make changes and commit:**
```bash
git add .
git commit -m "Add feature: description"
```

3. **Run tests:**
```bash
python run_tests.py
```

4. **Push and create PR:**
```bash
git push origin feature/your-feature-name
```

---

## Testing

### Test Suite Structure

```
tests/
├── test_crypto_layer.py      # Encryption tests (29 tests)
├── test_protocol.py          # Protocol tests (19 tests)
├── test_image_transfer.py    # Image transfer tests (8 tests)
├── test_integration.py       # Integration tests (10 tests)
├── test_config_manager.py    # Config tests (5 tests)
├── test_rate_limiter.py      # Rate limiting tests (12 tests)
├── test_key_rotation.py      # Key rotation tests (8 tests)
├── test_auth_manager.py      # Auth tests (13 tests)
├── test_input_validator.py   # Validation tests (20 tests)
├── test_ip_filter.py         # IP filter tests (17 tests)
└── run_tests.py              # Master test runner
```

**Total: 144 tests**

### Running Tests

**Run all tests:**
```bash
python run_tests.py
```

**Run specific test file:**
```bash
python -m unittest tests.test_crypto_layer
```

**Run specific test:**
```bash
python -m unittest tests.test_crypto_layer.TestCryptoLayer.test_key_generation
```

**With coverage:**
```bash
pytest --cov=. --cov-report=html
```

### Writing Tests

**Test Structure:**
```python
import unittest
from crypto_layer import CryptoLayer

class TestCryptoLayer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.crypto = CryptoLayer()
    
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    def test_encryption_decryption(self):
        """Test that encryption and decryption work"""
        # Arrange
        peer_id = "test_peer"
        plaintext = "Hello, World!"
        
        # Act
        encrypted, nonce = self.crypto.encrypt(peer_id, plaintext)
        decrypted = self.crypto.decrypt(peer_id, encrypted, nonce)
        
        # Assert
        self.assertEqual(plaintext, decrypted)

if __name__ == '__main__':
    unittest.main()
```

**Async Tests:**
```python
import asyncio
import unittest

class TestAsyncFeature(unittest.TestCase):
    def test_async_method(self):
        """Test async method"""
        async def run_test():
            result = await some_async_function()
            self.assertEqual(result, expected)
        
        asyncio.run(run_test())
```

---

## Adding New Features

### Adding a New Message Type

1. **Define message type in protocol.py:**
```python
class MessageType(str, Enum):
    # ... existing types ...
    NEW_MESSAGE_TYPE = "new_message_type"
```

2. **Add message builder:**
```python
@staticmethod
def new_message_type(param1: str, param2: int) -> str:
    """Build NEW_MESSAGE_TYPE message"""
    return Protocol.build_message(
        MessageType.NEW_MESSAGE_TYPE,
        param1=param1,
        param2=param2
    )
```

3. **Add server handler in server.py:**
```python
async def handle_new_message_type(self, client_id: str, data: Dict[str, Any]):
    """Handle NEW_MESSAGE_TYPE message"""
    param1 = data.get("param1")
    param2 = data.get("param2")
    
    # Validate inputs
    if not param1 or param2 is None:
        await self.send_error(client_id, "Missing parameters")
        return
    
    # Process message
    result = self.process_new_feature(param1, param2)
    
    # Send response
    await self.send_ack(client_id, f"Processed: {result}")
```

4. **Add to message router:**
```python
# In handle_client() message dispatcher
if msg_type == MessageType.NEW_MESSAGE_TYPE:
    await self.handle_new_message_type(client_id, parsed)
```

5. **Add client support in client.py:**
```python
async def handle_new_message_type(self, data: Dict[str, Any]):
    """Handle incoming NEW_MESSAGE_TYPE"""
    param1 = data.get("param1")
    param2 = data.get("param2")
    print(f"Received new message: {param1}, {param2}")
```

6. **Write tests:**
```python
def test_new_message_type(self):
    """Test NEW_MESSAGE_TYPE creation and parsing"""
    msg = Protocol.new_message_type("test", 42)
    parsed = Protocol.parse_message(msg)
    
    self.assertEqual(parsed["type"], MessageType.NEW_MESSAGE_TYPE)
    self.assertEqual(parsed["param1"], "test")
    self.assertEqual(parsed["param2"], 42)
```

### Adding a New Command

1. **Add command handler in client.py:**
```python
async def handle_command(self, command: str):
    """Process user commands"""
    parts = command.split()
    cmd = parts[0].lower()
    
    # ... existing commands ...
    
    elif cmd == "/newcmd":
        await self.handle_newcmd_command(parts[1:])
    
    # ... rest of commands ...

async def handle_newcmd_command(self, args: List[str]):
    """Handle /newcmd command"""
    if len(args) < 1:
        print("Usage: /newcmd <argument>")
        return
    
    argument = args[0]
    
    # Build and send message
    msg = Protocol.new_message_type(argument, 0)
    await self.send(msg)
    print(f"Sent new command with argument: {argument}")
```

2. **Update help text:**
```python
elif cmd == "/help":
    print("""
    Available commands:
    ...
    /newcmd <arg>   - Description of new command
    ...
    """)
```

### Adding Server Configuration Options

1. **Update server_config.sample.json:**
```json
{
  ...
  "new_feature_enabled": false,
  "new_feature_timeout": 60
}
```

2. **Load in server.py:**
```python
def __init__(self):
    # ... existing config ...
    self.new_feature_enabled = self.config.get("new_feature_enabled", False)
    self.new_feature_timeout = self.config.get("new_feature_timeout", 60)
```

3. **Use configuration:**
```python
async def handle_something(self):
    if not self.new_feature_enabled:
        return
    
    await asyncio.wait_for(
        some_operation(),
        timeout=self.new_feature_timeout
    )
```

---

## Debugging

### Logging

**Add logging to server.py:**
```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Use in code
logger.debug(f"Processing message from {client_id}")
logger.info(f"User {nickname} registered")
logger.warning(f"Rate limit exceeded for {client_id}")
logger.error(f"Failed to process message: {error}")
```

### Debugging Client

**Run with verbose output:**
```python
# Add debug flag to client
self.debug = True

if self.debug:
    print(f"[DEBUG] Sending: {message}")
    print(f"[DEBUG] Received: {data}")
```

### Common Issues

**Issue: Messages not decrypting**
- Check that key exchange completed
- Verify peer_id matches exactly
- Ensure nonce is included

**Issue: Connection timeouts**
- Increase `connection_timeout` in config
- Check network connectivity
- Verify server is running

**Issue: Rate limit errors**
- Reduce message sending rate
- Check rate limiter configuration
- Clear rate limiter state for testing

**Issue: Authentication failures**
- Verify password is correct
- Check if account is locked
- Ensure session token is valid

### Using Python Debugger

**Set breakpoints:**
```python
import pdb

def some_function():
    pdb.set_trace()  # Execution will stop here
    # ... rest of code ...
```

**Debugger commands:**
- `n`: Next line
- `s`: Step into function
- `c`: Continue execution
- `p variable`: Print variable
- `l`: List code around current line
- `q`: Quit debugger

---

## Performance Optimization

### Asyncio Best Practices

**Use async I/O for all blocking operations:**
```python
# Good
data = await reader.read(4096)
await writer.drain()

# Bad (blocks event loop)
time.sleep(1)  # Use asyncio.sleep(1) instead
```

**Batch operations when possible:**
```python
# Good: Parallel key exchanges
tasks = [
    self.exchange_key_with(user1),
    self.exchange_key_with(user2),
    self.exchange_key_with(user3)
]
results = await asyncio.gather(*tasks)

# Bad: Sequential
await self.exchange_key_with(user1)
await self.exchange_key_with(user2)
await self.exchange_key_with(user3)
```

### Memory Management

**Clean up old data:**
```python
# Remove disconnected clients
if client_id not in self.clients:
    if client_id in self.crypto.peer_keys:
        del self.crypto.peer_keys[client_id]
```

**Limit data structures:**
```python
# Cap rate limiter entries
if len(self.rate_limiter.clients) > 10000:
    # Remove oldest entries
    oldest = sorted(self.rate_limiter.clients.items(), 
                   key=lambda x: x[1].last_access)[:100]
    for client_id, _ in oldest:
        del self.rate_limiter.clients[client_id]
```

### Profiling

**Profile with cProfile:**
```bash
python -m cProfile -o profile.stats server.py
python -m pstats profile.stats
```

**Analyze results:**
```python
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative')
p.print_stats(20)  # Top 20 functions
```

---

## Common Patterns

### Async Context Managers

```python
class AsyncResource:
    async def __aenter__(self):
        """Set up resource"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resource"""
        await self.disconnect()

# Use
async with AsyncResource() as resource:
    await resource.do_something()
```

### Error Handling

```python
async def handle_message(self, client_id: str, data: Dict[str, Any]):
    """Handle incoming message with proper error handling"""
    try:
        # Validate inputs
        if "required_field" not in data:
            raise ValueError("Missing required field")
        
        # Process message
        result = await self.process(data)
        
        # Send success response
        await self.send_ack(client_id, f"Success: {result}")
        
    except ValueError as e:
        # Client error - notify client
        await self.send_error(client_id, str(e))
        logger.warning(f"Validation error from {client_id}: {e}")
        
    except Exception as e:
        # Server error - log and send generic error
        logger.error(f"Error handling message from {client_id}: {e}", 
                    exc_info=True)
        await self.send_error(client_id, "Internal server error")
```

### Timeout Pattern

```python
async def operation_with_timeout(self):
    """Perform operation with timeout"""
    try:
        result = await asyncio.wait_for(
            self.long_running_operation(),
            timeout=30.0
        )
        return result
    except asyncio.TimeoutError:
        logger.warning("Operation timed out after 30 seconds")
        return None
```

### State Management

```python
class StatefulConnection:
    def __init__(self):
        self.state = "disconnected"
        self.transitions = {
            "disconnected": ["connecting"],
            "connecting": ["connected", "disconnected"],
            "connected": ["authenticated", "disconnected"],
            "authenticated": ["disconnected"]
        }
    
    def transition(self, new_state: str):
        """Transition to new state with validation"""
        if new_state not in self.transitions.get(self.state, []):
            raise ValueError(
                f"Invalid transition: {self.state} -> {new_state}"
            )
        
        logger.info(f"State transition: {self.state} -> {new_state}")
        self.state = new_state
```

---

## Additional Resources

### Documentation
- [API.md](API.md) - API reference
- [PROTOCOL.md](PROTOCOL.md) - Protocol specification
- [SECURITY.md](SECURITY.md) - Security documentation
- [FEATURES.md](FEATURES.md) - Feature guide

### External References
- [Python asyncio docs](https://docs.python.org/3/library/asyncio.html)
- [cryptography library docs](https://cryptography.io/)
- [PEP 8 Style Guide](https://www.python.org/dev/peps/pep-0008/)

### Support
- GitHub Issues: Report bugs and request features
- Pull Requests: Contribute code improvements
- Discussions: Ask questions and share ideas

---

## Tips for Contributors

1. **Start small**: Begin with documentation or test improvements
2. **Ask questions**: Don't hesitate to ask for clarification
3. **Follow style**: Match existing code style and patterns
4. **Test thoroughly**: Write tests for all new features
5. **Document changes**: Update relevant documentation
6. **Be patient**: Code review may take time
7. **Stay respectful**: Follow the code of conduct

Happy coding! 🚀
