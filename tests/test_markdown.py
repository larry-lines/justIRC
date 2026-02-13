"""
Tests for Message Formatter with Markdown Support
"""

import unittest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from message_formatter import MessageFormatter


class TestMessageFormatter(unittest.TestCase):
    """Test message formatting functionality"""
    
    def setUp(self):
        """Set up formatter"""
        self.formatter = MessageFormatter()
    
    # ===== Basic Formatting Tests =====
    
    def test_parse_bold(self):
        """Test bold formatting"""
        result = self.formatter.parse_message("This is **bold** text")
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], ("This is ", "normal"))
        self.assertEqual(result[1], ("bold", "bold"))
        self.assertEqual(result[2], (" text", "normal"))
    
    def test_parse_italic(self):
        """Test italic formatting"""
        result = self.formatter.parse_message("This is _italic_ text")
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], ("This is ", "normal"))
        self.assertEqual(result[1], ("italic", "italic"))
        self.assertEqual(result[2], (" text", "normal"))
    
    def test_parse_code(self):
        """Test inline code formatting"""
        result = self.formatter.parse_message("Run `python test.py` command")
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], ("Run ", "normal"))
        self.assertEqual(result[1], ("python test.py", "code"))
        self.assertEqual(result[2], (" command", "normal"))
    
    def test_parse_strikethrough(self):
        """Test strikethrough formatting"""
        result = self.formatter.parse_message("This is ~~wrong~~ correct")
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], ("This is ", "normal"))
        self.assertEqual(result[1], ("wrong", "strikethrough"))
        self.assertEqual(result[2], (" correct", "normal"))
    
    def test_parse_link(self):
        """Test link parsing"""
        result = self.formatter.parse_message("Check [this link](https://example.com)")
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ("Check ", "normal"))
        self.assertEqual(result[1], ("this link (https://example.com)", "link"))
    
    def test_parse_multiple_formats(self):
        """Test multiple formats in one message"""
        result = self.formatter.parse_message("**Bold** and _italic_ with `code`")
        
        # Should have all three formats plus normal text
        self.assertGreaterEqual(len(result), 5)
        self.assertTrue(any(fmt == 'bold' for _, fmt in result))
        self.assertTrue(any(fmt == 'italic' for _, fmt in result))
        self.assertTrue(any(fmt == 'code' for _, fmt in result))
    
    def test_strip_formatting(self):
        """Test stripping all formatting"""
        text = "**Bold** _italic_ `code` ~~strike~~"
        result = self.formatter.strip_formatting(text)
        
        self.assertEqual(result, "Bold italic code strike")
    
    def test_parse_empty_string(self):
        """Test parsing empty string"""
        result = self.formatter.parse_message("")
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ("", "normal"))
    
    # ===== Markdown Block Elements Tests =====
    
    def test_parse_header_h1(self):
        """Test H1 header parsing"""
        result = self.formatter.parse_markdown_line("# Main Header")
        
        self.assertEqual(result['type'], 'header')
        self.assertEqual(result['level'], 1)
        self.assertEqual(result['content'], 'Main Header')
    
    def test_parse_header_h3(self):
        """Test H3 header parsing"""
        result = self.formatter.parse_markdown_line("### Subheader")
        
        self.assertEqual(result['type'], 'header')
        self.assertEqual(result['level'], 3)
        self.assertEqual(result['content'], 'Subheader')
    
    def test_parse_blockquote(self):
        """Test blockquote parsing"""
        result = self.formatter.parse_markdown_line("> This is a quote")
        
        self.assertEqual(result['type'], 'blockquote')
        self.assertEqual(result['content'], 'This is a quote')
    
    def test_parse_unordered_list(self):
        """Test unordered list parsing"""
        result = self.formatter.parse_markdown_line("- List item")
        
        self.assertEqual(result['type'], 'ul')
        self.assertEqual(result['content'], 'List item')
    
    def test_parse_ordered_list(self):
        """Test ordered list parsing"""
        result = self.formatter.parse_markdown_line("1. First item")
        
        self.assertEqual(result['type'], 'ol')
        self.assertEqual(result['number'], '1')
        self.assertEqual(result['content'], 'First item')
    
    def test_parse_horizontal_rule(self):
        """Test horizontal rule parsing"""
        result = self.formatter.parse_markdown_line("---")
        
        self.assertEqual(result['type'], 'hr')
    
    def test_parse_code_block(self):
        """Test code block detection"""
        result = self.formatter.parse_markdown_line("```python")
        
        self.assertEqual(result['type'], 'code_block')
    
    def test_parse_regular_text(self):
        """Test regular text (no markdown)"""
        result = self.formatter.parse_markdown_line("Just regular text")
        
        self.assertEqual(result['type'], 'text')
        self.assertEqual(result['content'], 'Just regular text')
    
    # ===== Format Line for Display Tests =====
    
    def test_format_header_for_display(self):
        """Test header formatting for display"""
        text, style = self.formatter.format_line_for_display("## Section Header")
        
        self.assertIn("##", text)
        self.assertIn("Section Header", text)
        self.assertTrue(style.get('bold'))
        self.assertEqual(style.get('size'), 12)  # 14 - 2
    
    def test_format_blockquote_for_display(self):
        """Test blockquote formatting for display"""
        text, style = self.formatter.format_line_for_display("> A quote")
        
        self.assertIn("|", text)
        self.assertIn("A quote", text)
        self.assertTrue(style.get('italic'))
    
    def test_format_ul_for_display(self):
        """Test unordered list formatting for display"""
        text, style = self.formatter.format_line_for_display("- Item")
        
        self.assertIn("\u2022", text)  # Bullet point
        self.assertIn("Item", text)
    
    def test_format_ol_for_display(self):
        """Test ordered list formatting for display"""
        text, style = self.formatter.format_line_for_display("1. First")
        
        self.assertIn("1.", text)
        self.assertIn("First", text)
    
    def test_format_hr_for_display(self):
        """Test horizontal rule formatting"""
        text, style = self.formatter.format_line_for_display("---")
        
        self.assertIn("\u2500", text)  # Horizontal line character
        self.assertEqual(len(text), 50)
    
    # ===== Link Extraction Tests =====
    
    def test_extract_links(self):
        """Test extracting markdown links"""
        text = "Check [link1](url1) and [link2](url2)"
        links = self.formatter.extract_links(text)
        
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0], ('link1', 'url1'))
        self.assertEqual(links[1], ('link2', 'url2'))
    
    def test_extract_links_none(self):
        """Test extracting links when there are none"""
        text = "No links here"
        links = self.formatter.extract_links(text)
        
        self.assertEqual(len(links), 0)
    
    def test_extract_urls(self):
        """Test extracting bare URLs"""
        text = "Visit https://example.com and http://test.org"
        urls = self.formatter.extract_urls(text)
        
        self.assertEqual(len(urls), 2)
        self.assertIn('https://example.com', urls)
        self.assertIn('http://test.org', urls)
    
    def test_extract_urls_complex(self):
        """Test extracting URLs with paths and query strings"""
        text = "See https://example.com/path?q=test&x=1"
        urls = self.formatter.extract_urls(text)
        
        self.assertEqual(len(urls), 1)
        self.assertIn('https://example.com/path?q=test&x=1', urls)
    
    def test_extract_urls_none(self):
        """Test extracting URLs when there are none"""
        text = "No URLs here"
        urls = self.formatter.extract_urls(text)
        
        self.assertEqual(len(urls), 0)
    
    # ===== Edge Cases =====
    
    def test_nested_formatting(self):
        """Test that nested formatting is handled"""
        # Note: Simple implementation doesn't support true nesting
        result = self.formatter.parse_message("**bold _and italic_**")
        
        # Should parse outer bold first
        self.assertTrue(any(fmt == 'bold' for _, fmt in result))
    
    def test_unclosed_formatting(self):
        """Test unclosed formatting markers"""
        result = self.formatter.parse_message("**unclosed bold")
        
        # Should not match if unclosed
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], "normal")
    
    def test_escaped_characters(self):
        """Test that we handle text with special characters"""
        result = self.formatter.parse_message("Price: $100 & tax")
        
        self.assertEqual(len(result), 1)
        self.assertIn("$100 & tax", result[0][0])


if __name__ == '__main__':
    unittest.main()
