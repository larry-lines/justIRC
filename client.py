"""
JustIRC Client - Secure CLI IRC Client
All messages are end-to-end encrypted
"""

import asyncio
import argparse
import logging
import json
import sys
import os
import base64
import uuid
from typing import Optional
from protocol import Protocol, MessageType
from crypto_layer import CryptoLayer, ChannelCrypto
from image_transfer import ImageTransfer


# Try to import colorama for colored output
try:
    from colorama import init, Fore, Style
    init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger('JustIRC-Client')


class IRCClient:
    """IRC Client with E2E encryption"""
    
    def __init__(self, server_host: str, server_port: int, nickname: str):
        self.server_host = server_host
        self.server_port = server_port
        self.nickname = nickname
        self.user_id: Optional[str] = None
        
        # Cryptography
        self.crypto = CryptoLayer()
        
        # Image transfers
        self.image_transfer = ImageTransfer(self.crypto)
        
        # Network
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        
        # State
        self.users = {}  # user_id -> {nickname, public_key}
        self.current_channel: Optional[str] = None
        self.joined_channels = set()
        self.pending_images = {}  # image_id -> {sender, metadata, accepted, queued_chunks}
        
        self.running = False
    
    async def connect(self):
        """Connect to the server"""
        try:
            # Try to connect with 10 second timeout
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.server_host, self.server_port),
                timeout=10.0
            )
            self.running = True
            
            self.print_info(f"Connected to {self.server_host}:{self.server_port}")
            
            # Register with server
            await self.register()
            
            return True
        except asyncio.TimeoutError:
            self.print_error(f"Connection timeout: Server unavailable after 10 seconds")
            return False
        except Exception as e:
            self.print_error(f"Connection failed: {e}")
            return False
    
    async def register(self):
        """Register with the server"""
        # Send registration with public key
        public_key = self.crypto.get_public_key_b64()
        msg = Protocol.register(self.nickname, public_key)
        await self.send(msg)
        
        self.print_info(f"Registering as {self.nickname}...")
    
    async def send(self, message: str):
        """Send a message to the server"""
        self.writer.write(message.encode('utf-8') + b'\n')
        await self.writer.drain()
    
    async def receive_loop(self):
        """Receive messages from server"""
        try:
            while self.running:
                data = await self.reader.readline()
                if not data:
                    break
                
                message_str = data.decode('utf-8').strip()
                if not message_str:
                    continue
                
                try:
                    message = json.loads(message_str)
                    await self.handle_message(message)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON: {message_str}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.print_error(f"Connection lost: {e}")
        finally:
            self.running = False
    
    async def handle_message(self, message: dict):
        """Handle incoming message"""
        msg_type = message.get('type')
        
        if msg_type == MessageType.ACK.value:
            await self.handle_ack(message)
        
        elif msg_type == MessageType.USER_LIST.value:
            await self.handle_user_list(message)
        
        elif msg_type == MessageType.PUBLIC_KEY_RESPONSE.value:
            await self.handle_public_key_response(message)
        
        elif msg_type == MessageType.REKEY_REQUEST.value:
            await self.handle_rekey_request(message)
        
        elif msg_type == MessageType.REKEY_RESPONSE.value:
            await self.handle_rekey_response(message)
        
        elif msg_type == MessageType.PRIVATE_MESSAGE.value:
            await self.handle_private_message(message)
        
        elif msg_type == MessageType.CHANNEL_MESSAGE.value:
            await self.handle_channel_message(message)
        
        elif msg_type == MessageType.JOIN_CHANNEL.value:
            await self.handle_user_joined(message)
        
        elif msg_type == MessageType.LEAVE_CHANNEL.value:
            await self.handle_user_left(message)
        
        elif msg_type == MessageType.IMAGE_START.value:
            await self.handle_image_start(message)
        
        elif msg_type == MessageType.IMAGE_CHUNK.value:
            await self.handle_image_chunk(message)
        
        elif msg_type == MessageType.IMAGE_END.value:
            await self.handle_image_end(message)
        
        elif msg_type == MessageType.KICK_USER.value:
            # User was kicked from a channel
            channel = message.get('channel')
            kicked_by = message.get('kicked_by')
            reason = message.get('reason', 'No reason given')
            
            if channel in self.joined_channels:
                self.joined_channels.remove(channel)
                if channel == self.current_channel:
                    self.current_channel = None
                self.print_error(f"You were kicked from {channel} by {kicked_by}: {reason}")
        
        elif msg_type == MessageType.SET_TOPIC.value:
            # Channel topic was changed
            channel = message.get('channel')
            topic = message.get('topic', '')
            set_by = message.get('set_by')
            
            if channel == self.current_channel:
                self.print_info(f"[{channel}] Topic set by {set_by}: {topic}")
        
        elif msg_type == MessageType.ERROR.value:
            self.print_error(f"Server error: {message.get('error')}")
    
    async def handle_ack(self, message: dict):
        """Handle acknowledgment"""
        if 'user_id' in message:
            self.user_id = message['user_id']
            self.print_success(message.get('message', 'Connected'))
        
        elif 'channel' in message:
            channel = message['channel']
            self.joined_channels.add(channel)
            self.current_channel = channel
            
            # Load member keys
            members = message.get('members', [])
            for member in members:
                if member['user_id'] != self.user_id:
                    self.users[member['user_id']] = {
                        'nickname': member['nickname'],
                        'public_key': member['public_key']
                    }
                    self.crypto.load_peer_public_key(
                        member['user_id'],
                        member['public_key']
                    )
            
            self.print_success(f"Joined channel {channel} ({len(members)} members)")
    
    async def handle_user_list(self, message: dict):
        """Handle user list update"""
        users = message.get('users', [])
        for user in users:
            self.users[user['user_id']] = {
                'nickname': user['nickname'],
                'public_key': user['public_key']
            }
            # Preload public key
            self.crypto.load_peer_public_key(user['user_id'], user['public_key'])
        
        if users:
            if len(users) == 1:
                # Single user update (someone just joined)
                user = users[0]
                self.print_info(f"{user['nickname']} is now online")
            else:
                # Initial user list
                self.print_info(f"{len(users)} users online")
    
    async def handle_public_key_response(self, message: dict):
        """Handle public key response"""
        user_id = message['user_id']
        nickname = message['nickname']
        public_key = message['public_key']
        
        self.users[user_id] = {'nickname': nickname, 'public_key': public_key}
        self.crypto.load_peer_public_key(user_id, public_key)
    
    async def handle_rekey_request(self, message: dict):
        """Handle incoming key rotation request"""
        from_id = message.get('from_id')
        from_nickname = message.get('from_nickname')
        new_public_key = message.get('new_public_key')
        
        if not from_id or not new_public_key:
            self.print_error("Invalid rekey request received")
            return
        
        # Load the new key
        self.crypto.load_peer_public_key(from_id, new_public_key)
        
        # Rotate our own key for this peer
        self.crypto.rotate_key_for_peer(from_id)
        
        # Send our new public key back
        response = Protocol.rekey_response(
            self.user_id,
            from_id,
            self.crypto.get_public_key_b64()
        )
        await self.send(response)
        
        self.print_info(f"🔐 Encryption keys rotated with {from_nickname}")
    
    async def handle_rekey_response(self, message: dict):
        """Handle key rotation response"""
        from_id = message.get('from_id')
        from_nickname = message.get('from_nickname')
        new_public_key = message.get('new_public_key')
        
        if not from_id or not new_public_key:
            self.print_error("Invalid rekey response received")
            return
        
        # Load the new key
        self.crypto.load_peer_public_key(from_id, new_public_key)
        
        self.print_success(f"🔐 Encryption keys successfully rotated with {from_nickname}")
    
    async def initiate_key_rotation(self, target_nickname: str):
        """Initiate key rotation with a user"""
        # Find the target user
        target_id = None
        for user_id, info in self.users.items():
            if info['nickname'] == target_nickname:
                target_id = user_id
                break
        
        if not target_id:
            self.print_error(f"User {target_nickname} not found")
            return
        
        # Rotate our key for this peer
        self.crypto.rotate_key_for_peer(target_id)
        
        # Send rekey request with our new public key
        request = Protocol.rekey_request(
            self.user_id,
            target_id,
            self.crypto.get_public_key_b64()
        )
        await self.send(request)
        
        self.print_info(f"🔐 Requesting key rotation with {target_nickname}...")
    
    async def handle_private_message(self, message: dict):
        """Handle encrypted private message"""
        from_id = message['from_id']
        encrypted_data = message['encrypted_data']
        nonce = message['nonce']
        
        try:
            # Decrypt message
            plaintext = self.crypto.decrypt(from_id, encrypted_data, nonce)
            sender = self.users.get(from_id, {}).get('nickname', from_id)
            
            self.print_message(sender, plaintext, private=True)
        
        except Exception as e:
            self.print_error(f"Failed to decrypt message from {from_id}: {e}")
    
    async def handle_channel_message(self, message: dict):
        """Handle encrypted channel message"""
        from_id = message.get('from_id')
        channel = message.get('to_id') or message.get('channel')
        sender = message.get('sender')
        
        # Handle server announcements (no encryption)
        if sender == "SERVER":
            text = message.get('text', '')
            print(f"{Fore.YELLOW}[{channel}] SERVER: {text}{Style.RESET_ALL}")
            return
        
        if not from_id:
            return
        
        encrypted_data = message.get('encrypted_data')
        nonce = message.get('nonce')
        
        try:
            # Decrypt message
            plaintext = self.crypto.decrypt(from_id, encrypted_data, nonce)
            sender_nick = self.users.get(from_id, {}).get('nickname', from_id)
            
            self.print_message(sender_nick, plaintext, channel=channel)
        
        except Exception as e:
            logger.error(f"Failed to decrypt channel message: {e}")
    
    async def handle_user_joined(self, message: dict):
        """Handle user joined notification"""
        user_id = message['user_id']
        nickname = message['nickname']
        channel = message['channel']
        public_key = message.get('public_key')
        
        if user_id != self.user_id:
            self.users[user_id] = {'nickname': nickname, 'public_key': public_key}
            if public_key:
                self.crypto.load_peer_public_key(user_id, public_key)
            
            self.print_info(f"{nickname} joined {channel}")
    
    async def handle_user_left(self, message: dict):
        """Handle user left notification"""
        nickname = message['nickname']
        channel = message['channel']
        self.print_info(f"{nickname} left {channel}")
    
    async def handle_image_start(self, message: dict):
        """Handle start of image transfer - prompt user for acceptance"""
        from_id = message['from_id']
        image_id = message['image_id']
        total_chunks = message['total_chunks']
        encrypted_metadata = message['encrypted_metadata']
        nonce = message['nonce']
        
        try:
            # Decrypt metadata
            metadata_json = self.crypto.decrypt(from_id, encrypted_metadata, nonce)
            metadata = json.loads(metadata_json)
            
            sender = self.users.get(from_id, {}).get('nickname', from_id)
            filename = metadata['filename']
            size_bytes = metadata['size']
            size_mb = size_bytes / (1024 * 1024)
            
            # Store as pending
            self.pending_images[image_id] = {
                'from_id': from_id,
                'sender': sender,
                'metadata': metadata,
                'total_chunks': total_chunks,
                'chunks': [None] * total_chunks,
                'received': 0,
                'accepted': None,
                'queued_chunks': {}
            }
            
            # Prompt user
            print(f"\n{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{sender}{Style.RESET_ALL} wants to send you an image:")
            print(f"  Filename: {Fore.WHITE}{filename}{Style.RESET_ALL}")
            print(f"  Size: {Fore.WHITE}{size_mb:.2f} MB{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")
            
            # Get user input in executor to not block async loop
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input(f"Accept? (yes/no): ").strip().lower()
            )
            
            if response in ['yes', 'y']:
                # Ask where to save
                save_path = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input(f"Save as [{filename}]: ").strip()
                )
                if not save_path:
                    save_path = filename
                
                self.accept_image_transfer(image_id, save_path)
                self.image_transfer.start_receiving(image_id, total_chunks, metadata)
                self.print_success(f"Accepting image from {sender}")
            else:
                self.decline_image_transfer(image_id)
                self.print_info(f"Declined image from {sender}")
        
        except Exception as e:
            self.print_error(f"Failed to start image transfer: {e}")
    
    async def handle_image_chunk(self, message: dict):
        """Handle image chunk - only process if accepted"""
        from_id = message['from_id']
        image_id = message['image_id']
        chunk_number = message['chunk_number']
        encrypted_data = message['encrypted_data']
        nonce = message['nonce']
        
        # Check if this is a pending transfer
        if image_id not in self.pending_images:
            return  # Unknown transfer, ignore
        
        pending = self.pending_images[image_id]
        
        # If user hasn't decided yet, queue the chunk
        if pending['accepted'] is None:
            pending['queued_chunks'][chunk_number] = (encrypted_data, nonce)
            return
        
        # If declined, ignore
        if not pending['accepted']:
            return
        
        # Accepted - decrypt and add chunk
        try:
            chunk_data = self.crypto.decrypt_image(
                from_id,
                base64.b64decode(encrypted_data),
                nonce
            )
            
            complete = self.image_transfer.add_chunk(image_id, chunk_number, chunk_data)
            
            if complete:
                # Image transfer complete - will be finalized on IMAGE_END
                pass
        
        except Exception as e:
            logger.error(f"Failed to decrypt image chunk: {e}")
    
    async def handle_image_end(self, message: dict):
        """Handle end of image transfer - only save if accepted"""
        image_id = message['image_id']
        from_id = message['from_id']
        
        # Check if this transfer exists and was accepted
        if image_id not in self.pending_images:
            return
        
        pending = self.pending_images[image_id]
        
        # Only save if accepted
        if not pending.get('accepted', False):
            # Clean up
            del self.pending_images[image_id]
            return
        
        image_data, metadata = self.image_transfer.get_complete_image(image_id)
        
        if image_data:
            # Save image with user-specified path
            save_path = pending.get('save_path', f"received_{metadata['filename']}")
            try:
                with open(save_path, 'wb') as f:
                    f.write(image_data)
                
                sender = self.users.get(from_id, {}).get('nickname', from_id)
                self.print_success(f"Image saved: {save_path} (from {sender})")
            except Exception as e:
                self.print_error(f"Failed to save image: {e}")
        
        # Clean up
        del self.pending_images[image_id]
    
    def accept_image_transfer(self, image_id: str, save_path: str):
        """Accept an image transfer and process queued chunks"""
        if image_id not in self.pending_images:
            return
        
        pending = self.pending_images[image_id]
        pending['accepted'] = True
        pending['save_path'] = save_path
        
        # Process any queued chunks that arrived while user was deciding
        if pending['queued_chunks']:
            for chunk_num, (encrypted_data, nonce) in pending['queued_chunks'].items():
                try:
                    chunk_data = self.crypto.decrypt_image(
                        pending['from_id'],
                        base64.b64decode(encrypted_data),
                        nonce
                    )
                    self.image_transfer.add_chunk(image_id, chunk_num, chunk_data)
                except Exception as e:
                    logger.error(f"Failed to decrypt queued chunk: {e}")
            
            pending['queued_chunks'].clear()
    
    def decline_image_transfer(self, image_id: str):
        """Decline an image transfer"""
        if image_id not in self.pending_images:
            return
        
        pending = self.pending_images[image_id]
        pending['accepted'] = False
        pending['queued_chunks'].clear()
    
    async def send_private_message(self, target_nickname: str, text: str):
        """Send encrypted private message"""
        # Find user ID
        target_id = None
        for uid, info in self.users.items():
            if info['nickname'] == target_nickname:
                target_id = uid
                break
        
        if not target_id:
            self.print_error(f"User {target_nickname} not found")
            return
        
        # Ensure we have their public key
        if not self.crypto.has_peer_key(target_id):
            self.print_error(f"No encryption key for {target_nickname}")
            return
        
        # Encrypt message
        encrypted_data, nonce = self.crypto.encrypt(target_id, text)
        
        # Send
        msg = Protocol.encrypted_message(
            self.user_id, target_id, encrypted_data, nonce, is_channel=False
        )
        await self.send(msg)
    
    async def send_channel_message(self, channel: str, text: str):
        """Send encrypted message to channel"""
        if channel not in self.joined_channels:
            self.print_error(f"Not in channel {channel}")
            return
        
        # Send encrypted message to each member
        # (In a real implementation, we'd use a shared channel key)
        for user_id, info in self.users.items():
            if user_id != self.user_id:
                try:
                    encrypted_data, nonce = self.crypto.encrypt(user_id, text)
                    msg = Protocol.encrypted_message(
                        self.user_id, channel, encrypted_data, nonce, is_channel=True
                    )
                    await self.send(msg)
                except Exception as e:
                    logger.error(f"Failed to send to {info['nickname']}: {e}")
    
    async def send_image(self, target_nickname: str, image_path: str):
        """Send encrypted image to user"""
        # Find user ID
        target_id = None
        for uid, info in self.users.items():
            if info['nickname'] == target_nickname:
                target_id = uid
                break
        
        if not target_id:
            self.print_error(f"User {target_nickname} not found")
            return
        
        if not os.path.exists(image_path):
            self.print_error(f"File not found: {image_path}")
            return
        
        try:
            # Prepare image
            chunks, filename, total_size = self.image_transfer.prepare_image(image_path)
            image_id = str(uuid.uuid4())
            
            # Encrypt metadata
            metadata = {'filename': filename, 'size': total_size}
            encrypted_metadata, nonce = self.crypto.encrypt(target_id, json.dumps(metadata))
            
            # Send start message
            msg = Protocol.image_start(
                self.user_id, target_id, image_id,
                len(chunks), encrypted_metadata, nonce
            )
            await self.send(msg)
            
            self.print_info(f"Sending image: {filename} ({len(chunks)} chunks)")
            
            # Send chunks
            for i, chunk in enumerate(chunks):
                encrypted_chunk, chunk_nonce = self.crypto.encrypt_image(target_id, chunk)
                msg = Protocol.image_chunk(
                    self.user_id, target_id, image_id, i,
                    base64.b64encode(encrypted_chunk).decode('utf-8'),
                    chunk_nonce
                )
                await self.send(msg)
            
            # Send end message
            msg = Protocol.image_end(self.user_id, target_id, image_id)
            await self.send(msg)
            
            self.print_success(f"Image sent: {filename}")
        
        except Exception as e:
            self.print_error(f"Failed to send image: {e}")
    
    async def join_channel(self, channel: str, password: str = None):
        """Join a channel"""
        msg = Protocol.join_channel(self.user_id, channel, password)
        await self.send(msg)
    
    async def leave_channel(self, channel: str):
        """Leave a channel"""
        msg = Protocol.leave_channel(self.user_id, channel)
        await self.send(msg)
        
        self.joined_channels.discard(channel)
        if self.current_channel == channel:
            self.current_channel = None
    
    def print_info(self, text: str):
        """Print info message"""
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {text}")
    
    def print_success(self, text: str):
        """Print success message"""
        print(f"{Fore.GREEN}[✓]{Style.RESET_ALL} {text}")
    
    def print_error(self, text: str):
        """Print error message"""
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {text}")
    
    def print_message(self, sender: str, text: str, private=False, channel=None):
        """Print chat message"""
        if private:
            print(f"{Fore.MAGENTA}[PM from {sender}]{Style.RESET_ALL} {text}")
        elif channel:
            print(f"{Fore.YELLOW}[{channel}] {sender}:{Style.RESET_ALL} {text}")
        else:
            print(f"{Fore.WHITE}{sender}:{Style.RESET_ALL} {text}")
    
    def accept_image_transfer(self, image_id: str, save_path: str):
        """Accept an image transfer and process queued chunks"""
        if image_id not in self.pending_images:
            return
        
        pending = self.pending_images[image_id]
        pending['accepted'] = True
        pending['save_path'] = save_path
        
        # Process any queued chunks that arrived while user was deciding
        if pending['queued_chunks']:
            for chunk_num, (encrypted_data, nonce) in pending['queued_chunks'].items():
                try:
                    chunk_data = self.crypto.decrypt_image(
                        pending['from_id'],
                        base64.b64decode(encrypted_data),
                        nonce
                    )
                    self.image_transfer.add_chunk(image_id, chunk_num, chunk_data)
                except Exception as e:
                    logger.error(f"Failed to decrypt queued chunk: {e}")
            
            pending['queued_chunks'].clear()
    
    def decline_image_transfer(self, image_id: str):
        """Decline an image transfer"""
        if image_id not in self.pending_images:
            return
        
        pending = self.pending_images[image_id]
        pending['accepted'] = False
        pending['queued_chunks'].clear()
    
    def print_help(self):
        """Print help"""
        help_text = """
Commands:
  /join <channel> [password]    Join a channel (with optional password)
  /leave [channel]              Leave current or specified channel
  /msg <user> <message>         Send private message
  /image <user> <file>          Send image to user
  /rekey <user>                 Rotate encryption keys with user (Perfect Forward Secrecy)
  /op <user>                    Grant operator status (no password needed, operators only)
  /kick <user> [reason]         Kick user from channel (operators only)
  /topic <new topic>            Set channel topic (operators only)
  /users                        List online users
  /channels                     List your channels
  /help                         Show this help
  /quit                         Quit
  
Channel: Send messages directly when in a channel
Private: Use /msg <user> <message>
Password-protected: Use /join #private mypassword
Operators: Channel creators are automatically operators
        """
        print(help_text)
    
    async def input_loop(self):
        """Handle user input"""
        self.print_help()
        
        while self.running:
            try:
                # Show prompt
                if self.current_channel:
                    prompt = f"{Fore.GREEN}[{self.current_channel}]{Style.RESET_ALL} > "
                else:
                    prompt = f"{Fore.BLUE}>{Style.RESET_ALL} "
                
                line = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input(prompt)
                )
                
                line = line.strip()
                if not line:
                    continue
                
                # Handle commands
                if line.startswith('/'):
                    await self.handle_command(line)
                else:
                    # Send to current channel
                    if self.current_channel:
                        await self.send_channel_message(self.current_channel, line)
                    else:
                        self.print_error("Not in a channel. Use /join <channel> or /msg <user> <text>")
            
            except EOFError:
                break
            except Exception as e:
                logger.error(f"Input error: {e}")
    
    async def handle_command(self, command: str):
        """Handle user command"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == '/quit':
            self.running = False
        
        elif cmd == '/help':
            self.print_help()
        
        elif cmd == '/join':
            if args:
                parts = args.split(maxsplit=1)
                channel = parts[0]
                password = parts[1] if len(parts) > 1 else None
                await self.join_channel(channel, password)
            else:
                self.print_error("Usage: /join <channel> [password]")
        
        elif cmd == '/leave':
            channel = args if args else self.current_channel
            if channel:
                await self.leave_channel(channel)
            else:
                self.print_error("Usage: /leave [channel]")
        
        elif cmd == '/msg':
            parts = args.split(maxsplit=1)
            if len(parts) == 2:
                await self.send_private_message(parts[0], parts[1])
            else:
                self.print_error("Usage: /msg <user> <message>")
        
        elif cmd == '/image':
            parts = args.split(maxsplit=1)
            if len(parts) == 2:
                await self.send_image(parts[0], parts[1])
            else:
                self.print_error("Usage: /image <user> <file>")
        
        elif cmd == '/rekey':
            if not args:
                self.print_error("Usage: /rekey <user>")
            else:
                target_nickname = args.strip()
                await self.initiate_key_rotation(target_nickname)
        
        elif cmd == '/op':
            if not self.current_channel:
                self.print_error("You must be in a channel to use /op")
            elif not args:
                self.print_error("Usage: /op <user>")
            else:
                target_nickname = args.strip()
                # Verified operators can grant op status without additional verification
                msg = Protocol.op_user(self.current_channel, target_nickname, "")
                await self.send(msg)
                self.print_info(f"Requesting operator status for {target_nickname}...")
        
        elif cmd == '/kick':
            if not self.current_channel:
                self.print_error("You must be in a channel to use /kick")
            elif not args:
                self.print_error("Usage: /kick <user> [reason]")
            else:
                parts = args.split(maxsplit=1)
                target_nickname = parts[0]
                reason = parts[1] if len(parts) > 1 else "No reason given"
                msg = Protocol.kick_user(self.current_channel, target_nickname, reason)
                await self.send(msg)
                self.print_info(f"Kicking {target_nickname} from {self.current_channel}...")
        
        elif cmd == '/topic':
            if not self.current_channel:
                self.print_error("You must be in a channel to use /topic")
            elif not args:
                self.print_error("Usage: /topic <new topic>")
            else:
                topic = args.strip()
                msg = Protocol.set_topic(self.current_channel, topic)
                await self.send(msg)
                self.print_info(f"Setting topic for {self.current_channel}...")
        
        elif cmd == '/users':
            if self.users:
                print(f"{Fore.CYAN}Online users:{Style.RESET_ALL}")
                for user_id, info in self.users.items():
                    print(f"  - {info['nickname']}")
            else:
                print("No other users online")
        
        elif cmd == '/channels':
            if self.joined_channels:
                print(f"{Fore.CYAN}Your channels:{Style.RESET_ALL}")
                for channel in self.joined_channels:
                    marker = "*" if channel == self.current_channel else " "
                    print(f" {marker} {channel}")
            else:
                print("Not in any channels")
        
        else:
            self.print_error(f"Unknown command: {cmd}")
    
    async def run(self):
        """Run the client"""
        if not await self.connect():
            return
        
        # Run receive and input loops concurrently
        try:
            await asyncio.gather(
                self.receive_loop(),
                self.input_loop()
            )
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='JustIRC Secure Client')
    parser.add_argument('--server', default='localhost', help='Server address')
    parser.add_argument('--port', type=int, default=6667, help='Server port')
    parser.add_argument('--nickname', required=True, help='Your nickname')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    client = IRCClient(args.server, args.port, args.nickname)
    
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == '__main__':
    main()
