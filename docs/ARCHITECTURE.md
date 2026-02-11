# JustIRC Architecture

## System Overview

```
┌─────────────┐                                    ┌─────────────┐
│   Client A  │                                    │   Client B  │
│             │                                    │             │
│  ┌───────┐  │                                    │  ┌───────┐  │
│  │ Crypto│  │                                    │  │ Crypto│  │
│  │ Layer │  │                                    │  │ Layer │  │
│  └───────┘  │                                    │  └───────┘  │
│      │      │                                    │      │      │
│  [Private   │                                    │  [Private   │
│   Key A]    │                                    │   Key B]    │
│      │      │                                    │      │      │
│  [Public    │         ┌──────────────┐         │  [Public    │
│   Key A]────┼────────▶│    Server    │◀────────┼────Key B]   │
│             │         │              │         │             │
│  Encrypt    │         │  (Routing    │         │  Decrypt    │
│  Messages   │         │   Only)      │         │  Messages   │
│             │         │              │         │             │
└─────────────┘         │  • No Keys   │         └─────────────┘
                        │  • No Decrypt│
                        │  • No Storage│
                        └──────────────┘
```

## Key Components

### 1. Crypto Layer (`crypto_layer.py`)

**Responsibilities:**
- Generate X25519 key pairs
- Perform ECDH key exchange
- Encrypt/decrypt messages with ChaCha20-Poly1305
- Manage shared secrets with peers

**Key Classes:**
- `CryptoLayer`: Main encryption/decryption handler
- `ChannelCrypto`: Channel (group) encryption manager

### 2. Protocol (`protocol.py`)

**Responsibilities:**
- Define message types
- Build protocol messages
- Parse incoming messages
- Maintain protocol version

**Message Types:**
- Connection: REGISTER, DISCONNECT
- Key Exchange: KEY_EXCHANGE, PUBLIC_KEY_REQUEST/RESPONSE
- Messaging: PRIVATE_MESSAGE, CHANNEL_MESSAGE
- Channels: JOIN_CHANNEL, LEAVE_CHANNEL
- Files: IMAGE_START, IMAGE_CHUNK, IMAGE_END
- Responses: ACK, ERROR, USER_LIST, CHANNEL_LIST

### 3. Server (`server.py`)

**Responsibilities:**
- Accept client connections
- Route encrypted messages
- Manage channel membership
- Distribute public keys
- NO decryption capabilities

**Key Classes:**
- `IRCServer`: Main server logic
- `Client`: Represents connected client

### 4. Client (`client.py` / `client_gui.py`)

**Responsibilities:**
- Connect to server
- Exchange keys with peers
- Encrypt outgoing messages
- Decrypt incoming messages
- Handle user interface

**Key Features:**
- CLI client with commands
- GUI client with Tkinter
- Image transfer support
- Channel management

## Data Flow

### Registration Flow

```
Client                          Server
  │                              │
  ├─── REGISTER ────────────────▶│
  │    (nickname, public_key)    │
  │                              │
  │◀──── ACK ─────────────────────┤
  │    (user_id, welcome)        │
  │                              │
  │◀──── USER_LIST ───────────────┤
  │    (other users + keys)      │
  │                              │
```

### Message Flow (E2E Encrypted)

```
Sender                      Server                    Recipient
  │                           │                          │
  ├─ Encrypt(msg, key_B) ────▶│                          │
  │                           │                          │
  │                           ├─ Route(encrypted) ──────▶│
  │                           │                          │
  │                           │                          ├─ Decrypt(msg, key_A)
  │                           │                          │
  │                           │                          ▼
                                                     [Plaintext]
```

### Key Exchange Flow

```
Alice                       Server                      Bob
  │                           │                          │
  │◀──── PUBLIC_KEY ──────────┤◀──── PUBLIC_KEY ─────────┤
  │      (Bob's key)          │      (Alice's key)       │
  │                           │                          │
  ├─ Compute Shared Secret ───┤                          │
  │  using Bob's public key   │                          ├─ Compute Shared Secret
  │  and Alice's private key  │                          │  using Alice's public key
  │                           │                          │  and Bob's private key
  │                           │                          │
  ▼                           │                          ▼
[Shared Secret AB]            │                   [Shared Secret AB]
                                                  (Same secret!)
```

### Image Transfer Flow

```
Sender                                           Recipient
  │                                                 │
  ├─ IMAGE_START ────────────────────────────────▶│
  │  (image_id, total_chunks, metadata)           │
  │                                                │
  ├─ IMAGE_CHUNK #0 ─────────────────────────────▶│
  ├─ IMAGE_CHUNK #1 ─────────────────────────────▶│
  ├─ IMAGE_CHUNK #2 ─────────────────────────────▶│
  │  ... (all encrypted)                          │
  │                                                │
  ├─ IMAGE_END ───────────────────────────────────▶│
  │  (image_id)                                   │
  │                                                ├─ Reassemble
  │                                                ├─ Decrypt
  │                                                ├─ Save to disk
  │                                                ▼
```

## Security Architecture

### Cryptographic Primitives

1. **X25519 (Key Exchange)**
   - Elliptic Curve Diffie-Hellman
   - 256-bit keys
   - Quantum-resistant? No (but widely used)

