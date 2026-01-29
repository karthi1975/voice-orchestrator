"""
Text normalization utilities for voice input

Handles common variations in spoken text to improve challenge validation accuracy.
Migrated from legacy challenge.py module.
"""

from typing import Dict


class TextNormalizer:
    """
    Normalizes spoken text to handle common variations.

    Handles:
    - Digit to word conversion ("4" → "four")
    - Homophone replacement ("for" → "four", "to" → "two")
    - Case normalization
    - Whitespace cleanup
    """

    # Common homophones and spoken variations
    REPLACEMENTS: Dict[str, str] = {
        ' for ': ' four ',
        ' to ': ' two ',
        ' too ': ' two ',
        ' won ': ' one ',
        ' ate ': ' eight ',
    }

    # Digit to word mapping
    DIGIT_MAP: Dict[str, str] = {
        '0': 'zero',
        '1': 'one',
        '2': 'two',
        '3': 'three',
        '4': 'four',
        '5': 'five',
        '6': 'six',
        '7': 'seven',
        '8': 'eight',
        '9': 'nine'
    }

    def normalize(self, text: str) -> str:
        """
        Normalize spoken text to standard form.

        Performs:
        1. Lowercase conversion
        2. Homophone replacement
        3. Digit to word conversion
        4. Whitespace cleanup

        Args:
            text: Raw spoken text

        Returns:
            Normalized text

        Examples:
            >>> normalizer = TextNormalizer()
            >>> normalizer.normalize("ocean 4")
            'ocean four'
            >>> normalizer.normalize("mountain FOR")
            'mountain four'
            >>> normalizer.normalize("  sunset   to  ")
            'sunset two'
        """
        # Convert to lowercase and strip
        text = text.lower().strip()

        # Add spaces for word boundary replacements
        text = f" {text} "

        # Replace common spoken variations
        for old, new in self.REPLACEMENTS.items():
            text = text.replace(old, new)

        # Convert digits to words
        for digit, word in self.DIGIT_MAP.items():
            text = text.replace(f' {digit} ', f' {word} ')

        # Clean up extra whitespace
        return ' '.join(text.split())

    def normalize_phrase(self, phrase: str) -> str:
        """
        Normalize a challenge phrase for comparison.

        Alias for normalize() for clarity when working with phrases.

        Args:
            phrase: Challenge phrase

        Returns:
            Normalized phrase
        """
        return self.normalize(phrase)


# Singleton instance for convenience
_normalizer = TextNormalizer()


def normalize_response(text: str) -> str:
    """
    Convenience function for normalizing text.

    Uses singleton TextNormalizer instance.

    Args:
        text: Text to normalize

    Returns:
        Normalized text

    Examples:
        >>> normalize_response("ocean 4")
        'ocean four'
    """
    return _normalizer.normalize(text)
