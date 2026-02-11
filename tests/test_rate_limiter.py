#!/usr/bin/env python3
"""
Tests for rate_limiter.py
"""

import unittest
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rate_limiter import RateLimiter, ConnectionRateLimiter


class TestRateLimiter(unittest.TestCase):
    """Test rate limiting functionality"""
    
    def test_rate_limiter_allows_under_limit(self):
        """Test that requests under limit are allowed"""
        limiter = RateLimiter(max_requests=5, time_window=10.0)
        
        for i in range(5):
            allowed = limiter.is_allowed("client1")
            self.assertTrue(allowed, f"Request {i+1} should be allowed")
    
    def test_rate_limiter_blocks_over_limit(self):
        """Test that requests over limit are blocked"""
        limiter = RateLimiter(max_requests=3, time_window=10.0)
        
        # First 3 should be allowed
        for i in range(3):
            self.assertTrue(limiter.is_allowed("client1"))
        
        # 4th should be blocked
        self.assertFalse(limiter.is_allowed("client1"))
    
    def test_rate_limiter_remaining(self):
        """Test get_remaining method"""
        limiter = RateLimiter(max_requests=5, time_window=10.0)
        
        self.assertEqual(limiter.get_remaining("client1"), 5)
        
        limiter.is_allowed("client1")
        self.assertEqual(limiter.get_remaining("client1"), 4)
        
        limiter.is_allowed("client1")
        self.assertEqual(limiter.get_remaining("client1"), 3)
    
    def test_rate_limiter_retry_after(self):
        """Test get_retry_after method"""
        limiter = RateLimiter(max_requests=2, time_window=5.0)
        
        # Under limit
        limiter.is_allowed("client1")
        self.assertEqual(limiter.get_retry_after("client1"), 0.0)
        
        # At limit
        limiter.is_allowed("client1")
        
        # Over limit
        limiter.is_allowed("client1")
        retry_after = limiter.get_retry_after("client1")
        self.assertGreater(retry_after, 0.0)
        self.assertLessEqual(retry_after, 5.0)
    
    def test_rate_limiter_reset(self):
        """Test reset functionality"""
        limiter = RateLimiter(max_requests=2, time_window=10.0)
        
        # Fill up limit
        limiter.is_allowed("client1")
        limiter.is_allowed("client1")
        
        # Should be blocked
        self.assertFalse(limiter.is_allowed("client1"))
        
        # Reset
        limiter.reset("client1")
        
        # Should be allowed again
        self.assertTrue(limiter.is_allowed("client1"))
    
    def test_rate_limiter_multiple_clients(self):
        """Test that limits are per-client"""
        limiter = RateLimiter(max_requests=2, time_window=10.0)
        
        # Client 1 fills limit
        limiter.is_allowed("client1")
        limiter.is_allowed("client1")
        self.assertFalse(limiter.is_allowed("client1"))
        
        # Client 2 should still be allowed
        self.assertTrue(limiter.is_allowed("client2"))
        self.assertTrue(limiter.is_allowed("client2"))
    
    def test_rate_limiter_cleanup(self):
        """Test cleanup of old client data"""
        limiter = RateLimiter(max_requests=5, time_window=1.0)
        
        limiter.is_allowed("client1")
        limiter.is_allowed("client2")
        
        self.assertIn("client1", limiter.requests)
        self.assertIn("client2", limiter.requests)
        
        # Sleep and cleanup (max_age=0 removes all)
        time.sleep(0.1)
        limiter.cleanup(max_age=0)
        
        # Old requests should be removed
        self.assertEqual(len(limiter.requests), 0)


class TestConnectionRateLimiter(unittest.TestCase):
    """Test connection rate limiting"""
    
    def test_connection_limiter_allows_under_limit(self):
        """Test connections under limit are allowed"""
        limiter = ConnectionRateLimiter(max_connections=3, time_window=10.0)
        
        for i in range(3):
            allowed, reason = limiter.is_allowed("192.168.1.1")
            self.assertTrue(allowed, f"Connection {i+1} should be allowed")
            self.assertEqual(reason, "")
    
    def test_connection_limiter_blocks_over_limit(self):
        """Test connections over limit are blocked"""
        limiter = ConnectionRateLimiter(max_connections=2, time_window=10.0)
        
        # First 2 allowed
        limiter.is_allowed("192.168.1.1")
        limiter.is_allowed("192.168.1.1")
        
        # 3rd blocked
        allowed, reason = limiter.is_allowed("192.168.1.1")
        self.assertFalse(allowed)
        self.assertIn("rate limit", reason.lower())
    
    def test_connection_limiter_ban_threshold(self):
        """Test that repeated violations lead to ban"""
        limiter = ConnectionRateLimiter(
            max_connections=1, 
            time_window=5.0, 
            ban_threshold=3
        )
        
        ip = "192.168.1.100"
        
        # Fill limit
        limiter.is_allowed(ip)
        
        # Trigger violations
        for i in range(3):
            allowed, reason = limiter.is_allowed(ip)
            self.assertFalse(allowed)
        
        # Next attempt should show ban message
        allowed, reason = limiter.is_allowed(ip)
        self.assertFalse(allowed)
        self.assertIn("banned", reason.lower())
    
    def test_connection_limiter_different_ips(self):
        """Test that limits are per-IP"""
        limiter = ConnectionRateLimiter(max_connections=1, time_window=10.0)
        
        # IP 1 fills limit
        limiter.is_allowed("192.168.1.1")
        allowed, _ = limiter.is_allowed("192.168.1.1")
        self.assertFalse(allowed)
        
        # IP 2 should still be allowed
        allowed, _ = limiter.is_allowed("192.168.1.2")
        self.assertTrue(allowed)
    
    def test_connection_limiter_cleanup(self):
        """Test cleanup functionality"""
        limiter = ConnectionRateLimiter(max_connections=5, time_window=1.0)
        
        limiter.is_allowed("192.168.1.1")
        limiter.is_allowed("192.168.1.2")
        
        self.assertIn("192.168.1.1", limiter.connections)
        
        # Cleanup old data
        time.sleep(0.1)
        limiter.cleanup(max_age=0)
        
        # Should be cleaned
        self.assertEqual(len(limiter.connections), 0)


if __name__ == '__main__':
    unittest.main()
