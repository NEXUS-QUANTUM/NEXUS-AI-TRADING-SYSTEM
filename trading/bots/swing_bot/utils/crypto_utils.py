"""
Swing Bot Crypto Utilities Module
===================================

This module provides cryptographic utilities for the Swing Bot trading system.
Includes hashing, encryption, signing, and secure key management.
"""

import hashlib
import hmac
import base64
import json
import os
import secrets
from typing import Any, Dict, Optional, Union, Tuple, List
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import jwt
import bcrypt


class CryptoUtils:
    """
    Utility class for cryptographic operations.
    """
    
    @staticmethod
    def generate_key(length: int = 32) -> str:
        """
        Generate a random key.
        
        Args:
            length: Key length in bytes
        
        Returns:
            Generated key as hex string
        """
        return secrets.token_hex(length)
    
    @staticmethod
    def generate_salt(length: int = 16) -> str:
        """
        Generate a random salt.
        
        Args:
            length: Salt length in bytes
        
        Returns:
            Generated salt as hex string
        """
        return secrets.token_hex(length)
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Password to hash
            salt: Salt (generated if None)
        
        Returns:
            Tuple of (hashed_password, salt)
        """
        if salt is None:
            salt = CryptoUtils.generate_salt()
        
        hashed = bcrypt.hashpw(password.encode(), salt.encode())
        return hashed.decode(), salt
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hash.
        
        Args:
            password: Password to verify
            hashed_password: Hashed password
        
        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode(), hashed_password.encode())
        except ValueError:
            return False
    
    @staticmethod
    def hash_data(data: Union[str, bytes], algorithm: str = 'sha256') -> str:
        """
        Hash data using the specified algorithm.
        
        Args:
            data: Data to hash
            algorithm: Hash algorithm (md5, sha1, sha256, sha512)
        
        Returns:
            Hex digest
        """
        if isinstance(data, str):
            data = data.encode()
        
        hash_func = hashlib.new(algorithm)
        hash_func.update(data)
        return hash_func.hexdigest()
    
    @staticmethod
    def hash_file(path: str, algorithm: str = 'sha256') -> str:
        """
        Hash a file.
        
        Args:
            path: File path
            algorithm: Hash algorithm
        
        Returns:
            Hex digest
        """
        hash_func = hashlib.new(algorithm)
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    
    @staticmethod
    def hmac_sign(data: Union[str, bytes], key: Union[str, bytes], algorithm: str = 'sha256') -> str:
        """
        Sign data using HMAC.
        
        Args:
            data: Data to sign
            key: Secret key
            algorithm: Hash algorithm
        
        Returns:
            HMAC hex digest
        """
        if isinstance(data, str):
            data = data.encode()
        if isinstance(key, str):
            key = key.encode()
        
        hash_func = getattr(hashlib, algorithm)
        signature = hmac.new(key, data, hash_func)
        return signature.hexdigest()
    
    @staticmethod
    def hmac_verify(data: Union[str, bytes], signature: str, key: Union[str, bytes]) -> bool:
        """
        Verify an HMAC signature.
        
        Args:
            data: Data to verify
            signature: HMAC signature
            key: Secret key
        
        Returns:
            True if signature is valid, False otherwise
        """
        expected = CryptoUtils.hmac_sign(data, key)
        return hmac.compare_digest(expected, signature)
    
    @staticmethod
    def generate_fernet_key() -> str:
        """
        Generate a Fernet encryption key.
        
        Returns:
            Fernet key as base64 string
        """
        return Fernet.generate_key().decode()
    
    @staticmethod
    def encrypt_fernet(data: Union[str, bytes], key: Union[str, bytes]) -> str:
        """
        Encrypt data using Fernet symmetric encryption.
        
        Args:
            data: Data to encrypt
            key: Fernet key
        
        Returns:
            Encrypted data as base64 string
        """
        if isinstance(data, str):
            data = data.encode()
        if isinstance(key, str):
            key = key.encode()
        
        fernet = Fernet(key)
        encrypted = fernet.encrypt(data)
        return base64.b64encode(encrypted).decode()
    
    @staticmethod
    def decrypt_fernet(encrypted_data: Union[str, bytes], key: Union[str, bytes]) -> str:
        """
        Decrypt data using Fernet symmetric encryption.
        
        Args:
            encrypted_data: Encrypted data
            key: Fernet key
        
        Returns:
            Decrypted data as string
        """
        if isinstance(encrypted_data, str):
            encrypted_data = encrypted_data.encode()
        if isinstance(key, str):
            key = key.encode()
        
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_data)
        return decrypted.decode()
    
    @staticmethod
    def generate_rsa_key_pair(key_size: int = 2048) -> Tuple[str, str]:
        """
        Generate an RSA key pair.
        
        Args:
            key_size: Key size in bits
        
        Returns:
            Tuple of (private_key_pem, public_key_pem)
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        
        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Serialize public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return private_pem.decode(), public_pem.decode()
    
    @staticmethod
    def encrypt_rsa(data: Union[str, bytes], public_key_pem: str) -> str:
        """
        Encrypt data using RSA public key.
        
        Args:
            data: Data to encrypt
            public_key_pem: RSA public key in PEM format
        
        Returns:
            Encrypted data as base64 string
        """
        if isinstance(data, str):
            data = data.encode()
        
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(),
            backend=default_backend()
        )
        
        encrypted = public_key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(encrypted).decode()
    
    @staticmethod
    def decrypt_rsa(encrypted_data: Union[str, bytes], private_key_pem: str) -> str:
        """
        Decrypt data using RSA private key.
        
        Args:
            encrypted_data: Encrypted data
            private_key_pem: RSA private key in PEM format
        
        Returns:
            Decrypted data as string
        """
        if isinstance(encrypted_data, str):
            encrypted_data = base64.b64decode(encrypted_data)
        
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )
        
        decrypted = private_key.decrypt(
            encrypted_data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted.decode()
    
    @staticmethod
    def sign_data(data: Union[str, bytes], private_key_pem: str) -> str:
        """
        Sign data using RSA private key.
        
        Args:
            data: Data to sign
            private_key_pem: RSA private key in PEM format
        
        Returns:
            Signature as base64 string
        """
        if isinstance(data, str):
            data = data.encode()
        
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )
        
        signature = private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()
    
    @staticmethod
    def verify_signature(
        data: Union[str, bytes],
        signature: Union[str, bytes],
        public_key_pem: str
    ) -> bool:
        """
        Verify an RSA signature.
        
        Args:
            data: Original data
            signature: Signature to verify
            public_key_pem: RSA public key in PEM format
        
        Returns:
            True if signature is valid, False otherwise
        """
        if isinstance(data, str):
            data = data.encode()
        if isinstance(signature, str):
            signature = base64.b64decode(signature)
        
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(),
            backend=default_backend()
        )
        
        try:
            public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False
    
    @staticmethod
    def derive_key(
        password: str,
        salt: Union[str, bytes],
        length: int = 32,
        iterations: int = 100000
    ) -> str:
        """
        Derive a key from a password using PBKDF2.
        
        Args:
            password: Password
            salt: Salt
            length: Key length in bytes
            iterations: Number of iterations
        
        Returns:
            Derived key as hex string
        """
        if isinstance(salt, str):
            salt = salt.encode()
        if isinstance(password, str):
            password = password.encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        key = kdf.derive(password)
        return key.hex()
    
    @staticmethod
    def generate_jwt_token(
        payload: Dict[str, Any],
        secret: str,
        algorithm: str = 'HS256',
        expires_in: Optional[int] = 3600
    ) -> str:
        """
        Generate a JWT token.
        
        Args:
            payload: Token payload
            secret: Secret key
            algorithm: JWT algorithm
            expires_in: Expiration time in seconds
        
        Returns:
            JWT token
        """
        if expires_in:
            import time
            payload['exp'] = int(time.time()) + expires_in
        
        return jwt.encode(payload, secret, algorithm=algorithm)
    
    @staticmethod
    def decode_jwt_token(token: str, secret: str, algorithms: List[str] = ['HS256']) -> Dict[str, Any]:
        """
        Decode a JWT token.
        
        Args:
            token: JWT token
            secret: Secret key
            algorithms: Allowed algorithms
        
        Returns:
            Decoded payload
        """
        return jwt.decode(token, secret, algorithms=algorithms)
    
    @staticmethod
    def verify_jwt_token(token: str, secret: str) -> bool:
        """
        Verify a JWT token.
        
        Args:
            token: JWT token
            secret: Secret key
        
        Returns:
            True if token is valid, False otherwise
        """
        try:
            CryptoUtils.decode_jwt_token(token, secret)
            return True
        except jwt.InvalidTokenError:
            return False
    
    @staticmethod
    def generate_api_key() -> Tuple[str, str]:
        """
        Generate an API key pair.
        
        Returns:
            Tuple of (api_key, api_secret)
        """
        api_key = CryptoUtils.generate_key(16)
        api_secret = CryptoUtils.generate_key(32)
        return api_key, api_secret
    
    @staticmethod
    def generate_otp_secret(length: int = 20) -> str:
        """
        Generate an OTP secret.
        
        Args:
            length: Secret length in bytes
        
        Returns:
            OTP secret as base32 string
        """
        import pyotp
        return pyotp.random_base32()
    
    @staticmethod
    def generate_totp(secret: str) -> str:
        """
        Generate a TOTP code.
        
        Args:
            secret: OTP secret
        
        Returns:
            TOTP code
        """
        import pyotp
        totp = pyotp.TOTP(secret)
        return totp.now()
    
    @staticmethod
    def verify_totp(secret: str, code: str) -> bool:
        """
        Verify a TOTP code.
        
        Args:
            secret: OTP secret
            code: TOTP code to verify
        
        Returns:
            True if code is valid, False otherwise
        """
        import pyotp
        totp = pyotp.TOTP(secret)
        return totp.verify(code)
    
    @staticmethod
    def generate_hotp(secret: str, counter: int) -> str:
        """
        Generate an HOTP code.
        
        Args:
            secret: OTP secret
            counter: Counter value
        
        Returns:
            HOTP code
        """
        import pyotp
        hotp = pyotp.HOTP(secret)
        return hotp.at(counter)
    
    @staticmethod
    def verify_hotp(secret: str, code: str, counter: int) -> bool:
        """
        Verify an HOTP code.
        
        Args:
            secret: OTP secret
            code: HOTP code to verify
            counter: Counter value
        
        Returns:
            True if code is valid, False otherwise
        """
        import pyotp
        hotp = pyotp.HOTP(secret)
        return hotp.verify(code, counter)
    
    @staticmethod
    def secure_compare(a: Union[str, bytes], b: Union[str, bytes]) -> bool:
        """
        Securely compare two strings or bytes.
        
        Args:
            a: First value
            b: Second value
        
        Returns:
            True if values are equal, False otherwise
        """
        if isinstance(a, str):
            a = a.encode()
        if isinstance(b, str):
            b = b.encode()
        return hmac.compare_digest(a, b)


