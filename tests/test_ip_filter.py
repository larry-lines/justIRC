#!/usr/bin/env python3
"""
Tests for IP filtering
"""

import unittest
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ip_filter import IPFilter


class TestIPFilter(unittest.TestCase):
    """Test IP filtering functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.blacklist_file = os.path.join(self.temp_dir, 'blacklist.json')
        self.whitelist_file = os.path.join(self.temp_dir, 'whitelist.json')
        self.ip_filter = IPFilter(
            blacklist_file=self.blacklist_file,
            whitelist_file=self.whitelist_file,
            enable_whitelist=False
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        for f in [self.blacklist_file, self.whitelist_file]:
            if os.path.exists(f):
                os.remove(f)
        os.rmdir(self.temp_dir)
    
    def test_allow_by_default(self):
        """Test that IPs are allowed by default"""
        self.assertTrue(self.ip_filter.is_allowed("192.168.1.1"))
    
    def test_blacklist_single_ip(self):
        """Test blacklisting a single IP"""
        self.ip_filter.add_to_blacklist("192.168.1.100")
        self.assertFalse(self.ip_filter.is_allowed("192.168.1.100"))
        self.assertTrue(self.ip_filter.is_allowed("192.168.1.101"))
    
    def test_blacklist_network(self):
        """Test blacklisting a network range"""
        self.ip_filter.add_to_blacklist("192.168.1.0/24")
        self.assertFalse(self.ip_filter.is_allowed("192.168.1.50"))
        self.assertFalse(self.ip_filter.is_allowed("192.168.1.1"))
        self.assertTrue(self.ip_filter.is_allowed("192.168.2.1"))
    
    def test_remove_from_blacklist(self):
        """Test removing IP from blacklist"""
        self.ip_filter.add_to_blacklist("192.168.1.100")
        self.assertFalse(self.ip_filter.is_allowed("192.168.1.100"))
        
        self.ip_filter.remove_from_blacklist("192.168.1.100")
        self.assertTrue(self.ip_filter.is_allowed("192.168.1.100"))
    
    def test_whitelist_mode(self):
        """Test whitelist mode"""
        self.ip_filter.enable_whitelist = True
        
        # Should be blocked by default
        self.assertFalse(self.ip_filter.is_allowed("192.168.1.1"))
        
        # Add to whitelist
        self.ip_filter.add_to_whitelist("192.168.1.1")
        self.assertTrue(self.ip_filter.is_allowed("192.168.1.1"))
        self.assertFalse(self.ip_filter.is_allowed("192.168.1.2"))
    
    def test_whitelist_network(self):
        """Test whitelisting a network"""
        self.ip_filter.enable_whitelist = True
        self.ip_filter.add_to_whitelist("192.168.1.0/24")
        
        self.assertTrue(self.ip_filter.is_allowed("192.168.1.50"))
        self.assertFalse(self.ip_filter.is_allowed("192.168.2.1"))
    
    def test_temp_ban(self):
        """Test temporary bans"""
        ip = "192.168.1.100"
        
        # Should be allowed initially
        self.assertTrue(self.ip_filter.is_allowed(ip))
        
        # Temp ban
        self.ip_filter.temp_ban(ip, duration_minutes=1)
        self.assertFalse(self.ip_filter.is_allowed(ip))
    
    def test_remove_temp_ban(self):
        """Test removing temporary ban"""
        ip = "192.168.1.100"
        self.ip_filter.temp_ban(ip)
        self.assertFalse(self.ip_filter.is_allowed(ip))
        
        self.ip_filter.remove_temp_ban(ip)
        self.assertTrue(self.ip_filter.is_allowed(ip))
    
    def test_blacklist_persistence(self):
        """Test that blacklist persists to file"""
        self.ip_filter.add_to_blacklist("192.168.1.100")
        
        # Create new filter with same file
        ip_filter2 = IPFilter(
            blacklist_file=self.blacklist_file,
            whitelist_file=self.whitelist_file
        )
        
        # Should still be blacklisted
        self.assertFalse(ip_filter2.is_allowed("192.168.1.100"))
    
    def test_whitelist_persistence(self):
        """Test that whitelist persists to file"""
        self.ip_filter.add_to_whitelist("192.168.1.100")
        
        # Create new filter with same file
        ip_filter2 = IPFilter(
            blacklist_file=self.blacklist_file,
            whitelist_file=self.whitelist_file,
            enable_whitelist=True
        )
        
        # Should be whitelisted
        self.assertTrue(ip_filter2.is_allowed("192.168.1.100"))
    
    def test_get_counts(self):
        """Test getting blacklist/whitelist counts"""
        self.ip_filter.add_to_blacklist("192.168.1.100")
        self.ip_filter.add_to_blacklist("192.168.2.0/24")
        
        self.assertEqual(self.ip_filter.get_blacklist_count(), 2)
    
    def test_clear_blacklist(self):
        """Test clearing blacklist"""
        self.ip_filter.add_to_blacklist("192.168.1.100")
        self.ip_filter.add_to_blacklist("192.168.2.0/24")
        
        self.ip_filter.clear_blacklist()
        self.assertEqual(self.ip_filter.get_blacklist_count(), 0)
        self.assertTrue(self.ip_filter.is_allowed("192.168.1.100"))
    
    def test_invalid_ip(self):
        """Test handling invalid IP"""
        result = self.ip_filter.add_to_blacklist("not.an.ip")
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
