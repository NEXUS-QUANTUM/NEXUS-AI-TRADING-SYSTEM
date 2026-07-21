"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot String Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de chaînes pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import re
import json
import html
import xml
import base64
import hashlib
import zlib
import textwrap
import unicodedata
import string
import random
import uuid
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
    Generator
)
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import difflib
import Levenshtein
import phonetics
import inflect

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# TYPE VARIABLES
# ============================================================
T = TypeVar('T')
R = TypeVar('R')

# ============================================================
# ENUMS
# ============================================================

class CaseType(Enum):
    """Types de cas"""
    CAMEL = "camel"
    PASCAL = "pascal"
    SNAKE = "snake"
    KEBAB = "kebab"
    CONSTANT = "constant"
    TITLE = "title"
    LOWER = "lower"
    UPPER = "upper"

class StringFilter(Enum):
    """Filtres de chaînes"""
    ALPHANUMERIC = "alphanumeric"
    ALPHA = "alpha"
    NUMERIC = "numeric"
    ASCII = "ascii"
    PRINTABLE = "printable"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"
    HEX = "hex"
    BASE64 = "base64"

# ============================================================
# STRING UTILITIES
# ============================================================

class StringUtils:
    """Utilitaires de chaînes"""
    
    @staticmethod
    def truncate(
        value: str,
        length: int = 100,
        suffix: str = "...",
        middle: bool = False
    ) -> str:
        """
        Tronque une chaîne
        
        Args:
            value: Chaîne à tronquer
            length: Longueur maximale
            suffix: Suffixe
            middle: Tronquer au milieu
            
        Returns:
            str: Chaîne tronquée
        """
        if not value or len(value) <= length:
            return value
        
        if middle:
            half = (length - len(suffix)) // 2
            return value[:half] + suffix + value[-half:]
        else:
            return value[:length - len(suffix)] + suffix
    
    @staticmethod
    def truncate_words(value: str, word_count: int = 20, suffix: str = "...") -> str:
        """
        Tronque par mots
        
        Args:
            value: Chaîne à tronquer
            word_count: Nombre de mots
            suffix: Suffixe
            
        Returns:
            str: Chaîne tronquée
        """
        if not value:
            return ""
        
        words = value.split()
        if len(words) <= word_count:
            return value
        
        return " ".join(words[:word_count]) + suffix
    
    @staticmethod
    def normalize(
        value: str,
        form: str = 'NFKC',
        strip_accents: bool = True,
        strip_punctuation: bool = False
    ) -> str:
        """
        Normalise une chaîne
        
        Args:
            value: Chaîne à normaliser
            form: Forme de normalisation ('NFC', 'NFD', 'NFKC', 'NFKD')
            strip_accents: Supprimer les accents
            strip_punctuation: Supprimer la ponctuation
            
        Returns:
            str: Chaîne normalisée
        """
        if not value:
            return ""
        
        # Normaliser unicode
        value = unicodedata.normalize(form, value)
        
        # Supprimer les accents
        if strip_accents:
            value = ''.join(
                c for c in unicodedata.normalize('NFKD', value)
                if not unicodedata.combining(c)
            )
        
        # Supprimer la ponctuation
        if strip_punctuation:
            value = re.sub(r'[^\w\s]', '', value)
        
        return value
    
    @staticmethod
    def slugify(
        value: str,
        separator: str = '-',
        lower: bool = True,
        strip_accents: bool = True
    ) -> str:
        """
        Convertit en slug
        
        Args:
            value: Chaîne à convertir
            separator: Séparateur
            lower: Mettre en minuscules
            strip_accents: Supprimer les accents
            
        Returns:
            str: Slug
        """
        if not value:
            return ""
        
        # Normaliser
        value = StringUtils.normalize(value, strip_accents=strip_accents)
        
        # Remplacer les caractères non alphanumériques
        value = re.sub(r'[^a-zA-Z0-9]+', separator, value)
        
        # Supprimer les séparateurs en début/fin
        value = value.strip(separator)
        
        if lower:
            value = value.lower()
        
        return value
    
    @staticmethod
    def to_case(value: str, case_type: CaseType) -> str:
        """
        Convertit en cas spécifique
        
        Args:
            value: Chaîne à convertir
            case_type: Type de cas
            
        Returns:
            str: Chaîne convertie
        """
        if not value:
            return ""
        
        # Nettoyer la chaîne
        cleaned = re.sub(r'[^a-zA-Z0-9]+', ' ', value).strip()
        
        if case_type == CaseType.CAMEL:
            words = cleaned.split()
            return words[0].lower() + ''.join(w.capitalize() for w in words[1:])
        
        elif case_type == CaseType.PASCAL:
            return ''.join(w.capitalize() for w in cleaned.split())
        
        elif case_type == CaseType.SNAKE:
            return '_'.join(w.lower() for w in cleaned.split())
        
        elif case_type == CaseType.KEBAB:
            return '-'.join(w.lower() for w in cleaned.split())
        
        elif case_type == CaseType.CONSTANT:
            return '_'.join(w.upper() for w in cleaned.split())
        
        elif case_type == CaseType.TITLE:
            return ' '.join(w.capitalize() for w in cleaned.split())
        
        elif case_type == CaseType.LOWER:
            return cleaned.lower()
        
        elif case_type == CaseType.UPPER:
            return cleaned.upper()
        
        return value
    
    @staticmethod
    def camel_to_snake(value: str) -> str:
        """Convertit du camelCase en snake_case"""
        return StringUtils.to_case(value, CaseType.SNAKE)
    
    @staticmethod
    def snake_to_camel(value: str) -> str:
        """Convertit du snake_case en camelCase"""
        return StringUtils.to_case(value, CaseType.CAMEL)
    
    @staticmethod
    def snake_to_pascal(value: str) -> str:
        """Convertit du snake_case en PascalCase"""
        return StringUtils.to_case(value, CaseType.PASCAL)
    
    @staticmethod
    def extract_numbers(value: str) -> List[float]:
        """
        Extrait les nombres d'une chaîne
        
        Args:
            value: Chaîne à analyser
            
        Returns:
            List[float]: Liste des nombres
        """
        if not value:
            return []
        
        pattern = r'[-+]?\d*\.?\d+'
        return [float(m) for m in re.findall(pattern, value)]
    
    @staticmethod
    def extract_words(value: str) -> List[str]:
        """
        Extrait les mots d'une chaîne
        
        Args:
            value: Chaîne à analyser
            
        Returns:
            List[str]: Liste des mots
        """
        if not value:
            return []
        
        return re.findall(r'[a-zA-Z]+', value)
    
    @staticmethod
    def extract_emails(value: str) -> List[str]:
        """
        Extrait les emails d'une chaîne
        
        Args:
            value: Chaîne à analyser
            
        Returns:
            List[str]: Liste des emails
        """
        if not value:
            return []
        
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return re.findall(pattern, value)
    
    @staticmethod
    def extract_urls(value: str) -> List[str]:
        """
        Extrait les URLs d'une chaîne
        
        Args:
            value: Chaîne à analyser
            
        Returns:
            List[str]: Liste des URLs
        """
        if not value:
            return []
        
        pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/]?'
        return re.findall(pattern, value)
    
    @staticmethod
    def extract_phone_numbers(value: str) -> List[str]:
        """
        Extrait les numéros de téléphone
        
        Args:
            value: Chaîne à analyser
            
        Returns:
            List[str]: Liste des numéros
        """
        if not value:
            return []
        
        pattern = r'\+?[1-9]\d{1,14}'
        return re.findall(pattern, value)
    
    @staticmethod
    def filter_string(
        value: str,
        filter_type: StringFilter,
        replacement: str = ''
    ) -> str:
        """
        Filtre une chaîne
        
        Args:
            value: Chaîne à filtrer
            filter_type: Type de filtre
            replacement: Caractère de remplacement
            
        Returns:
            str: Chaîne filtrée
        """
        if not value:
            return ""
        
        if filter_type == StringFilter.ALPHANUMERIC:
            return re.sub(r'[^a-zA-Z0-9]', replacement, value)
        elif filter_type == StringFilter.ALPHA:
            return re.sub(r'[^a-zA-Z]', replacement, value)
        elif filter_type == StringFilter.NUMERIC:
            return re.sub(r'[^0-9]', replacement, value)
        elif filter_type == StringFilter.ASCII:
            return value.encode('ascii', 'ignore').decode('ascii')
        elif filter_type == StringFilter.PRINTABLE:
            return ''.join(c for c in value if c.isprintable())
        elif filter_type == StringFilter.EMAIL:
            pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            return re.sub(pattern, replacement, value)
        elif filter_type == StringFilter.URL:
            pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/]?'
            return re.sub(pattern, replacement, value)
        elif filter_type == StringFilter.PHONE:
            pattern = r'\+?[1-9]\d{1,14}'
            return re.sub(pattern, replacement, value)
        elif filter_type == StringFilter.HEX:
            return ''.join(c for c in value if c in string.hexdigits)
        elif filter_type == StringFilter.BASE64:
            return ''.join(c for c in value if c in string.ascii_letters + string.digits + '+/=')
        
        return value
    
    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """
        Calcule la distance de Levenshtein
        
        Args:
            s1: Première chaîne
            s2: Deuxième chaîne
            
        Returns:
            int: Distance
        """
        return Levenshtein.distance(s1, s2) if s1 and s2 else 0
    
    @staticmethod
    def similarity_score(s1: str, s2: str) -> float:
        """
        Calcule le score de similarité
        
        Args:
            s1: Première chaîne
            s2: Deuxième chaîne
            
        Returns:
            float: Score (0-1)
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        
        return Levenshtein.ratio(s1, s2)
    
    @staticmethod
    def find_similar(
        target: str,
        candidates: List[str],
        threshold: float = 0.6,
        limit: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Trouve les chaînes similaires
        
        Args:
            target: Chaîne cible
            candidates: Liste des candidats
            threshold: Seuil de similarité
            limit: Nombre maximum de résultats
            
        Returns:
            List[Tuple[str, float]]: Candidats similaires
        """
        results = []
        
        for candidate in candidates:
            score = StringUtils.similarity_score(target, candidate)
            if score >= threshold:
                results.append((candidate, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    @staticmethod
    def pluralize(value: str, count: int = 2) -> str:
        """
        Pluralise un mot
        
        Args:
            value: Mot à pluraliser
            count: Nombre
            
        Returns:
            str: Mot pluralisé
        """
        if count == 1:
            return value
        
        p = inflect.engine()
        return p.plural(value)
    
    @staticmethod
    def singularize(value: str) -> str:
        """
        Singularise un mot
        
        Args:
            value: Mot à singulariser
            
        Returns:
            str: Mot singularisé
        """
        p = inflect.engine()
        return p.singular_noun(value) or value
    
    @staticmethod
    def wrap_text(
        value: str,
        width: int = 80,
        initial_indent: str = '',
        subsequent_indent: str = ''
    ) -> str:
        """
        Enroule du texte
        
        Args:
            value: Texte à enrouler
            width: Largeur maximale
            initial_indent: Indentation initiale
            subsequent_indent: Indentation suivante
            
        Returns:
            str: Texte enroulé
        """
        return textwrap.fill(
            value,
            width=width,
            initial_indent=initial_indent,
            subsequent_indent=subsequent_indent
        )
    
    @staticmethod
    def indent_text(value: str, prefix: str = '    ', levels: int = 1) -> str:
        """
        Indente du texte
        
        Args:
            value: Texte à indenter
            prefix: Préfixe d'indentation
            levels: Nombre de niveaux
            
        Returns:
            str: Texte indenté
        """
        indent = prefix * levels
        return '\n'.join(indent + line if line else line for line in value.split('\n'))
    
    @staticmethod
    def dedent_text(value: str) -> str:
        """
        Dédente du texte
        
        Args:
            value: Texte à dédenter
            
        Returns:
            str: Texte dédenté
        """
        return textwrap.dedent(value)

# ============================================================
# JSON UTILITIES
# ============================================================

class JSONUtils:
    """Utilitaires JSON"""
    
    @staticmethod
    def to_json(data: Any, indent: int = 2, compact: bool = False) -> str:
        """
        Convertit en JSON
        
        Args:
            data: Données à convertir
            indent: Indentation
            compact: Format compact
            
        Returns:
            str: JSON
        """
        def default_serializer(obj):
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, Enum):
                return obj.value
            return str(obj)
        
        if compact:
            return json.dumps(data, default=default_serializer, separators=(',', ':'))
        else:
            return json.dumps(data, default=default_serializer, indent=indent)
    
    @staticmethod
    def from_json(json_str: str) -> Any:
        """
        Parse du JSON
        
        Args:
            json_str: Chaîne JSON
            
        Returns:
            Any: Données parsées
        """
        return json.loads(json_str)
    
    @staticmethod
    def is_json(json_str: str) -> bool:
        """
        Vérifie si une chaîne est du JSON valide
        
        Args:
            json_str: Chaîne à vérifier
            
        Returns:
            bool: True si valide
        """
        try:
            json.loads(json_str)
            return True
        except ValueError:
            return False

# ============================================================
# HTML UTILITIES
# ============================================================

class HTMLUtils:
    """Utilitaires HTML"""
    
    @staticmethod
    def escape(text: str) -> str:
        """Échappe du texte HTML"""
        return html.escape(text)
    
    @staticmethod
    def unescape(text: str) -> str:
        """Déséchappe du texte HTML"""
        return html.unescape(text)
    
    @staticmethod
    def strip_tags(text: str) -> str:
        """Supprime les balises HTML"""
        return re.sub(r'<[^>]+>', '', text)
    
    @staticmethod
    def extract_text(html_str: str) -> str:
        """Extrait le texte du HTML"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_str, 'html.parser')
        return soup.get_text()

# ============================================================
# XML UTILITIES
# ============================================================

class XMLUtils:
    """Utilitaires XML"""
    
    @staticmethod
    def escape(text: str) -> str:
        """Échappe du texte XML"""
        return xml.sax.saxutils.escape(text)
    
    @staticmethod
    def unescape(text: str) -> str:
        """Déséchappe du texte XML"""
        return xml.sax.saxutils.unescape(text)
    
    @staticmethod
    def strip_tags(text: str) -> str:
        """Supprime les balises XML"""
        return re.sub(r'<[^>]+>', '', text)

# ============================================================
# ENCODING UTILITIES
# ============================================================

class EncodingUtils:
    """Utilitaires d'encodage"""
    
    @staticmethod
    def to_base64(data: Union[str, bytes]) -> str:
        """Convertit en base64"""
        if isinstance(data, str):
            data = data.encode()
        return base64.b64encode(data).decode()
    
    @staticmethod
    def from_base64(data: str) -> bytes:
        """Convertit depuis base64"""
        return base64.b64decode(data)
    
    @staticmethod
    def to_hex(data: Union[str, bytes]) -> str:
        """Convertit en hexadécimal"""
        if isinstance(data, str):
            data = data.encode()
        return data.hex()
    
    @staticmethod
    def from_hex(data: str) -> bytes:
        """Convertit depuis hexadécimal"""
        return bytes.fromhex(data)
    
    @staticmethod
    def compress(data: Union[str, bytes]) -> bytes:
        """Compresse des données"""
        if isinstance(data, str):
            data = data.encode()
        return zlib.compress(data)
    
    @staticmethod
    def decompress(data: bytes) -> bytes:
        """Décompresse des données"""
        return zlib.decompress(data)

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'CaseType',
    'StringFilter',
    
    # Classes
    'StringUtils',
    'JSONUtils',
    'HTMLUtils',
    'XMLUtils',
    'EncodingUtils',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("String utilities module initialized")
