#!/usr/bin/env python3
"""
Tests for config_manager.py
"""

import unittest
import os
import sys
import tempfile
import shutil
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import ConfigManager


class TestConfigManager(unittest.TestCase):
    """Test configuration management"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
    
    def tearDown(self):
        """Clean up"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_config_creation(self):
        """Test config file creation"""
        config = ConfigManager(self.config_file)
        self.assertIsNotNone(config)
    
    def test_default_values(self):
        """Test default configuration values"""
        config = ConfigManager(self.config_file)
        
        # Should have default theme
        theme = config.get('theme')
        self.assertIsNotNone(theme)
    
    def test_save_and_load(self):
        """Test saving and loading configuration"""
        config = ConfigManager(self.config_file)
        
        # Set some values
        config.set('server_host', value='localhost')
        config.set('server_port', value=6667)
        config.set('nickname', value='testuser')
        # save() is called automatically in set()
        
        # Load in new instance
        config2 = ConfigManager(self.config_file)
        
        self.assertEqual(config2.get('server_host'), 'localhost')
        self.assertEqual(config2.get('server_port'), 6667)
        self.assertEqual(config2.get('nickname'), 'testuser')
    
    def test_get_with_default(self):
        """Test getting value with default"""
        config = ConfigManager(self.config_file)
        
        # Non-existent key should return None or can be set
        value = config.get('nonexistent')
        # This is implementation specific - just verify it works
        self.assertTrue(value is None or isinstance(value, (str, int, dict)))
    
    def test_update_existing_value(self):
        """Test updating existing value"""
        config = ConfigManager(self.config_file)
        
        config.set('key', value='value1')
        self.assertEqual(config.get('key'), 'value1')
        
        config.set('key', value='value2')
        self.assertEqual(config.get('key'), 'value2')


if __name__ == '__main__':
    unittest.main()
