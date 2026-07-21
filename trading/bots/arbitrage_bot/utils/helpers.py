"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Helpers Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Helpers génériques pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import os
import sys
import json
import inspect
import hashlib
import random
import string
import re
import uuid
import base64
import zlib
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    Callable,
    TypeVar,
    Generic,
    Iterator,
    Generator,
    Set,
    FrozenSet,
    Sequence,
    Mapping,
    MutableMapping,
    Iterable,
    Container,
    Sized,
    Collection,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Coroutine,
    Type,
    overload
)
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, date, time, timedelta
from functools import wraps, partial, lru_cache
from contextlib import contextmanager, asynccontextmanager
import threading
import asyncio
import signal
import warnings
import collections
from collections.abc import Iterable as IterableABC
from itertools import chain, cycle, islice, groupby, zip_longest, count, repeat

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# TYPE VARIABLES
# ============================================================
T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')
R = TypeVar('R')

# ============================================================
# ID GENERATORS
# ============================================================

class IDGenerator:
    """Générateur d'identifiants"""
    
    @staticmethod
    def generate_uuid() -> str:
        """Génère un UUID v4"""
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_uuid_hex() -> str:
        """Génère un UUID v4 en hexadécimal"""
        return uuid.uuid4().hex
    
    @staticmethod
    def generate_uuid_int() -> int:
        """Génère un UUID v4 en entier"""
        return uuid.uuid4().int
    
    @staticmethod
    def generate_id(prefix: str = '', suffix: str = '', length: int = 8) -> str:
        """
        Génère un ID aléatoire
        
        Args:
            prefix: Préfixe
            suffix: Suffixe
            length: Longueur
            
        Returns:
            str: ID généré
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        return f"{prefix}{timestamp}{random_part}{suffix}"
    
    @staticmethod
    def generate_order_id(prefix: str = 'ORD', suffix: str = '') -> str:
        """
        Génère un ID de commande
        
        Args:
            prefix: Préfixe
            suffix: Suffixe
            
        Returns:
            str: ID de commande
        """
        return IDGenerator.generate_id(prefix=prefix, suffix=suffix, length=6)
    
    @staticmethod
    def generate_trade_id(prefix: str = 'TRD', suffix: str = '') -> str:
        """
        Génère un ID de trade
        
        Args:
            prefix: Préfixe
            suffix: Suffixe
            
        Returns:
            str: ID de trade
        """
        return IDGenerator.generate_id(prefix=prefix, suffix=suffix, length=8)
    
    @staticmethod
    def generate_position_id(prefix: str = 'POS', suffix: str = '') -> str:
        """
        Génère un ID de position
        
        Args:
            prefix: Préfixe
            suffix: Suffixe
            
        Returns:
            str: ID de position
        """
        return IDGenerator.generate_id(prefix=prefix, suffix=suffix, length=8)
    
    @staticmethod
    def generate_alert_id(prefix: str = 'ALT', suffix: str = '') -> str:
        """
        Génère un ID d'alerte
        
        Args:
            prefix: Préfixe
            suffix: Suffixe
            
        Returns:
            str: ID d'alerte
        """
        return IDGenerator.generate_id(prefix=prefix, suffix=suffix, length=8)
    
    @staticmethod
    def generate_session_id() -> str:
        """
        Génère un ID de session
        
        Returns:
            str: ID de session
        """
        return IDGenerator.generate_id(prefix='SESS_', length=12)
    
    @staticmethod
    def generate_api_key() -> str:
        """
        Génère une clé API
        
        Returns:
            str: Clé API
        """
        return base64.urlsafe_b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes).decode('utf-8').rstrip('=')

# ============================================================
# HASH HELPERS
# ============================================================

class HashHelpers:
    """Helpers de hachage"""
    
    @staticmethod
    def hash_string(value: str, algorithm: str = 'sha256') -> str:
        """
        Hash une chaîne
        
        Args:
            value: Chaîne à hacher
            algorithm: Algorithme de hash
            
        Returns:
            str: Hash
        """
        if algorithm == 'md5':
            return hashlib.md5(value.encode()).hexdigest()
        elif algorithm == 'sha1':
            return hashlib.sha1(value.encode()).hexdigest()
        elif algorithm == 'sha256':
            return hashlib.sha256(value.encode()).hexdigest()
        elif algorithm == 'sha512':
            return hashlib.sha512(value.encode()).hexdigest()
        else:
            return hashlib.sha256(value.encode()).hexdigest()
    
    @staticmethod
    def hash_dict(data: Dict[str, Any], algorithm: str = 'sha256') -> str:
        """
        Hash un dictionnaire
        
        Args:
            data: Dictionnaire à hacher
            algorithm: Algorithme de hash
            
        Returns:
            str: Hash
        """
        # Trier les clés pour la cohérence
        sorted_data = {k: data[k] for k in sorted(data.keys())}
        json_str = json.dumps(sorted_data, sort_keys=True, default=str)
        return HashHelpers.hash_string(json_str, algorithm)
    
    @staticmethod
    def hash_file(filepath: str, algorithm: str = 'sha256') -> str:
        """
        Hash un fichier
        
        Args:
            filepath: Chemin du fichier
            algorithm: Algorithme de hash
            
        Returns:
            str: Hash
        """
        hash_func = hashlib.new(algorithm)
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    
    @staticmethod
    def create_checksum(data: Union[str, bytes]) -> str:
        """
        Crée une checksum
        
        Args:
            data: Données
            
        Returns:
            str: Checksum
        """
        if isinstance(data, str):
            data = data.encode()
        return base64.b64encode(zlib.crc32(data).to_bytes(4, 'big')).decode()

# ============================================================
# VALIDATION HELPERS
# ============================================================

class ValidationHelpers:
    """Helpers de validation"""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Vérifie si une adresse email est valide"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def is_valid_phone(phone: str) -> bool:
        """Vérifie si un numéro de téléphone est valide"""
        pattern = r'^\+?[1-9]\d{1,14}$'
        return bool(re.match(pattern, phone))
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Vérifie si une URL est valide"""
        pattern = r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/]?'
        return bool(re.match(pattern, url))
    
    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """Vérifie si une adresse IP est valide"""
        pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        return bool(re.match(pattern, ip))
    
    @staticmethod
    def is_valid_date(date_str: str) -> bool:
        """Vérifie si une chaîne est une date valide"""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_valid_datetime(dt_str: str) -> bool:
        """Vérifie si une chaîne est une date/heure valide"""
        try:
            datetime.fromisoformat(dt_str)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_valid_uuid(uuid_str: str) -> bool:
        """Vérifie si une chaîne est un UUID valide"""
        try:
            uuid.UUID(uuid_str)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_valid_json(json_str: str) -> bool:
        """Vérifie si une chaîne est du JSON valide"""
        try:
            json.loads(json_str)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_valid_hex(hex_str: str) -> bool:
        """Vérifie si une chaîne est hexadécimale"""
        return all(c in string.hexdigits for c in hex_str)
    
    @staticmethod
    def is_valid_base64(b64_str: str) -> bool:
        """Vérifie si une chaîne est en base64"""
        try:
            base64.b64decode(b64_str, validate=True)
            return True
        except Exception:
            return False

