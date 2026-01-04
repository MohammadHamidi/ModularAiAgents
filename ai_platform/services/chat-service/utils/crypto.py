"""
AES encryption/decryption utilities for Safiranayeha integration.

Handles decryption of URL parameters sent from the Safiranayeha website.
"""
import base64
import json
from typing import Dict, Any, TypeVar, Type
from urllib.parse import unquote
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Safiranayeha AES encryption parameters
AES_KEY = "DLwXJz9yzC7Kk2J1M0Brp7snLTUEY1Fg"
AES_IV = "nqcWgiLLZWJaFkZi"


class AESDecryptor:
    """AES decryption for Safiranayeha URL parameters."""

    def __init__(self, key: str = AES_KEY, iv: str = AES_IV):
        """
        Initialize AES decryptor with key and IV.

        Args:
            key: AES key (32 bytes for AES-256)
            iv: Initialization vector (16 bytes)
        """
        self.key = key.encode('utf-8')
        self.iv = iv.encode('utf-8')

        # Validate key and IV lengths
        if len(self.key) != 32:
            raise ValueError(f"AES key must be 32 bytes, got {len(self.key)}")
        if len(self.iv) != 16:
            raise ValueError(f"AES IV must be 16 bytes, got {len(self.iv)}")

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt AES encrypted string.

        Args:
            encrypted: URL-encoded base64 encrypted string

        Returns:
            Decrypted JSON string

        Raises:
            ValueError: If decryption fails
        """
        try:
            # URL decode
            url_decoded = unquote(encrypted)
            logger.debug(f"URL decoded: {url_decoded[:50]}...")

            # Base64 decode
            cipher_bytes = base64.b64decode(url_decoded)
            logger.debug(f"Base64 decoded: {len(cipher_bytes)} bytes")

            # Create AES cipher in CBC mode
            cipher = AES.new(self.key, AES.MODE_CBC, self.iv)

            # Decrypt
            decrypted_bytes = cipher.decrypt(cipher_bytes)

            # Remove PKCS7 padding
            decrypted_bytes = unpad(decrypted_bytes, AES.block_size)

            # Decode to string
            decrypted_str = decrypted_bytes.decode('utf-8')
            logger.info(f"Successfully decrypted: {decrypted_str[:100]}...")

            return decrypted_str

        except Exception as e:
            logger.error(f"AES decryption failed: {e}", exc_info=True)
            raise ValueError(f"Failed to decrypt parameter: {str(e)}")

    def decrypt_json(self, encrypted: str) -> Dict[str, Any]:
        """
        Decrypt and parse JSON from encrypted string.

        Args:
            encrypted: URL-encoded base64 encrypted string containing JSON

        Returns:
            Parsed JSON as dictionary

        Raises:
            ValueError: If decryption or JSON parsing fails
        """
        try:
            decrypted_str = self.decrypt(encrypted)
            data = json.loads(decrypted_str)
            logger.info(f"Successfully parsed JSON with keys: {list(data.keys())}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            raise ValueError(f"Failed to parse decrypted JSON: {str(e)}")

    def decrypt_typed(self, encrypted: str, model_class: Type[T]) -> T:
        """
        Decrypt and parse JSON into a typed model.

        Args:
            encrypted: URL-encoded base64 encrypted string
            model_class: Pydantic model class to parse into

        Returns:
            Instance of model_class

        Raises:
            ValueError: If decryption or parsing fails
        """
        data = self.decrypt_json(encrypted)
        try:
            return model_class(**data)
        except Exception as e:
            logger.error(f"Failed to parse into {model_class.__name__}: {e}")
            raise ValueError(f"Failed to parse into {model_class.__name__}: {str(e)}")


# Global decryptor instance
decryptor = AESDecryptor()


def decrypt_safiranayeha_param(encrypted: str) -> Dict[str, Any]:
    """
    Convenience function to decrypt Safiranayeha URL parameter.

    Args:
        encrypted: URL-encoded base64 encrypted string

    Returns:
        Dictionary with UserId and Path

    Example:
        >>> data = decrypt_safiranayeha_param(encrypted_param)
        >>> user_id = data['UserId']
        >>> path = data['Path']
    """
    return decryptor.decrypt_json(encrypted)


# Example usage
if __name__ == "__main__":
    # Test encryption/decryption
    import sys

    if len(sys.argv) > 1:
        encrypted_param = sys.argv[1]
        try:
            data = decrypt_safiranayeha_param(encrypted_param)
            print(f"Decrypted data: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Usage: python crypto.py <encrypted_param>")
        print("\nTest with sample data:")
        print("  (Provide an encrypted parameter from Safiranayeha)")