# Function aliases for easier import
generate_key = CryptoUtils.generate_key
generate_salt = CryptoUtils.generate_salt
hash_password = CryptoUtils.hash_password
verify_password = CryptoUtils.verify_password
hash_data = CryptoUtils.hash_data
hash_file = CryptoUtils.hash_file
hmac_sign = CryptoUtils.hmac_sign
hmac_verify = CryptoUtils.hmac_verify
generate_fernet_key = CryptoUtils.generate_fernet_key
encrypt_fernet = CryptoUtils.encrypt_fernet
decrypt_fernet = CryptoUtils.decrypt_fernet
generate_rsa_key_pair = CryptoUtils.generate_rsa_key_pair
encrypt_rsa = CryptoUtils.encrypt_rsa
decrypt_rsa = CryptoUtils.decrypt_rsa
sign_data = CryptoUtils.sign_data
verify_signature = CryptoUtils.verify_signature
derive_key = CryptoUtils.derive_key
generate_jwt_token = CryptoUtils.generate_jwt_token
decode_jwt_token = CryptoUtils.decode_jwt_token
verify_jwt_token = CryptoUtils.verify_jwt_token
generate_api_key = CryptoUtils.generate_api_key
generate_otp_secret = CryptoUtils.generate_otp_secret
generate_totp = CryptoUtils.generate_totp
verify_totp = CryptoUtils.verify_totp
generate_hotp = CryptoUtils.generate_hotp
verify_hotp = CryptoUtils.verify_hotp
secure_compare = CryptoUtils.secure_compare


__all__ = [
    # Class
    'CryptoUtils',
    
    # Function aliases
    'generate_key',
    'generate_salt',
    'hash_password',
    'verify_password',
    'hash_data',
    'hash_file',
    'hmac_sign',
    'hmac_verify',
    'generate_fernet_key',
    'encrypt_fernet',
    'decrypt_fernet',
    'generate_rsa_key_pair',
    'encrypt_rsa',
    'decrypt_rsa',
    'sign_data',
    'verify_signature',
    'derive_key',
    'generate_jwt_token',
    'decode_jwt_token',
    'verify_jwt_token',
    'generate_api_key',
    'generate_otp_secret',
    'generate_totp',
    'verify_totp',
    'generate_hotp',
    'verify_hotp',
    'secure_compare',
]
