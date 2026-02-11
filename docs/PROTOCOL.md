# JustIRC Protocol Specification

**Version:** 1.0  
**Last Updated:** 2024

## Table of Contents

1. [Overview](#overview)
2. [Transport Layer](#transport-layer)
3. [Message Format](#message-format)
4. [Connection Lifecycle](#connection-lifecycle)
5. [Encryption Protocol](#encryption-protocol)
6. [Authentication Flow](#authentication-flow)
7. [State Machine](#state-machine)
8. [Protocol Extensions](#protocol-extensions)

---

## Overview

JustIRC implements an end-to-end encrypted IRC protocol using modern cryptographic primitives. The protocol is designed for:

- **End-to-end encryption**: All messages encrypted between clients
- **Perfect Forward Secrecy**: Ephemeral X25519 key exchange with rotation
- **Server routing**: Server routes encrypted messages without access to content
- **Channel support**: Multi-party encrypted channels with shared keys
- **File transfer**: Chunked encrypted file transfer
- **Authentication**: Optional password-based account system

### Design Principles

1. **Zero-knowledge server**: Server cannot read message content
2. **Client-side encryption**: All encryption happens on clients
3. **Stateful protocol**: Clients maintain connection state
4. **Asynchronous design**: Built on Python asyncio
5. **JSON-based messages**: Human-readable protocol format

---

## Transport Layer

### Connection Details

- **Protocol**: TCP
- **Default Port**: 6667
- **Encoding**: UTF-8
- **Line Delimiter**: `\n` (newline)

### Message Framing

Each message is a single line of JSON terminated with a newline character:

```
{json_message}\n
```

Maximum message size: **65,536 bytes** (configurable via `max_message_size`)

### Connection Establishment

```
Client                          Server
  |                                |
  |--- TCP Connection ----------->|
  |                                |
  |<-- Server Ready (Optional) ---|
  |                                |
  |--- REGISTER ----------------->|
  |                                |
  |<-- ACK (user_id) -------------|
  |                                |
  [Connection established]
```

### Connection Timeouts

- **Connection Timeout**: 300 seconds (idle connections)
- **Read Timeout**: 60 seconds (waiting for message)
- **Reconnection**: Clients should reconnect with same nickname

---

## Message Format

### Base Message Structure

```json
{
  "version": "1.0",
  "type": "message_type",
  "timestamp": 1234567890.123,
  ... type-specific fields ...
}
```

**Required Fields:**
- `version` (string): Protocol version ("1.0")
- `type` (string): Message type identifier
- `timestamp` (float): Unix timestamp (seconds since epoch)

### Message Types

#### Connection Messages

**REGISTER**
```json
{
  "version": "1.0",
  "type": "register",
  "timestamp": 1234567890.123,
  "nickname": "alice",
  "public_key": "base64_x25519_public_key",
  "password": "optional_password",
  "session_token": "optional_session_token"
}
```

**DISCONNECT**
```json
{
  "version": "1.0",
  "type": "disconnect",
  "timestamp": 1234567890.123
}
```

#### Authentication Messages

**AUTH_REQUEST**
```json
{
  "version": "1.0",
  "type": "auth_request",
  "timestamp": 1234567890.123,
  "username": "alice",
  "password": "password123"
}
```

**AUTH_RESPONSE**
```json
{
  "version": "1.0",
  "type": "auth_response",
  "timestamp": 1234567890.123,
  "success": true,
  "session_token": "64_char_token",
  "message": "Authenticated as alice"
}
```

**CREATE_ACCOUNT**
```json
{
  "version": "1.0",
  "type": "create_account",
  "timestamp": 1234567890.123,
  "username": "alice",
  "password": "password123",
  "email": "alice@example.com"
}
```

**CHANGE_PASSWORD**
```json
{
  "version": "1.0",
  "type": "change_password",
  "timestamp": 1234567890.123,
  "old_password": "oldpass",
  "new_password": "newpass"
}
```

**AUTH_REQUIRED**
```json
{
  "version": "1.0",
  "type": "auth_required",
  "timestamp": 1234567890.123,
  "message": "Authentication required to use this server"
}
```

#### Key Exchange Messages

**PUBLIC_KEY_REQUEST**
```json
{
  "version": "1.0",
  "type": "public_key_request",
  "timestamp": 1234567890.123,
  "target_nickname": "bob"
}
```

**PUBLIC_KEY_RESPONSE**
```json
{
  "version": "1.0",
  "type": "public_key_response",
  "timestamp": 1234567890.123,
  "user_id": "user_1_bob",
  "nickname": "bob",
  "public_key": "base64_x25519_public_key"
}
```

**KEY_EXCHANGE**
```json
{
  "version": "1.0",
  "type": "key_exchange",
  "timestamp": 1234567890.123,
  "from_id": "user_0_alice",
  "to_id": "user_1_bob",
  "public_key": "base64_x25519_public_key"
}
```

**REKEY_REQUEST**
```json
{
  "version": "1.0",
  "type": "rekey_request",
  "timestamp": 1234567890.123,
  "from_id": "user_0_alice",
  "to_id": "user_1_bob",
  "new_public_key": "base64_x25519_public_key"
}
```

**REKEY_RESPONSE**
```json
{
  "version": "1.0",
  "type": "rekey_response",
  "timestamp": 1234567890.123,
  "from_id": "user_1_bob",
  "to_id": "user_0_alice",
  "new_public_key": "base64_x25519_public_key"
}
```

#### Encrypted Messages

**PRIVATE_MESSAGE**
```json
{
  "version": "1.0",
  "type": "private_message",
  "timestamp": 1234567890.123,
  "from_id": "user_0_alice",
  "to_id": "user_1_bob",
  "encrypted_data": "base64_chacha20poly1305_ciphertext",
  "nonce": "base64_12byte_nonce"
}
```

**CHANNEL_MESSAGE**
```json
{
  "version": "1.0",
  "type": "channel_message",
  "timestamp": 1234567890.123,
  "from_id": "user_0_alice",
  "to_id": "#lobby",
  "encrypted_data": "base64_chacha20poly1305_ciphertext",
  "nonce": "base64_12byte_nonce"
}
```

#### Channel Management Messages

**JOIN_CHANNEL**
```json
{
  "version": "1.0",
  "type": "join_channel",
  "timestamp": 1234567890.123,
  "user_id": "user_0_alice",
  "channel": "#lobby",
  "password": "",
  "creator_password": ""
}
```

**LEAVE_CHANNEL**
```json
{
  "version": "1.0",
  "type": "leave_channel",
  "timestamp": 1234567890.123,
  "user_id": "user_0_alice",
  "channel": "#lobby"
}
```

**SET_TOPIC**
```json
{
  "version": "1.0",
  "type": "set_topic",
  "timestamp": 1234567890.123,
  "channel": "#lobby",
  "topic": "Welcome to the lobby!"
}
```

**OP_USER**
```json
{
  "version": "1.0",
  "type": "op_user",
  "timestamp": 1234567890.123,
  "channel": "#lobby",
  "target_nickname": "bob",
  "password": "creator_password"
}
```

**KICK_USER**
```json
{
  "version": "1.0",
  "type": "kick_user",
  "timestamp": 1234567890.123,
  "channel": "#lobby",
  "target_nickname": "bob",
  "reason": "Spamming"
}
```

**BAN_USER**
```json
{
  "version": "1.0",
  "type": "ban_user",
  "timestamp": 1234567890.123,
  "channel": "#lobby",
  "target_nickname": "bob"
}
```

#### File Transfer Messages

**IMAGE_START**
```json
{
  "version": "1.0",
  "type": "image_start",
  "timestamp": 1234567890.123,
  "from_id": "user_0_alice",
  "to_id": "user_1_bob",
  "filename": "photo.jpg",
  "total_chunks": 15,
  "file_size": 48000
}
```

**IMAGE_CHUNK**
```json
{
  "version": "1.0",
  "type": "image_chunk",
  "timestamp": 1234567890.123,
  "from_id": "user_0_alice",
  "to_id": "user_1_bob",
  "chunk_number": 5,
  "encrypted_data": "base64_encrypted_chunk",
  "nonce": "base64_12byte_nonce"
}
```

**IMAGE_END**
```json
{
  "version": "1.0",
  "type": "image_end",
  "timestamp": 1234567890.123,
  "from_id": "user_0_alice",
  "to_id": "user_1_bob"
}
```

#### Server Response Messages

**ACK**
```json
{
  "version": "1.0",
  "type": "ack",
  "timestamp": 1234567890.123,
  "success": true,
  "message": "Operation successful",
  "user_id": "user_0_alice",
  "channel": "#lobby"
}
```

**ERROR**
```json
{
  "version": "1.0",
  "type": "error",
  "timestamp": 1234567890.123,
  "error": "Error description"
}
```

**USER_LIST**
```json
{
  "version": "1.0",
  "type": "user_list",
  "timestamp": 1234567890.123,
  "users": [
    {
      "user_id": "user_0_alice",
      "nickname": "alice",
      "public_key": "base64_key"
    }
  ]
}
```

**USER_JOINED**
```json
{
  "version": "1.0",
  "type": "user_joined",
  "timestamp": 1234567890.123,
  "channel": "#lobby",
  "user_id": "user_1_bob",
  "nickname": "bob",
  "public_key": "base64_key"
}
```

**USER_LEFT**
```json
{
  "version": "1.0",
  "type": "user_left",
  "timestamp": 1234567890.123,
  "channel": "#lobby",
  "user_id": "user_1_bob",
  "nickname": "bob"
}
```

---

## Connection Lifecycle

### State Diagram

```
[Disconnected]
      |
      | TCP Connect
      v
[Connected]
      |
      | REGISTER (with public key)
      v
[Registered] <---> [Authenticated] (optional)
      |
      | JOIN_CHANNEL / PRIVATE_MESSAGE
      v
[Active]
      |
      | Message exchange, key rotation
      |
      | DISCONNECT or timeout
      v
[Disconnected]
```

### Registration Flow

```
Client                          Server
  |                                |
  |--- REGISTER ----------------->|
  |    (nickname, public_key)      |
  |                                |
  |                     Validate nickname
  |                     Check if taken
  |                     Assign user_id
  |                                |
  |<-- ACK -----------------------|
  |    (user_id)                   |
  |                                |
  [Registered and ready]
```

### Authentication Flow (Optional)

```
Client                          Server
  |                                |
  |--- REGISTER ----------------->|
  |    (nickname, public_key)      |
  |                                |
  |<-- AUTH_REQUIRED -------------|
  |                                |
  |--- AUTH_REQUEST ------------->|
  |    (username, password)        |
  |                                |
  |                     Verify credentials
  |                     Create session
  |                                |
  |<-- AUTH_RESPONSE -------------|
  |    (session_token)             |
  |                                |
  |--- REGISTER ----------------->|
  |    (nickname, key, token)      |
  |                                |
  |<-- ACK -----------------------|
  |                                |
  [Authenticated and registered]
```

---

## Encryption Protocol

### Cryptographic Primitives

- **Key Exchange**: X25519 (Curve25519 ECDH)
- **Encryption**: ChaCha20-Poly1305 (AEAD)
- **Key Derivation**: HKDF-SHA256
- **Password Hashing**: PBKDF2-HMAC-SHA256 (100,000 iterations)

### Private Message Encryption

1. **Key Exchange**:
   - Each client generates ephemeral X25519 keypair
   - Clients exchange public keys via server
   - Shared secret computed using X25519 ECDH
   - Shared secret derived into encryption key using HKDF

2. **Encryption**:
   - Sender encrypts plaintext with ChaCha20-Poly1305
   - Uses shared key derived from X25519 exchange
   - Generates random 12-byte nonce for each message
   - Produces ciphertext with authentication tag

3. **Decryption**:
   - Receiver looks up shared key by sender user_id
   - Decrypts using ChaCha20-Poly1305 with nonce
   - Verifies authentication tag
   - Returns plaintext

### Channel Encryption

1. **Channel Key Creation**:
   - First user to join creates 32-byte symmetric key
   - Key stored in client's channel_keys dictionary
   - Key distributed to new members via encrypted KEY_EXCHANGE

2. **Channel Message Encryption**:
   - Sender encrypts with channel's shared key
   - All channel members can decrypt with same key
   - Each message has unique random nonce

3. **Key Distribution**:
   - When user joins channel, operator sends KEY_EXCHANGE
   - Channel key encrypted with user's public key
   - User decrypts and stores channel key

### Key Rotation Protocol

Key rotation maintains Perfect Forward Secrecy by periodically changing encryption keys.

**Rotation Triggers:**
- Time-based: After 3600 seconds (1 hour) by default
- Message-based: After 10,000 messages by default
- Manual: Via `/rekey` command

**Rotation Flow:**
```
Alice                           Bob
  |                              |
  | Detect rotation needed       |
  | Generate new keypair         |
  |                              |
  |--- REKEY_REQUEST ----------->|
  |    (new_public_key)          |
  |                              |
  |                   Generate new keypair
  |                   Compute new shared secret
  |                              |
  |<-- REKEY_RESPONSE -----------|
  |    (new_public_key)          |
  |                              |
  | Compute new shared secret    |
  | Delete old keys              |
  |                              |
  [New keys active]
```

**Key Rotation Properties:**
- Old messages cannot be decrypted after rotation
- Each rotation generates fresh ephemeral keys
- Keys never reused across sessions
- Manual rotation always available

---

## Authentication Flow

### Account Creation

```
Client                          Server
  |                                |
  |--- CREATE_ACCOUNT ----------->|
  |    (username, password, email) |
  |                                |
  |                     Validate inputs
  |                     Check username available
  |                     Hash password (PBKDF2)
  |                     Store account
  |                                |
  |<-- ACK -----------------------|
  |    "Account created"           |
```

### Login and Session Management

```
Client                          Server
  |                                |
  |--- AUTH_REQUEST ------------->|
  |    (username, password)        |
  |                                |
  |                     Verify password hash
  |                     Check lockout status
  |                     Generate session token
  |                     Store session
  |                                |
  |<-- AUTH_RESPONSE -------------|
  |    (session_token)             |
  |                                |
  |--- REGISTER ----------------->|
  |    (nickname, key, token)      |
  |                                |
  |                     Verify session token
  |                     Associate session->user
  |                                |
  |<-- ACK -----------------------|
  |    (user_id)                   |
```

### Password Requirements

- **Minimum length**: 8 characters
- **Maximum length**: 256 characters
- **Allowed characters**: Any printable characters
- **Storage**: PBKDF2-HMAC-SHA256 with 100,000 iterations
- **Salt**: 32 bytes random per password

### Session Tokens

- **Format**: 64-character URL-safe base64 string
- **Expiration**: Persistent until logout
- **Storage**: In-memory on server
- **Security**: Tokens are random, unpredictable

### Account Lockout

- **Threshold**: 5 failed attempts
- **Window**: 15 minutes
- **Duration**: 15 minutes from last failed attempt
- **Reset**: Automatic after lockout expires

---

## State Machine

### Client States

```
DISCONNECTED -> CONNECTED -> REGISTERED -> ACTIVE
     ^                                       |
     |                                       |
     +---------------------------------------+
                    DISCONNECT
```

**DISCONNECTED**
- No connection to server
- Can attempt TCP connection

**CONNECTED**
- TCP connection established
- Can send REGISTER message
- Must provide nickname and public key

**REGISTERED**
- Successfully registered with server
- Received user_id from server
- Can join channels, send messages
- Can exchange keys with other users

**ACTIVE**
- Actively participating in channels and conversations
- Sending and receiving messages
- May rotate keys periodically
- Can logout or disconnect

### Server States (per client)

```
AWAITING_REGISTER -> REGISTERED -> AUTHENTICATED (optional)
                         |
                         v
                   MESSAGE_HANDLING
```

**AWAITING_REGISTER**
- New client connection
- Waiting for REGISTER message
- May send AUTH_REQUIRED if auth enabled
- Timeout after connection_timeout seconds

**REGISTERED**
- Client has registered nickname
- Can route messages
- Can join channels
- May require authentication for certain operations

**AUTHENTICATED** (optional)
- Client has valid session token
- Full access to server features
- Associated with account

**MESSAGE_HANDLING**
- Processing client messages
- Routing encrypted messages
- Managing channels
- Enforcing rate limits

---

## Protocol Extensions

### Rate Limiting

JustIRC implements token bucket rate limiting:

**Message Rate Limit:**
- 30 messages per 10 seconds per user
- Applies to PRIVATE_MESSAGE and CHANNEL_MESSAGE

**Image Chunk Rate Limit:**
- 100 chunks per 10 seconds per user
- Applies to IMAGE_CHUNK messages

**Connection Rate Limit:**
- 5 connections per minute per IP
- 10 violations trigger 15-minute IP ban

**Rate Limit Response:**
```json
{
  "type": "error",
  "error": "Rate limit exceeded. Try again in X seconds."
}
```

### Input Validation

**Nickname Validation:**
- Length: 3-20 characters
- Pattern: `^[a-zA-Z0-9_-]+$`
- Reserved: server, admin, root, system

**Channel Name Validation:**
- Must start with `#`
- Length: 2-51 characters (including #)
- Pattern: `^#[a-zA-Z0-9_-]+$`

**Message Validation:**
- Maximum: 4096 bytes (4KB)
- No null bytes or control characters

**Topic Validation:**
- Maximum: 256 characters

### IP Filtering

**Blacklist Mode** (default):
- Block specific IPs or CIDR networks
- Temporary bans with expiration
- Persistent blacklist storage

**Whitelist Mode** (optional):
- Only allow specific IPs or networks
- All other IPs blocked
- Persistent whitelist storage

**Temporary Ban:**
- Default duration: 15 minutes
- Automatic expiry
- Can be removed manually

### Error Codes

| Error Message | Description |
|--------------|-------------|
| "Missing nickname or public_key" | Registration incomplete |
| "Nickname {name} already taken" | Nickname in use |
| "Authentication required" | Server requires auth |
| "Invalid username or password" | Auth failed |
| "Account temporarily locked" | Too many failed attempts |
| "Access denied" | IP blocked |
| "Rate limit exceeded" | Too many requests |
| "Message too large" | Message exceeds max_message_size |
| "Read timeout" | Client took too long |
| "Invalid channel name" | Channel name format invalid |
| "You are banned from {channel}" | User banned |
| "Channel not found" | Channel doesn't exist |
| "Not authorized" | Insufficient permissions |

---

## Security Considerations

### End-to-End Encryption

- Server **CANNOT** read message content
- Server only routes encrypted messages
- Clients must trust each other's public keys
- No server-side message persistence

### Perfect Forward Secrecy

- Keys rotated periodically (time/message count)
- Old messages cannot be decrypted after rotation
- Each session uses ephemeral keys
- Manual rotation available via `/rekey`

### Authentication

- Passwords never sent in plaintext after registration
- PBKDF2 with 100,000 iterations
- 32-byte random salt per password
- Account lockout prevents brute force
- Session tokens are URL-safe random strings

### Input Validation

- All inputs validated before processing
- Control characters removed
- Maximum lengths enforced
- Reserved names blocked
- SQL injection not applicable (no SQL)

### Denial of Service Protection

- Rate limiting on messages and connections
- Connection timeouts prevent resource exhaustion
- Maximum message size enforced
- IP bans for abuse
- Optional IP whitelist mode

---

## Future Extensions

Potential future protocol enhancements:

1. **Voice/Video**: Real-time encrypted A/V streams
2. **File Transfer**: General file transfer beyond images
3. **Read Receipts**: Optional delivery confirmations
4. **Typing Indicators**: Optional typing status
5. **Push Notifications**: Mobile notification support
6. **Multi-Device**: Sync across multiple devices
7. **Server Federation**: Connect multiple servers
8. **Plugin System**: Extend protocol with custom messages

---

## Version History

**Version 1.0** (Current)
- Initial protocol specification
- End-to-end encryption with X25519 + ChaCha20-Poly1305
- Key rotation support
- Authentication system
- Rate limiting
- Input validation
- IP filtering

---

## References

- [RFC 1459](https://tools.ietf.org/html/rfc1459) - Internet Relay Chat Protocol
- [RFC 7748](https://tools.ietf.org/html/rfc7748) - Elliptic Curves (X25519)
- [RFC 7539](https://tools.ietf.org/html/rfc7539) - ChaCha20-Poly1305 AEAD
- [RFC 5869](https://tools.ietf.org/html/rfc5869) - HKDF
- [NIST SP 800-132](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-132.pdf) - PBKDF2
