# JustIRC Feature Guide

## Private Messaging

Private messages are end-to-end encrypted between two users. The server cannot read the content.

### CLI Client

```bash
# Send private message
/msg Alice Hello, this is a private message!

# The recipient sees:
[PM from Bob] Hello, this is a private message!
```

### GUI Client

1. **Double-click** a user in the Users list
2. Status bar shows: "PM to: Username"
3. Type your message and press Enter or click Send
4. Your message appears as: `[PM to Username] message`
5. Received messages appear as: `[PM from Username] message`

---

## Image Sharing

Images are encrypted before transmission and only the recipient can decrypt them.

### CLI Client

```bash
# Send image to user
/image Alice photo.jpg

# Progress messages:
[INFO] Sending image: photo.jpg (15 chunks)
[✓] Image sent: photo.jpg

# Recipient sees:
[INFO] Receiving image from Bob: photo.jpg
[✓] Image saved: received_photo.jpg
```

**Supported formats:** PNG, JPG, JPEG, GIF, BMP, and all other file types

### GUI Client

1. Select a user from the Users list
2. Click **"Send Image"** button
3. Choose an image file in the dialog
4. Progress appears in chat:
   - `[INFO] Sending image: filename.png (N chunks)`
   - `[✓] Image sent: filename.png`

**Receiving images:**
- `[INFO] Receiving image from Username: filename.png`
- `[✓] Image saved: received_filename.png`
- Files are saved in the current directory

---

## Channel Messaging

Channels are group chat rooms. Messages are encrypted peer-to-peer with each member.

### CLI Client

```bash
# Join a public channel
/join #general

# Join password-protected channel
/join #private secretpass

# Send message (when in a channel)
Hello everyone!

# Leave channel
/leave
```

### GUI Client

1. Click **"Join"** button under Channels
2. Enter channel name (e.g., `#general`)
3. Enter password (optional, leave empty for public channels)
4. Click **"Join"**

**Using channels:**
- Click a channel in the Channels list to select it
- Type messages and press Enter
- Status bar shows: "Channel: #channelname"
- Messages appear as: `[#channel] Username: message`

**Leaving channels:**
- Select the channel in the Channels list
- Click **"Leave"** button

---

## Modern User Interface

The GUI client features a modernized interface designed for usability and style.

### Theming System
- **Multiple Themes:** Choose from Dark, Light, Classic, Cyber, and Custom themes.
- **Cyber Theme:** A specialized security-themed interface with Navy/Blue/Green palette matching the application identity.
- **Customization:** Full control over UI colors via `config_manager.py`.

### UI Components
- **Flat Design:** Modern, borderless inputs and lists for a clean look.
- **Custom Scrollbars:** Themed scrollbars that blend with the background (especially in Cyber/Dark themes).
- **Responsive Layout:** A three-panel layout (Channels, Chat, Users) that scales with the window.
- **Visual Feedback:** Hover states on buttons and selection highlights in lists.

---

## Password-Protected Channels

Create private channels that require a password to join.

### How it works:

1. **First user** creates the channel by joining with a password
2. **Other users** must provide the correct password to join
3. Wrong password shows: `[ERROR] Incorrect channel password`

### Security Notes:

- Channel password is stored on the server (for access control)
- Messages within channels are still end-to-end encrypted
- The server cannot read messages, only controls who can join

### Example Session:

**Alice creates private channel:**
```bash
/join #team supersecret
[✓] Joined channel #team (1 members)
```

**Bob joins with correct password:**
```bash
/join #team supersecret
[✓] Joined channel #team (2 members)
```

**Charlie tries wrong password:**
```bash
/join #team wrongpass
[ERROR] Incorrect channel password
```

---

## Real-Time Updates

### User List Updates

- When a new user connects, all clients see: `[INFO] Username is now online`
- User list automatically refreshes in GUI
- CLI shows updated count with `/users` command

### Channel Updates

- When someone joins a channel you're in: `[SYSTEM] Username joined #channel`
- When someone leaves: `[SYSTEM] Username left #channel`
- Channel member list is shown when you join

---

## Tips & Tricks

### CLI Client

1. **Quick PM**: Remember the last person you talked to (not implemented, use `/msg` each time)
2. **Channel switching**: Use `/join #newchannel` to switch channels
3. **User list**: Use `/users` to see who's online
4. **Your channels**: Use `/channels` to see channels you've joined

### GUI Client

1. **Quick PM**: Double-click a user to start private messaging
2. **Multiple channels**: Join multiple channels and switch between them by clicking
3. **Clear status**: Channel or PM recipient is always shown in the status bar
4. **Image preview**: Images are saved to disk (no preview in chat yet)

---

## Security Information

### What's Encrypted:

✅ All private messages (server cannot read)  
✅ All channel messages (server cannot read)  
✅ All images (server cannot read)  
✅ Image metadata (filename, size)

