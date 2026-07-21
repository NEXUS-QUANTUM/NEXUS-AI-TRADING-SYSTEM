"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Crypto Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires cryptographiques pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import hashlib
import hmac
import base64
import binascii
import json
import os
import secrets
import string
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    BinaryIO,
    Callable
)
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
import jwt
from jwt import PyJWTError
from datetime import datetime, timedelta
import bcrypt
import argon2
from argon2 import PasswordHasher
import zlib
import qrcode
from io import BytesIO
import pyotp
import qrcode.image.svg

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_ENCODING = 'utf-8'
DEFAULT_HASH_ALGORITHM = 'sha256'
DEFAULT_SALT_LENGTH = 32
DEFAULT_ITERATIONS = 100000
DEFAULT_KEY_LENGTH = 32
DEFAULT_BLOCK_SIZE = 128

# ============================================================
# HASH UTILITIES
# ============================================================

class HashUtils:
    """Utilitaires de hachage"""
    
    @staticmethod
    def hash_sha256(data: Union[str, bytes]) -> str:
        """
        Hash SHA-256
        
        Args:
            data: Données à hacher
            
        Returns:
            str: Hash hexadécimal
        """
        if isinstance(data, str):
            data = data.encode(DEFAULT_ENCODING)
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def hash_sha512(data: Union[str, bytes]) -> str:
        """
        Hash SHA-512
        
        Args:
            data: Données à hacher
            
        Returns:
            str: Hash hexadécimal
        """
        if isinstance(data, str):
            data = data.encode(DEFAULT_ENCODING)
        return hashlib.sha512(data).hexdigest()
    
    @staticmethod
    def hash_md5(data: Union[str, bytes]) -> str:
        """
        Hash MD5
        
        Args:
            data: Données à hacher
            
        Returns:
            str: Hash hexadécimal
        """
        if isinstance(data, str):
            data = data.encode(DEFAULT_ENCODING)
        return hashlib.md5(data).hexdigest()
    
    @staticmethod
    def hash_blake2(data: Union[str, bytes], digest_size: int = 32) -> str:
        """
        Hash BLAKE2
        
        Args:
            data: Données à hacher
            digest_size: Taille du digest
            
        Returns:
            str: Hash hexadécimal
        """
        if isinstance(data, str):
            data = data.encode(DEFAULT_ENCODING)
        return hashlib.blake2b(data, digest_size=digest_size).hexdigest()
    
    @staticmethod
    def hash_keccak(data: Union[str, bytes], digest_size: int = 256) -> str:
        """
        Hash Keccak (SHA-3)
        
        Args:
            data: Données à hacher
            digest_size: Taille du digest
            
        Returns:
            str: Hash hexadécimal
        """
        if isinstance(data, str):
            data = data.encode(DEFAULT_ENCODING)
        return hashlib.shake_256(data).hexdigest(digest_size // 8)
    
    @staticmethod
    def hmac_sha256(key: Union[str, bytes], data: Union[str, bytes]) -> str:
        """
        HMAC SHA-256
        
        Args:
            key: Clé HMAC
            data: Données à hacher
            
        Returns:
            str: HMAC hexadécimal
        """
        if isinstance(key, str):
            key = key.encode(DEFAULT_ENCODING)
        if isinstance(data, str):
            data = data.encode(DEFAULT_ENCODING)
        return hmac.new(key, data, hashlib.sha256).hexdigest()
    
    @staticmethod
    def hmac_sha512(key: Union[str, bytes], data: Union[str, bytes]) -> str:
        """
        HMAC SHA-512
        
        Args:
            key: Clé HMAC
            data: Données à hacher
            
        Returns:
            str: HMAC hexadécimal
        """
        if isinstance(key, str):
            key = key.encode(DEFAULT_ENCODING)
        if isinstance(data, str):
            data = data.encode(DEFAULT_ENCODING)
        return hmac.new(key, data, hashlib.sha512).hexdigest()
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Hash un mot de passe avec bcrypt
        
        Args:
            password: Mot de passe à hacher
            salt: Sel optionnel
            
        Returns:
            Tuple[str, str]: (hash, salt)
        """
        if salt is None:
            salt = secrets.token_hex(DEFAULT_SALT_LENGTH)
        
        salt_bytes = salt.encode(DEFAULT_ENCODING) if isinstance(salt, str) else salt
        password_bytes = password.encode(DEFAULT_ENCODING)
        
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
        return hashed.decode(DEFAULT_ENCODING), salt
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Vérifie un mot de passe avec bcrypt
        
        Args:
            password: Mot de passe à vérifier
            hashed_password: Hash à vérifier
            
        Returns:
            bool: True si le mot de passe correspond
        """
        password_bytes = password.encode(DEFAULT_ENCODING)
        hashed_bytes = hashed_password.encode(DEFAULT_ENCODING)
        
        try:
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception:
            return False
    
    @staticmethod
    def hash_password_argon2(password: str) -> str:
        """
        Hash un mot de passe avec Argon2
        
        Args:
            password: Mot de passe à hacher
            
        Returns:
            str: Hash
        """
        ph = PasswordHasher()
        return ph.hash(password)
    
    @staticmethod
    def verify_password_argon2(password: str, hashed_password: str) -> bool:
        """
        Vérifie un mot de passe avec Argon2
        
        Args:
            password: Mot de passe à vérifier
            hashed_password: Hash à vérifier
            
        Returns:
            bool: True si le mot de passe correspond
        """
        ph = PasswordHasher()
        try:
            ph.verify(hashed_password, password)
            return True
        except argon2.exceptions.VerificationError:
            return False


# ============================================================
# ENCRYPTION UTILITIES
# ============================================================

class EncryptionUtils:
    """Utilitaires de chiffrement"""
    
    @staticmethod
    def generate_key() -> bytes:
        """
        Génère une clé Fernet
        
        Returns:
            bytes: Clé Fernet
        """
        return Fernet.generate_key()
    
    @staticmethod
    def encrypt_fernet(data: Union[str, bytes], key: bytes) -> bytes:
        """
        Chiffre des données avec Fernet
        
        Args:
            data: Données à chiffrer
            key: Clé Fernet
            
        Returns:
            bytes: Données chiffrées
        """
        if isinstance(data, str):
            data = data.encode(DEFAULT_ENCODING)
        
        f = Fernet(key)
        return f.encrypt(data)
    
    @staticmethod
    def decrypt_fernet(data: bytes, key: bytes) -> bytes:
        """
        Déchiffre des données avec Fernet
        
        Args:
            data: Données chiffrées
            key: Clé Fernet
            
        Returns:
            bytes: Données déchiffrées
        """
        f = Fernet(key)
        return f.decrypt(data)
    
    @staticmethod
    def encrypt_aes(data: Union[str, bytes], key: bytes, iv: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """
        Chiffre des données avec AES-CBC
        
        Args:
            data: Données à chiffrer
            key: Clé AES (32 bytes pour AES-256)
            iv: Vecteur d'initialisation
            
        Returns:
            Tuple[bytes, bytes]: (données chiffrées, iv)
        """
        if isinstance(data, str):
            data = data.encode(DEFAULT_ENCODING)
        
        if iv is None:
            iv = os.urandom(16)
        
        # Padding des données
        padder = sym_padding.PKCS7(DEFAULT_BLOCK_SIZE).padder()
        padded_data = padder.update(data) + padder.finalize()
        
        # Chiffrement
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        
        return encrypted, iv
    
    @staticmethod
    def decrypt_aes(data: bytes, key: bytes, iv: bytes) -> bytes:
        """
        Déchiffre des données avec AES-CBC
        
        Args:
            data: Données chiffrées
            key: Clé AES
            iv: Vecteur d'initialisation
            
        Returns:
            bytes: Données déchiffrées
        """
        # Déchiffrement
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(data) + decryptor.finalize()
        
        # Retirer le padding
        unpadder = sym_padding.PKCS7(DEFAULT_BLOCK_SIZE).unpadder()
        return unpadder.update(decrypted) + unpadder.finalize()
    
    @staticmethod
    def derive_key(password: str, salt: Optional[bytes] = None, iterations: int = DEFAULT_ITERATIONS) -> Tuple[bytes, bytes]:
        """
        Dérive une clé à partir d'un mot de passe avec PBKDF2
        
        Args:
            password: Mot de passe
            salt: Sel
            iterations: Nombre d'itérations
            
        Returns:
            Tuple[bytes, bytes]: (clé, sel)
        """
        if salt is None:
            salt = os.urandom(DEFAULT_SALT_LENGTH)
        
        password_bytes = password.encode(DEFAULT_ENCODING)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=DEFAULT_KEY_LENGTH,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        key = kdf.derive(password_bytes)
        
        return key, salt
    
    @staticmethod
    def derive_key_scrypt(
        password: str,
        salt: Optional[bytes] = None,
        n: int = 16384,
        r: int = 8,
        p: int = 1
    ) -> Tuple[bytes, bytes]:
        """
        Dérive une clé à partir d'un mot de passe avec Scrypt
        
        Args:
            password: Mot de passe
            salt: Sel
            n: Paramètre CPU/mémoire
            r: Paramètre de taille de bloc
            p: Paramètre de parallélisme
            
        Returns:
            Tuple[bytes, bytes]: (clé, sel)
        """
        if salt is None:
            salt = os.urandom(DEFAULT_SALT_LENGTH)
        
        password_bytes = password.encode(DEFAULT_ENCODING)
        
        kdf = Scrypt(
            salt=salt,
            length=DEFAULT_KEY_LENGTH,
            n=n,
            r=r,
            p=p,
            backend=default_backend()
        )
        key = kdf.derive(password_bytes)
        
        return key, salt
    
    @staticmethod
    def generate_rsa_keypair(key_size: int = 2048) -> Tuple[bytes, bytes]:
        """
        Génère une paire de clés RSA
        
        Args:
            key_size: Taille de la clé
            
        Returns:
            Tuple[bytes, bytes]: (clé privée, clé publique)
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_key = private_key.public_key()
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return private_bytes, public_bytes
    
    @staticmethod
    def encrypt_rsa(data: Union[str, bytes], public_key_pem: bytes) -> bytes:
        """
        Chiffre des données avec RSA
        
        Args:
            data: Données à chiffrer
            public_key_pem: Clé publique PEM
            
        Returns:
            bytes: Données chiffrées
        """
        if isinstance(data, str):
            data = data.encode(DEFAULT_ENCODING)
        
        public_key = load_pem_public_key(public_key_pem, backend=default_backend())
        
        encrypted = public_key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return encrypted
    
    @staticmethod
    def decrypt_rsa(data: bytes, private_key_pem: bytes) -> bytes:
        """
        Déchiffre des données avec RSA
        
        Args:
            data: Données chiffrées
            private_key_pem: Clé privée PEM
            
        Returns:
            bytes: Données déchiffrées
        """
        private_key = load_pem_private_key(
            private_key_pem,
            password=None,
            backend=default_backend()
        )
        
        decrypted = private_key.decrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return decrypted
    
    @staticmethod
    def sign_rsa(data: Union[str, bytes], private_key_pem: bytes) -> bytes:
        """
        Signe des données avec RSA
        
        Args:
            data: Données à signer
            private_key_pem: Clé privée PEM
            
        Returns:
            bytes: Signature
        """
        if isinstance(data, str):
            data = data.encode(DEFAULT_ENCODING)
        
        private_key = load_pem_private_key(
            private_key_pem,
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
        
        return signature
    
    @staticmethod
    def verify_rsa(data: Union[str, bytes], signature: bytes, public_key_pem: bytes) -> bool:
        """
        Vérifie une signature RSA
        
        Args:
            data: Données signées
            signature: Signature
            public_key_pem: Clé publique PEM
            
        Returns:
            bool: True si la signature est valide
        """
        if isinstance(data, str):
            data = data.encode(DEFAULT_ENCODING)
        
        public_key = load_pem_public_key(public_key_pem, backend=default_backend())
        
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


# ============================================================
# JWT UTILITIES
# ============================================================

class JWTUtils:
    """Utilitaires JWT"""
    
    @staticmethod
    def generate_token(
        data: Dict[str, Any],
        secret: str,
        algorithm: str = 'HS256',
        expires_in: int = 3600
    ) -> str:
        """
        Génère un token JWT
        
        Args:
            data: Données à inclure
            secret: Clé secrète
            algorithm: Algorithme
            expires_in: Durée de validité en secondes
            
        Returns:
            str: Token JWT
        """
        payload = {
            **data,
            'exp': datetime.utcnow() + timedelta(seconds=expires_in),
            'iat': datetime.utcnow(),
        }
        
        return jwt.encode(payload, secret, algorithm=algorithm)
    
    @staticmethod
    def decode_token(
        token: str,
        secret: str,
        algorithms: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Décode un token JWT
        
        Args:
            token: Token JWT
            secret: Clé secrète
            algorithms: Algorithmes autorisés
            
        Returns:
            Optional[Dict[str, Any]]: Données décodées
        """
        if algorithms is None:
            algorithms = ['HS256', 'HS384', 'HS512']
        
        try:
            return jwt.decode(token, secret, algorithms=algorithms)
        except PyJWTError as e:
            logger.error(f"JWT decode error: {e}")
            return None
    
    @staticmethod
    def get_token_expiry(token: str, secret: str) -> Optional[datetime]:
        """
        Récupère la date d'expiration d'un token
        
        Args:
            token: Token JWT
            secret: Clé secrète
            
        Returns:
            Optional[datetime]: Date d'expiration
        """
        decoded = JWTUtils.decode_token(token, secret)
        if decoded and 'exp' in decoded:
            return datetime.fromtimestamp(decoded['exp'])
        return None
    
    @staticmethod
    def is_token_valid(token: str, secret: str) -> bool:
        """
        Vérifie si un token est valide
        
        Args:
            token: Token JWT
            secret: Clé secrète
            
        Returns:
            bool: True si le token est valide
        """
        decoded = JWTUtils.decode_token(token, secret)
        return decoded is not None


# ============================================================
# OTP UTILITIES
# ============================================================

class OTPUtils:
    """Utilitaires OTP (One-Time Password)"""
    
    @staticmethod
    def generate_totp_secret() -> str:
        """
        Génère un secret TOTP
        
        Returns:
            str: Secret TOTP
        """
        return pyotp.random_base32()
    
    @staticmethod
    def generate_totp(secret: str, interval: int = 30) -> str:
        """
        Génère un code TOTP
        
        Args:
            secret: Secret TOTP
            interval: Intervalle en secondes
            
        Returns:
            str: Code TOTP
        """
        totp = pyotp.TOTP(secret, interval=interval)
        return totp.now()
    
    @staticmethod
    def verify_totp(secret: str, code: str, interval: int = 30) -> bool:
        """
        Vérifie un code TOTP
        
        Args:
            secret: Secret TOTP
            code: Code à vérifier
            interval: Intervalle en secondes
            
        Returns:
            bool: True si le code est valide
        """
        totp = pyotp.TOTP(secret, interval=interval)
        return totp.verify(code)
    
    @staticmethod
    def generate_totp_qr(secret: str, issuer: str, account_name: str) -> str:
        """
        Génère un QR code TOTP
        
        Args:
            secret: Secret TOTP
            issuer: Émetteur
            account_name: Nom du compte
            
        Returns:
            str: QR code en SVG
        """
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(account_name, issuer_name=issuer)
        
        qr = qrcode.make(provisioning_uri, image_factory=qrcode.image.svg.SvgImage)
        return qr.to_string().decode(DEFAULT_ENCODING)
    
    @staticmethod
    def generate_hotp_secret() -> str:
        """
        Génère un secret HOTP
        
        Returns:
            str: Secret HOTP
        """
        return pyotp.random_base32()
    
    @staticmethod
    def generate_hotp(secret: str, counter: int) -> str:
        """
        Génère un code HOTP
        
        Args:
            secret: Secret HOTP
            counter: Compteur
            
        Returns:
            str: Code HOTP
        """
        hotp = pyotp.HOTP(secret)
        return hotp.at(counter)
    
    @staticmethod
    def verify_hotp(secret: str, code: str, counter: int) -> bool:
        """
        Vérifie un code HOTP
        
        Args:
            secret: Secret HOTP
            code: Code à vérifier
            counter: Compteur
            
        Returns:
            bool: True si le code est valide
        """
        hotp = pyotp.HOTP(secret)
        return hotp.verify(code, counter)


# ============================================================
# RANDOM UTILITIES
# ============================================================

class RandomUtils:
    """Utilitaires aléatoires sécurisés"""
    
    @staticmethod
    def random_bytes(length: int = 32) -> bytes:
        """
        Génère des bytes aléatoires sécurisés
        
        Args:
            length: Nombre de bytes
            
        Returns:
            bytes: Bytes aléatoires
        """
        return os.urandom(length)
    
    @staticmethod
    def random_hex(length: int = 32) -> str:
        """
        Génère une chaîne hexadécimale aléatoire
        
        Args:
            length: Longueur en bytes
            
        Returns:
            str: Chaîne hexadécimale
        """
        return secrets.token_hex(length)
    
    @staticmethod
    def random_urlsafe(length: int = 32) -> str:
        """
        Génère une chaîne aléatoire URL-safe
        
        Args:
            length: Longueur en bytes
            
        Returns:
            str: Chaîne aléatoire
        """
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def random_password(length: int = 16, include_special: bool = True) -> str:
        """
        Génère un mot de passe aléatoire sécurisé
        
        Args:
            length: Longueur
            include_special: Inclure des caractères spéciaux
            
        Returns:
            str: Mot de passe
        """
        characters = string.ascii_letters + string.digits
        if include_special:
            characters += string.punctuation
        
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    @staticmethod
    def random_uuid() -> str:
        """
        Génère un UUID v4
        
        Returns:
            str: UUID
        """
        return str(uuid.uuid4())
    
    @staticmethod
    def random_int(min_value: int = 0, max_value: int = 100) -> int:
        """
        Génère un entier aléatoire sécurisé
        
        Args:
            min_value: Valeur minimale
            max_value: Valeur maximale
            
        Returns:
            int: Entier aléatoire
        """
        return secrets.randbelow(max_value - min_value + 1) + min_value
    
    @staticmethod
    def random_float(min_value: float = 0.0, max_value: float = 1.0) -> float:
        """
        Génère un flottant aléatoire sécurisé
        
        Args:
            min_value: Valeur minimale
            max_value: Valeur maximale
            
        Returns:
            float: Flottant aléatoire
        """
        return min_value + (max_value - min_value) * secrets.randbits(53) / (2 ** 53)


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Classes
    'HashUtils',
    'EncryptionUtils',
    'JWTUtils',
    'OTPUtils',
    'RandomUtils',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Crypto utilities module initialized")
