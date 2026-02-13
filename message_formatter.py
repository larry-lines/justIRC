"""
Message Formatter for JustIRC
Handles formatting of chat messages with full markdown support
Supports: bold, italic, code, links, lists, blockquotes, headers, etc.
"""

import re
from typing import List, Tuple, Dict, Any


class MessageFormatter:
    """Formats messages with simple markup"""
    
    def __init__(self):
        # Inline regex patterns for formatting
        # Order matters - more specific patterns first
        self.inline_patterns = [
            # Code blocks: `code`
            (r'`([^`]+)`', 'code'),
            # Bold: *text* or **text**
            (r'\*\*([^\*]+)\*\*', 'bold'),
            (r'\*([^\*]+)\*', 'bold'),
            # Italic: _text_ or __text__
            (r'__([^_]+)__', 'italic'),
            (r'_([^_]+)_', 'italic'),
            # Strike-through: ~~text~~
            (r'~~([^~]+)~~', 'strikethrough'),
            # Links: [text](url)
            (r'\[([^\]]+)\]\(([^\)]+)\)', 'link'),
        ]
        
        self.enable_markdown = True
    
    def parse_message(self, text: str) -> List[Tuple[str, str]]:
        """Parse message and return list of (text, format) tuples
        
        Args:
            text: Raw message text with markup
            
        Returns:
            List of (text, format) tuples where format can be:
            - 'normal': Regular text
            - 'bold': Bold text
            - 'italic': Italic text
            - 'code': Inline code
            - 'strikethrough': Strike-through text
        """
        if not text:
            return [('', 'normal')]
        
        result = []
        pos = 0
        
        while pos < len(text):
            # Find the earliest match among all patterns
            earliest_match = None
            earliest_pos = len(text)
            earliest_format = None
            
            for pattern, fmt in self.inline_patterns:
                match = re.search(pattern, text[pos:])
                if match and match.start() < earliest_pos:
                    earliest_match = match
                    earliest_pos = match.start()
                    earliest_format = fmt
            
            if earliest_match:
                # Add any regular text before the match
                if earliest_pos > 0:
                    result.append((text[pos:pos + earliest_pos], 'normal'))
                
                # Add the formatted text (content without markup)
                if earliest_format == 'link':
                    # Links have two groups: text and URL
                    link_text = earliest_match.group(1)
                    link_url = earliest_match.group(2)
                    result.append((f"{link_text} ({link_url})", earliest_format))
                else:
                    formatted_text = earliest_match.group(1)
                    result.append((formatted_text, earliest_format))
                
                # Move position past this match
                pos += earliest_pos + len(earliest_match.group(0))
            else:
                # No more matches, add remaining text as normal
                if pos < len(text):
                    result.append((text[pos:], 'normal'))
                break
        
        return result if result else [('', 'normal')]
    
    def strip_formatting(self, text: str) -> str:
        """Remove all formatting markup from text
        
        Args:
            text: Text with markup
            
        Returns:
            Plain text without markup
        """
        result = text
        for pattern, fmt in self.inline_patterns:
            if fmt == 'link':
                # For links, keep just the text part
                result = re.sub(pattern, r'\1', result)
            else:
                result = re.sub(pattern, r'\1', result)
        return result
    
    def parse_markdown_line(self, line: str) -> Dict[str, Any]:
        """Parse a line for markdown block elements
        
        Args:
            line: Single line of text
            
        Returns:
            Dict with 'type' and 'content' or 'level'
        """
        if not line or not self.enable_markdown:
            return {'type': 'text', 'content': line}
        
        # Headers: # Header, ## Header, etc.
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if header_match:
            level = len(header_match.group(1))
            text = header_match.group(2)
            return {'type': 'header', 'level': level, 'content': text}
        
        # Blockquote: > text
        if line.startswith('> '):
            return {'type': 'blockquote', 'content': line[2:]}
        
        # Unordered list: - item or * item
        ul_match = re.match(r'^[\-\*]\s+(.+)$', line)
        if ul_match:
            return {'type': 'ul', 'content': ul_match.group(1)}
        
        # Ordered list: 1. item
        ol_match = re.match(r'^(\d+)\.\s+(.+)$', line)
        if ol_match:
            return {'type': 'ol', 'number': ol_match.group(1), 'content': ol_match.group(2)}
        
        # Horizontal rule: --- or ***
        if re.match(r'^(---|\*\*\*|___)$', line.strip()):
            return {'type': 'hr'}
        
        # Code block: ``` or indented with 4 spaces/tab
        if line.startswith('```') or line.startswith('    '):
            return {'type': 'code_block', 'content': line}
        
        # Regular text
        return {'type': 'text', 'content': line}
    
    def format_line_for_display(self, line: str) -> Tuple[str, Dict[str, Any]]:
        """Format a line for display with markdown styling info
        
        Args:
            line: Line of text
            
        Returns:
            (formatted_text, styling_info) tuple
        """
        parsed = self.parse_markdown_line(line)
        
        if parsed['type'] == 'header':
            # Display headers with markers and emphasis
            level = parsed['level']
            marker = '#' * level
            text = parsed['content']
            return f"{marker} {text}", {'bold': True, 'size': 14 - level}
        
        elif parsed['type'] == 'blockquote':
            # Indent blockquotes
            return f"  | {parsed['content']}", {'italic': True, 'indent': True}
        
        elif parsed['type'] == 'ul':
            # Bullet point
            return f"  • {parsed['content']}", {}
        
        elif parsed['type'] == 'ol':
            # Numbered list
            return f"  {parsed['number']}. {parsed['content']}", {}
        
        elif parsed['type'] == 'hr':
            # Horizontal rule
            return "─" * 50, {}
        
        elif parsed['type'] == 'code_block':
            # Code block
            return parsed['content'], {'font': 'monospace', 'bg': 'dark'}
        
        else:
            # Regular text
            return parsed.get('content', line), {}
    
    def extract_links(self, text: str) -> List[Tuple[str, str]]:
        """Extract all links from text
        
        Args:
            text: Text potentially containing links
            
        Returns:
            List of (link_text, link_url) tuples
        """
        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        matches = re.findall(link_pattern, text)
        return matches
    
    def extract_urls(self, text: str) -> List[str]:
        """Extract bare URLs from text
        
        Args:
            text: Text potentially containing URLs
            
        Returns:
            List of URLs
        """
        # Match http(s) URLs
        url_pattern = r'https?://[^\s<>"]+'
        urls = re.findall(url_pattern, text)
        return urls
    
    def get_supported_markup(self) -> str:
        """Get description of supported markup formats
        
        Returns:
            String describing markup syntax
        """
        return """Supported Markdown:
• **bold** or *bold* - Bold text
• _italic_ or __italic__ - Italic text
• `code` - Inline code
• ~~strikethrough~~ - Strike-through text
• [text](url) - Links
• # Header, ## Header - Headers (levels 1-6)
• > quote - Blockquotes
• - item or * item - Bullet lists
• 1. item - Numbered lists
• --- or *** - Horizontal rule
"""
