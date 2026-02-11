"""
IP filtering for JustIRC server
Provides blacklist and whitelist functionality
"""

import ipaddress
import json
import os
from typing import Set, Optional, List
from datetime import datetime, timedelta


class IPFilter:
    """Manages IP blacklist and whitelist"""
    
    def __init__(self, blacklist_file: str = "ip_blacklist.json",
                 whitelist_file: str = "ip_whitelist.json",
                 enable_whitelist: bool = False):
        """
        Initialize IP filter
        
        Args:
            blacklist_file: Path to blacklist file
            whitelist_file: Path to whitelist file
            enable_whitelist: If True, only whitelist IPs are allowed
        """
        self.blacklist_file = blacklist_file
        self.whitelist_file = whitelist_file
        self.enable_whitelist = enable_whitelist
        
        self.blacklist: Set[str] = set()
        self.whitelist: Set[str] = set()
        self.blacklist_networks: List[ipaddress.IPv4Network] = []
        self.whitelist_networks: List[ipaddress.IPv4Network] = []
        self.temp_bans: dict = {}  # IP -> expiry timestamp
        
        self.load_filters()
    
    def is_allowed(self, ip: str) -> bool:
        """
        Check if an IP is allowed to connect
        
        Args:
            ip: IP address to check
            
        Returns:
            True if allowed, False otherwise
        """
        # Check temp bans first
        if ip in self.temp_bans:
            if datetime.now().timestamp() < self.temp_bans[ip]:
                return False  # Still banned
            else:
                del self.temp_bans[ip]  # Ban expired  
        
        # Check blacklist
        if self._is_blacklisted(ip):
            return False
        
        # If whitelist is enabled, check whitelist
        if self.enable_whitelist:
            return self._is_whitelisted(ip)
        
        return True
    
    def _is_blacklisted(self, ip: str) -> bool:
        """Check if IP is in blacklist"""
        # Direct match
        if ip in self.blacklist:
            return True
        
        # Check network ranges
        try:
            ip_obj = ipaddress.ip_address(ip)
            for network in self.blacklist_networks:
                if ip_obj in network:
                    return True
        except ValueError:
            return False
        
        return False
    
    def _is_whitelisted(self, ip: str) -> bool:
        """Check if IP is in whitelist"""
        # Direct match
        if ip in self.whitelist:
            return True
        
        # Check network ranges
        try:
            ip_obj = ipaddress.ip_address(ip)
            for network in self.whitelist_networks:
                if ip_obj in network:
                    return True
        except ValueError:
            return False
        
        return False
    
    def add_to_blacklist(self, ip_or_network: str, save: bool = True) -> bool:
        """
        Add IP or network to blacklist
        
        Args:
            ip_or_network: IP address or CIDR network (e.g., "192.168.1.0/24")
            save: Whether to save to file
            
        Returns:
            True if added successfully
        """
        try:
            # Try to parse as network
            if '/' in ip_or_network:
                network = ipaddress.ip_network(ip_or_network, strict=False)
                if network not in self.blacklist_networks:
                    self.blacklist_networks.append(network)
                    if save:
                        self.save_blacklist()
                    return True
            else:
                # Parse as single IP
                ipaddress.ip_address(ip_or_network)  # Validate
                if ip_or_network not in self.blacklist:
                    self.blacklist.add(ip_or_network)
                    if save:
                        self.save_blacklist()
                    return True
        except ValueError:
            return False
        
        return False
    
    def remove_from_blacklist(self, ip_or_network: str, save: bool = True) -> bool:
        """
        Remove IP or network from blacklist
        
        Args:
            ip_or_network: IP address or CIDR network
            save: Whether to save to file
            
        Returns:
            True if removed successfully
        """
        removed = False
        
        if ip_or_network in self.blacklist:
            self.blacklist.remove(ip_or_network)
            removed = True
        else:
            # Try to find matching network
            try:
                network = ipaddress.ip_network(ip_or_network, strict=False)
                for existing_net in self.blacklist_networks[:]:
                    if existing_net == network:
                        self.blacklist_networks.remove(existing_net)
                        removed = True
                        break
            except ValueError:
                pass
        
        if removed and save:
            self.save_blacklist()
        
        return removed
    
    def add_to_whitelist(self, ip_or_network: str, save: bool = True) -> bool:
        """
        Add IP or network to whitelist
        
        Args:
            ip_or_network: IP address or CIDR network
            save: Whether to save to file
            
        Returns:
            True if added successfully
        """
        try:
            if '/' in ip_or_network:
                network = ipaddress.ip_network(ip_or_network, strict=False)
                if network not in self.whitelist_networks:
                    self.whitelist_networks.append(network)
                    if save:
                        self.save_whitelist()
                    return True
            else:
                ipaddress.ip_address(ip_or_network)  # Validate
                if ip_or_network not in self.whitelist:
                    self.whitelist.add(ip_or_network)
                    if save:
                        self.save_whitelist()
                    return True
        except ValueError:
            return False
        
        return False
    
    def temp_ban(self, ip: str, duration_minutes: int = 15):
        """
        Temporarily ban an IP address
        
        Args:
            ip: IP address to ban
            duration_minutes: Ban duration in minutes (default 15)
        """
        expiry = datetime.now() + timedelta(minutes=duration_minutes)
        self.temp_bans[ip] = expiry.timestamp()
    
    def remove_temp_ban(self, ip: str):
        """Remove temporary ban for an IP"""
        if ip in self.temp_bans:
            del self.temp_bans[ip]
    
    def load_filters(self):
        """Load blacklist and whitelist from files"""
        # Load blacklist
        if os.path.exists(self.blacklist_file):
            try:
                with open(self.blacklist_file, 'r') as f:
                    data = json.load(f)
                    self.blacklist = set(data.get('ips', []))
                    
                    # Load networks
                    networks = data.get('networks', [])
                    self.blacklist_networks = [
                        ipaddress.ip_network(net, strict=False)
                        for net in networks
                    ]
            except Exception as e:
                print(f"Warning: Failed to load blacklist: {e}")
        
        # Load whitelist
        if os.path.exists(self.whitelist_file):
            try:
                with open(self.whitelist_file, 'r') as f:
                    data = json.load(f)
                    self.whitelist = set(data.get('ips', []))
                    
                    # Load networks
                    networks = data.get('networks', [])
                    self.whitelist_networks = [
                        ipaddress.ip_network(net, strict=False)
                        for net in networks
                    ]
            except Exception as e:
                print(f"Warning: Failed to load whitelist: {e}")
    
    def save_blacklist(self):
        """Save blacklist to file"""
        try:
            data = {
                'ips': list(self.blacklist),
                'networks': [str(net) for net in self.blacklist_networks]
            }
            with open(self.blacklist_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save blacklist: {e}")
    
    def save_whitelist(self):
        """Save whitelist to file"""
        try:
            data = {
                'ips': list(self.whitelist),
                'networks': [str(net) for net in self.whitelist_networks]
            }
            with open(self.whitelist_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save whitelist: {e}")
    
    def get_blacklist_count(self) -> int:
        """Get total number of blacklisted items"""
        return len(self.blacklist) + len(self.blacklist_networks)
    
    def get_whitelist_count(self) -> int:
        """Get total number of whitelisted items"""
        return len(self.whitelist) + len(self.whitelist_networks)
    
    def clear_blacklist(self, save: bool = True):
        """Clear all blacklist entries"""
        self.blacklist.clear()
        self.blacklist_networks.clear()
        if save:
            self.save_blacklist()
    
    def clear_whitelist(self, save: bool = True):
        """Clear all whitelist entries"""
        self.whitelist.clear()
        self.whitelist_networks.clear()
        if save:
            self.save_whitelist()