# ============================================================
# STRING HELPERS
# ============================================================

class StringHelpers:
    """Helpers de chaînes"""
    
    @staticmethod
    def truncate(value: str, length: int = 100, suffix: str = '...') -> str:
        """
        Tronque une chaîne
        
        Args:
            value: Chaîne à tronquer
            length: Longueur maximale
            suffix: Suffixe
            
        Returns:
            str: Chaîne tronquée
        """
        if len(value) <= length:
            return value
        return value[:length - len(suffix)] + suffix
    
    @staticmethod
    def slugify(value: str, separator: str = '-', lower: bool = True) -> str:
        """
        Convertit en slug
        
        Args:
            value: Chaîne à convertir
            separator: Séparateur
            lower: Mettre en minuscules
            
        Returns:
            str: Slug
        """
        # Normaliser unicode
        value = ''.join(
            c for c in unicodedata.normalize('NFKD', value)
            if not unicodedata.combining(c)
        )
        
        # Remplacer les caractères non alphanumériques
        value = re.sub(r'[^a-zA-Z0-9]+', separator, value)
        
        # Supprimer les séparateurs en début/fin
        value = value.strip(separator)
        
        if lower:
            value = value.lower()
        
        return value
    
    @staticmethod
    def camel_to_snake(value: str) -> str:
        """Convertit du camelCase en snake_case"""
        value = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', value)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', value).lower()
    
    @staticmethod
    def snake_to_camel(value: str) -> str:
        """Convertit du snake_case en camelCase"""
        components = value.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])
    
    @staticmethod
    def snake_to_pascal(value: str) -> str:
        """Convertit du snake_case en PascalCase"""
        return ''.join(x.title() for x in value.split('_'))
    
    @staticmethod
    def extract_numbers(value: str) -> List[float]:
        """Extrait les nombres d'une chaîne"""
        return [float(x) for x in re.findall(r'[-+]?\d*\.?\d+', value)]
    
    @staticmethod
    def extract_words(value: str) -> List[str]:
        """Extrait les mots d'une chaîne"""
        return re.findall(r'[a-zA-Z]+', value)

