"""
Test Suite for Performance & Scalability Features

Tests:
- MessageQueue: queuing, delivery, expiration, persistence
- MessageBatcher: batching, timeouts
- PerformanceMonitor: connection tracking, throughput, channel stats
- ConnectionManager: limits, idle detection, cleanup
- RoutingOptimizer: caching, hit rates
"""

import unittest
import time
import os
import tempfile
import shutil
import json
from unittest.mock import Mock, MagicMock, AsyncMock
import asyncio

# Add parent directory to path for imports
import sys
import os.path
# Get the directory containing this file
test_dir = os.path.dirname(os.path.abspath(__file__))
# Add parent directory (project root) to path
sys.path.insert(0, os.path.dirname(test_dir))

from message_queue import MessageQueue, QueuedMessage, MessageBatcher
from performance_monitor import (
    PerformanceMonitor,
    ConnectionManager,
    ConnectionMetrics,
    RoutingOptimizer
)


class TestQueuedMessage(unittest.TestCase):
    """Test QueuedMessage dataclass"""
    
    def test_create_message(self):
        """Test creating a queued message"""
        msg = QueuedMessage(
            message_id="test_123",
            recipient_id="user_1",
            sender_id="user_2",
            sender_nickname="Alice",
            message_type="PRIVATE_MESSAGE",
            encrypted_content="encrypted_data_here",
            timestamp=time.time(),
            ttl=3600
        )
        
        self.assertEqual(msg.message_id, "test_123")
        self.assertEqual(msg.sender_nickname, "Alice")
        self.assertEqual(msg.ttl, 3600)
    
    def test_is_expired(self):
        """Test message expiration"""
        # Non-expired message
        msg1 = QueuedMessage(
            message_id="test_1",
            recipient_id="user_1",
            sender_id="user_2",
            sender_nickname="Alice",
            message_type="PRIVATE_MESSAGE",
            encrypted_content="data",
            timestamp=time.time(),
            ttl=3600
        )
        self.assertFalse(msg1.is_expired())
        
        # Expired message
        msg2 = QueuedMessage(
            message_id="test_2",
            recipient_id="user_1",
            sender_id="user_2",
            sender_nickname="Bob",
            message_type="PRIVATE_MESSAGE",
            encrypted_content="data",
            timestamp=time.time() - 7200,  # 2 hours ago
            ttl=3600  # 1 hour TTL
        )
        self.assertTrue(msg2.is_expired())
    
    def test_to_dict(self):
        """Test converting message to dictionary"""
        msg = QueuedMessage(
            message_id="test_123",
            recipient_id="user_1",
            sender_id="user_2",
            sender_nickname="Alice",
            message_type="PRIVATE_MESSAGE",
            encrypted_content="data",
            timestamp=123456.789,
            ttl=3600
        )
        
        d = msg.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d['message_id'], "test_123")
        self.assertEqual(d['sender_nickname'], "Alice")
        self.assertEqual(d['timestamp'], 123456.789)
    
    def test_from_dict(self):
        """Test creating message from dictionary"""
        data = {
            'message_id': "test_123",
            'recipient_id': "user_1",
            'sender_id': "user_2",
            'sender_nickname': "Alice",
            'message_type': "PRIVATE_MESSAGE",
            'encrypted_content': "data",
            'timestamp': 123456.789,
            'ttl': 3600,
            'metadata': None
        }
        
        msg = QueuedMessage.from_dict(data)
        self.assertEqual(msg.message_id, "test_123")
        self.assertEqual(msg.ttl, 3600)


