"""
JustIRC Message History - Local encrypted message storage
Provides SQLite-based message history with optional encryption
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class MessageHistory:
    """Manages local message history with optional encryption"""
    
    def __init__(self, db_path: str = "justirc_history.db", password: Optional[str] = None):
        """
        Initialize message history database
        
        Args:
            db_path: Path to SQLite database file
            password: Optional password for encrypting message content
        """
        self.db_path = db_path
        self.password = password
        self.cipher = None
        
        # If password provided, derive encryption key
        if password:
            self._setup_encryption(password)
        
        # Initialize database
        self._init_db()
    
    def _setup_encryption(self, password: str):
        """Setup encryption using password-derived key"""
        # Use a fixed salt (in production, store this securely)
        salt = b'justirc_message_history_salt_v1'
        
        # Derive key from password using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password.encode())
        
        # Create cipher for ChaCha20-Poly1305
        self.cipher = ChaCha20Poly1305(key)
    
    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                channel TEXT,
                sender TEXT NOT NULL,
                sender_id TEXT,
                content TEXT NOT NULL,
                message_type TEXT DEFAULT 'msg',
                is_encrypted INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Channels table for metadata
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                name TEXT PRIMARY KEY,
                last_message_time REAL,
                message_count INTEGER DEFAULT 0,
                is_private INTEGER DEFAULT 0
            )
        ''')
        
        # Create indexes for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_channel 
            ON messages(channel)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp 
            ON messages(timestamp DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_sender 
            ON messages(sender)
        ''')
        
        conn.commit()
        conn.close()
    
    def _encrypt_content(self, content: str) -> Tuple[str, str]:
        """
        Encrypt message content
        
        Returns:
            (encrypted_content_base64, nonce_base64)
        """
        if not self.cipher:
            return content, ""
        
        # Generate random nonce
        nonce = os.urandom(12)
        
        # Encrypt
        encrypted = self.cipher.encrypt(nonce, content.encode('utf-8'), None)
        
        # Return base64 encoded
        return base64.b64encode(encrypted).decode('ascii'), base64.b64encode(nonce).decode('ascii')
    
    def _decrypt_content(self, encrypted_content: str, nonce: str) -> str:
        """
        Decrypt message content
        
        Args:
            encrypted_content: Base64 encoded encrypted content
            nonce: Base64 encoded nonce
            
        Returns:
            Decrypted content
        """
        if not self.cipher or not nonce:
            return encrypted_content
        
        try:
            encrypted_bytes = base64.b64decode(encrypted_content)
            nonce_bytes = base64.b64decode(nonce)
            
            decrypted = self.cipher.decrypt(nonce_bytes, encrypted_bytes, None)
            return decrypted.decode('utf-8')
        except Exception as e:
            return f"[Decryption failed: {e}]"
    
    def add_message(self, sender: str, content: str, channel: Optional[str] = None, 
                    sender_id: Optional[str] = None, message_type: str = "msg") -> int:
        """
        Add a message to history
        
        Args:
            sender: Nickname of sender
            content: Message content
            channel: Channel name (None for PM)
            sender_id: User ID of sender
            message_type: Type of message (msg, action, system)
            
        Returns:
            Message ID
        """
        timestamp = datetime.now().timestamp()
        
        # Encrypt content if password is set
        is_encrypted = 0
        nonce = ""
        if self.cipher:
            content, nonce = self._encrypt_content(content)
            is_encrypted = 1
            # Store nonce with content
            content = f"{nonce}:{content}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert message
        cursor.execute('''
            INSERT INTO messages (timestamp, channel, sender, sender_id, content, message_type, is_encrypted)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, channel, sender, sender_id, content, message_type, is_encrypted))
        
        message_id = cursor.lastrowid
        
        # Update channel metadata
        if channel:
            cursor.execute('''
                INSERT OR REPLACE INTO channels (name, last_message_time, message_count, is_private)
                VALUES (?, ?, 
                    COALESCE((SELECT message_count FROM channels WHERE name = ?), 0) + 1,
                    0)
            ''', (channel, timestamp, channel))
        
        conn.commit()
        conn.close()
        
        return message_id
    
    def get_messages(self, channel: Optional[str] = None, limit: int = 100, 
                     offset: int = 0) -> List[Dict]:
        """
        Get messages from history
        
        Args:
            channel: Channel name (None for all channels/PMs)
            limit: Maximum number of messages to return
            offset: Offset for pagination
            
        Returns:
            List of message dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if channel:
            cursor.execute('''
                SELECT id, timestamp, channel, sender, sender_id, content, message_type, is_encrypted
                FROM messages
                WHERE channel = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (channel, limit, offset))
        else:
            cursor.execute('''
                SELECT id, timestamp, channel, sender, sender_id, content, message_type, is_encrypted
                FROM messages
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
        
        messages = []
        for row in cursor.fetchall():
            msg_id, timestamp, ch, sender, sender_id, content, msg_type, is_encrypted = row
            
            # Decrypt if needed
            if is_encrypted and ':' in content:
                nonce, encrypted_content = content.split(':', 1)
                content = self._decrypt_content(encrypted_content, nonce)
            
            messages.append({
                'id': msg_id,
                'timestamp': timestamp,
                'datetime': datetime.fromtimestamp(timestamp),
                'channel': ch,
                'sender': sender,
                'sender_id': sender_id,
                'content': content,
                'type': msg_type
            })
        
        conn.close()
        return list(reversed(messages))  # Return in chronological order
    
    def search_messages(self, query: str, channel: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """
        Search messages by content
        
        Args:
            query: Search query
            channel: Optional channel to search in
            limit: Maximum number of results
            
        Returns:
            List of matching messages
        """
        # Note: Searching encrypted content won't work well
        # This is a limitation of local encryption
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        search_pattern = f"%{query}%"
        
        if channel:
            cursor.execute('''
                SELECT id, timestamp, channel, sender, sender_id, content, message_type, is_encrypted
                FROM messages
                WHERE channel = ? AND (content LIKE ? OR sender LIKE ?)
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (channel, search_pattern, search_pattern, limit))
        else:
            cursor.execute('''
                SELECT id, timestamp, channel, sender, sender_id, content, message_type, is_encrypted
                FROM messages
                WHERE content LIKE ? OR sender LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (search_pattern, search_pattern, limit))
        
        messages = []
        for row in cursor.fetchall():
            msg_id, timestamp, ch, sender, sender_id, content, msg_type, is_encrypted = row
            
            # Decrypt if needed
            if is_encrypted and ':' in content:
                nonce, encrypted_content = content.split(':', 1)
                content = self._decrypt_content(encrypted_content, nonce)
            
            messages.append({
                'id': msg_id,
                'timestamp': timestamp,
                'datetime': datetime.fromtimestamp(timestamp),
                'channel': ch,
                'sender': sender,
                'sender_id': sender_id,
                'content': content,
                'type': msg_type
            })
        
        conn.close()
        return messages
    
    def get_channels(self) -> List[Dict]:
        """
        Get list of channels with message counts
        
        Returns:
            List of channel dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT name, last_message_time, message_count
            FROM channels
            ORDER BY last_message_time DESC
        ''')
        
        channels = []
        for row in cursor.fetchall():
            name, last_msg_time, msg_count = row
            channels.append({
                'name': name,
                'last_message': datetime.fromtimestamp(last_msg_time) if last_msg_time else None,
                'message_count': msg_count
            })
        
        conn.close()
        return channels
    
    def export_to_json(self, filepath: str, channel: Optional[str] = None):
        """
        Export messages to JSON file
        
        Args:
            filepath: Path to output JSON file
            channel: Optional channel to export (None for all)
        """
        messages = self.get_messages(channel=channel, limit=10000)
        
        export_data = {
            'exported_at': datetime.now().isoformat(),
            'channel': channel,
            'message_count': len(messages),
            'messages': [
                {
                    'timestamp': msg['datetime'].isoformat(),
                    'channel': msg['channel'],
                    'sender': msg['sender'],
                    'content': msg['content'],
                    'type': msg['type']
                }
                for msg in messages
            ]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    def export_to_text(self, filepath: str, channel: Optional[str] = None):
        """
        Export messages to plain text file
        
        Args:
            filepath: Path to output text file
            channel: Optional channel to export (None for all)
        """
        messages = self.get_messages(channel=channel, limit=10000)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"JustIRC Message History Export\n")
            f.write(f"Exported: {datetime.now().isoformat()}\n")
            if channel:
                f.write(f"Channel: {channel}\n")
            f.write(f"{'='*80}\n\n")
            
            for msg in messages:
                timestamp = msg['datetime'].strftime('%Y-%m-%d %H:%M:%S')
                channel_str = f"[{msg['channel']}] " if msg['channel'] else "[PM] "
                f.write(f"{timestamp} {channel_str}<{msg['sender']}> {msg['content']}\n")
    
    def clear_history(self, channel: Optional[str] = None, older_than_days: Optional[int] = None):
        """
        Clear message history
        
        Args:
            channel: Optional channel to clear (None for all)
            older_than_days: Only clear messages older than this many days
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if older_than_days:
            cutoff_timestamp = (datetime.now().timestamp() - (older_than_days * 24 * 3600))
            if channel:
                cursor.execute('DELETE FROM messages WHERE channel = ? AND timestamp < ?', 
                             (channel, cutoff_timestamp))
            else:
                cursor.execute('DELETE FROM messages WHERE timestamp < ?', (cutoff_timestamp,))
        else:
            if channel:
                cursor.execute('DELETE FROM messages WHERE channel = ?', (channel,))
                cursor.execute('DELETE FROM channels WHERE name = ?', (channel,))
            else:
                cursor.execute('DELETE FROM messages')
                cursor.execute('DELETE FROM channels')
        
        conn.commit()
        conn.close()
    
    def get_statistics(self) -> Dict:
        """
        Get message history statistics
        
        Returns:
            Dictionary with statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total messages
        cursor.execute('SELECT COUNT(*) FROM messages')
        total_messages = cursor.fetchone()[0]
        
        # Total channels
        cursor.execute('SELECT COUNT(*) FROM channels')
        total_channels = cursor.fetchone()[0]
        
        # Messages by type
        cursor.execute('SELECT message_type, COUNT(*) FROM messages GROUP BY message_type')
        by_type = dict(cursor.fetchall())
        
        # Oldest and newest messages
        cursor.execute('SELECT MIN(timestamp), MAX(timestamp) FROM messages')
        oldest, newest = cursor.fetchone()
        
        conn.close()
        
        return {
            'total_messages': total_messages,
            'total_channels': total_channels,
            'by_type': by_type,
            'oldest_message': datetime.fromtimestamp(oldest) if oldest else None,
            'newest_message': datetime.fromtimestamp(newest) if newest else None,
            'encrypted': self.cipher is not None
        }
