"""
IRC Command Handler
Handles all slash commands (/join, /msg, /op, etc.)
"""
import asyncio
from typing import Optional, Callable, Dict, Any
from protocol import Protocol, MessageType


class CommandHandler:
    """Handles IRC slash commands"""
    
    def __init__(self, client):
        """
        Initialize command handler with reference to client
        
        Args:
            client: Reference to IRCClient instance
        """
        self.client = client
    
    async def handle_command(self, text: str):
        """
        Handle IRC slash commands
        
        Args:
            text: Command string starting with '/'
        """
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        command_map = {
            '/me': self._cmd_me,
            '/op': self._cmd_op,
            '/mod': self._cmd_mod,
            '/join': self._cmd_join,
            '/leave': self._cmd_leave,
            '/part': self._cmd_leave,
            '/msg': self._cmd_msg,
            '/query': self._cmd_msg,
            '/image': self._cmd_image,
            '/users': self._cmd_users,
            '/whois': self._cmd_whois,
            '/list': self._cmd_list,
            '/kick': self._cmd_kick,
            '/topic': self._cmd_topic,
            '/mode': self._cmd_mode,
            '/unop': self._cmd_unop,
            '/unmod': self._cmd_unmod,
            '/ban': self._cmd_ban,
            '/kickban': self._cmd_kickban,
            '/invite': self._cmd_invite,
            '/unban': self._cmd_unban,
            '/transfer': self._cmd_transfer,
            '/history': self._cmd_history,
            '/search': self._cmd_search,
            '/export': self._cmd_export,
            '/block': self._cmd_block,
            '/unblock': self._cmd_unblock,
            '/blocked': self._cmd_blocked,
            '/register': self._cmd_register,
            '/profile': self._cmd_profile,
            '/quit': self._cmd_quit,
            '/help': self._cmd_help,
        }
        
        handler = command_map.get(cmd)
        if handler:
            await handler(args)
        else:
            self.client.root.after(0, lambda: self.client.log(
                f"Unknown command: {cmd}. Type /help for available commands", "error"
            ))
    
    async def _cmd_me(self, args: str):
        """Handle /me action command"""
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /me <action>", "error"))
            return
        
        action_text = f"* {self.client.nickname} {args}"
        
        if self.client.current_channel:
            # Send to channel
            for user_id, info in self.client.users.items():
                if user_id != self.client.user_id:
                    try:
                        encrypted_data, nonce = self.client.crypto.encrypt(user_id, action_text)
                        msg = Protocol.encrypted_message(
                            self.client.user_id, self.client.current_channel, encrypted_data, nonce, is_channel=True
                        )
                        await self.client.send_to_server(msg)
                    except Exception:
                        pass
            # Echo
            self.client.root.after(0, lambda: self.client.log(
                f"[{self.client.current_channel}] {action_text}", "action"
            ))
        
        elif self.client.current_recipient:
            # Send as PM
            target_id = None
            for uid, info in self.client.users.items():
                if info['nickname'] == self.client.current_recipient:
                    target_id = uid
                    break
            if target_id:
                encrypted_data, nonce = self.client.crypto.encrypt(target_id, action_text)
                msg = Protocol.encrypted_message(
                    self.client.user_id, target_id, encrypted_data, nonce, is_channel=False
                )
                await self.client.send_to_server(msg)
                self.client.root.after(0, lambda: self.client.log(
                    f"[PM to {self.client.current_recipient}] {action_text}", "action"
                ))
    
    async def _cmd_op(self, args: str):
        """Handle /op command"""
        if not self.client.current_channel:
            self.client.root.after(0, lambda: self.client.log("You must be in a channel", "error"))
            return
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /op <user>", "error"))
            return
        
        target_nickname = args.strip()
        # Send OP_USER message directly - server will prompt target user for password
        msg = Protocol.build_message(
            MessageType.OP_USER,
            channel=self.client.current_channel,
            target_nickname=target_nickname
        )
        asyncio.run_coroutine_threadsafe(
            self.client.send_to_server(msg),
            self.client.loop
        )
    
    async def _cmd_mod(self, args: str):
        """Handle /mod command"""
        if not self.client.current_channel:
            self.client.root.after(0, lambda: self.client.log("You must be in a channel", "error"))
            return
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /mod <user>", "error"))
            return
        
        target_nickname = args.strip()
        msg = Protocol.build_message(
            MessageType.MOD_USER,
            channel=self.client.current_channel,
            target_nickname=target_nickname
        )
        asyncio.run_coroutine_threadsafe(
            self.client.send_to_server(msg),
            self.client.loop
        )
    
    async def _cmd_join(self, args: str):
        """Handle /join command"""
        if not args:
            self.client.root.after(0, lambda: self.client.log(
                "Usage: /join #channel [join_password] [creator_password]\n"
                "  - For new channels: creator_password required (4+ chars)\n"
                "  - For existing channels: use creator_password to regain operator status",
                "error"
            ))
            return
        parts = args.split(maxsplit=2)
        channel = parts[0]
        if not channel.startswith('#'):
            channel = '#' + channel
        join_password = parts[1] if len(parts) > 1 else None
        creator_password = parts[2] if len(parts) > 2 else join_password
        await self.client._join_channel(channel, join_password, creator_password)
    
    async def _cmd_leave(self, args: str):
        """Handle /leave or /part command"""
        channel = args.strip() if args else self.client.current_channel
        if channel:
            await self.client._leave_channel(channel)
        else:
            self.client.root.after(0, lambda: self.client.log("Usage: /leave [channel]", "error"))
    
    async def _cmd_msg(self, args: str):
        """Handle /msg or /query command"""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            self.client.root.after(0, lambda: self.client.log("Usage: /msg <user> <message>", "error"))
            return
        await self.client._send_private_message(parts[0], parts[1])
    
    async def _cmd_image(self, args: str):
        """Handle /image command"""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            self.client.root.after(0, lambda: self.client.log("Usage: /image <user> <filepath>", "error"))
            return
        await self.client._send_image(parts[0], parts[1])
    
    async def _cmd_users(self, args: str):
        """Handle /users command"""
        if self.client.users:
            user_list = "Online users:\n" + "\n".join(
                f"  • {info['nickname']}" for uid, info in self.client.users.items()
            )
            self.client.root.after(0, lambda: self.client.log(user_list, "info"))
        else:
            self.client.root.after(0, lambda: self.client.log("No users online", "info"))
    
    async def _cmd_whois(self, args: str):
        """Handle /whois command"""
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /whois <nickname>", "error"))
            return
        nickname = args.strip()
        msg = Protocol.whois(nickname)
        await self.client.send_to_server(msg)
    
    async def _cmd_list(self, args: str):
        """Handle /list command"""
        msg = Protocol.list_channels()
        await self.client.send_to_server(msg)
    
    async def _cmd_kick(self, args: str):
        """Handle /kick command"""
        if not self.client.current_channel:
            self.client.root.after(0, lambda: self.client.log("You must be in a channel to use /kick", "error"))
            return
        parts = args.split(maxsplit=1)
        if not parts:
            self.client.root.after(0, lambda: self.client.log("Usage: /kick <user> [reason]", "error"))
            return
        target_nickname = parts[0]
        reason = parts[1] if len(parts) > 1 else "No reason given"
        msg = Protocol.kick_user(self.client.current_channel, target_nickname, reason)
        await self.client.send_to_server(msg)
    
    async def _cmd_topic(self, args: str):
        """Handle /topic command"""
        if not self.client.current_channel:
            self.client.root.after(0, lambda: self.client.log("You must be in a channel to use /topic", "error"))
            return
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /topic <new topic>", "error"))
            return
        topic = args.strip()
        msg = Protocol.set_topic(self.client.current_channel, topic)
        await self.client.send_to_server(msg)
    
    async def _cmd_mode(self, args: str):
        """Handle /mode command"""
        if not self.client.current_channel:
            self.client.root.after(0, lambda: self.client.log("You must be in a channel", "error"))
            return
        if not args:
            self.client.root.after(0, lambda: self.client.log(
                "Usage: /mode +m|-m (modes: m=moderated, s=secret, i=invite-only, n=no external, p=private)",
                "error"
            ))
            return
        
        mode_str = args.strip()
        if not mode_str.startswith(('+', '-')) or len(mode_str) < 2:
            self.client.root.after(0, lambda: self.client.log("Format: /mode +m or /mode -s", "error"))
            return
        
        enable = mode_str[0] == '+'
        mode = mode_str[1]
        
        msg = Protocol.set_mode(self.client.current_channel, mode, enable)
        await self.client.send_to_server(msg)
    
    async def _cmd_unop(self, args: str):
        """Handle /unop command"""
        if not self.client.current_channel:
            self.client.root.after(0, lambda: self.client.log("You must be in a channel", "error"))
            return
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /unop <user>", "error"))
            return
        target_nickname = args.strip()
        msg = Protocol.build_message(
            MessageType.UNOP_USER,
            channel=self.client.current_channel,
            target_nickname=target_nickname
        )
        await self.client.send_to_server(msg)
    
    async def _cmd_unmod(self, args: str):
        """Handle /unmod command"""
        if not self.client.current_channel:
            self.client.root.after(0, lambda: self.client.log("You must be in a channel", "error"))
            return
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /unmod <user>", "error"))
            return
        target_nickname = args.strip()
        msg = Protocol.build_message(
            MessageType.UNMOD_USER,
            channel=self.client.current_channel,
            target_nickname=target_nickname
        )
        await self.client.send_to_server(msg)
    
    async def _cmd_ban(self, args: str):
        """Handle /ban command"""
        if not self.client.current_channel:
            self.client.root.after(0, lambda: self.client.log("You must be in a channel", "error"))
            return
        parts = args.split(maxsplit=2)
        if not parts:
            self.client.root.after(0, lambda: self.client.log("Usage: /ban <user> [duration] [reason]", "error"))
            return
        
        target_nickname = parts[0]
        duration = None
        reason = "No reason given"
        
        # Parse optional duration and reason
        if len(parts) > 1:
            duration = self.client._parse_duration(parts[1])
            if duration is not None:
                if len(parts) > 2:
                    reason = parts[2]
            else:
                reason = ' '.join(parts[1:])
        
        msg = Protocol.build_message(
            MessageType.BAN_USER,
            channel=self.client.current_channel,
            target_nickname=target_nickname,
            reason=reason,
            duration=duration
        )
        await self.client.send_to_server(msg)
    
    async def _cmd_kickban(self, args: str):
        """Handle /kickban command"""
        if not self.client.current_channel:
            self.client.root.after(0, lambda: self.client.log("You must be in a channel", "error"))
            return
        parts = args.split(maxsplit=1)
        if not parts:
            self.client.root.after(0, lambda: self.client.log("Usage: /kickban <user> [reason]", "error"))
            return
        target_nickname = parts[0]
        reason = parts[1] if len(parts) > 1 else "No reason given"
        msg = Protocol.build_message(
            MessageType.KICKBAN_USER,
            channel=self.client.current_channel,
            target_nickname=target_nickname,
            reason=reason
        )
        await self.client.send_to_server(msg)
    
    async def _cmd_invite(self, args: str):
        """Handle /invite command"""
        if not self.client.current_channel:
            self.client.root.after(0, lambda: self.client.log("You must be in a channel", "error"))
            return
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /invite <user>", "error"))
            return
        target_nickname = args.strip()
        msg = Protocol.invite_user(self.client.current_channel, target_nickname)
        await self.client.send_to_server(msg)
    
    async def _cmd_unban(self, args: str):
        """Handle /unban command"""
        if not self.client.current_channel:
            self.client.root.after(0, lambda: self.client.log("You must be in a channel", "error"))
            return
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /unban <user>", "error"))
            return
        target_nickname = args.strip()
        msg = Protocol.build_message(
            MessageType.UNBAN_USER,
            channel=self.client.current_channel,
            target_nickname=target_nickname
        )
        await self.client.send_to_server(msg)
    
    async def _cmd_transfer(self, args: str):
        """Handle /transfer command"""
        if not self.client.current_channel:
            self.client.root.after(0, lambda: self.client.log("You must be in a channel", "error"))
            return
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /transfer <operator_nickname>", "error"))
            return
        target_nickname = args.strip()
        msg = Protocol.build_message(
            MessageType.TRANSFER_OWNERSHIP,
            channel=self.client.current_channel,
            target_nickname=target_nickname
        )
        await self.client.send_to_server(msg)
    
    async def _cmd_history(self, args: str):
        """Handle /history command"""
        if not self.client.history:
            self.client.root.after(0, lambda: self.client.log(
                "Message history is not enabled. Enable it in settings.", "error"
            ))
            return
        
        limit = 50
        if args:
            try:
                limit = int(args.strip())
            except ValueError:
                self.client.root.after(0, lambda: self.client.log("Usage: /history [limit]", "error"))
                return
        
        messages = self.client.history.get_messages(channel=self.client.current_channel, limit=limit)
        if messages:
            self.client.root.after(0, lambda: self.client.log(f"=== Last {len(messages)} messages ===", "info"))
            for msg in messages:
                timestamp = msg['datetime'].strftime('%H:%M:%S')
                ch = f"[{msg['channel']}] " if msg['channel'] else "[PM] "
                self.client.root.after(0, lambda t=timestamp, c=ch, s=msg['sender'], m=msg['content']: 
                    self.client.log(f"{t} {c}<{s}> {m}", "info"))
        else:
            self.client.root.after(0, lambda: self.client.log("No message history found", "info"))
    
    async def _cmd_search(self, args: str):
        """Handle /search command"""
        if not self.client.history:
            self.client.root.after(0, lambda: self.client.log(
                "Message history is not enabled. Enable it in settings.", "error"
            ))
            return
        
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /search <query>", "error"))
            return
        
        query = args.strip()
        messages = self.client.history.search_messages(query, channel=self.client.current_channel, limit=30)
        if messages:
            self.client.root.after(0, lambda: self.client.log(
                f"=== Found {len(messages)} messages matching '{query}' ===", "info"
            ))
            for msg in messages:
                timestamp = msg['datetime'].strftime('%Y-%m-%d %H:%M')
                ch = f"[{msg['channel']}] " if msg['channel'] else "[PM] "
                self.client.root.after(0, lambda t=timestamp, c=ch, s=msg['sender'], m=msg['content']: 
                    self.client.log(f"{t} {c}<{s}> {m}", "info"))
        else:
            self.client.root.after(0, lambda: self.client.log(f"No messages found matching '{query}'", "info"))
    
    async def _cmd_export(self, args: str):
        """Handle /export command"""
        from tkinter import filedialog
        
        if not self.client.history:
            self.client.root.after(0, lambda: self.client.log(
                "Message history is not enabled. Enable it in settings.", "error"
            ))
            return
        
        def do_export():
            filepath = filedialog.asksaveasfilename(
                title="Export Message History",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*")]
            )
            if filepath:
                try:
                    if filepath.endswith('.json'):
                        self.client.history.export_to_json(filepath, channel=self.client.current_channel)
                    else:
                        self.client.history.export_to_text(filepath, channel=self.client.current_channel)
                    self.client.log(f"History exported to {filepath}", "success")
                except Exception as e:
                    self.client.log(f"Export failed: {e}", "error")
        
        self.client.root.after(0, do_export)
    
    async def _cmd_block(self, args: str):
        """Handle /block command"""
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /block <nickname>", "error"))
            return
        
        nickname = args.strip()
        user_id = None
        for uid, info in self.client.users.items():
            if info.get('nickname', '').lower() == nickname.lower():
                user_id = uid
                break
        
        if user_id:
            self.client.block_user(user_id)
        else:
            self.client.root.after(0, lambda n=nickname: self.client.log(f"User not found: {n}", "error"))
    
    async def _cmd_unblock(self, args: str):
        """Handle /unblock command"""
        if not args:
            self.client.root.after(0, lambda: self.client.log("Usage: /unblock <nickname>", "error"))
            return
        
        nickname = args.strip()
        user_id = None
        for uid, info in self.client.users.items():
            if info.get('nickname', '').lower() == nickname.lower():
                user_id = uid
                break
        
        if user_id:
            self.client.unblock_user(user_id)
        else:
            self.client.root.after(0, lambda n=nickname: self.client.log(f"User not found: {n}", "error"))
    
    async def _cmd_blocked(self, args: str):
        """Handle /blocked command"""
        if self.client.blocked_users:
            blocked_names = []
            for uid in self.client.blocked_users:
                nickname = self.client.users.get(uid, {}).get('nickname', uid)
                blocked_names.append(nickname)
            self.client.root.after(0, lambda: self.client.log(
                f"Blocked users: {', '.join(blocked_names)}", "info"
            ))
        else:
            self.client.root.after(0, lambda: self.client.log("No blocked users", "info"))
    
    async def _cmd_register(self, args: str):
        """Handle /register command to register nickname"""
        if not args:
            self.client.root.after(0, lambda: self.client.log(
                "Usage: /register <password> - Register your current nickname", "error"
            ))
            return
        
        password = args.strip()
        
        if len(password) < 6:
            self.client.root.after(0, lambda: self.client.log(
                "Password must be at least 6 characters", "error"
            ))
            return
        
        # Send registration request to server
        msg = Protocol.register_nickname(self.client.nickname, password)
        await self.client.send_to_server(msg)
        
        self.client.root.after(0, lambda: self.client.log(
            f"Registering nickname '{self.client.nickname}'...", "info"
        ))
    
    async def _cmd_profile(self, args: str):
        """Handle /profile command to view or update profile"""
        if not args:
            # Show own profile or usage
            msg = Protocol.get_profile(self.client.nickname)
            await self.client.send_to_server(msg)
            return
        
        parts = args.split(maxsplit=1)
        subcmd = parts[0].lower()
        
        if subcmd == 'view':
            # View another user's profile
            if len(parts) < 2:
                self.client.root.after(0, lambda: self.client.log(
                    "Usage: /profile view <nickname>", "error"
                ))
                return
            
            target_nickname = parts[1].strip()
            msg = Protocol.get_profile(target_nickname)
            await self.client.send_to_server(msg)
        
        elif subcmd == 'bio':
            # Update bio
            if len(parts) < 2:
                self.client.root.after(0, lambda: self.client.log(
                    "Usage: /profile bio <text>", "error"
                ))
                return
            
            bio = parts[1].strip()
            msg = Protocol.update_profile(bio=bio)
            await self.client.send_to_server(msg)
            self.client.root.after(0, lambda: self.client.log(
                "Updating profile bio...", "info"
            ))
        
        elif subcmd == 'status':
            # Update status message
            if len(parts) < 2:
                self.client.root.after(0, lambda: self.client.log(
                    "Usage: /profile status <message>", "error"
                ))
                return
            
            status_msg = parts[1].strip()
            msg = Protocol.update_profile(status_message=status_msg)
            await self.client.send_to_server(msg)
            self.client.root.after(0, lambda: self.client.log(
                "Updating status message...", "info"
            ))
        
        else:
            self.client.root.after(0, lambda: self.client.log(
                "Usage: /profile [view <nickname> | bio <text> | status <message>]", "error"
            ))
    
    async def _cmd_quit(self, args: str):
        """Handle /quit command"""
        self.client.running = False
        self.client.disconnect()
    
    async def _cmd_help(self, args: str):
        """Handle /help command"""
        self.client.root.after(0, self.client.show_help)