# ============================================================
# DICT HELPERS
# ============================================================

class DictHelpers:
    """Helpers de dictionnaires"""
    
    @staticmethod
    def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fusionne deux dictionnaires en profondeur
        
        Args:
            dict1: Dictionnaire de base
            dict2: Dictionnaire à fusionner
            
        Returns:
            Dict[str, Any]: Dictionnaire fusionné
        """
        result = dict1.copy()
        
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = DictHelpers.deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def deep_get(dictionary: Dict[str, Any], path: str, default: Any = None) -> Any:
        """
        Récupère une valeur en profondeur
        
        Args:
            dictionary: Dictionnaire
            path: Chemin (ex: "a.b.c")
            default: Valeur par défaut
            
        Returns:
            Any: Valeur trouvée
        """
        parts = path.split('.')
        current = dictionary
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        
        return current
    
    @staticmethod
    def deep_set(dictionary: Dict[str, Any], path: str, value: Any):
        """
        Définit une valeur en profondeur
        
        Args:
            dictionary: Dictionnaire
            path: Chemin (ex: "a.b.c")
            value: Valeur à définir
        """
        parts = path.split('.')
        current = dictionary
        
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
    
    @staticmethod
    def deep_update(dictionary: Dict[str, Any], path: str, value: Any):
        """
        Met à jour une valeur en profondeur
        
        Args:
            dictionary: Dictionnaire
            path: Chemin (ex: "a.b.c")
            value: Valeur à mettre à jour
        """
        parts = path.split('.')
        current = dictionary
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        if isinstance(current.get(parts[-1]), dict) and isinstance(value, dict):
            current[parts[-1]] = DictHelpers.deep_merge(current[parts[-1]], value)
        else:
            current[parts[-1]] = value
    
    @staticmethod
    def flatten(dictionary: Dict[str, Any], parent_key: str = '', separator: str = '.') -> Dict[str, Any]:
        """
        Aplatit un dictionnaire
        
        Args:
            dictionary: Dictionnaire à aplatir
            parent_key: Clé parent
            separator: Séparateur
            
        Returns:
            Dict[str, Any]: Dictionnaire aplati
        """
        items = []
        
        for key, value in dictionary.items():
            new_key = f"{parent_key}{separator}{key}" if parent_key else key
            
            if isinstance(value, dict):
                items.extend(DictHelpers.flatten(value, new_key, separator).items())
            else:
                items.append((new_key, value))
        
        return dict(items)
    
    @staticmethod
    def unflatten(flat_dict: Dict[str, Any], separator: str = '.') -> Dict[str, Any]:
        """
        Dé-aplatit un dictionnaire
        
        Args:
            flat_dict: Dictionnaire aplati
            separator: Séparateur
            
        Returns:
            Dict[str, Any]: Dictionnaire dé-aplati
        """
        result = {}
        
        for key, value in flat_dict.items():
            parts = key.split(separator)
            current = result
            
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[parts[-1]] = value
        
        return result

# ============================================================
# LIST HELPERS
# ============================================================

class ListHelpers:
    """Helpers de listes"""
    
    @staticmethod
    def chunk(lst: List[T], size: int) -> List[List[T]]:
        """
        Divise une liste en morceaux
        
        Args:
            lst: Liste à diviser
            size: Taille des morceaux
            
        Returns:
            List[List[T]]: Liste de morceaux
        """
        return [lst[i:i + size] for i in range(0, len(lst), size)]
    
    @staticmethod
    def unique(lst: List[T], key: Optional[Callable[[T], Any]] = None) -> List[T]:
        """
        Supprime les doublons d'une liste
        
        Args:
            lst: Liste
            key: Fonction de clé
            
        Returns:
            List[T]: Liste sans doublons
        """
        seen = set()
        result = []
        
        for item in lst:
            item_key = key(item) if key else item
            if item_key not in seen:
                seen.add(item_key)
                result.append(item)
        
        return result
    
    @staticmethod
    def flatten(lst: List[Any]) -> List[Any]:
        """
        Aplatit une liste de listes
        
        Args:
            lst: Liste à aplatir
            
        Returns:
            List[Any]: Liste aplatie
        """
        result = []
        
        for item in lst:
            if isinstance(item, list):
                result.extend(ListHelpers.flatten(item))
            else:
                result.append(item)
        
        return result
    
    @staticmethod
    def group_by(lst: List[T], key_func: Callable[[T], Any]) -> Dict[Any, List[T]]:
        """
        Groupe une liste par une clé
        
        Args:
            lst: Liste
            key_func: Fonction de clé
            
        Returns:
            Dict[Any, List[T]]: Dictionnaire groupé
        """
        result = {}
        
        for item in lst:
            key = key_func(item)
            if key not in result:
                result[key] = []
            result[key].append(item)
        
        return result

# ============================================================
# CONTEXT HELPERS
# ============================================================

class ContextHelpers:
    """Helpers de contexte"""
    
    @staticmethod
    @contextmanager
    def timed(operation: str = "Operation"):
        """
        Context manager pour mesurer le temps
        
        Args:
            operation: Nom de l'opération
            
        Yields:
            None
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            logger.debug(f"{operation} completed in {elapsed:.3f}s")
    
    @staticmethod
    @contextmanager
    def suppress(*exceptions: Type[Exception]):
        """
        Context manager pour supprimer des exceptions
        
        Args:
            exceptions: Exceptions à supprimer
            
        Yields:
            None
        """
        try:
            yield
        except exceptions:
            pass
    
    @staticmethod
    @contextmanager
    def temp_env_var(key: str, value: str):
        """
        Context manager pour une variable d'environnement temporaire
        
        Args:
            key: Nom de la variable
            value: Valeur temporaire
            
        Yields:
            None
        """
        old_value = os.environ.get(key)
        os.environ[key] = value
        try:
            yield
        finally:
            if old_value is None:
                del os.environ[key]
            else:
                os.environ[key] = old_value
    
    @staticmethod
    @contextmanager
    def temp_sys_path(path: str):
        """
        Context manager pour un chemin sys.path temporaire
        
        Args:
            path: Chemin à ajouter
            
        Yields:
            None
        """
        sys.path.insert(0, path)
        try:
            yield
        finally:
            sys.path.remove(path)

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Classes
    'IDGenerator',
    'HashHelpers',
    'ValidationHelpers',
    'StringHelpers',
    'DictHelpers',
    'ListHelpers',
    'ContextHelpers',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Helpers utilities module initialized")