class TestMessageQueue(unittest.TestCase):
    """Test MessageQueue system"""
    
    def setUp(self):
        """Create temporary directory for tests"""
        self.temp_dir = tempfile.mkdtemp()
        self.queue = MessageQueue(
            storage_dir=self.temp_dir,
            max_messages_per_user=10,
            default_ttl=3600,
            cleanup_interval=3600
        )
    
    def tearDown(self):
        """Clean up temporary directory"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_enqueue_message(self):
        """Test enqueueing a message"""
        result = self.queue.enqueue(
            recipient_id="user_1",
            sender_id="user_2",
            sender_nickname="Alice",
            message_type="PRIVATE_MESSAGE",
            encrypted_content="encrypted_data"
        )
        
        self.assertTrue(result)
        self.assertEqual(self.queue.get_queue_size("user_1"), 1)
        self.assertTrue(self.queue.has_messages("user_1"))
    
    def test_enqueue_multiple_messages(self):
        """Test enqueueing multiple messages"""
        for i in range(5):
            self.queue.enqueue(
                recipient_id="user_1",
                sender_id="user_2",
                sender_nickname=f"User{i}",
                message_type="PRIVATE_MESSAGE",
                encrypted_content=f"message_{i}"
            )
        
        self.assertEqual(self.queue.get_queue_size("user_1"), 5)
    
    def test_dequeue_all(self):
        """Test dequeueing all messages"""
        # Enqueue messages
        for i in range(3):
            self.queue.enqueue(
                recipient_id="user_1",
                sender_id="user_2",
                sender_nickname="Alice",
                message_type="PRIVATE_MESSAGE",
                encrypted_content=f"message_{i}"
            )
        
        # Dequeue all
        messages = self.queue.dequeue_all("user_1")
        
        self.assertEqual(len(messages), 3)
        self.assertEqual(self.queue.get_queue_size("user_1"), 0)
        self.assertFalse(self.queue.has_messages("user_1"))
    
    def test_peek_messages(self):
        """Test peeking at messages without removing"""
        # Enqueue messages
        for i in range(5):
            self.queue.enqueue(
                recipient_id="user_1",
                sender_id="user_2",
                sender_nickname="Alice",
                message_type="PRIVATE_MESSAGE",
                encrypted_content=f"message_{i}"
            )
        
        # Peek at first 3
        messages = self.queue.peek("user_1", limit=3)
        
        self.assertEqual(len(messages), 3)
        self.assertEqual(self.queue.get_queue_size("user_1"), 5)  # Still has 5
    
    def test_queue_size_limit(self):
        """Test queue size limit enforcement"""
        # Try to enqueue more than max (10)
        for i in range(15):
            self.queue.enqueue(
                recipient_id="user_1",
                sender_id="user_2",
                sender_nickname="Alice",
                message_type="PRIVATE_MESSAGE",
                encrypted_content=f"message_{i}"
            )
        
        # Should only keep the last 10
        self.assertEqual(self.queue.get_queue_size("user_1"), 10)
        self.assertEqual(self.queue.stats['total_dropped'], 5)
    
    def test_clear_queue(self):
        """Test clearing a user's queue"""
        # Enqueue messages
        for i in range(3):
            self.queue.enqueue(
                recipient_id="user_1",
                sender_id="user_2",
                sender_nickname="Alice",
                message_type="PRIVATE_MESSAGE",
                encrypted_content=f"message_{i}"
            )
        
        # Clear queue
        cleared = self.queue.clear_queue("user_1")
        
        self.assertEqual(cleared, 3)
        self.assertEqual(self.queue.get_queue_size("user_1"), 0)
    
    def test_expired_message_cleanup(self):
        """Test cleanup of expired messages"""
        # Enqueue expired message
        self.queue.enqueue(
            recipient_id="user_1",
            sender_id="user_2",
            sender_nickname="Alice",
            message_type="PRIVATE_MESSAGE",
            encrypted_content="old_message",
            ttl=1  # 1 second TTL
        )
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Cleanup
        removed = self.queue.cleanup_expired()
        
        self.assertEqual(removed, 1)
        self.assertEqual(self.queue.get_queue_size("user_1"), 0)
    
    def test_get_stats(self):
        """Test getting queue statistics"""
        # Enqueue some messages
        for i in range(5):
            self.queue.enqueue(
                recipient_id=f"user_{i % 2}",
                sender_id="user_sender",
                sender_nickname="Alice",
                message_type="PRIVATE_MESSAGE",
                encrypted_content="message"
            )
        
        stats = self.queue.get_stats()
        
        self.assertEqual(stats['active_queues'], 2)
        self.assertEqual(stats['total_messages_waiting'], 5)
        self.assertEqual(stats['total_queued'], 5)
    
    def test_save_and_load(self):
        """Test persistence to disk"""
        # Enqueue messages
        for i in range(3):
            self.queue.enqueue(
                recipient_id="user_1",
                sender_id="user_2",
                sender_nickname="Alice",
                message_type="PRIVATE_MESSAGE",
                encrypted_content=f"message_{i}"
            )
        
        # Save to disk
        self.queue.save_to_disk()
        
        # Create new queue and load
        queue2 = MessageQueue(storage_dir=self.temp_dir)
        
        self.assertEqual(queue2.get_queue_size("user_1"), 3)


