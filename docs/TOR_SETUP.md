# Using JustIRC with Tor for Enhanced Anonymity

This guide explains how to use JustIRC with Tor to hide your IP address from the server.

## Overview

While JustIRC already protects message content through end-to-end encryption, the server can still see client IP addresses. Using Tor adds an additional layer of anonymity by routing your connection through the Tor network.

## Prerequisites

- JustIRC installed and working
- Tor installed on your system

## Installing Tor

### Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install tor
sudo systemctl start tor
sudo systemctl enable tor
```

### Linux (Fedora/RHEL)

```bash
sudo dnf install tor
sudo systemctl start tor
sudo systemctl enable tor
```

### macOS

```bash
brew install tor
brew services start tor
```

### Windows

1. Download Tor Browser from https://www.torproject.org/
2. Or install Tor Expert Bundle for command-line use

## Configuring Tor

Edit `/etc/tor/torrc` (Linux/Mac) or `torrc` in Tor directory (Windows):

```
# Enable SOCKS5 proxy
SOCKSPort 9050

# For hidden service (optional)
HiddenServiceDir /var/lib/tor/justirc/
HiddenServicePort 6667 127.0.0.1:6667
```

Restart Tor:
```bash
sudo systemctl restart tor
```

## Running Server as Hidden Service (Optional)

If you want to run the server as a Tor hidden service:

1. Configure Tor with HiddenServiceDir and HiddenServicePort (see above)
2. Start Tor
3. Get your .onion address:
   ```bash
   sudo cat /var/lib/tor/justirc/hostname
   ```
4. Start JustIRC server:
   ```bash
   python server.py --host 127.0.0.1 --port 6667
   ```
5. Share your .onion address with clients

## Connecting Client Through Tor

### Method 1: Using Python SOCKS Library

Install additional dependency:
```bash
pip install pysocks
```

Create `client_tor.py`:

```python
import socks
import socket
from client import IRCClient

# Configure SOCKS proxy
socks.set_default_proxy(socks.SOCKS5, "localhost", 9050)
socket.socket = socks.socksocket

# Now use client normally
# ... (rest of client code)
```

Run:
```bash
python client_tor.py --server your-server.onion --port 6667 --nickname YourName
```

### Method 2: Using torsocks

```bash
torsocks python client.py --server your-server.onion --port 6667 --nickname YourName
```

### Method 3: Using proxychains

Configure `/etc/proxychains.conf`:
```
[ProxyList]
socks5 127.0.0.1 9050
```

Run:
```bash
proxychains python client.py --server your-server.onion --port 6667 --nickname YourName
```

## Verifying Tor Connection

To verify your connection is going through Tor:

1. On the server, you should see connections from Tor exit nodes, not your real IP
2. Check your IP: https://check.torproject.org/

## Security Considerations

### Advantages

- **IP Anonymity**: Server cannot see your real IP address
- **Location Privacy**: Your geographic location is hidden
- **ISP Privacy**: Your ISP cannot see you're using JustIRC

### Limitations

- **Slower**: Tor adds latency to connections
- **Exit Node Visibility**: Exit nodes can see traffic (but it's encrypted)
- **Metadata**: Connection timing and patterns may still be visible
- **Trust**: You're trusting Tor relays (use with caution)

### Best Practices

1. **Use Hidden Services**: If possible, run server as .onion hidden service
2. **No Personal Info**: Don't share identifying information over IRC
3. **Unique Nickname**: Use a nickname not associated with other identities
4. **Keep Tor Updated**: Always use the latest version of Tor
5. **Verify .onion Addresses**: Confirm server addresses through trusted channels

## Troubleshooting

### Connection Fails

- Check Tor is running: `systemctl status tor`
- Verify SOCKS proxy port: `netstat -an | grep 9050`
- Try connecting to a known .onion site to test Tor

### Slow Performance

- Tor adds latency - this is normal
- Try different Tor circuits: `sudo systemctl restart tor`
- Consider using Tor bridges if censored

### Hidden Service Not Working

- Check permissions: `ls -la /var/lib/tor/justirc/`
- Check Tor logs: `sudo journalctl -u tor`
- Ensure server is binding to 127.0.0.1, not 0.0.0.0

## Advanced: Bridge Mode

If Tor is blocked in your country, use bridges:

Edit `/etc/tor/torrc`:
```
UseBridges 1
Bridge obfs4 [bridge address]
```

Get bridges from: https://bridges.torproject.org/

## Conclusion

Using JustIRC with Tor provides defense-in-depth:
- End-to-end encryption protects message content
- Tor protects network-level anonymity

For maximum privacy, combine both technologies.
