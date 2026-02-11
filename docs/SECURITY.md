# JustIRC Security Documentation

## Overview

JustIRC is designed with security as the top priority. This document explains the security architecture and best practices.

## Threat Model

### What JustIRC Protects Against:

1. **Server Compromise**: Even if the server is compromised, messages cannot be read
2. **Network Eavesdropping**: All data is encrypted in transit
3. **Man-in-the-Middle Attacks**: Public key verification prevents MITM attacks
4. **Message Tampering**: Authenticated encryption prevents message modification
5. **IP Address Exposure**: Client IP addresses are not shared with other clients

### What JustIRC Does NOT Protect Against:

1. **Endpoint Compromise**: If a client device is compromised, messages can be read
2. **Malicious Clients**: A malicious client with valid credentials can participate
3. **Denial of Service**: Server can be overwhelmed with connections
4. **Traffic Analysis**: Metadata (timing, message size) is visible to server

## Cryptographic Design

### Key Exchange

- **Algorithm**: X25519 (Elliptic Curve Diffie-Hellman)
- **Key Size**: 256 bits
- **Purpose**: Establish shared secrets between clients

Each client generates an ephemeral X25519 key pair on startup:
- Private key never leaves the client
- Public key is shared via the server
- Shared secret computed locally using ECDH

### Message Encryption

- **Algorithm**: ChaCha20-Poly1305 (AEAD)
- **Key Size**: 256 bits
- **Nonce Size**: 96 bits (randomly generated per message)
- **Authentication**: Built-in via Poly1305 MAC

Properties:
- Authenticated encryption prevents tampering
- Unique nonce per message prevents replay attacks
- Constant-time implementation prevents timing attacks

### Key Derivation

- **Algorithm**: HKDF with SHA-256
- **Purpose**: Derive encryption key from ECDH shared secret
- **Info String**: "JustIRC-E2E-Encryption"

This ensures the derived key is suitable for ChaCha20-Poly1305.

### Key Rotation

- **Automatic Rotation**: Keys rotate automatically based on:
  - Time: After 1 hour of continuous use (configurable)
  - Usage: After 10,000 messages exchanged (configurable)
- **Manual Rotation**: Users can initiate rotation via `/rekey <username>`
- **Protocol**: Uses REKEY_REQUEST/REKEY_RESPONSE messages
- **Process**:
  1. Initiator generates new ephemeral key pair
  2. Initiator sends new public key to peer
  3. Peer loads new key and generates own new key pair
  4. Peer sends new public key back
  5. Both parties compute new shared secret
  6. Message counters and timers reset
- **Benefits**:
  - Limits exposure window if keys are compromised
  - Provides Perfect Forward Secrecy for long conversations
  - Prevents cryptanalysis from large message samples

## Security Properties

### End-to-End Encryption

Messages are encrypted on the sender's device and only decrypted on the recipient's device. The server:
- Cannot read message content
- Cannot modify messages without detection
- Only routes encrypted payloads

### Perfect Forward Secrecy

Each session uses new ephemeral keys with automatic rotation:
- Keys are generated per session
- Keys are stored only in memory
- Keys automatically rotate after 1 hour or 10,000 messages
- Manual key rotation available via `/rekey` command
- Compromise of one session doesn't affect others
- Compromise of current keys doesn't expose past messages

### Anonymity Features

IP Address Protection:
- Client IP addresses are not shared with other clients
- Server knows IPs but cannot read messages
- Consider using Tor/VPN for additional anonymity

## Server Hardening

### Input Validation

All user inputs are validated and sanitized before processing:

**Validation Rules:**
- Nicknames: 3-20 alphanumeric characters, underscores, and hyphens only
- Channel Names: Must start with #, 1-50 characters
- Messages: Maximum 4KB, no null bytes or control characters
- Email Addresses: RFC-compliant format validation
- Passwords: Minimum 8 characters, maximum 256 characters

**Protection Against:**
- Injection attacks (null byte injection, command injection)
- Buffer overflow attempts
- Malformed input Processing
- Reserved name hijacking (server, admin, root, system)

### IP Filtering

Network-level access control prevents unwanted connections:

**Blacklist Mode (Default):**
- Block specific IP addresses
- Block entire network ranges (CIDR notation: 192.168.0.0/24)
- Automatic temporary bans (configurable duration)
- Persistent across server restarts

**Whitelist Mode (Optional):**
- Only allow specified IP addresses or networks
- Deny all others by default
- Useful for private/internal servers

**Configuration:**
```json
{
  "enable_ip_whitelist": false
}
```

### Connection Management

