# JustIRC Quick Start Guide

## What is JustIRC?

JustIRC is a secure, end-to-end encrypted IRC chat system where:
- **All messages are encrypted** - Only sender and recipient can read messages
- **Server is blind** - Server cannot see message content, only routes encrypted data
- **Images are secure** - Image sharing is also fully encrypted
- **Privacy focused** - IP addresses are not shared between clients

## Installation

### 1. Clone or Download

```bash
cd ~/Repos/justIRC
```

### 2. Run Setup

**Linux/Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**
```bash
setup.bat
```

This will:
- Create a virtual environment
- Install all dependencies
- Set up the project

## Running JustIRC

### Start the Server

In one terminal:

```bash
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate.bat  # Windows

python server.py
```

The server will start on `localhost:6667` by default.

### Start a Client

**Option 1: GUI Client (Recommended for beginners)**

In another terminal:

```bash
source venv/bin/activate  # Linux/Mac
python client_gui.py
```

Then:
1. Enter server address (localhost), port (6667), and your nickname
2. Click "Connect"
3. Join a channel with the "Join Channel" button
4. Start chatting!

**Option 2: CLI Client (For power users)**

```bash
source venv/bin/activate  # Linux/Mac
python client.py --nickname Alice
```

Basic commands:
- `/join #general` - Join a channel
- `/join #private mypassword` - Join a password-protected channel
- `/msg Bob Hello` - Send private message to Bob
- `/image Bob photo.jpg` - Send image to Bob
- `/help` - Show all commands
- `/quit` - Disconnect

## Your First Conversation

### Setup (3 terminals)

**Terminal 1 - Server:**
```bash
source venv/bin/activate
python server.py
```

**Terminal 2 - Alice:**
```bash
source venv/bin/activate
python client.py --nickname Alice
```

**Terminal 3 - Bob:**
```bash
source venv/bin/activate
python client.py --nickname Bob
```

### Chat in a Channel

**Alice:**
```
/join #general
Hello everyone!
```

**Bob:**
```
/join #general
Hi Alice!
```

Both Alice and Bob can now see each other's messages in #general.

### Private Channel with Password

**Alice:**
```
/join #secret supersecretpass
```

**Bob:**
```
/join #secret wrongpassword
[ERROR] Incorrect channel password

/join #secret supersecretpass
[✓] Joined channel #secret (2 members)
```

### Private Message

**Alice:**
```
/msg Bob This is a private message just for you
```

**Bob will see:**
```
[PM from Alice] This is a private message just for you
```

### Send an Image

**Alice:**
```
/image Bob myimage.png
```

Bob will receive the encrypted image and it will be saved as `received_myimage.png`.

## Advanced Usage

### Custom Server Address

Run server on a specific address:
```bash
python server.py --host 0.0.0.0 --port 7000
```

Connect client to remote server:
```bash
python client.py --server example.com --port 7000 --nickname Alice
```

### Using with Tor

For enhanced anonymity, see [TOR_SETUP.md](TOR_SETUP.md)

### Running as System Service

For production deployment, see [DEPLOYMENT.md](DEPLOYMENT.md)

## Security Tips

1. **Verify Recipients**: Make sure you're sending to the right person
2. **Use Unique Nicknames**: Choose nicknames not associated with other identities
3. **Keep Software Updated**: Always use the latest version
4. **Use Tor/VPN**: For additional IP privacy
5. **Secure Your Device**: Protect your computer with strong passwords

## Common Issues

### "Connection refused"

- Make sure the server is running
- Check firewall settings
- Verify the server address and port

### "Failed to decrypt message"

- Key exchange may have failed
- Try reconnecting both clients
- Ensure both clients are using compatible versions

### "Nickname already taken"

- Someone else is using that nickname
- Choose a different nickname
- Disconnect the other client first (if it's yours)

### GUI doesn't start

- Make sure tkinter is installed (comes with Python)
- On Linux: `sudo apt install python3-tk`
- Try the CLI client instead

## Next Steps

- Read [SECURITY.md](SECURITY.md) to understand the security model
- See [TOR_SETUP.md](TOR_SETUP.md) for Tor integration
- Check out the source code to understand how it works
- Run `python test_suite.py` to verify everything works

## Getting Help

- Check existing documentation in the repository
- Review the source code (it's well-commented!)
- Open an issue on GitHub (if applicable)

## Contributing

Contributions are welcome! Please:
1. Test your changes thoroughly
2. Follow the existing code style
3. Add tests for new features
4. Update documentation

## License

JustIRC is released under the MIT License. See [LICENSE](LICENSE) file.

---

**Remember**: While JustIRC provides strong encryption, no system is perfectly secure. Use responsibly and stay informed about security best practices.
