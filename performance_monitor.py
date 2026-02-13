"""
Performance Monitoring and Connection Management for JustIRC Server

Provides real-time metrics, connection pooling, and performance optimization
"""

import time
import logging
import asyncio
from typing import Dict, List, Optional, Set
from collections import defaultdict, deque
from dataclasses import dataclass, field


logger = logging.getLogger('PerformanceMonitor')


@dataclass
class ConnectionMetrics:
    """Metrics for a single connection"""
    user_id: str
    connected_at: float
    last_activity: float
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    
    def get_idle_time(self) -> float:
        """Get seconds since last activity"""
        return time.time() - self.last_activity
    
    def get_connection_duration(self) -> float:
        """Get total connection time in seconds"""
        return time.time() - self.connected_at


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system
    
    Tracks:
    - Message throughput (messages/second)
    - Connection statistics
    - Channel activity
    - Server load metrics
    - Performance bottlenecks
    """
    
    def __init__(self, history_size: int = 60):
        """
        Initialize performance monitor
        
        Args:
            history_size: Number of seconds of history to keep
        """
        self.history_size = history_size
        
        # Connection tracking
        self.connections: Dict[str, ConnectionMetrics] = {}
        
        # Message throughput tracking (messages per second)
        self.message_timestamps: deque = deque(maxlen=1000)
        
        # Channel activity tracking
        self.channel_message_counts: Dict[str, int] = defaultdict(int)
        self.channel_member_counts: Dict[str, int] = defaultdict(int)
        
        # Server-wide statistics
        self.total_messages = 0
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.peak_connections = 0
        self.server_start_time = time.time()
        
        # Performance history (for graphing)
        self.message_rate_history: deque = deque(maxlen=history_size)
        self.connection_count_history: deque = deque(maxlen=history_size)
        self.last_snapshot = time.time()
        
        logger.info("Performance monitor initialized")
    
    def register_connection(self, user_id: str):
        """Register a new connection"""
        now = time.time()
        self.connections[user_id] = ConnectionMetrics(
            user_id=user_id,
            connected_at=now,
            last_activity=now
        )
        
        # Update peak connections
        current_count = len(self.connections)
        if current_count > self.peak_connections:
            self.peak_connections = current_count
            logger.info(f"New peak connection count: {self.peak_connections}")
    
    def unregister_connection(self, user_id: str):
        """Remove a connection"""
        if user_id in self.connections:
            metrics = self.connections[user_id]
            duration = metrics.get_connection_duration()
            logger.debug(
                f"Connection closed: {user_id}, duration: {duration:.1f}s, "
                f"sent: {metrics.messages_sent}, recv: {metrics.messages_received}"
            )
            del self.connections[user_id]
    
    def record_message(
        self,
        user_id: str,
        message_size: int,
        direction: str = 'sent'
    ):
        """
        Record a message being sent or received
        
        Args:
            user_id: User ID
            message_size: Size of message in bytes
            direction: 'sent' or 'received'
        """
        now = time.time()
        
        # Update connection metrics
        if user_id in self.connections:
            metrics = self.connections[user_id]
            metrics.last_activity = now
            
            if direction == 'sent':
                metrics.messages_sent += 1
                metrics.bytes_sent += message_size
                self.total_bytes_sent += message_size
            else:
                metrics.messages_received += 1
                metrics.bytes_received += message_size
                self.total_bytes_received += message_size
        
        # Record timestamp for throughput calculation
        self.message_timestamps.append(now)
        self.total_messages += 1
    
    def record_channel_message(self, channel: str, member_count: int):
        """Record a message sent to a channel"""
        self.channel_message_counts[channel] += 1
        self.channel_member_counts[channel] = member_count
    
    def get_message_rate(self, window: int = 60) -> float:
        """
        Calculate current message rate (messages per second)
        
        Args:
            window: Time window in seconds
        
        Returns:
            Messages per second
        """
        if not self.message_timestamps:
            return 0.0
        
        now = time.time()
        cutoff = now - window
        
        # Count messages in the time window
        recent_messages = sum(1 for ts in self.message_timestamps if ts >= cutoff)
        
        return recent_messages / window if window > 0 else 0.0
    
    def get_connection_stats(self) -> dict:
        """Get current connection statistics"""
        if not self.connections:
            return {
                'active_connections': 0,
                'peak_connections': self.peak_connections,
                'avg_idle_time': 0.0,
                'avg_messages_per_connection': 0.0
            }
        
        idle_times = [m.get_idle_time() for m in self.connections.values()]
        message_counts = [m.messages_sent + m.messages_received for m in self.connections.values()]
        
        return {
            'active_connections': len(self.connections),
            'peak_connections': self.peak_connections,
            'avg_idle_time': sum(idle_times) / len(idle_times),
            'avg_messages_per_connection': sum(message_counts) / len(message_counts)
        }
    
    def get_channel_stats(self) -> dict:
        """Get channel activity statistics"""
        if not self.channel_message_counts:
            return {
                'total_channels': 0,
                'most_active_channel': None,
                'total_channel_messages': 0
            }
        
        most_active = max(
            self.channel_message_counts.items(),
            key=lambda x: x[1]
        )
        
        return {
            'total_channels': len(self.channel_message_counts),
            'most_active_channel': most_active[0],
            'most_active_count': most_active[1],
            'total_channel_messages': sum(self.channel_message_counts.values())
        }
    
    def get_idle_connections(self, threshold: int = 300) -> List[str]:
        """
        Get list of idle connections
        
        Args:
            threshold: Idle time threshold in seconds
        
        Returns:
            List of user IDs that have been idle
        """
        return [
            user_id for user_id, metrics in self.connections.items()
            if metrics.get_idle_time() > threshold
        ]
    
    def get_throughput_stats(self) -> dict:
        """Get message throughput statistics"""
        uptime = time.time() - self.server_start_time
        
        return {
            'current_rate': self.get_message_rate(window=10),
            'avg_rate_1min': self.get_message_rate(window=60),
            'total_messages': self.total_messages,
            'avg_rate_overall': self.total_messages / uptime if uptime > 0 else 0,
            'total_bytes_sent': self.total_bytes_sent,
            'total_bytes_received': self.total_bytes_received,
            'uptime_seconds': uptime
        }
    
    def take_snapshot(self):
        """Take a snapshot of current performance metrics"""
        now = time.time()
        
        # Only take snapshot once per second
        if now - self.last_snapshot < 1.0:
            return
        
        self.message_rate_history.append({
            'timestamp': now,
            'rate': self.get_message_rate(window=1)
        })
        
        self.connection_count_history.append({
            'timestamp': now,
            'count': len(self.connections)
        })
        
        self.last_snapshot = now
    
    def get_summary(self) -> dict:
        """Get comprehensive performance summary"""
        return {
            'connections': self.get_connection_stats(),
            'throughput': self.get_throughput_stats(),
            'channels': self.get_channel_stats()
        }
    
    def log_summary(self):
        """Log a performance summary"""
        summary = self.get_summary()
        
        logger.info("=== Performance Summary ===")
        logger.info(f"Active Connections: {summary['connections']['active_connections']}")
        logger.info(f"Message Rate: {summary['throughput']['current_rate']:.2f} msg/s")
        logger.info(f"Total Messages: {summary['throughput']['total_messages']}")
        logger.info(f"Total Channels: {summary['channels']['total_channels']}")
        logger.info("==========================")


class ConnectionManager:
    """
    Manages client connections with optimization features
    
    Features:
    - Connection pooling and reuse
    - Idle connection detection and cleanup
    - Connection limit enforcement
    - Health checking
    """
    
    def __init__(
        self,
        max_connections: int = 1000,
        idle_timeout: int = 300,
        cleanup_interval: int = 60
    ):
        """
        Initialize connection manager
        
        Args:
            max_connections: Maximum simultaneous connections
            idle_timeout: Seconds before idle connection is removed
            cleanup_interval: Seconds between cleanup runs
        """
        self.max_connections = max_connections
        self.idle_timeout = idle_timeout
        self.cleanup_interval = cleanup_interval
        
        # Active connections
        self.active_connections: Set[str] = set()
        
        # Last activity tracking
        self.last_activity: Dict[str, float] = {}
        
        # Cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.total_connections_accepted = 0
        self.total_connections_rejected = 0
        self.total_idle_timeouts = 0
        
        logger.info(
            f"ConnectionManager initialized: max={max_connections}, "
            f"idle_timeout={idle_timeout}s"
        )
    
    def can_accept_connection(self) -> bool:
        """Check if server can accept a new connection"""
        return len(self.active_connections) < self.max_connections
    
    def register_connection(self, user_id: str) -> bool:
        """
        Register a new connection
        
        Returns:
            True if accepted, False if rejected (limit reached)
        """
        if not self.can_accept_connection():
            self.total_connections_rejected += 1
            logger.warning(
                f"Connection rejected (limit reached): {user_id}, "
                f"active: {len(self.active_connections)}/{self.max_connections}"
            )
            return False
        
        self.active_connections.add(user_id)
        self.last_activity[user_id] = time.time()
        self.total_connections_accepted += 1
        
        logger.debug(f"Connection registered: {user_id} ({len(self.active_connections)} active)")
        return True
    
    def unregister_connection(self, user_id: str):
        """Unregister a connection"""
        if user_id in self.active_connections:
            self.active_connections.remove(user_id)
            
            if user_id in self.last_activity:
                del self.last_activity[user_id]
            
            logger.debug(f"Connection unregistered: {user_id} ({len(self.active_connections)} active)")
    
    def update_activity(self, user_id: str):
        """Update last activity time for a connection"""
        self.last_activity[user_id] = time.time()
    
    def get_idle_connections(self) -> List[str]:
        """Get list of connections that have been idle too long"""
        now = time.time()
        idle_threshold = now - self.idle_timeout
        
        return [
            user_id for user_id, last_active in self.last_activity.items()
            if last_active < idle_threshold
        ]
    
    async def cleanup_idle_connections(self, disconnect_callback):
        """
        Cleanup idle connections
        
        Args:
            disconnect_callback: Async function to call to disconnect a user
        """
        idle_connections = self.get_idle_connections()
        
        for user_id in idle_connections:
            logger.info(f"Disconnecting idle connection: {user_id}")
            await disconnect_callback(user_id)
            self.total_idle_timeouts += 1
        
        return len(idle_connections)
    
    async def periodic_cleanup(self, disconnect_callback):
        """Periodically cleanup idle connections"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                cleaned = await self.cleanup_idle_connections(disconnect_callback)
                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} idle connections")
            
            except asyncio.CancelledError:
                logger.info("Connection cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    def start_cleanup_task(self, disconnect_callback):
        """Start the periodic cleanup background task"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(
                self.periodic_cleanup(disconnect_callback)
            )
            logger.info("Started connection cleanup task")
    
    def stop_cleanup_task(self):
        """Stop the periodic cleanup task"""
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            logger.info("Stopped connection cleanup task")
    
    def get_stats(self) -> dict:
        """Get connection manager statistics"""
        return {
            'active_connections': len(self.active_connections),
            'max_connections': self.max_connections,
            'utilization': len(self.active_connections) / self.max_connections * 100,
            'total_accepted': self.total_connections_accepted,
            'total_rejected': self.total_connections_rejected,
            'total_idle_timeouts': self.total_idle_timeouts
        }


class RoutingOptimizer:
    """
    Optimizes message routing with caching and lookup acceleration
    """
    
    def __init__(self, cache_size: int = 100):
        """
        Initialize routing optimizer
        
        Args:
            cache_size: Size of routing cache
        """
        self.cache_size = cache_size
        
        # Cache frequently used lookups
        self.nickname_cache: deque = deque(maxlen=cache_size)
        self.channel_member_cache: Dict[str, Set[str]] = {}
        
        # Performance tracking
        self.cache_hits = 0
        self.cache_misses = 0
        
        logger.info(f"RoutingOptimizer initialized with cache_size={cache_size}")
    
    def cache_channel_members(self, channel: str, members: Set[str]):
        """Cache channel member list for fast access"""
        self.channel_member_cache[channel] = members.copy()
    
    def get_cached_channel_members(self, channel: str) -> Optional[Set[str]]:
        """Get cached channel members"""
        if channel in self.channel_member_cache:
            self.cache_hits += 1
            return self.channel_member_cache[channel]
        
        self.cache_misses += 1
        return None
    
    def invalidate_channel_cache(self, channel: str):
        """Invalidate cache for a channel (when members change)"""
        if channel in self.channel_member_cache:
            del self.channel_member_cache[channel]
    
    def get_cache_stats(self) -> dict:
        """Get cache performance statistics"""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': hit_rate,
            'cached_channels': len(self.channel_member_cache)
        }
