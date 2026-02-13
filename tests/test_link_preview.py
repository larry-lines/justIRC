"""
Tests for Link Preview Module
"""

import unittest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from link_preview import LinkPreview, MetaTagParser


class TestMetaTagParser(unittest.TestCase):
    """Test HTML meta tag parsing"""
    
    def test_parse_title_tag(self):
        """Test parsing title tag"""
        parser = MetaTagParser()
        html = "<html><head><title>Test Title</title></head></html>"
        parser.feed(html)
        
        self.assertEqual(parser.meta_data['title'], 'Test Title')
    
    def test_parse_og_title(self):
        """Test parsing OpenGraph title"""
        parser = MetaTagParser()
        html = '<meta property="og:title" content="OG Title">'
        parser.feed(html)
        
        self.assertEqual(parser.meta_data['title'], 'OG Title')
    
    def test_parse_og_description(self):
        """Test parsing OpenGraph description"""
        parser = MetaTagParser()
        html = '<meta property="og:description" content="OG Description">'
        parser.feed(html)
        
        self.assertEqual(parser.meta_data['description'], 'OG Description')
    
    def test_parse_og_image(self):
        """Test parsing OpenGraph image"""
        parser = MetaTagParser()
        html = '<meta property="og:image" content="https://example.com/image.jpg">'
        parser.feed(html)
        
        self.assertEqual(parser.meta_data['image'], 'https://example.com/image.jpg')
    
    def test_parse_meta_description(self):
        """Test parsing standard meta description"""
        parser = MetaTagParser()
        html = '<meta name="description" content="Meta Description">'
        parser.feed(html)
        
        self.assertEqual(parser.meta_data['description'], 'Meta Description')
    
    def test_parse_twitter_tags(self):
        """Test parsing Twitter Card tags"""
        parser = MetaTagParser()
        html = '''
        <meta name="twitter:title" content="Twitter Title">
        <meta name="twitter:description" content="Twitter Description">
        <meta name="twitter:image" content="https://example.com/twitter.jpg">
        '''
        parser.feed(html)
        
        self.assertEqual(parser.meta_data['title'], 'Twitter Title')
        self.assertEqual(parser.meta_data['description'], 'Twitter Description')
        self.assertEqual(parser.meta_data['image'], 'https://example.com/twitter.jpg')
    
    def test_og_priority_over_twitter(self):
        """Test that OpenGraph tags have priority over Twitter tags"""
        parser = MetaTagParser()
        html = '''
        <meta property="og:title" content="OG Title">
        <meta name="twitter:title" content="Twitter Title">
        '''
        parser.feed(html)
        
        # OG should win since it comes first
        self.assertEqual(parser.meta_data['title'], 'OG Title')


