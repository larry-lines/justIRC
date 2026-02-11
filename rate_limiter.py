"""
Rate Limiting Module for JustIRC Server
Implements token bucket algorithm for rate limiting
"""

import time
from typing import Dict, Tuple
from collections import deque


class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, max_requests: int, time_window: float):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, deque] = {}  # client_id -> deque of timestamps
    
    def is_allowed(self, client_id: str) -> bool:
        """
        Check if request is allowed for client
        
        Args:
            client_id: Identifier for the client
            
        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()
        
        # Initialize request history for new clients
        if client_id not in self.requests:
            self.requests[client_id] = deque()
        
        # Get request history for this client
        history = self.requests[client_id]
        
        # Remove requests outside the time window
        while history and history[0] < now - self.time_window:
            history.popleft()
        
        # Check if under rate limit
        if len(history) < self.max_requests:
            history.append(now)
            return True
        
        return False
    
    def get_remaining(self, client_id: str) -> int:
        """
        Get remaining requests for client in current window
        
        Args:
            client_id: Identifier for the client
            
        Returns:
            Number of remaining requests
        """
        now = time.time()
        
        if client_id not in self.requests:
            return self.max_requests
        
        history = self.requests[client_id]
        
        # Remove expired requests
        while history and history[0] < now - self.time_window:
            history.popleft()
        
        return max(0, self.max_requests - len(history))
    
    def get_retry_after(self, client_id: str) -> float:
        """
        Get time until next request is allowed
        
        Args:
            client_id: Identifier for the client
            
        Returns:
            Seconds until next request allowed, 0 if allowed now
        """
        now = time.time()
        
        if client_id not in self.requests:
            return 0.0
        
        history = self.requests[client_id]
        
        # Remove expired requests
        while history and history[0] < now - self.time_window:
            history.popleft()
        
        # If under limit, no wait time
        if len(history) < self.max_requests:
            return 0.0
        
        # Wait until oldest request expires
        oldest = history[0]
        wait_time = (oldest + self.time_window) - now
        return max(0.0, wait_time)
    
    def reset(self, client_id: str = None):
        """
        Reset rate limit for client(s)
        
        Args:
            client_id: Client to reset, or None to reset all
        """
        if client_id is None:
            self.requests.clear()
        elif client_id in self.requests:
            del self.requests[client_id]
    
    def cleanup(self, max_age: float = 3600):
        """
        Remove old client data to prevent memory leaks
        
        Args:
            max_age: Remove clients with no recent requests (seconds)
        """
        now = time.time()
        to_remove = []
        
        for client_id, history in self.requests.items():
            if not history or history[-1] < now - max_age:
                to_remove.append(client_id)
        
        for client_id in to_remove:
            del self.requests[client_id]


class ConnectionRateLimiter:
    """Rate limiter for new connections by IP address"""
    
    def __init__(self, max_connections: int, time_window: float, ban_threshold: int = None):
        """
        Initialize connection rate limiter
        
        Args:
            max_connections: Max connections per IP in time window
            time_window: Time window in seconds
            ban_threshold: Number of violations before temp ban (optional)
        """
        self.max_connections = max_connections
        self.time_window = time_window
        self.ban_threshold = ban_threshold
        self.connections: Dict[str, deque] = {}  # IP -> timestamps
        self.violations: Dict[str, int] = {}  # IP -> violation count
        self.banned: Dict[str, float] = {}  # IP -> ban expiry time
    
    def is_allowed(self, ip_address: str) -> Tuple[bool, str]:
        """
        Check if connection is allowed from IP
        
        Args:
            ip_address: IP address of connecting client
            
        Returns:
            Tuple of (allowed, reason)
        """
        now = time.time()
        
        # Check if IP is banned
        if ip_address in self.banned:
            if now < self.banned[ip_address]:
                remaining = int(self.banned[ip_address] - now)
                return False, f"IP temporarily banned. Try again in {remaining} seconds"
            else:
                # Ban expired
                del self.banned[ip_address]
                if ip_address in self.violations:
                    del self.violations[ip_address]
        
        # Initialize connection history
        if ip_address not in self.connections:
            self.connections[ip_address] = deque()
        
        history = self.connections[ip_address]
        
        # Remove old connections
        while history and history[0] < now - self.time_window:
            history.popleft()
        
        # Check rate limit
        if len(history) < self.max_connections:
            history.append(now)
            return True, ""
        
        # Rate limit exceeded
        if self.ban_threshold:
            if ip_address not in self.violations:
                self.violations[ip_address] = 0
            
            self.violations[ip_address] += 1
            
            if self.violations[ip_address] >= self.ban_threshold:
                # Temporary ban
                ban_duration = 300  # 5 minutes
                self.banned[ip_address] = now + ban_duration
                return False, f"Too many connection attempts. Banned for {ban_duration} seconds"
        
        return False, "Connection rate limit exceeded"
    
    def record_disconnect(self, ip_address: str):
        """
        Record a disconnection (for statistics)
        
        Args:
            ip_address: IP address that disconnected
        """
        # Could be used for tracking connection patterns
        pass
    
    def cleanup(self, max_age: float = 3600):
        """Remove old data"""
        now = time.time()
        
        # Clean old connection history
        to_remove = []
        for ip, history in self.connections.items():
            if not history or history[-1] < now - max_age:
                to_remove.append(ip)
        for ip in to_remove:
            del self.connections[ip]
        
        # Clean expired bans
        to_remove = []
        for ip, expiry in self.banned.items():
            if now >= expiry:
                to_remove.append(ip)
        for ip in to_remove:
            del self.banned[ip]
            if ip in self.violations:
                del self.violations[ip]


if __name__ == "__main__":
    # Test rate limiter
    limiter = RateLimiter(max_requests=5, time_window=10.0)
    
    print("Testing rate limiter...")
    for i in range(7):
        allowed = limiter.is_allowed("test_client")
        remaining = limiter.get_remaining("test_client")
        print(f"Request {i+1}: Allowed={allowed}, Remaining={remaining}")
        
        if not allowed:
            retry_after = limiter.get_retry_after("test_client")
            print(f"Rate limited! Retry after {retry_after:.2f} seconds")
    
    print("\nTesting connection rate limiter...")
    conn_limiter = ConnectionRateLimiter(max_connections=3, time_window=5.0, ban_threshold=5)
    
    for i in range(6):
        allowed, reason = conn_limiter.is_allowed("192.168.1.100")
        print(f"Connection {i+1}: Allowed={allowed}")
        if not allowed:
            print(f"  Reason: {reason}")
