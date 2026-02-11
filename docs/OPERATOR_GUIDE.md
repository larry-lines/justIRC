# Channel Operator Quick Reference

## Creating a New Channel

When you create a channel for the first time, you need to set a creator password to be able to regain operator status later.

### Simple Creation (Single Password)
```
/join #mychannel mypassword
```
- Uses `mypassword` for both joining and operator access
- You become channel operator (👑)
- Password is encrypted and stored on server

### Advanced Creation (Separate Passwords)
```
/join #mychannel joinpass creatorpass
```
- `joinpass`: Required for anyone to join
- `creatorpass`: Required to regain operator status
- You become channel operator (👑)

## Joining Existing Channels

### Join as Regular Member
```
/join #mychannel joinpass
```
- Joins without operator privileges
- No crown displayed next to your name

### Rejoin as Operator (Regain Status)
```
/join #mychannel joinpass creatorpass
```
- Requires correct creator password
- Regains operator status (👑 appears)
- Works even after server restarts

## Visual Indicators

### Crown Emoji (👑)
- Appears next to operator names in channel user list
- Operators are sorted to top of list
- Visible to all channel members

## Password Requirements

### Creator Password
- Minimum 4 characters
- Required when creating new channels
- Stored as SHA-256 hash on server
- Cannot be recovered if forgotten

### Join Password
- Optional (channels can be open)
- No minimum length
- Also stored as SHA-256 hash

## Examples

### Example 1: Private Team Channel
```
/join #team-secret teampass123 adminpass456
```
- Team members use: `/join #team-secret teampass123`
- Admin regains operator with: `/join #team-secret teampass123 adminpass456`

### Example 2: Open Community Channel
```
/join #community public123
```
- Everyone joins with same password
- First creator can always regain operator
- Good for small communities

### Example 3: Completely Open Channel
```
/join #public
```
❌ **Will fail!** - Creator password required
- Use at least: `/join #public pass`
- Minimum 4 characters for creator password

## Channel Persistence

✓ **Channels survive**:
- Server restarts
- All users leaving
- Operator disconnections

✓ **Passwords preserved**:
- Stored in `server_data/channels.json`
- Encrypted (SHA-256 hashed)
- Never expire

## Operator Privileges

Currently, operators (👑) can:
- Grant operator status to others: `/op username`
- Stay operator after leaving/rejoining (with creator password)

Future operator features (planned):
- Kick users
- Ban users  
- Set channel topic
- Change passwords
- Transfer ownership

## Troubleshooting

### "Creating new channel requires a creator password"
**Problem**: You tried `/join #channel` or used password shorter than 4 characters

**Solution**: Use at least 4 characters: `/join #channel mypass1234`

### "Incorrect creator password"
**Problem**: Wrong password when trying to regain operator

**Solutions**:
- Double-check password spelling
- Remember: passwords are case-sensitive
- If truly forgotten: Cannot be recovered (security feature)

### "Incorrect channel password"
**Problem**: Wrong join password for existing channel

**Solutions**:
- Ask channel creator for correct password
- Passwords are case-sensitive

### No Crown Displayed
**Problem**: Joined channel but no 👑 next to your name

**Causes**:
- Didn't provide creator_password when joining
- Wrong creator_password
- Someone else created the channel
- You're using an old client version

**Solution**: Rejoin with creator password: `/join #channel joinpass creatorpass`

## Security Notes

🔒 **Password Security**:
- All passwords hashed with SHA-256
- Never stored in plaintext
- Server cannot see your password
- End-to-end encryption still applies to messages

⚠️ **Important**:
- No password recovery mechanism
- Write down creator passwords
- Share carefully (grants operator access)
- Consider using password manager

## File Locations

### Server Files
- Channel data: `server_data/channels.json`
- Format: JSON with hashed passwords
- Backup recommended for production

### Client Files
- Config: `justirc_config.json`
- Last server automatically saved
- Theme preferences stored

## Migration from Old Version

If upgrading from version without operator system:

✓ **Automatic**:
- Old channels are NOT immediately persistent
- First user to create new channel after upgrade becomes operator
- Existing channels continue working normally

❌ **Manual Action Needed**:
- Old channels: No retroactive passwords
- Solution: Create new channel with same name after everyone leaves

## Tips & Best Practices

### For Channel Creators
1. **Use strong creator passwords** (12+ characters)
2. **Document your passwords** securely
3. **Share join passwords** with team
4. **Keep creator passwords** private
5. **Test** regaining operator status immediately

### For Channel Members
1. **Save join passwords** for channels you frequent
2. **Don't ask for creator passwords** (operators only)
3. **Respect operator decisions**

### For Server Administrators
1. **Backup** `server_data/channels.json` regularly
2. **Monitor** channel creation for abuse
3. **Document** your channel password policy
4. **Plan** for password recovery requests (none available)

## Command Summary

| Command | Purpose |
|---------|---------|
| `/join #chan pass` | Create channel with single password |
| `/join #chan jp cp` | Create with separate join/creator passwords |
| `/join #chan jp` | Join as member |
| `/join #chan jp cp` | Rejoin as operator |
| `/leave` | Leave current channel |
| `/op user` | Grant operator to user (operators only) |

## Getting Help

- Type `/help` in client for full command list
- Check [CHANGELOG_OPERATOR_SYSTEM.md](CHANGELOG_OPERATOR_SYSTEM.md) for technical details
- Report bugs on GitHub issues

---

Version 1.1.0 | February 2026