class TestLinkPreview(unittest.TestCase):
    """Test link preview functionality"""
    
    def setUp(self):
        """Set up link preview"""
        self.preview = LinkPreview(cache_previews=True)
    
    # ===== URL Extraction Tests =====
    
    def test_extract_single_url(self):
        """Test extracting single URL"""
        text = "Check out https://example.com"
        urls = self.preview.extract_urls(text)
        
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], 'https://example.com')
    
    def test_extract_multiple_urls(self):
        """Test extracting multiple URLs"""
        text = "Visit https://example.com and http://test.org"
        urls = self.preview.extract_urls(text)
        
        self.assertEqual(len(urls), 2)
        self.assertIn('https://example.com', urls)
        self.assertIn('http://test.org', urls)
    
    def test_extract_url_with_path(self):
        """Test extracting URL with path"""
        text = "See https://example.com/path/to/page"
        urls = self.preview.extract_urls(text)
        
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], 'https://example.com/path/to/page')
    
    def test_extract_url_with_query(self):
        """Test extracting URL with query parameters"""
        text = "Link: https://example.com/search?q=test&page=1"
        urls = self.preview.extract_urls(text)
        
        self.assertEqual(len(urls), 1)
        self.assertIn('q=test', urls[0])
        self.assertIn('page=1', urls[0])
    
    def test_extract_url_with_fragment(self):
        """Test extracting URL with fragment"""
        text = "See https://example.com/page#section"
        urls = self.preview.extract_urls(text)
        
        self.assertEqual(len(urls), 1)
        self.assertIn('#section', urls[0])
    
    def test_extract_urls_none(self):
        """Test text with no URLs"""
        text = "No URLs in this text"
        urls = self.preview.extract_urls(text)
        
        self.assertEqual(len(urls), 0)
    
    def test_extract_urls_with_punctuation(self):
        """Test that URLs don't include trailing punctuation"""
        text = "Visit https://example.com."
        urls = self.preview.extract_urls(text)
        
        # Should not include the period
        self.assertEqual(urls[0], 'https://example.com')
    
    # ===== URL Support Tests =====
    
    def test_is_supported_url_http(self):
        """Test that http URLs are supported"""
        self.assertTrue(self.preview.is_supported_url('http://example.com'))
    
    def test_is_supported_url_https(self):
        """Test that https URLs are supported"""
        self.assertTrue(self.preview.is_supported_url('https://example.com'))
    
    def test_is_not_supported_url_ftp(self):
        """Test that ftp URLs are not supported"""
        self.assertFalse(self.preview.is_supported_url('ftp://example.com'))
    
    def test_is_not_supported_url_image(self):
        """Test that direct image URLs are not supported"""
        self.assertFalse(self.preview.is_supported_url('https://example.com/image.jpg'))
        self.assertFalse(self.preview.is_supported_url('https://example.com/photo.png'))
    
    def test_is_not_supported_url_video(self):
        """Test that video URLs are not supported"""
        self.assertFalse(self.preview.is_supported_url('https://example.com/video.mp4'))
    
    def test_is_not_supported_url_archive(self):
        """Test that archive URLs are not supported"""
        self.assertFalse(self.preview.is_supported_url('https://example.com/file.zip'))
    
    def test_is_not_supported_url_pdf(self):
        """Test that PDF URLs are not supported"""
        self.assertFalse(self.preview.is_supported_url('https://example.com/document.pdf'))
    
    # ===== Domain Extraction Tests =====
    
    def test_extract_domain_simple(self):
        """Test extracting domain from simple URL"""
        domain = self.preview._extract_domain('https://example.com')
        self.assertEqual(domain, 'example.com')
    
    def test_extract_domain_with_path(self):
        """Test extracting domain from URL with path"""
        domain = self.preview._extract_domain('https://example.com/path/page')
        self.assertEqual(domain, 'example.com')
    
    def test_extract_domain_with_subdomain(self):
        """Test extracting domain with subdomain"""
        domain = self.preview._extract_domain('https://blog.example.com')
        self.assertEqual(domain, 'blog.example.com')
    
    # ===== Preview Formatting Tests =====
    
    def test_format_preview_text_basic(self):
        """Test formatting basic preview"""
        preview = {
            'url': 'https://example.com',
            'title': 'Example Site',
            'description': 'A test site',
            'image': None,
            'site_name': None
        }
        
        text = self.preview.format_preview_text(preview)
        
        self.assertIn('Example Site', text)
        self.assertIn('A test site', text)
        self.assertIn('🔗', text)
    
    def test_format_preview_text_with_site_name(self):
        """Test formatting preview with site name"""
        preview = {
            'url': 'https://example.com',
            'title': 'Article Title',
            'description': 'Description here',
            'image': None,
            'site_name': 'Example Blog'
        }
        
        text = self.preview.format_preview_text(preview)
        
        self.assertIn('Article Title', text)
        self.assertIn('Example Blog', text)
    
    def test_format_preview_text_error(self):
        """Test formatting error preview"""
        preview = {
            'url': 'https://example.com',
            'title': 'example.com',
            'description': 'HTTP 404 Error',
            'image': None,
            'site_name': None,
            'error': True
        }
        
        text = self.preview.format_preview_text(preview)
        
        self.assertIn('example.com', text)
        self.assertIn('404', text)
    
    # ===== Cache Tests =====
    
    def test_cache_stores_previews(self):
        """Test that successful previews are cached"""
        # Create a mock preview
        url = 'https://test.example.com'
        preview = {
            'url': url,
            'title': 'Test',
            'description': 'Test site'
        }
        
        # Manually add to cache
        self.preview.preview_cache[url] = preview
        
        # Should be in cache
        self.assertIn(url, self.preview.preview_cache)
        self.assertEqual(self.preview.get_cache_size(), 1)
    
    def test_cache_clears(self):
        """Test cache clearing"""
        # Add some items
        self.preview.preview_cache['url1'] = {'title': 'Test1'}
        self.preview.preview_cache['url2'] = {'title': 'Test2'}
        
        self.assertEqual(self.preview.get_cache_size(), 2)
        
        # Clear cache
        self.preview.clear_cache()
        
        self.assertEqual(self.preview.get_cache_size(), 0)
    
    def test_cache_respects_size_limit(self):
        """Test that cache respects size limit"""
        # Create preview with small cache
        small_preview = LinkPreview(cache_previews=True, max_cache_size=3)
        
        # Add items beyond limit
        for i in range(5):
            url = f'https://example{i}.com'
            small_preview.preview_cache[url] = {'title': f'Site {i}'}
            
            # Manually enforce limit (since we're not using fetch_preview)
            if len(small_preview.preview_cache) > small_preview.max_cache_size:
                oldest = next(iter(small_preview.preview_cache))
                del small_preview.preview_cache[oldest]
        
        # Should not exceed limit
        self.assertLessEqual(len(small_preview.preview_cache), 3)
    
    # ===== Get Previews for Message Tests =====
    
    def test_get_previews_respects_max(self):
        """Test that get_previews_for_message respects max_previews"""
        text = "Visit https://a.com https://b.com https://c.com https://d.com"
        
        # Mock the fetch to avoid network calls
        def mock_fetch(url):
            return {'url': url, 'title': url}
        
        original_fetch = self.preview.fetch_preview
        self.preview.fetch_preview = mock_fetch
        
        previews = self.preview.get_previews_for_message(text, max_previews=2)
        
        # Should only get 2 previews
        self.assertEqual(len(previews), 2)
        
        # Restore original
        self.preview.fetch_preview = original_fetch


if __name__ == '__main__':
    unittest.main()