Resource limits and timeouts prevent DoS attacks:

**Timeout Settings:**
- Connection timeout: 300 seconds (configurable)
- Read timeout: 60 seconds per message (configurable)
- Automatic cleanup of idle connections

**Message Limits:**
- Maximum message size: 64KB (configurable)
- Oversized messages rejected with error

**Rate Limiting:**
- Per-client message limits: 30 messages/10 seconds
- Per-client image limits: 100 chunks/10 seconds
- Per-IP connection limits: 5 connections/minute
- Automatic temporary bans after repeated violations

### Authentication Security

Optional password authentication with industry-standard security:

**Password Hashing:**
- Algorithm: PBKDF2-HMAC-SHA256
- Iterations: 100,000 (OWASP recommendation)
- Salt: 256-bit random salt per password
- Constant-time comparison to prevent timing attacks

**Account Protection:**
- Automatic lockout after 5 failed attempts
- 15-minute lockout window
- Password requirements: minimum 8 characters
- Session tokens for persistent authentication
- Account enable/disable controls

**Modes:**
- Optional authentication: Accounts available but not required
- Required authentication: All users must authenticate
- Anonymous mode: No authentication (default)

**Configuration:**
```json
{
  "enable_authentication": false,
  "require_authentication": false
}
```

## Best Practices

### For Users

1. **Verify Public Keys**: When possible, verify public keys out-of-band
2. **Use Strong Nicknames**: Choose unique nicknames to prevent impersonation
3. **Secure Your Device**: Keep your device and OS updated
4. **Use Tor/VPN**: For additional IP privacy, route through Tor or a VPN
5. **Verify Recipients**: Ensure you're sending to the intended recipient

### For Server Operators

1. **Use TLS**: Wrap connections in TLS for transport security
2. **Rate Limiting**: Implement rate limiting to prevent abuse
3. **Logging**: Minimize logging (no message content, only metadata)
4. **Updates**: Keep server software updated
5. **Monitoring**: Monitor for unusual activity patterns
6. **Firewall**: Use a firewall to protect the server

### For Developers

1. **Code Review**: Review cryptographic code carefully
2. **Dependencies**: Keep cryptography library updated
3. **Random Numbers**: Use system CSPRNG for all randomness
4. **Memory Safety**: Clear sensitive data from memory when done
5. **Error Handling**: Don't leak information in error messages

## Limitations

### Known Limitations

1. **Metadata Leakage**: Server sees who is talking to whom and when
2. **No User Authentication**: Anyone can connect with any nickname
3. **No Key Verification**: Initial key exchange is not verified
4. **Channel Security**: Channel encryption uses peer-to-peer, not group keys
5. **No Message Persistence**: Messages are not stored (by design)

### Future Improvements

Planned security enhancements:
- Signal Protocol integration with Double Ratchet
- Key verification and trust-on-first-use (TOFU)
- Onion routing within the protocol
- Group key management for channels
- User authentication with certificates
- Enhanced key rotation with asymmetric ratcheting

## Compliance

### Data Protection

JustIRC is designed to minimize data collection:
- No message content stored
- No user registration database
- Ephemeral keys only
- No persistent identifiers

This design aids compliance with:
- GDPR (minimal data collection)
- Privacy regulations
- Data retention requirements

### Cryptographic Standards

JustIRC uses modern, well-vetted cryptographic primitives:
- X25519: RFC 7748
- ChaCha20-Poly1305: RFC 8439
- HKDF: RFC 5869

All algorithms are implemented in the `cryptography` library, which is:
- Widely used and audited
- Actively maintained
- Compliant with FIPS standards

## Security Audits

### Self-Assessment

This software has not undergone a professional security audit. Use at your own risk.

Recommended actions:
- Independent code review
- Penetration testing
- Cryptographic audit
- Threat modeling workshop

### Reporting Vulnerabilities

If you discover a security vulnerability:
1. Do NOT open a public issue
2. Email the maintainer directly
3. Include detailed reproduction steps
4. Allow time for a fix before disclosure

## References

### Standards

- [RFC 7748](https://tools.ietf.org/html/rfc7748) - X25519
- [RFC 8439](https://tools.ietf.org/html/rfc8439) - ChaCha20-Poly1305
- [RFC 5869](https://tools.ietf.org/html/rfc5869) - HKDF

### Further Reading

- [Signal Protocol](https://signal.org/docs/)
- [Cryptography Engineering](https://www.schneier.com/books/cryptography_engineering/) by Ferguson, Schneier, and Kohno
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)

---

**Remember**: Security is a process, not a product. Stay vigilant and keep your systems updated.
