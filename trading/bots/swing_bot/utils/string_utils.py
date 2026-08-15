"""
Swing Bot String Utilities Module
==================================

This module provides string manipulation utilities for the Swing Bot trading system.
Includes string formatting, validation, conversion, and parsing utilities.
"""

import re
import json
import hashlib
import base64
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
import unicodedata
import string


class StringUtils:
    """
    Utility class for string operations.
    """
    
    @staticmethod
    def to_snake_case(text: str) -> str:
        """
        Convert a string to snake_case.
        
        Args:
            text: Input string
        
        Returns:
            Snake case string
        """
        # Handle camelCase
        text = re.sub(r'(?<=[a-z])(?=[A-Z])', '_', text)
        # Handle spaces and dashes
        text = re.sub(r'[\s-]+', '_', text)
        # Convert to lowercase
        text = text.lower()
        # Remove duplicate underscores
        text = re.sub(r'_+', '_', text)
        # Remove leading/trailing underscores
        return text.strip('_')
    
    @staticmethod
    def to_camel_case(text: str) -> str:
        """
        Convert a string to camelCase.
        
        Args:
            text: Input string
        
        Returns:
            Camel case string
        """
        # Handle snake_case
        parts = text.split('_')
        # Handle spaces and dashes
        parts = re.split(r'[\s-]+', text)
        # First part stays lowercase
        if parts:
            result = parts[0].lower()
            # Capitalize remaining parts
            for part in parts[1:]:
                result += part.capitalize()
            return result
        return text
    
    @staticmethod
    def to_pascal_case(text: str) -> str:
        """
        Convert a string to PascalCase.
        
        Args:
            text: Input string
        
        Returns:
            Pascal case string
        """
        # Handle snake_case
        parts = text.split('_')
        # Handle spaces and dashes
        parts = re.split(r'[\s-]+', text)
        # Capitalize all parts
        return ''.join(part.capitalize() for part in parts)
    
    @staticmethod
    def to_kebab_case(text: str) -> str:
        """
        Convert a string to kebab-case.
        
        Args:
            text: Input string
        
        Returns:
            Kebab case string
        """
        # Handle camelCase
        text = re.sub(r'(?<=[a-z])(?=[A-Z])', '-', text)
        # Handle spaces and underscores
        text = re.sub(r'[\s_]+', '-', text)
        # Convert to lowercase
        text = text.lower()
        # Remove duplicate dashes
        text = re.sub(r'-+', '-', text)
        # Remove leading/trailing dashes
        return text.strip('-')
    
    @staticmethod
    def to_title_case(text: str) -> str:
        """
        Convert a string to Title Case.
        
        Args:
            text: Input string
        
        Returns:
            Title case string
        """
        words = re.split(r'[\s_-]+', text)
        return ' '.join(word.capitalize() for word in words)
    
    @staticmethod
    def to_constant_case(text: str) -> str:
        """
        Convert a string to CONSTANT_CASE.
        
        Args:
            text: Input string
        
        Returns:
            Constant case string
        """
        # Handle camelCase
        text = re.sub(r'(?<=[a-z])(?=[A-Z])', '_', text)
        # Handle spaces and dashes
        text = re.sub(r'[\s-]+', '_', text)
        # Convert to uppercase
        text = text.upper()
        # Remove duplicate underscores
        text = re.sub(r'_+', '_', text)
        # Remove leading/trailing underscores
        return text.strip('_')
    
    @staticmethod
    def to_sentence_case(text: str) -> str:
        """
        Convert a string to Sentence case.
        
        Args:
            text: Input string
        
        Returns:
            Sentence case string
        """
        # Split by sentence boundaries
        sentences = re.split(r'([.!?]+\s*)', text)
        result = []
        for i, sentence in enumerate(sentences):
            if i % 2 == 0 and sentence.strip():
                # Capitalize first letter of sentence
                result.append(sentence[0].upper() + sentence[1:].lower() if sentence else '')
            else:
                result.append(sentence)
        return ''.join(result)
    
    @staticmethod
    def truncate(text: str, max_length: int, suffix: str = '...') -> str:
        """
        Truncate a string to a maximum length.
        
        Args:
            text: Input string
            max_length: Maximum length
            suffix: Suffix to append if truncated
        
        Returns:
            Truncated string
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def strip_accents(text: str) -> str:
        """
        Remove accents from a string.
        
        Args:
            text: Input string
        
        Returns:
            String without accents
        """
        return ''.join(
            c for c in unicodedata.normalize('NFKD', text)
            if not unicodedata.combining(c)
        )
    
    @staticmethod
    def slugify(text: str, max_length: Optional[int] = None) -> str:
        """
        Create a URL-friendly slug.
        
        Args:
            text: Input string
            max_length: Maximum length of slug
        
        Returns:
            Slug string
        """
        # Remove accents
        text = StringUtils.strip_accents(text)
        # Convert to lowercase
        text = text.lower()
        # Replace spaces and special chars with hyphens
        text = re.sub(r'[^a-z0-9]+', '-', text)
        # Remove leading/trailing hyphens
        text = text.strip('-')
        # Remove duplicate hyphens
        text = re.sub(r'-+', '-', text)
        
        if max_length:
            text = text[:max_length]
        
        return text
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """
        Check if a string is a valid email address.
        
        Args:
            email: Email string
        
        Returns:
            True if valid email, False otherwise
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """
        Check if a string is a valid URL.
        
        Args:
            url: URL string
        
        Returns:
            True if valid URL, False otherwise
        """
        pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$'
        return bool(re.match(pattern, url))
    
    @staticmethod
    def is_valid_phone(phone: str) -> bool:
        """
        Check if a string is a valid phone number.
        
        Args:
            phone: Phone number string
        
        Returns:
            True if valid phone number, False otherwise
        """
        # Remove common separators
        clean = re.sub(r'[\s\-().]+', '', phone)
        return clean.isdigit() and len(clean) >= 10
    
    @staticmethod
    def is_valid_symbol(symbol: str) -> bool:
        """
        Check if a string is a valid trading symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            True if valid symbol, False otherwise
        """
        return bool(re.match(r'^[A-Z0-9/_.-]+$', symbol))
    
    @staticmethod
    def is_valid_hex(text: str) -> bool:
        """
        Check if a string is a valid hexadecimal string.
        
        Args:
            text: Hex string
        
        Returns:
            True if valid hex, False otherwise
        """
        return bool(re.match(r'^[0-9a-fA-F]+$', text))
    
    @staticmethod
    def is_valid_base64(text: str) -> bool:
        """
        Check if a string is a valid base64 string.
        
        Args:
            text: Base64 string
        
        Returns:
            True if valid base64, False otherwise
        """
        try:
            base64.b64decode(text, validate=True)
            return True
        except Exception:
            return False
    
    @staticmethod
    def is_valid_json(text: str) -> bool:
        """
        Check if a string is valid JSON.
        
        Args:
            text: JSON string
        
        Returns:
            True if valid JSON, False otherwise
        """
        try:
            json.loads(text)
            return True
        except json.JSONDecodeError:
            return False
    
    @staticmethod
    def is_valid_uuid(text: str) -> bool:
        """
        Check if a string is a valid UUID.
        
        Args:
            text: UUID string
        
        Returns:
            True if valid UUID, False otherwise
        """
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(pattern, text.lower()))
    
    @staticmethod
    def extract_numbers(text: str) -> List[float]:
        """
        Extract all numbers from a string.
        
        Args:
            text: Input string
        
        Returns:
            List of extracted numbers
        """
        return [float(x) for x in re.findall(r'-?\d+\.?\d*', text)]
    
    @staticmethod
    def extract_words(text: str) -> List[str]:
        """
        Extract all words from a string.
        
        Args:
            text: Input string
        
        Returns:
            List of extracted words
        """
        return re.findall(r'[a-zA-Z]+', text)
    
    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """
        Extract all email addresses from a string.
        
        Args:
            text: Input string
        
        Returns:
            List of extracted emails
        """
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return re.findall(pattern, text)
    
    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """
        Extract all URLs from a string.
        
        Args:
            text: Input string
        
        Returns:
            List of extracted URLs
        """
        pattern = r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/[^\s]*)?'
        return re.findall(pattern, text)
    
    @staticmethod
    def strip_html(text: str) -> str:
        """
        Strip HTML tags from a string.
        
        Args:
            text: Input string
        
        Returns:
            String without HTML tags
        """
        return re.sub(r'<[^>]+>', '', text)
    
    @staticmethod
    def escape_html(text: str) -> str:
        """
        Escape HTML special characters.
        
        Args:
            text: Input string
        
        Returns:
            HTML-escaped string
        """
        html_escapes = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '/': '&#x2F;',
        }
        return ''.join(html_escapes.get(c, c) for c in text)
    
    @staticmethod
    def unescape_html(text: str) -> str:
        """
        Unescape HTML special characters.
        
        Args:
            text: Input string
        
        Returns:
            Unescaped string
        """
        html_unescapes = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#x27;': "'",
            '&#x2F;': '/',
            '&nbsp;': ' ',
        }
        for escaped, unescaped in html_unescapes.items():
            text = text.replace(escaped, unescaped)
        return text
    
    @staticmethod
    def hash_string(text: str, algorithm: str = 'sha256') -> str:
        """
        Hash a string using the specified algorithm.
        
        Args:
            text: Input string
            algorithm: Hash algorithm (md5, sha1, sha256, sha512)
        
        Returns:
            Hashed string
        """
        if algorithm == 'md5':
            return hashlib.md5(text.encode()).hexdigest()
        elif algorithm == 'sha1':
            return hashlib.sha1(text.encode()).hexdigest()
        elif algorithm == 'sha256':
            return hashlib.sha256(text.encode()).hexdigest()
        elif algorithm == 'sha512':
            return hashlib.sha512(text.encode()).hexdigest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    @staticmethod
    def encode_base64(text: str) -> str:
        """
        Encode a string to base64.
        
        Args:
            text: Input string
        
        Returns:
            Base64 encoded string
        """
        return base64.b64encode(text.encode()).decode()
    
    @staticmethod
    def decode_base64(text: str) -> str:
        """
        Decode a base64 string.
        
        Args:
            text: Base64 string
        
        Returns:
            Decoded string
        """
        return base64.b64decode(text.encode()).decode()
    
    @staticmethod
    def format_bytes(size: int, decimals: int = 2) -> str:
        """
        Format bytes to human-readable string.
        
        Args:
            size: Size in bytes
            decimals: Number of decimal places
        
        Returns:
            Formatted string
        """
        if size == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        i = 0
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        
        return f"{size:.{decimals}f} {units[i]}"
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Format duration in seconds to human-readable string.
        
        Args:
            seconds: Duration in seconds
        
        Returns:
            Formatted string
        """
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f}m"
        elif seconds < 86400:
            return f"{seconds / 3600:.1f}h"
        else:
            return f"{seconds / 86400:.1f}d"
    
    @staticmethod
    def format_currency(amount: float, currency: str = '$', decimals: int = 2) -> str:
        """
        Format a currency amount.
        
        Args:
            amount: Amount to format
            currency: Currency symbol
            decimals: Number of decimal places
        
        Returns:
            Formatted string
        """
        return f"{currency}{amount:,.{decimals}f}"
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 2) -> str:
        """
        Format a percentage.
        
        Args:
            value: Value to format
            decimals: Number of decimal places
        
        Returns:
            Formatted string
        """
        return f"{value * 100:.{decimals}f}%"
    
    @staticmethod
    def pluralize(word: str, count: int) -> str:
        """
        Pluralize a word based on count.
        
        Args:
            word: Word to pluralize
            count: Count to check
        
        Returns:
            Pluralized word
        """
        if count == 1:
            return word
        # Simple pluralization rules
        if word.endswith('y') and not word.endswith('ay') and not word.endswith('ey'):
            return word[:-1] + 'ies'
        if word.endswith(('s', 'x', 'z', 'ch', 'sh')):
            return word + 'es'
        return word + 's'
    
    @staticmethod
    def is_blank(text: Optional[str]) -> bool:
        """
        Check if a string is None, empty, or only whitespace.
        
        Args:
            text: Input string
        
        Returns:
            True if blank, False otherwise
        """
        return text is None or not text.strip()
    
    @staticmethod
    def default_if_blank(text: Optional[str], default: str) -> str:
        """
        Return default if string is blank.
        
        Args:
            text: Input string
            default: Default value
        
        Returns:
            Input or default
        """
        return default if StringUtils.is_blank(text) else text


# Function aliases for easier import
to_snake_case = StringUtils.to_snake_case
to_camel_case = StringUtils.to_camel_case
to_pascal_case = StringUtils.to_pascal_case
to_kebab_case = StringUtils.to_kebab_case
to_title_case = StringUtils.to_title_case
to_constant_case = StringUtils.to_constant_case
to_sentence_case = StringUtils.to_sentence_case
truncate = StringUtils.truncate
strip_accents = StringUtils.strip_accents
slugify = StringUtils.slugify
is_valid_email = StringUtils.is_valid_email
is_valid_url = StringUtils.is_valid_url
is_valid_phone = StringUtils.is_valid_phone
is_valid_symbol = StringUtils.is_valid_symbol
is_valid_hex = StringUtils.is_valid_hex
is_valid_base64 = StringUtils.is_valid_base64
is_valid_json = StringUtils.is_valid_json
is_valid_uuid = StringUtils.is_valid_uuid
extract_numbers = StringUtils.extract_numbers
extract_words = StringUtils.extract_words
extract_emails = StringUtils.extract_emails
extract_urls = StringUtils.extract_urls
strip_html = StringUtils.strip_html
escape_html = StringUtils.escape_html
unescape_html = StringUtils.unescape_html
hash_string = StringUtils.hash_string
encode_base64 = StringUtils.encode_base64
decode_base64 = StringUtils.decode_base64
format_bytes = StringUtils.format_bytes
format_duration = StringUtils.format_duration
format_currency = StringUtils.format_currency
format_percentage = StringUtils.format_percentage
pluralize = StringUtils.pluralize
is_blank = StringUtils.is_blank
default_if_blank = StringUtils.default_if_blank


__all__ = [
    # Class
    'StringUtils',
    
    # Function aliases
    'to_snake_case',
    'to_camel_case',
    'to_pascal_case',
    'to_kebab_case',
    'to_title_case',
    'to_constant_case',
    'to_sentence_case',
    'truncate',
    'strip_accents',
    'slugify',
    'is_valid_email',
    'is_valid_url',
    'is_valid_phone',
    'is_valid_symbol',
    'is_valid_hex',
    'is_valid_base64',
    'is_valid_json',
    'is_valid_uuid',
    'extract_numbers',
    'extract_words',
    'extract_emails',
    'extract_urls',
    'strip_html',
    'escape_html',
    'unescape_html',
    'hash_string',
    'encode_base64',
    'decode_base64',
    'format_bytes',
    'format_duration',
    'format_currency',
    'format_percentage',
    'pluralize',
    'is_blank',
    'default_if_blank',
]
