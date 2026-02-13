"""
Link Preview Module for JustIRC
Fetches and displays previews for URLs in messages
"""

import re
import urllib.request
import urllib.error
from html.parser import HTMLParser
from typing import Dict, Optional, List
import json


class MetaTagParser(HTMLParser):
    """Parses HTML to extract meta tags for link previews"""
    
    def __init__(self):
        super().__init__()
        self.meta_data = {
            'title': None,
            'description': None,
            'image': None,
            'site_name': None
        }
        self.in_title = False
        self.title_text = []
    
    def handle_starttag(self, tag, attrs):
        """Handle start tags"""
        attrs_dict = dict(attrs)
        
        # Title tag
        if tag == 'title':
            self.in_title = True
        
        # Meta tags
        elif tag == 'meta':
            # OpenGraph tags (og:*)
            if attrs_dict.get('property', '').startswith('og:'):
                prop = attrs_dict['property'][3:]  # Remove 'og:' prefix
                content = attrs_dict.get('content', '')
                
                if prop in self.meta_data and content:
                    self.meta_data[prop] = content
            
            # Twitter Card tags
            elif attrs_dict.get('name', '').startswith('twitter:'):
                prop = attrs_dict['name'][8:]  # Remove 'twitter:' prefix
                content = attrs_dict.get('content', '')
                
                if prop == 'title' and not self.meta_data['title']:
                    self.meta_data['title'] = content
                elif prop == 'description' and not self.meta_data['description']:
                    self.meta_data['description'] = content
                elif prop == 'image' and not self.meta_data['image']:
                    self.meta_data['image'] = content
            
            # Standard meta tags
            elif attrs_dict.get('name') == 'description':
                if not self.meta_data['description']:
                    self.meta_data['description'] = attrs_dict.get('content', '')
    
    def handle_endtag(self, tag):
        """Handle end tags"""
        if tag == 'title':
            self.in_title = False
            if self.title_text and not self.meta_data['title']:
                self.meta_data['title'] = ''.join(self.title_text).strip()
    
    def handle_data(self, data):
        """Handle text data"""
        if self.in_title:
            self.title_text.append(data)


class LinkPreview:
    """Handles link preview generation"""
    
    def __init__(self, cache_previews: bool = True, max_cache_size: int = 100):
        """
        Initialize link preview
        
        Args:
            cache_previews: Whether to cache preview data
            max_cache_size: Maximum number of previews to cache
        """
        self.cache_previews = cache_previews
        self.max_cache_size = max_cache_size
        self.preview_cache: Dict[str, Dict] = {}
        
        # User agent for requests
        self.user_agent = 'Mozilla/5.0 (compatible; JustIRC-LinkPreview/1.0)'
    
    def extract_urls(self, text: str) -> List[str]:
        """
        Extract URLs from text
        
        Args:
            text: Text to extract URLs from
            
        Returns:
            List of URLs
        """
        # Pattern for http/https URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+[^\s<>"{}|\\^`\[\].,;:!?\'\")]'
        urls = re.findall(url_pattern, text)
        return urls
    
    def fetch_preview(self, url: str, timeout: int = 5) -> Optional[Dict]:
        """
        Fetch preview data for a URL
        
        Args:
            url: URL to fetch preview for
            timeout: Request timeout in seconds
            
        Returns:
            Dict with preview data or None if failed
        """
        # Check cache first
        if self.cache_previews and url in self.preview_cache:
            return self.preview_cache[url]
        
        try:
            # Create request with user agent
            req = urllib.request.Request(
                url,
                headers={'User-Agent': self.user_agent}
            )
            
            # Fetch page content (limit to 100KB to avoid large downloads)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                # Only process HTML content
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' not in content_type.lower():
                    return None
                
                # Read limited content
                content = response.read(100000).decode('utf-8', errors='ignore')
            
            # Parse HTML for meta tags
            parser = MetaTagParser()
            parser.feed(content)
            
            preview = {
                'url': url,
                'title': parser.meta_data['title'] or self._extract_domain(url),
                'description': parser.meta_data['description'],
                'image': parser.meta_data['image'],
                'site_name': parser.meta_data['site_name']
            }
            
            # Truncate description if too long
            if preview['description'] and len(preview['description']) > 200:
                preview['description'] = preview['description'][:197] + '...'
            
            # Cache the preview
            if self.cache_previews:
                # Limit cache size
                if len(self.preview_cache) >= self.max_cache_size:
                    # Remove oldest entry (simple FIFO)
                    oldest_key = next(iter(self.preview_cache))
                    del self.preview_cache[oldest_key]
                
                self.preview_cache[url] = preview
            
            return preview
            
        except urllib.error.HTTPError as e:
            # HTTP error (404, 403, etc.)
            return {
                'url': url,
                'title': self._extract_domain(url),
                'description': f'HTTP {e.code} Error',
                'image': None,
                'site_name': None,
                'error': True
            }
        
        except urllib.error.URLError as e:
            # Network error
            return {
                'url': url,
                'title': self._extract_domain(url),
                'description': 'Failed to load preview',
                'image': None,
                'site_name': None,
                'error': True
            }
        
        except Exception as e:
            # Other errors
            return {
                'url': url,
                'title': self._extract_domain(url),
                'description': f'Error: {str(e)[:50]}',
                'image': None,
                'site_name': None,
                'error': True
            }
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL for fallback title"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split('/')[0]
            return domain
        except:
            return 'Link'
    
    def format_preview_text(self, preview: Dict) -> str:
        """
        Format preview data as text
        
        Args:
            preview: Preview data dict
            
        Returns:
            Formatted text representation
        """
        if preview.get('error'):
            return f"🔗 {preview['title']} - {preview['description']}"
        
        lines = []
        lines.append(f"🔗 {preview['title']}")
        
        if preview.get('description'):
            lines.append(f"   {preview['description']}")
        
        if preview.get('site_name'):
            lines.append(f"   Source: {preview['site_name']}")
        
        return '\n'.join(lines)
    
    def clear_cache(self):
        """Clear the preview cache"""
        self.preview_cache.clear()
    
    def get_cache_size(self) -> int:
        """Get current cache size"""
        return len(self.preview_cache)
    
    def is_supported_url(self, url: str) -> bool:
        """
        Check if URL is supported for previews
        
        Args:
            url: URL to check
            
        Returns:
            True if supported, False otherwise
        """
        # Support http and https only
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Exclude common file extensions that aren't web pages
        excluded_extensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',  # Images
            '.mp4', '.avi', '.mov', '.webm',  # Videos
            '.mp3', '.wav', '.ogg',  # Audio
            '.zip', '.tar', '.gz', '.rar',  # Archives
            '.pdf', '.doc', '.docx', '.xls', '.xlsx',  # Documents
            '.exe', '.dmg', '.deb', '.rpm'  # Executables
        ]
        
        url_lower = url.lower()
        for ext in excluded_extensions:
            if url_lower.endswith(ext):
                return False
        
        return True
    
    def get_previews_for_message(self, text: str, max_previews: int = 3) -> List[Dict]:
        """
        Get previews for all URLs in a message
        
        Args:
            text: Message text
            max_previews: Maximum number of previews to fetch
            
        Returns:
            List of preview dicts
        """
        urls = self.extract_urls(text)
        previews = []
        
        for url in urls[:max_previews]:
            if self.is_supported_url(url):
                preview = self.fetch_preview(url)
                if preview:
                    previews.append(preview)
        
        return previews