### What's NOT Encrypted:

❌ Channel passwords (server needs these for access control)  
❌ Usernames/nicknames (server needs these for routing)  
❌ Who is talking to whom (metadata visible to server)  
❌ Message timing and sizes (traffic analysis possible)

### Key Rotation (Perfect Forward Secrecy):

🔐 **Automatic Rotation**: Keys automatically rotate after:
- 1 hour of continuous use (configurable)
- 10,000 messages exchanged (configurable)
- Ensures past messages remain secure even if current keys are compromised

🔐 **Manual Rotation**: Use `/rekey <username>` to immediately rotate encryption keys with a specific user for enhanced security

### Best Practices:

1. **Verify recipients** before sending sensitive data
2. **Use strong passwords** for private channels
3. **Use Tor/VPN** for IP anonymity (see TOR_SETUP.md)
4. **Delete received images** after viewing if sensitive
5. **Don't reuse passwords** from other services
6. **Rotate keys regularly** for sensitive conversations using `/rekey`

---

## Server Hardening

JustIRC includes comprehensive server hardening features for production deployments:

### Input Validation

🛡️ **Comprehensive Validation**: All user inputs are validated and sanitized:
- Nicknames: 3-20 alphanumeric characters (plus _ and -)
- Channel names: Must start with #, 1-50 characters
- Messages: Maximum 4KB, no control characters
- Passwords: 8-256 characters
- Reserved names blocked (server, admin, root, system)

### IP Filtering

🚫 **Blacklist/Whitelist**: Control access at the network level:
- Blacklist: Block specific IPs or network ranges (CIDR notation)
- Whitelist: Only allow specific IPs or networks (optional mode)
- Temporary bans: Automatic expiry after configurable duration
- Persistent storage: Lists survive server restarts

**Configuration** (`server_config.json`):
```json
{
  "enable_ip_whitelist": false
}
```

**Files** (auto-created):
- `server_data/ip_blacklist.json`: Blacklisted IPs/networks
- `server_data/ip_whitelist.json`: Whitelisted IPs/networks

### Connection Limits

⏱️ **Timeouts and Limits**: Prevent resource exhaustion:
- Connection timeout: 300 seconds (5 minutes) default
- Read timeout: 60 seconds (1 minute) per message
- Max message size: 64KB default
- Rate limiting: 30 messages/10s, 5 connections/min per IP

**Configuration** (`server_config.json`):
```json
{
  "connection_timeout": 300,
  "read_timeout": 60,
  "max_message_size": 65536
}
```

### Authentication Security

🔐 **Account Protection**:
- PBKDF2-HMAC-SHA256 password hashing (100,000 iterations)
- Automatic account lockout after 5 failed attempts (15-minute window)
- Session token management for persistent authentication
- Optional account requirement for server access

**Configuration** (`server_config.json`):
```json
{
  "enable_authentication": false,
  "require_authentication": false
}
```

---

## Troubleshooting

### "No encryption key for Username"

- The user just joined, wait for key exchange to complete
- Try disconnecting and reconnecting
- User may have disconnected - check `/users`

### "Failed to decrypt message"

- Key exchange may have failed
- Both users should disconnect and reconnect
- Ensure you're using the same version of JustIRC

### Image transfer stuck

- Check your connection
- Server may have restarted
- Try sending again (generates new image ID)

### PM not working

- Make sure user is online (check `/users` or user list)
- Verify you double-clicked the correct user (GUI)
- Check status bar shows "PM to: Username" (GUI)

---

## Example Workflows

### Secure Team Chat

```bash
# Team leader creates private channel
/join #project-alpha team2026pass

# Team members join
/join #project-alpha team2026pass

# Share files
/image @teammate design.png

# Private side conversation
/msg Alice Can you review this after the meeting?
```

### Anonymous Discussion

```bash
# Use with Tor for full anonymity
torsocks python3 client.py --nickname Anonymous123

# Join public discussion
/join #debate

# Send messages
My opinion on topic X is...
```

### Secure File Exchange

```bash
# Start private conversation
/msg Alice Hi, I'll send you the document

# Send encrypted file
/image Alice document.pdf

# Alice receives
[✓] Image saved: received_document.pdf
```

---

## Keyboard Shortcuts

### GUI Client

- **Enter** - Send message
- **Double-click user** - Start PM
- **Double-click channel** - Switch to channel

### CLI Client

- **Up/Down arrows** - Command history
- **Ctrl+C** - Disconnect and quit
- **Tab** - (Not implemented) Auto-complete usernames

---

For more information:
- [README.md](README.md) - Project overview
- [SECURITY.md](SECURITY.md) - Security architecture
- [QUICKSTART.md](QUICKSTART.md) - Getting started guide
