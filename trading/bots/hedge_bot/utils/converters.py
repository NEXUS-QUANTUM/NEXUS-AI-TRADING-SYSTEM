"""
NEXUS AI TRADING SYSTEM - Hedge Bot Converters Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de conversion pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import json
import yaml
import csv
import pickle
import base64
import hashlib
import re
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    Type,
    TypeVar,
    Callable,
    Iterator,
    Generator
)
from datetime import datetime, timedelta, date, time
from decimal import Decimal, getcontext
from fractions import Fraction
from enum import Enum
import xml.etree.ElementTree as ET
from pathlib import Path
import io
import uuid
import binascii
import html
import urllib.parse
from dataclasses import dataclass, field, asdict, is_dataclass

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
# NUMBER CONVERTERS
# ============================================================

class NumberConverter:
    """Convertisseur de nombres"""
    
    @staticmethod
    def to_decimal(value: Any, precision: int = 8) -> Decimal:
        """
        Convertit une valeur en Decimal
        
        Args:
            value: Valeur à convertir
            precision: Précision décimale
            
        Returns:
            Decimal: Valeur convertie
        """
        try:
            getcontext().prec = precision
            if isinstance(value, Decimal):
                return value
            elif isinstance(value, (int, float)):
                return Decimal(str(value))
            elif isinstance(value, str):
                return Decimal(value)
            elif isinstance(value, (list, tuple)):
                return Decimal(str(value[0])) if value else Decimal('0')
            else:
                return Decimal(str(value))
        except Exception as e:
            logger.error(f"Conversion to Decimal failed: {e}")
            return Decimal('0')
    
    @staticmethod
    def to_float(value: Any, default: float = 0.0) -> float:
        """
        Convertit une valeur en float
        
        Args:
            value: Valeur à convertir
            default: Valeur par défaut
            
        Returns:
            float: Valeur convertie
        """
        try:
            if isinstance(value, float):
                return value
            elif isinstance(value, (int, Decimal)):
                return float(value)
            elif isinstance(value, str):
                return float(value.replace(',', '').replace(' ', ''))
            elif isinstance(value, (list, tuple)):
                return float(value[0]) if value else default
            else:
                return float(str(value))
        except Exception:
            return default
    
    @staticmethod
    def to_int(value: Any, default: int = 0) -> int:
        """
        Convertit une valeur en int
        
        Args:
            value: Valeur à convertir
            default: Valeur par défaut
            
        Returns:
            int: Valeur convertie
        """
        try:
            if isinstance(value, int):
                return value
            elif isinstance(value, float):
                return int(value)
            elif isinstance(value, Decimal):
                return int(value)
            elif isinstance(value, str):
                return int(value.replace(',', '').replace(' ', ''))
            elif isinstance(value, (list, tuple)):
                return int(value[0]) if value else default
            else:
                return int(str(value))
        except Exception:
            return default
    
    @staticmethod
    def to_percent(value: Any, decimals: int = 2) -> float:
        """
        Convertit une valeur en pourcentage
        
        Args:
            value: Valeur à convertir
            decimals: Nombre de décimales
            
        Returns:
            float: Pourcentage
        """
        try:
            if isinstance(value, str):
                value = float(value.replace('%', '').replace(',', ''))
            return round(float(value) * 100, decimals)
        except Exception:
            return 0.0
    
    @staticmethod
    def to_bps(value: Any) -> int:
        """
        Convertit une valeur en basis points (bps)
        
        Args:
            value: Valeur à convertir
            
        Returns:
            int: Basis points
        """
        try:
            if isinstance(value, str):
                value = float(value.replace('%', '').replace(',', ''))
            return int(float(value) * 10000)
        except Exception:
            return 0
    
    @staticmethod
    def to_ratio(value: Any) -> float:
        """
        Convertit une valeur en ratio (0-1)
        
        Args:
            value: Valeur à convertir
            
        Returns:
            float: Ratio
        """
        try:
            if isinstance(value, str):
                if '%' in value:
                    value = float(value.replace('%', '')) / 100
                else:
                    value = float(value)
            elif isinstance(value, (int, float)):
                if value > 1:
                    value = value / 100
            return float(value)
        except Exception:
            return 0.0
    
    @staticmethod
    def format_number(value: Any, decimals: int = 2, prefix: str = "", suffix: str = "") -> str:
        """
        Formate un nombre
        
        Args:
            value: Valeur à formater
            decimals: Nombre de décimales
            prefix: Préfixe
            suffix: Suffixe
            
        Returns:
            str: Nombre formaté
        """
        try:
            num = float(value)
            formatted = f"{num:,.{decimals}f}"
            return f"{prefix}{formatted}{suffix}"
        except Exception:
            return str(value)
    
    @staticmethod
    def format_currency(value: Any, currency: str = "USD", decimals: int = 2) -> str:
        """
        Formate une valeur en devise
        
        Args:
            value: Valeur à formater
            currency: Code devise
            decimals: Nombre de décimales
            
        Returns:
            str: Valeur formatée
        """
        symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "JPY": "¥",
            "BTC": "₿",
            "ETH": "Ξ",
            "SOL": "◎",
            "ADA": "₳",
            "DOT": "●",
            "USDT": "₮",
            "USDC": "₮",
        }
        symbol = symbols.get(currency, currency)
        return NumberConverter.format_number(value, decimals, prefix=symbol)
    
    @staticmethod
    def format_percent(value: Any, decimals: int = 2, include_sign: bool = True) -> str:
        """
        Formate un pourcentage
        
        Args:
            value: Valeur à formater
            decimals: Nombre de décimales
            include_sign: Inclure le signe
            
        Returns:
            str: Pourcentage formaté
        """
        try:
            pct = NumberConverter.to_percent(value, decimals)
            sign = "+" if include_sign and pct > 0 else ""
            return f"{sign}{pct:.{decimals}f}%"
        except Exception:
            return str(value)
    
    @staticmethod
    def format_compact(value: Any, decimals: int = 1) -> str:
        """
        Formate un nombre en format compact
        
        Args:
            value: Valeur à formater
            decimals: Nombre de décimales
            
        Returns:
            str: Nombre formaté
        """
        try:
            num = float(value)
            abs_num = abs(num)
            sign = "-" if num < 0 else ""
            
            if abs_num >= 1_000_000_000:
                return f"{sign}{abs_num/1_000_000_000:.{decimals}f}B"
            elif abs_num >= 1_000_000:
                return f"{sign}{abs_num/1_000_000:.{decimals}f}M"
            elif abs_num >= 1_000:
                return f"{sign}{abs_num/1_000:.{decimals}f}K"
            else:
                return f"{sign}{abs_num:.{decimals}f}"
        except Exception:
            return str(value)

# ============================================================
# DATE/TIME CONVERTERS
# ============================================================

class DateTimeConverter:
    """Convertisseur de dates et heures"""
    
    # Formats de date communs
    FORMATS = {
        "iso": "%Y-%m-%dT%H:%M:%S",
        "iso_ms": "%Y-%m-%dT%H:%M:%S.%f",
        "iso_z": "%Y-%m-%dT%H:%M:%SZ",
        "iso_ms_z": "%Y-%m-%dT%H:%M:%S.%fZ",
        "datetime": "%Y-%m-%d %H:%M:%S",
        "date": "%Y-%m-%d",
        "time": "%H:%M:%S",
        "timestamp": "%Y%m%d%H%M%S",
        "rfc2822": "%a, %d %b %Y %H:%M:%S %z",
        "rfc3339": "%Y-%m-%dT%H:%M:%S%z",
        "rfc3339_ms": "%Y-%m-%dT%H:%M:%S.%f%z",
        "http": "%a, %d %b %Y %H:%M:%S GMT",
        "cookie": "%A, %d-%b-%Y %H:%M:%S GMT",
        "email": "%a, %d %b %Y %H:%M:%S %z",
        "compact": "%Y%m%d%H%M%S",
        "unix": "unix",  # timestamp unix
        "ms": "ms",      # timestamp millisecondes
    }
    
    @staticmethod
    def to_datetime(value: Any, default: Optional[datetime] = None) -> Optional[datetime]:
        """
        Convertit une valeur en datetime
        
        Args:
            value: Valeur à convertir
            default: Valeur par défaut
            
        Returns:
            Optional[datetime]: Datetime converti
        """
        if value is None:
            return default
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        
        if isinstance(value, time):
            return datetime.combine(datetime.today(), value)
        
        if isinstance(value, (int, float)):
            try:
                # Si plus grand que 1e10, c'est probablement en millisecondes
                if value > 1e10:
                    return datetime.fromtimestamp(value / 1000)
                return datetime.fromtimestamp(value)
            except:
                pass
        
        if isinstance(value, str):
            # Essayer différents formats
            for format_name, format_str in DateTimeConverter.FORMATS.items():
                if format_name in ['unix', 'ms']:
                    continue
                try:
                    return datetime.strptime(value, format_str)
                except ValueError:
                    continue
            
            try:
                # Essayer avec dateutil si disponible
                from dateutil.parser import parse
                return parse(value)
            except:
                pass
        
        return default
    
    @staticmethod
    def to_date(value: Any, default: Optional[date] = None) -> Optional[date]:
        """
        Convertit une valeur en date
        
        Args:
            value: Valeur à convertir
            default: Valeur par défaut
            
        Returns:
            Optional[date]: Date convertie
        """
        dt = DateTimeConverter.to_datetime(value)
        if dt:
            return dt.date()
        return default
    
    @staticmethod
    def to_time(value: Any, default: Optional[time] = None) -> Optional[time]:
        """
        Convertit une valeur en heure
        
        Args:
            value: Valeur à convertir
            default: Valeur par défaut
            
        Returns:
            Optional[time]: Heure convertie
        """
        dt = DateTimeConverter.to_datetime(value)
        if dt:
            return dt.time()
        return default
    
    @staticmethod
    def to_timestamp(value: Any, default: Optional[float] = None) -> Optional[float]:
        """
        Convertit une valeur en timestamp
        
        Args:
            value: Valeur à convertir
            default: Valeur par défaut
            
        Returns:
            Optional[float]: Timestamp
        """
        if value is None:
            return default
        
        if isinstance(value, (int, float)):
            if value > 1e10:  # millisecondes
                return value / 1000
            return float(value)
        
        dt = DateTimeConverter.to_datetime(value)
        if dt:
            return dt.timestamp()
        
        return default
    
    @staticmethod
    def to_timestamp_ms(value: Any, default: Optional[int] = None) -> Optional[int]:
        """
        Convertit une valeur en timestamp millisecondes
        
        Args:
            value: Valeur à convertir
            default: Valeur par défaut
            
        Returns:
            Optional[int]: Timestamp en millisecondes
        """
        ts = DateTimeConverter.to_timestamp(value)
        if ts is not None:
            return int(ts * 1000)
        return default
    
    @staticmethod
    def format_datetime(
        value: Any,
        format_str: str = "iso",
        default: str = "",
        tz: Optional[str] = None
    ) -> str:
        """
        Formate une date/heure
        
        Args:
            value: Valeur à formater
            format_str: Format de sortie
            default: Valeur par défaut
            tz: Fuseau horaire
            
        Returns:
            str: Date/heure formatée
        """
        dt = DateTimeConverter.to_datetime(value)
        if dt is None:
            return default
        
        # Convertir le fuseau horaire
        if tz:
            import pytz
            dt = dt.astimezone(pytz.timezone(tz))
        
        if format_str in DateTimeConverter.FORMATS:
            format_str = DateTimeConverter.FORMATS[format_str]
        
        return dt.strftime(format_str)
    
    @staticmethod
    def format_date(value: Any, default: str = "") -> str:
        """
        Formate une date
        
        Args:
            value: Valeur à formater
            default: Valeur par défaut
            
        Returns:
            str: Date formatée
        """
        return DateTimeConverter.format_datetime(value, "date", default)
    
    @staticmethod
    def format_time(value: Any, default: str = "") -> str:
        """
        Formate une heure
        
        Args:
            value: Valeur à formater
            default: Valeur par défaut
            
        Returns:
            str: Heure formatée
        """
        return DateTimeConverter.format_datetime(value, "time", default)
    
    @staticmethod
    def format_timestamp(value: Any, default: str = "") -> str:
        """
        Formate un timestamp
        
        Args:
            value: Valeur à formater
            default: Valeur par défaut
            
        Returns:
            str: Timestamp formaté
        """
        return DateTimeConverter.format_datetime(value, "timestamp", default)
    
    @staticmethod
    def parse_duration(duration_str: str) -> float:
        """
        Parse une durée en secondes
        
        Args:
            duration_str: Chaîne de durée
            
        Returns:
            float: Durée en secondes
        """
        if not duration_str:
            return 0.0
        
        patterns = [
            (r'(\d+\.?\d*)\s*(?:d|day|days)', 86400),
            (r'(\d+\.?\d*)\s*(?:h|hr|hour|hours)', 3600),
            (r'(\d+\.?\d*)\s*(?:m|min|minute|minutes)', 60),
            (r'(\d+\.?\d*)\s*(?:s|sec|second|seconds)', 1),
            (r'(\d+\.?\d*)\s*(?:ms|millisecond|milliseconds)', 0.001),
            (r'(\d+\.?\d*)\s*(?:w|week|weeks)', 604800),
            (r'(\d+\.?\d*)\s*(?:mo|month|months)', 2592000),
            (r'(\d+\.?\d*)\s*(?:y|yr|year|years)', 31536000),
        ]
        
        total = 0.0
        for pattern, multiplier in patterns:
            matches = re.findall(pattern, duration_str.lower())
            for match in matches:
                total += float(match) * multiplier
        
        return total

# ============================================================
# STRING CONVERTERS
# ============================================================

class StringConverter:
    """Convertisseur de chaînes"""
    
    @staticmethod
    def to_string(value: Any, default: str = "") -> str:
        """
        Convertit une valeur en chaîne
        
        Args:
            value: Valeur à convertir
            default: Valeur par défaut
            
        Returns:
            str: Chaîne convertie
        """
        if value is None:
            return default
        
        if isinstance(value, str):
            return value
        
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='ignore')
        
        try:
            return str(value)
        except Exception:
            return default
    
    @staticmethod
    def to_bytes(value: Any, encoding: str = 'utf-8') -> bytes:
        """
        Convertit une valeur en bytes
        
        Args:
            value: Valeur à convertir
            encoding: Encodage
            
        Returns:
            bytes: Bytes
        """
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode(encoding)
        return str(value).encode(encoding)
    
    @staticmethod
    def to_slug(value: str, separator: str = '-', lower: bool = True) -> str:
        """
        Convertit une chaîne en slug
        
        Args:
            value: Chaîne à convertir
            separator: Séparateur
            lower: Mettre en minuscules
            
        Returns:
            str: Slug
        """
        if not value:
            return ""
        
        # Convertir en ASCII
        import unicodedata
        value = unicodedata.normalize('NFKD', str(value))
        value = value.encode('ascii', 'ignore').decode('ascii')
        
        # Remplacer les caractères non alphanumériques
        value = re.sub(r'[^a-zA-Z0-9]+', separator, value)
        
        # Supprimer les séparateurs en début/fin
        value = value.strip(separator)
        
        if lower:
            value = value.lower()
        
        return value
    
    @staticmethod
    def truncate(value: str, length: int = 100, suffix: str = "...", middle: bool = False) -> str:
        """
        Tronque une chaîne
        
        Args:
            value: Chaîne à tronquer
            length: Longueur maximale
            suffix: Suffixe à ajouter
            middle: Tronquer au milieu
            
        Returns:
            str: Chaîne tronquée
        """
        if not value:
            return ""
        
        if len(value) <= length:
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
    def camel_to_snake(value: str) -> str:
        """
        Convertit du camelCase en snake_case
        
        Args:
            value: Chaîne en camelCase
            
        Returns:
            str: Chaîne en snake_case
        """
        value = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', value)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', value).lower()
    
    @staticmethod
    def snake_to_camel(value: str) -> str:
        """
        Convertit du snake_case en camelCase
        
        Args:
            value: Chaîne en snake_case
            
        Returns:
            str: Chaîne en camelCase
        """
        components = value.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])
    
    @staticmethod
    def snake_to_pascal(value: str) -> str:
        """
        Convertit du snake_case en PascalCase
        
        Args:
            value: Chaîne en snake_case
            
        Returns:
            str: Chaîne en PascalCase
        """
        return ''.join(x.title() for x in value.split('_'))
    
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
        matches = re.findall(pattern, value)
        return [float(m) for m in matches if m]
    
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
        
        pattern = r'[a-zA-Z]+'
        matches = re.findall(pattern, value)
        return matches
    
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

# ============================================================
# DATA FORMAT CONVERTERS
# ============================================================

class DataFormatConverter:
    """Convertisseur de formats de données"""
    
    @staticmethod
    def to_json(data: Any, indent: Optional[int] = None) -> str:
        """
        Convertit des données en JSON
        
        Args:
            data: Données à convertir
            indent: Indentation
            
        Returns:
            str: JSON
        """
        def default_serializer(obj):
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            if is_dataclass(obj):
                return asdict(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, date):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, Path):
                return str(obj)
            return str(obj)
        
        try:
            return json.dumps(data, default=default_serializer, indent=indent)
        except Exception as e:
            logger.error(f"JSON conversion error: {e}")
            return "{}"
    
    @staticmethod
    def from_json(data: Union[str, bytes]) -> Any:
        """
        Convertit du JSON en données
        
        Args:
            data: Données JSON
            
        Returns:
            Any: Données converties
        """
        try:
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            return json.loads(data)
        except Exception as e:
            logger.error(f"JSON parsing error: {e}")
            return None
    
    @staticmethod
    def to_yaml(data: Any) -> str:
        """
        Convertit des données en YAML
        
        Args:
            data: Données à convertir
            
        Returns:
            str: YAML
        """
        try:
            return yaml.dump(data, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"YAML conversion error: {e}")
            return ""
    
    @staticmethod
    def from_yaml(data: Union[str, bytes]) -> Any:
        """
        Convertit du YAML en données
        
        Args:
            data: Données YAML
            
        Returns:
            Any: Données converties
        """
        try:
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            return yaml.safe_load(data)
        except Exception as e:
            logger.error(f"YAML parsing error: {e}")
            return None
    
    @staticmethod
    def to_csv(data: List[Dict[str, Any]], delimiter: str = ',') -> str:
        """
        Convertit des données en CSV
        
        Args:
            data: Données à convertir
            delimiter: Délimiteur
            
        Returns:
            str: CSV
        """
        if not data:
            return ""
        
        try:
            output = io.StringIO()
            fieldnames = data[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=delimiter)
            writer.writeheader()
            writer.writerows(data)
            return output.getvalue()
        except Exception as e:
            logger.error(f"CSV conversion error: {e}")
            return ""
    
    @staticmethod
    def from_csv(data: Union[str, bytes], delimiter: str = ',') -> List[Dict[str, Any]]:
        """
        Convertit du CSV en données
        
        Args:
            data: Données CSV
            delimiter: Délimiteur
            
        Returns:
            List[Dict[str, Any]]: Données converties
        """
        try:
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            
            input_stream = io.StringIO(data)
            reader = csv.DictReader(input_stream, delimiter=delimiter)
            return list(reader)
        except Exception as e:
            logger.error(f"CSV parsing error: {e}")
            return []
    
    @staticmethod
    def to_xml(data: Any, root_name: str = "root") -> str:
        """
        Convertit des données en XML
        
        Args:
            data: Données à convertir
            root_name: Nom de l'élément racine
            
        Returns:
            str: XML
        """
        def _build_xml(parent, data):
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, (dict, list)):
                        child = ET.SubElement(parent, key)
                        _build_xml(child, value)
                    else:
                        child = ET.SubElement(parent, key)
                        child.text = str(value)
            elif isinstance(data, list):
                for item in data:
                    child = ET.SubElement(parent, "item")
                    _build_xml(child, item)
            else:
                parent.text = str(data)
        
        try:
            root = ET.Element(root_name)
            _build_xml(root, data)
            return ET.tostring(root, encoding='unicode')
        except Exception as e:
            logger.error(f"XML conversion error: {e}")
            return ""
    
    @staticmethod
    def from_xml(data: Union[str, bytes]) -> Any:
        """
        Convertit du XML en données
        
        Args:
            data: Données XML
            
        Returns:
            Any: Données converties
        """
        def _parse_xml(element):
            result = {}
            
            for child in element:
                if len(child) == 0:
                    result[child.tag] = child.text
                else:
                    if child.tag not in result:
                        result[child.tag] = []
                    result[child.tag].append(_parse_xml(child))
            
            return result
        
        try:
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            
            root = ET.fromstring(data)
            return _parse_xml(root)
        except Exception as e:
            logger.error(f"XML parsing error: {e}")
            return {}
    
    @staticmethod
    def to_pickle(data: Any) -> bytes:
        """
        Convertit des données en pickle
        
        Args:
            data: Données à convertir
            
        Returns:
            bytes: Données pickle
        """
        try:
            return pickle.dumps(data)
        except Exception as e:
            logger.error(f"Pickle conversion error: {e}")
            return b''
    
    @staticmethod
    def from_pickle(data: bytes) -> Any:
        """
        Convertit du pickle en données
        
        Args:
            data: Données pickle
            
        Returns:
            Any: Données converties
        """
        try:
            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Pickle parsing error: {e}")
            return None
    
    @staticmethod
    def to_base64(data: Union[str, bytes]) -> str:
        """
        Convertit des données en base64
        
        Args:
            data: Données à convertir
            
        Returns:
            str: Base64
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            return base64.b64encode(data).decode('utf-8')
        except Exception as e:
            logger.error(f"Base64 conversion error: {e}")
            return ""
    
    @staticmethod
    def from_base64(data: str) -> bytes:
        """
        Convertit du base64 en données
        
        Args:
            data: Base64
            
        Returns:
            bytes: Données converties
        """
        try:
            return base64.b64decode(data)
        except Exception as e:
            logger.error(f"Base64 parsing error: {e}")
            return b''

# ============================================================
# CASE CONVERTERS
# ============================================================

class CaseConverter:
    """Convertisseur de cas"""
    
    @staticmethod
    def to_snake(value: str) -> str:
        """Convertit en snake_case"""
        return StringConverter.camel_to_snake(value)
    
    @staticmethod
    def to_camel(value: str) -> str:
        """Convertit en camelCase"""
        return StringConverter.snake_to_camel(value)
    
    @staticmethod
    def to_pascal(value: str) -> str:
        """Convertit en PascalCase"""
        return StringConverter.snake_to_pascal(value)
    
    @staticmethod
    def to_kebab(value: str) -> str:
        """Convertit en kebab-case"""
        value = StringConverter.camel_to_snake(value)
        return value.replace('_', '-')
    
    @staticmethod
    def to_constant(value: str) -> str:
        """Convertit en CONSTANT_CASE"""
        value = StringConverter.camel_to_snake(value)
        return value.upper()

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Classes
    'NumberConverter',
    'DateTimeConverter',
    'StringConverter',
    'DataFormatConverter',
    'CaseConverter',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Converters utilities module initialized")
