"""
Message Queue System for JustIRC
Handles offline message queuing, batching, and delivery
"""

import json
import time
import os
import logging
from typing import Dict, List, Optional, Any
from collections import deque, defaultdict
from dataclasses import dataclass, asdict


logger = logging.getLogger('MessageQueue')


@dataclass
class QueuedMessage:
    """Represents a queued message"""
    message_id: str
    recipient_id: str
    sender_id: str
    sender_nickname: str
    message_type: str
    encrypted_content: str
    timestamp: float
    ttl: int = 604800  # 7 days default
    metadata: Optional[dict] = None
    
    def is_expired(self) -> bool:
        """Check if message has expired based on TTL"""
        return time.time() > (self.timestamp + self.ttl)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'QueuedMessage':
        """Create from dictionary"""
        return cls(**data)


class MessageQueue:
    """
    High-performance message queue for offline users
    
    Features:
    - Persistent storage to disk
    - Message expiration (TTL)
    - Size limits per user
    - Efficient batch retrieval
    - Priority queuing support
    """
    
    def __init__(
        self,
        storage_dir: str = './server_data/message_queue',
        max_messages_per_user: int = 1000,
        default_ttl: int = 604800,  # 7 days
        cleanup_interval: int = 3600  # 1 hour
    ):
        """
        Initialize message queue
        
        Args:
            storage_dir: Directory for persistent storage
            max_messages_per_user: Maximum messages to queue per user
            default_ttl: Default time-to-live in seconds
            cleanup_interval: How often to run cleanup (seconds)
        """
        self.storage_dir = storage_dir
        self.max_messages_per_user = max_messages_per_user
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        
        # In-memory queue: user_id -> deque of messages
        self.queues: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_messages_per_user))
        
        # Statistics
        self.stats = {
            'total_queued': 0,
            'total_delivered': 0,
            'total_expired': 0,
            'total_dropped': 0  # Dropped due to size limit
        }
        
        # Last cleanup time
        self.last_cleanup = time.time()
        
        # Ensure storage directory exists
        os.makedirs(storage_dir, exist_ok=True)
        
        # Load persisted messages
        self.load_from_disk()
        
        logger.info(f"MessageQueue initialized with {len(self.queues)} user queues")
    
    def enqueue(
        self,
        recipient_id: str,
        sender_id: str,
        sender_nickname: str,
        message_type: str,
        encrypted_content: str,
        ttl: Optional[int] = None,
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Add a message to the queue for an offline user
        
        Args:
            recipient_id: User ID of recipient
            sender_id: User ID of sender
            sender_nickname: Nickname of sender
            message_type: Type of message (PRIVATE_MESSAGE, CHANNEL_MESSAGE, etc.)
            encrypted_content: The encrypted message payload (JSON string)
            ttl: Time-to-live in seconds (None = use default)
            metadata: Optional metadata dictionary
        
        Returns:
            True if message was queued, False if queue is full
        """
        if ttl is None:
            ttl = self.default_ttl
        
        # Generate unique message ID
        message_id = f"{recipient_id}_{int(time.time() * 1000000)}"
        
        message = QueuedMessage(
            message_id=message_id,
            recipient_id=recipient_id,
            sender_id=sender_id,
            sender_nickname=sender_nickname,
            message_type=message_type,
            encrypted_content=encrypted_content,
            timestamp=time.time(),
            ttl=ttl,
            metadata=metadata
        )
        
        # Check if queue is at capacity
        queue = self.queues[recipient_id]
        if len(queue) >= self.max_messages_per_user:
            # Queue is full, oldest message will be dropped (deque maxlen handles this)
            self.stats['total_dropped'] += 1
            logger.warning(f"Message queue full for {recipient_id}, dropping oldest message")
        
        # Add to queue
        queue.append(message)
        self.stats['total_queued'] += 1
        
        logger.debug(f"Queued message from {sender_nickname} to {recipient_id} (queue size: {len(queue)})")
        
        # Periodic cleanup
        self._maybe_cleanup()
        
        return True
    
    def dequeue_all(self, recipient_id: str) -> List[QueuedMessage]:
        """
        Retrieve all queued messages for a user
        
        Args:
            recipient_id: User ID to retrieve messages for
        
        Returns:
            List of queued messages (oldest first)
        """
        if recipient_id not in self.queues:
            return []
        
        queue = self.queues[recipient_id]
        messages = []
        
        # Get all non-expired messages
        while queue:
            message = queue.popleft()
            
            if message.is_expired():
                self.stats['total_expired'] += 1
                logger.debug(f"Expired message {message.message_id} for {recipient_id}")
                continue
            
            messages.append(message)
            self.stats['total_delivered'] += 1
        
        # Clean up empty queue
        if recipient_id in self.queues and len(self.queues[recipient_id]) == 0:
            del self.queues[recipient_id]
        
        logger.info(f"Delivered {len(messages)} queued messages to {recipient_id}")
        return messages
    
    def peek(self, recipient_id: str, limit: int = 10) -> List[QueuedMessage]:
        """
        Peek at queued messages without removing them
        
        Args:
            recipient_id: User ID to peek at
            limit: Maximum number of messages to return
        
        Returns:
            List of messages (up to limit)
        """
        if recipient_id not in self.queues:
            return []
        
        queue = self.queues[recipient_id]
        messages = []
        
        for message in list(queue)[:limit]:
            if not message.is_expired():
                messages.append(message)
        
        return messages
    
    def get_queue_size(self, recipient_id: str) -> int:
        """Get number of messages waiting for a user"""
        if recipient_id not in self.queues:
            return 0
        return len(self.queues[recipient_id])
    
    def has_messages(self, recipient_id: str) -> bool:
        """Check if user has any queued messages"""
        return self.get_queue_size(recipient_id) > 0
    
    def clear_queue(self, recipient_id: str) -> int:
        """
        Clear all messages for a user
        
        Returns:
            Number of messages cleared
        """
        if recipient_id not in self.queues:
            return 0
        
        count = len(self.queues[recipient_id])
        del self.queues[recipient_id]
        logger.info(f"Cleared {count} messages for {recipient_id}")
        return count
    
    def cleanup_expired(self) -> int:
        """
        Remove expired messages from all queues
        
        Returns:
            Number of messages removed
        """
        removed = 0
        empty_queues = []
        
        for recipient_id, queue in self.queues.items():
            original_size = len(queue)
            
            # Filter out expired messages
            non_expired = deque(
                (msg for msg in queue if not msg.is_expired()),
                maxlen=self.max_messages_per_user
            )
            
            expired_count = original_size - len(non_expired)
            if expired_count > 0:
                self.queues[recipient_id] = non_expired
                removed += expired_count
                self.stats['total_expired'] += expired_count
                logger.debug(f"Removed {expired_count} expired messages for {recipient_id}")
            
            # Track empty queues for cleanup
            if len(non_expired) == 0:
                empty_queues.append(recipient_id)
        
        # Remove empty queues
        for recipient_id in empty_queues:
            del self.queues[recipient_id]
        
        if removed > 0:
            logger.info(f"Cleanup: removed {removed} expired messages, {len(empty_queues)} empty queues")
        
        self.last_cleanup = time.time()
        return removed
    
    def _maybe_cleanup(self):
        """Run cleanup if enough time has passed"""
        if time.time() - self.last_cleanup > self.cleanup_interval:
            self.cleanup_expired()
    
    def get_stats(self) -> dict:
        """
        Get queue statistics
        
        Returns:
            Dictionary with queue stats
        """
        total_messages = sum(len(q) for q in self.queues.values())
        
        return {
            **self.stats,
            'active_queues': len(self.queues),
            'total_messages_waiting': total_messages,
            'avg_queue_size': total_messages / len(self.queues) if self.queues else 0
        }
    
    def save_to_disk(self):
        """Persist queues to disk"""
        try:
            # Save each user's queue to a separate file for efficiency
            for recipient_id, queue in self.queues.items():
                if len(queue) == 0:
                    continue
                
                filepath = os.path.join(self.storage_dir, f"{recipient_id}.json")
                messages = [msg.to_dict() for msg in queue]
                
                with open(filepath, 'w') as f:
                    json.dump(messages, f)
            
            # Save statistics
            stats_file = os.path.join(self.storage_dir, '_stats.json')
            with open(stats_file, 'w') as f:
                json.dump(self.stats, f)
            
            logger.debug(f"Saved {len(self.queues)} user queues to disk")
        
        except Exception as e:
            logger.error(f"Error saving message queue to disk: {e}")
    
    def load_from_disk(self):
        """Load persisted queues from disk"""
        try:
            if not os.path.exists(self.storage_dir):
                return
            
            loaded_queues = 0
            loaded_messages = 0
            
            # Load each user's queue
            for filename in os.listdir(self.storage_dir):
                if not filename.endswith('.json') or filename == '_stats.json':
                    continue
                
                filepath = os.path.join(self.storage_dir, filename)
                recipient_id = filename[:-5]  # Remove .json
                
                with open(filepath, 'r') as f:
                    messages_data = json.load(f)
                
                # Reconstruct messages
                messages = [QueuedMessage.from_dict(data) for data in messages_data]
                
                # Filter out expired messages on load
                non_expired = [msg for msg in messages if not msg.is_expired()]
                
                if non_expired:
                    self.queues[recipient_id] = deque(
                        non_expired,
                        maxlen=self.max_messages_per_user
                    )
                    loaded_queues += 1
                    loaded_messages += len(non_expired)
                
                # Clean up file if all messages expired
                if not non_expired:
                    os.remove(filepath)
            
            # Load statistics
            stats_file = os.path.join(self.storage_dir, '_stats.json')
            if os.path.exists(stats_file):
                with open(stats_file, 'r') as f:
                    self.stats = json.load(f)
            
            if loaded_queues > 0:
                logger.info(f"Loaded {loaded_messages} messages from {loaded_queues} user queues")
        
        except Exception as e:
            logger.error(f"Error loading message queue from disk: {e}")
    
    def shutdown(self):
        """Clean shutdown - save everything to disk"""
        logger.info("Shutting down message queue, saving to disk...")
        self.cleanup_expired()
        self.save_to_disk()
        logger.info("Message queue shutdown complete")


class MessageBatcher:
    """
    Batches messages for efficient network transmission
    Reduces overhead by combining multiple small messages
    """
    
    def __init__(self, batch_size: int = 10, batch_timeout: float = 0.1):
        """
        Initialize message batcher
        
        Args:
            batch_size: Max messages per batch
            batch_timeout: Max time to wait before sending partial batch (seconds)
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        
        # Pending batches: user_id -> (messages[], timestamp)
        self.pending: Dict[str, tuple[List[Any], float]] = {}
    
    def add_message(self, recipient_id: str, message: Any) -> Optional[List[Any]]:
        """
        Add a message to the batch
        
        Returns:
            Complete batch if ready to send, None if still accumulating
        """
        current_time = time.time()
        
        if recipient_id not in self.pending:
            self.pending[recipient_id] = ([], current_time)
        
        batch, start_time = self.pending[recipient_id]
        batch.append(message)
        
        # Check if batch is ready to send
        if len(batch) >= self.batch_size or (current_time - start_time) >= self.batch_timeout:
            # Return and clear batch
            ready_batch = batch.copy()
            del self.pending[recipient_id]
            return ready_batch
        
        # Update pending batch
        self.pending[recipient_id] = (batch, start_time)
        return None
    
    def flush_all(self) -> Dict[str, List[Any]]:
        """
        Flush all pending batches
        
        Returns:
            Dictionary mapping recipient_id to their message batch
        """
        result = {}
        for recipient_id, (batch, _) in self.pending.items():
            if batch:
                result[recipient_id] = batch
        
        self.pending.clear()
        return result
    
    def flush_user(self, recipient_id: str) -> Optional[List[Any]]:
        """Flush pending messages for a specific user"""
        if recipient_id not in self.pending:
            return None
        
        batch, _ = self.pending[recipient_id]
        del self.pending[recipient_id]
        return batch if batch else None
