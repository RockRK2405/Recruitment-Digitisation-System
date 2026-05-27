import re
from config.logging_config import logger

class DocumentCleaner:
    """Cleans optical scanning artifacts, normalizes whitespace, and parses standard strings."""
    
    @staticmethod
    def remove_ocr_noise(text: str) -> str:
        """Removes common optical character noise patterns (e.g. loose symbols, vertical lines)."""
        if not text:
            return ""
            
        # Remove stray non-ascii or single bracket artifacts
        text = re.sub(r'[\\_\|\~\[\]\^`]', ' ', text)
        
        # Remove multiple lines of dots/hyphens (often used for design borders in CVs)
        text = re.sub(r'[\.\-\*]{3,}', ' ', text)
        
        return text

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Standardizes line breaks and consolidates multi-space lines into single-space paragraphs."""
        if not text:
            return ""
            
        # Replace multiple spaces with a single space
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Replace multiple newlines with double newlines
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        
        return text.strip()

    @staticmethod
    def extract_phone(text: str) -> str:
        """Safely extracts a standardized phone number from messy OCR text."""
        if not text:
            return ""
            
        # Hunt for typical phone patterns in text (e.g. +91 98765-43210, 09876543210, 9876543210)
        phone_match = re.search(
            r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text
        )
        if phone_match:
            raw_phone = phone_match.group(0)
            # Remove all non-numeric characters except +
            cleaned = re.sub(r'[^\d+]', '', raw_phone)
            # Add Indian prefix +91 if length is 10 and doesn't have prefix
            if len(cleaned) == 10 and not cleaned.startswith("+"):
                cleaned = "+91" + cleaned
            return cleaned
            
        return ""

    @staticmethod
    def extract_email(text: str) -> str:
        """Safely extracts a valid email address from OCR text."""
        if not text:
            return ""
            
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if email_match:
            return email_match.group(0).lower().strip()
            
        return ""

    @classmethod
    def clean(cls, text: str) -> str:
        """Runs the fully consolidated text cleaning workflow."""
        if not text:
            return ""
        
        no_noise = cls.remove_ocr_noise(text)
        clean_text = cls.normalize_whitespace(no_noise)
        
        return clean_text