2. **ChaCha20-Poly1305 (AEAD)**
   - Stream cipher with authentication
   - 256-bit keys, 96-bit nonces
   - Faster than AES on systems without AES-NI
   - Timing-attack resistant

3. **HKDF-SHA256 (Key Derivation)**
   - Derives encryption key from ECDH output
   - Ensures key is properly distributed
   - Domain separation with info string

### Security Layers

```
┌─────────────────────────────────────┐
│  Transport Layer (Optional TLS)     │  ← Defense in depth
├─────────────────────────────────────┤
│  Application Layer Encryption       │  ← End-to-end encryption
│  (ChaCha20-Poly1305)                │     Server cannot decrypt
├─────────────────────────────────────┤
│  Authenticated Encryption           │  ← Prevents tampering
│  (Poly1305 MAC)                     │
└─────────────────────────────────────┘
```

### Threat Mitigation

| Threat              | Mitigation                                   |
|---------------------|----------------------------------------------|
| Eavesdropping       | E2E encryption with ChaCha20-Poly1305       |
| Message tampering   | Authenticated encryption (Poly1305 MAC)     |
| Server compromise   | Server cannot decrypt messages              |
| MITM attack         | Public key exchange (with TOFU)             |
| Replay attacks      | Unique nonces per message                   |
| IP exposure         | Server doesn't share IPs; use Tor           |
| Traffic analysis    | Constant-size padding (not yet implemented) |

## Network Protocol

### Message Format

All messages are JSON, newline-delimited:

```json
{
  "version": "1.0",
  "type": "private_message",
  "from_id": "user_0_alice",
  "to_id": "user_1_bob",
  "encrypted_data": "base64_encrypted_content",
  "nonce": "base64_nonce",
  "timestamp": 1234567890.123
}
```

### Connection Lifecycle

```
1. TCP Connect
2. REGISTER (send nickname + public key)
3. Receive ACK with user_id
4. Receive USER_LIST
5. Exchange messages
6. DISCONNECT or connection closed
```

## Performance Considerations

### Scalability

- **Connections**: Limited by OS file descriptor limit
- **Encryption**: Minimal overhead (~1-2ms per message)
- **Memory**: O(n) where n = number of connected clients
- **CPU**: Dominated by encryption operations

### Optimizations

- Async I/O with asyncio (efficient concurrent connections)
- ChaCha20 is fast in software
- No disk I/O (memory-only)
- Per-peer encryption (no broadcast re-encryption needed)

### Bottlenecks

- Network latency (cannot be optimized)
- Key exchange (one-time cost per peer)
- Image transfer (large payloads, multiple chunks)

## Comparison with Other Systems

| Feature              | JustIRC | Signal | IRC  | Matrix |
|----------------------|---------|--------|------|--------|
| E2E Encryption       | ✓       | ✓      | ✗    | ✓      |
| Server-side storage  | ✗       | ~      | ~    | ✓      |
| Decentralized        | ✗       | ✗      | ✓    | ✓      |
| Image encryption     | ✓       | ✓      | ✗    | ✓      |
| Anonymous by default | ~       | ✗      | ✓    | ✗      |
| Setup complexity     | Low     | Low    | Low  | Medium |

## Future Enhancements

### Planned Features

1. **Double Ratchet**: Like Signal Protocol for better PFS
2. **Group Keys**: Proper group encryption for channels
3. **Key Verification**: QR codes or fingerprints for TOFU
4. **Onion Routing**: Built-in anonymity layer
5. **Voice/Video**: Encrypted A/V calls
6. **File Transfer**: General file sharing (not just images)

### Potential Improvements

- Message padding (hide message length)
- Typing indicators (encrypted)
- Read receipts (encrypted)
- Voice messages
- Reactions/emojis
- Federation (multiple servers)

## Deployment Topologies

### 1. Single Server

```
     Clients ────▶ Server ◀──── Clients
                    │
               (Single point)
```

### 2. With Tor Hidden Service

```
Clients ────▶ Tor Network ────▶ Hidden Service
              (Anonymous)        (Server)
```

### 3. Behind Reverse Proxy

```
Clients ────▶ Nginx/TLS ────▶ Server
              (Port 443)      (Port 6667)
```

### 4. Containerized

```
Docker Container
├── JustIRC Server
├── Nginx (TLS termination)
└── Monitoring
```

## Monitoring and Observability

### Metrics to Track

- Active connections
- Messages per second
- Encryption operations per second
- Memory usage
- Network throughput

### Logs

- Connection/disconnection events
- Channel join/leave
- Errors only (no message content!)

## Compliance and Legal

### Data Collection

**What the server knows:**
- Client IP addresses
- Connection times
- Nicknames (not verified)
- Who talks to whom (metadata)

**What the server does NOT know:**
- Message content
- Image content
- User identities (beyond nicknames)

### GDPR Compliance

- Minimal data collection
- No persistent storage
- Right to disconnect (erase all data)
- No user tracking

---

For more details, see:
- [SECURITY.md](SECURITY.md) - Security deep dive
- [QUICKSTART.md](QUICKSTART.md) - Getting started
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment
- [TOR_SETUP.md](TOR_SETUP.md) - Tor integration