class TestMessageBatcher(unittest.TestCase):
    """Test MessageBatcher"""
    
    def test_batch_accumulation(self):
        """Test accumulating messages in batch"""
        batcher = MessageBatcher(batch_size=3, batch_timeout=1.0)
        
        # Add messages
        result1 = batcher.add_message("user_1", "msg1")
        result2 = batcher.add_message("user_1", "msg2")
        
        self.assertIsNone(result1)
        self.assertIsNone(result2)
        
        # Third message should complete batch
        result3 = batcher.add_message("user_1", "msg3")
        
        self.assertIsNotNone(result3)
        self.assertEqual(len(result3), 3)
    
    def test_batch_timeout(self):
        """Test batch timeout"""
        batcher = MessageBatcher(batch_size=10, batch_timeout=0.1)
        
        # Add one message
        batcher.add_message("user_1", "msg1")
        
        # Wait for timeout
        time.sleep(0.2)
        
        # Next message should trigger batch due to timeout
        result = batcher.add_message("user_1", "msg2")
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
    
    def test_flush_user(self):
        """Test flushing messages for specific user"""
        batcher = MessageBatcher(batch_size=10, batch_timeout=1.0)
        
        batcher.add_message("user_1", "msg1")
        batcher.add_message("user_1", "msg2")
        batcher.add_message("user_2", "msg3")
        
        # Flush user_1
        result = batcher.flush_user("user_1")
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        
        # user_2 should still have pending message
        result2 = batcher.flush_user("user_2")
        self.assertEqual(len(result2), 1)
    
    def test_flush_all(self):
        """Test flushing all pending batches"""
        batcher = MessageBatcher(batch_size=10, batch_timeout=1.0)
        
        batcher.add_message("user_1", "msg1")
        batcher.add_message("user_2", "msg2")
        batcher.add_message("user_3", "msg3")
        
        result = batcher.flush_all()
        
        self.assertEqual(len(result), 3)
        self.assertIn("user_1", result)
        self.assertIn("user_2", result)
        self.assertIn("user_3", result)


class TestPerformanceMonitor(unittest.TestCase):
    """Test PerformanceMonitor"""
    
    def setUp(self):
        """Create monitor instance"""
        self.monitor = PerformanceMonitor(history_size=60)
    
    def test_register_connection(self):
        """Test registering connections"""
        self.monitor.register_connection("user_1")
        self.monitor.register_connection("user_2")
        
        stats = self.monitor.get_connection_stats()
        self.assertEqual(stats['active_connections'], 2)
        self.assertEqual(stats['peak_connections'], 2)
    
    def test_unregister_connection(self):
        """Test unregistering connections"""
        self.monitor.register_connection("user_1")
        self.monitor.register_connection("user_2")
        self.monitor.unregister_connection("user_1")
        
        stats = self.monitor.get_connection_stats()
        self.assertEqual(stats['active_connections'], 1)
        self.assertEqual(stats['peak_connections'], 2)  # Peak stays
    
    def test_record_message(self):
        """Test recording messages"""
        self.monitor.register_connection("user_1")
        
        self.monitor.record_message("user_1", 100, direction='sent')
        self.monitor.record_message("user_1", 50, direction='received')
        
        metrics = self.monitor.connections["user_1"]
        self.assertEqual(metrics.messages_sent, 1)
        self.assertEqual(metrics.messages_received, 1)
        self.assertEqual(metrics.bytes_sent, 100)
        self.assertEqual(metrics.bytes_received, 50)
    
    def test_message_rate_calculation(self):
        """Test message rate calculation"""
        self.monitor.register_connection("user_1")
        
        # Record messages
        for i in range(10):
            self.monitor.record_message("user_1", 50, direction='sent')
        
        rate = self.monitor.get_message_rate(window=60)
        self.assertGreater(rate, 0)
    
    def test_channel_stats(self):
        """Test channel activity tracking"""
        self.monitor.record_channel_message("#general", 5)
        self.monitor.record_channel_message("#general", 6)
        self.monitor.record_channel_message("#random", 3)
        
        stats = self.monitor.get_channel_stats()
        self.assertEqual(stats['total_channels'], 2)
        self.assertEqual(stats['most_active_channel'], "#general")
        self.assertEqual(stats['most_active_count'], 2)
    
    def test_idle_connections(self):
        """Test idle connection detection"""
        self.monitor.register_connection("user_1")
        self.monitor.register_connection("user_2")
        
        # Wait a bit for both to become idle
        time.sleep(0.3)
        
        # Mark user_1 as having recent activity
        self.monitor.record_message("user_1", 100, direction='sent')
        
        # Get idle connections (threshold = 0.2 seconds)
        # user_2 should be idle (0.3 seconds), user_1 should not (just now)
        idle = self.monitor.get_idle_connections(threshold=0.2)
        
        self.assertIn("user_2", idle)  # user_2 had no activity for 0.3s
        self.assertNotIn("user_1", idle)  # user_1 just had activity
    
    def test_throughput_stats(self):
        """Test throughput statistics"""
        self.monitor.register_connection("user_1")
        
        for i in range(100):
            self.monitor.record_message("user_1", 50, direction='sent')
        
        stats = self.monitor.get_throughput_stats()
        self.assertEqual(stats['total_messages'], 100)
        self.assertEqual(stats['total_bytes_sent'], 5000)
        self.assertGreater(stats['current_rate'], 0)


