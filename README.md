# JustIRC - Secure End-to-End Encrypted IRC

A privacy-focused IRC system with end-to-end encryption, where the server only handles routing and never sees message content.

## Features

- **End-to-End Encryption**: All messages encrypted using X25519 key exchange and ChaCha20-Poly1305
- **Zero Server Storage**: Server acts only as a message router, never stores data
- **Encrypted Image Sharing**: Images are encrypted before transmission, decrypted by recipient
- **IP Address Protection**: IP addresses are not shared with other clients
- **Perfect Forward Secrecy**: Each session uses new ephemeral keys
- **Anonymous Authentication**: Optional anonymous mode
- **Password-Protected Channels**: Create private channels with password protection
- **Modern Themeable GUI**: 4 themes including cyber security-inspired design with custom logo
- **Operator System**: Channel operators with /op command
- **IRC Commands**: Full slash command support (/me, /join, /msg, /image, etc.)

## Security Architecture

1. **Key Exchange**: X25519 elliptic curve Diffie-Hellman
2. **Message Encryption**: ChaCha20-Poly1305 (authenticated encryption)
3. **Signatures**: Ed25519 for message authentication
4. **No Server Decryption**: Server cannot read message content
5. **Memory-Only**: No persistent storage on server

## Components

- `server.py` - Routing server (no decryption capabilities)
- `client.py` - CLI client application
- `client_gui.py` - Tkinter-based GUI client
- `crypto_layer.py` - All cryptographic operations
- `protocol.py` - Message protocol definitions

## Documentation

- [FEATURES.md](docs/FEATURES.md) - Complete feature guide with examples
- [QUICKSTART.md](docs/QUICKSTART.md) - Get started in 5 minutes
- [SECURITY.md](docs/SECURITY.md) - Security architecture deep dive
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design & diagrams
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - Production deployment guide (includes Docker & GCP)
- [GCP_DEPLOY.md](docs/GCP_DEPLOY.md) - Quick GCP deployment reference
- [TOR_SETUP.md](docs/TOR_SETUP.md) - Tor integration for anonymity
- [THEMES.md](docs/THEMES.md) - Theme customization and logo design guide
- [PACKAGING.md](docs/PACKAGING.md) - Package as standalone .exe (Windows) or .deb (Linux)
- [OPERATOR_GUIDE.md](docs/OPERATOR_GUIDE.md) - Channel operator quick reference guide

## 📦 Standalone Packages (No Python Required!)

Build standalone executables that don't require Python installation:

### Windows (.exe)
```batch
build-windows.bat
```
Creates single-file executables: `JustIRC-GUI.exe`, `JustIRC-CLI.exe`, `JustIRC-Server.exe`

### Linux (.deb)
```bash
./build-linux.sh
```
Creates installable package: `python3-justirc_1.0.0-1_all.deb`

See [PACKAGING.md](docs/PACKAGING.md) for complete packaging guide.

## Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Start Server

```bash
python server.py --host 0.0.0.0 --port 6667
```

### Docker Deployment (Recommended)

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build manually
docker build -t justirc-server .
docker run -d -p 6667:6667 --name justirc justirc-server
```

### Cloud Deployment (GCP - Free Tier)

Deploy to Google Cloud Platform for **FREE** with capacity for 5000+ messages/minute:

```bash
# Set your GCP project
export GCP_PROJECT_ID=your-project-id

# Deploy (automated)
./deploy_gcp.sh
```

See [GCP_DEPLOY.md](docs/GCP_DEPLOY.md) for detailed instructions.

**Cost**: FREE on e2-micro free tier, or ~$7-8/month for standard deployment.

### Start Client (GUI)

```bash
python client_gui.py
```

### Start Client (CLI)

```bash
python client.py --server localhost --port 6667 --nickname yourname
```

## Architecture

```
Client A                Server              Client B
   |                      |                     |
   |-- Register --------->|                     |
   |<-- Public Key -------|                     |
   |                      |<-- Register --------|
   |                      |-- Public Key ------>|
   |-- Encrypted Message->|                     |
   |                      |-- Route Message --->|
   |                      |   (Still encrypted) |
```

## Protocol

All messages are JSON-formatted with the following structure:

```json
{
  "type": "message|join|leave|key_exchange|image",
  "from": "sender_id",
  "to": "recipient_id|channel",
  "encrypted_data": "base64_encrypted_payload",
  "nonce": "base64_nonce",
  "timestamp": 1234567890
}
```

## Security Considerations

- Server operator cannot read messages
- Each client generates ephemeral keys per session
- Images are chunked, encrypted, and transmitted securely
- No logs are kept on the server
- IP addresses are not exposed to other clients

## License

MIT License - Use responsibly and respect privacy laws in your jurisdiction.