class TestConnectionManager(unittest.TestCase):
    """Test ConnectionManager"""
    
    def test_connection_limit(self):
        """Test connection limit enforcement"""
        manager = ConnectionManager(max_connections=3)
        
        self.assertTrue(manager.register_connection("user_1"))
        self.assertTrue(manager.register_connection("user_2"))
        self.assertTrue(manager.register_connection("user_3"))
        self.assertFalse(manager.register_connection("user_4"))  # Limit reached
    
    def test_can_accept_connection(self):
        """Test checking if connections can be accepted"""
        manager = ConnectionManager(max_connections=2)
        
        self.assertTrue(manager.can_accept_connection())
        
        manager.register_connection("user_1")
        self.assertTrue(manager.can_accept_connection())
        
        manager.register_connection("user_2")
        self.assertFalse(manager.can_accept_connection())  # At limit
    
    def test_update_activity(self):
        """Test updating last activity time"""
        manager = ConnectionManager()
        manager.register_connection("user_1")
        
        time1 = manager.last_activity["user_1"]
        time.sleep(0.1)
        manager.update_activity("user_1")
        time2 = manager.last_activity["user_1"]
        
        self.assertGreater(time2, time1)
    
    def test_get_idle_connections(self):
        """Test getting idle connections"""
        manager = ConnectionManager(idle_timeout=1)
        
        manager.register_connection("user_1")
        manager.register_connection("user_2")
        
        # Update activity for user_1
        time.sleep(0.5)
        manager.update_activity("user_1")
        
        # Wait more
        time.sleep(0.6)
        
        # user_2 should be idle (1.1 seconds), user_1 should not (0.6 seconds)
        idle = manager.get_idle_connections()
        
        self.assertIn("user_2", idle)
    
    def test_get_stats(self):
        """Test getting connection manager statistics"""
        manager = ConnectionManager(max_connections=10)
        
        manager.register_connection("user_1")
        manager.register_connection("user_2")
        manager.register_connection("user_3")
        
        stats = manager.get_stats()
        
        self.assertEqual(stats['active_connections'], 3)
        self.assertEqual(stats['max_connections'], 10)
        self.assertEqual(stats['utilization'], 30.0)
        self.assertEqual(stats['total_accepted'], 3)


class TestRoutingOptimizer(unittest.TestCase):
    """Test RoutingOptimizer"""
    
    def test_cache_channel_members(self):
        """Test caching channel members"""
        optimizer = RoutingOptimizer(cache_size=10)
        
        members = {"user_1", "user_2", "user_3"}
        optimizer.cache_channel_members("#general", members)
        
        cached = optimizer.get_cached_channel_members("#general")
        self.assertEqual(cached, members)
    
    def test_cache_hit(self):
        """Test cache hit tracking"""
        optimizer = RoutingOptimizer()
        
        members = {"user_1", "user_2"}
        optimizer.cache_channel_members("#general", members)
        
        # Should be a hit
        result = optimizer.get_cached_channel_members("#general")
        self.assertIsNotNone(result)
        
        stats = optimizer.get_cache_stats()
        self.assertEqual(stats['cache_hits'], 1)
        self.assertEqual(stats['cache_misses'], 0)
    
    def test_cache_miss(self):
        """Test cache miss tracking"""
        optimizer = RoutingOptimizer()
        
        # Should be a miss
        result = optimizer.get_cached_channel_members("#nonexistent")
        self.assertIsNone(result)
        
        stats = optimizer.get_cache_stats()
        self.assertEqual(stats['cache_hits'], 0)
        self.assertEqual(stats['cache_misses'], 1)
    
    def test_invalidate_cache(self):
        """Test cache invalidation"""
        optimizer = RoutingOptimizer()
        
        members = {"user_1", "user_2"}
        optimizer.cache_channel_members("#general", members)
        
        # Invalidate
        optimizer.invalidate_channel_cache("#general")
        
        # Should now be a miss
        result = optimizer.get_cached_channel_members("#general")
        self.assertIsNone(result)
    
    def test_cache_hit_rate(self):
        """Test cache hit rate calculation"""
        optimizer = RoutingOptimizer()
        
        members = {"user_1", "user_2"}
        optimizer.cache_channel_members("#general", members)
        
        # 3 hits, 2 misses
        optimizer.get_cached_channel_members("#general")  # hit
        optimizer.get_cached_channel_members("#general")  # hit
        optimizer.get_cached_channel_members("#general")  # hit
        optimizer.get_cached_channel_members("#random")  # miss
        optimizer.get_cached_channel_members("#test")  # miss
        
        stats = optimizer.get_cache_stats()
        self.assertEqual(stats['cache_hits'], 3)
        self.assertEqual(stats['cache_misses'], 2)
        self.assertEqual(stats['hit_rate'], 60.0)  # 3/5 = 60%


if __name__ == '__main__':
    unittest.main()
