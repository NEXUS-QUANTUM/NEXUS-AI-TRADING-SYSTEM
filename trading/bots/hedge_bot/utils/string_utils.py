"""
NEXUS AI TRADING SYSTEM - HEDGE BOT STRING UTILS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module d'utilitaires pour la manipulation des chaînes de caractères.
Support du formatage, validation, transformation, et plus.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import base64
import hashlib
import json
import logging
import re
import string
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import emoji
import inflect
import names
import phonenumbers
import validators
from faker import Faker
from slugify import slugify

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class StringCase(Enum):
    """Types de casse."""
    LOWER = "lower"
    UPPER = "upper"
    CAPITALIZE = "capitalize"
    TITLE = "title"
    SNAKE = "snake"
    CAMEL = "camel"
    PASCAL = "pascal"
    CONSTANT = "constant"
    KEBAB = "kebab"
    TRAIN = "train"
    DOT = "dot"


class StringValidation(Enum):
    """Types de validation."""
    EMAIL = "email"
    URL = "url"
    UUID = "uuid"
    IP = "ip"
    DOMAIN = "domain"
    PHONE = "phone"
    CREDIT_CARD = "credit_card"
    ISBN = "isbn"
    ZIP_CODE = "zip_code"
    HEX_COLOR = "hex_color"


@dataclass
class StringStats:
    """Statistiques d'une chaîne."""
    length: int
    word_count: int
    sentence_count: int
    char_count: Dict[str, int]
    unique_chars: int
    digit_count: int
    letter_count: int
    punctuation_count: int
    whitespace_count: int
    average_word_length: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "length": self.length,
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "char_count": self.char_count,
            "unique_chars": self.unique_chars,
            "digit_count": self.digit_count,
            "letter_count": self.letter_count,
            "punctuation_count": self.punctuation_count,
            "whitespace_count": self.whitespace_count,
            "average_word_length": self.average_word_length,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE STRING UTILS
# ============================================================================

class StringUtils:
    """
    Utilitaires pour la manipulation des chaînes de caractères.
    """

    # Caractères spéciaux
    SPECIAL_CHARS = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
        "ñ": "n", "Ñ": "N", "ç": "c", "Ç": "C",
        "ü": "u", "Ü": "U"
    }

    # Ponctuation
    PUNCTUATION = string.punctuation + "…—–"
    
    # Mots communs (stop words)
    STOP_WORDS = {
        "a", "an", "the", "and", "or", "but", "for", "nor", "on", "at", 
        "to", "by", "in", "of", "with", "without", "for", "from", "up",
        "down", "off", "over", "under", "above", "below", "between",
        "among", "through", "during", "within", "without", "about",
        "against", "between", "through", "during", "within"
    }

    def __init__(
        self,
        default_locale: str = "en_US",
        random_seed: Optional[int] = None
    ):
        """
        Initialise les utilitaires de chaînes.

        Args:
            default_locale: Locale par défaut
            random_seed: Seed pour la reproductibilité
        """
        self.default_locale = default_locale
        self.random_seed = random_seed
        
        # Faker pour la génération de données
        self.faker = Faker(default_locale)
        if random_seed:
            self.faker.seed_instance(random_seed)
        
        # Inflect pour les conversions
        self.inflect = inflect.engine()
        
        # Métriques
        self._metrics = {
            "total_operations": 0,
            "by_type": {},
            "last_operation": None
        }

        logger.info("StringUtils initialisé avec succès")

    # ========================================================================
    # TRANSFORMATION DE CASSE
    # ========================================================================

    def to_case(self, text: str, case: StringCase) -> str:
        """
        Convertit une chaîne dans une casse spécifique.

        Args:
            text: Chaîne à convertir
            case: Type de casse

        Returns:
            Chaîne convertie
        """
        self._update_metrics("to_case")
        
        if case == StringCase.LOWER:
            return text.lower()
        elif case == StringCase.UPPER:
            return text.upper()
        elif case == StringCase.CAPITALIZE:
            return text.capitalize()
        elif case == StringCase.TITLE:
            return text.title()
        elif case == StringCase.SNAKE:
            return self._to_snake_case(text)
        elif case == StringCase.CAMEL:
            return self._to_camel_case(text)
        elif case == StringCase.PASCAL:
            return self._to_pascal_case(text)
        elif case == StringCase.CONSTANT:
            return self._to_constant_case(text)
        elif case == StringCase.KEBAB:
            return self._to_kebab_case(text)
        elif case == StringCase.TRAIN:
            return self._to_train_case(text)
        elif case == StringCase.DOT:
            return self._to_dot_case(text)
        else:
            return text

    def _to_snake_case(self, text: str) -> str:
        """
        Convertit en snake_case.

        Args:
            text: Chaîne à convertir

        Returns:
            Chaîne en snake_case
        """
        # Gestion des mots séparés par des espaces ou tirets
        text = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', text)
        text = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', text)
        text = re.sub(r'[-.]', '_', text)
        text = re.sub(r'\s+', '_', text)
        text = re.sub(r'_+', '_', text)
        return text.lower().strip('_')

    def _to_camel_case(self, text: str) -> str:
        """
        Convertit en camelCase.

        Args:
            text: Chaîne à convertir

        Returns:
            Chaîne en camelCase
        """
        snake = self._to_snake_case(text)
        parts = snake.split('_')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:])

    def _to_pascal_case(self, text: str) -> str:
        """
        Convertit en PascalCase.

        Args:
            text: Chaîne à convertir

        Returns:
            Chaîne en PascalCase
        """
        snake = self._to_snake_case(text)
        return ''.join(p.capitalize() for p in snake.split('_'))

    def _to_constant_case(self, text: str) -> str:
        """
        Convertit en CONSTANT_CASE.

        Args:
            text: Chaîne à convertir

        Returns:
            Chaîne en CONSTANT_CASE
        """
        return self._to_snake_case(text).upper()

    def _to_kebab_case(self, text: str) -> str:
        """
        Convertit en kebab-case.

        Args:
            text: Chaîne à convertir

        Returns:
            Chaîne en kebab-case
        """
        snake = self._to_snake_case(text)
        return snake.replace('_', '-')

    def _to_train_case(self, text: str) -> str:
        """
        Convertit en Train-Case.

        Args:
            text: Chaîne à convertir

        Returns:
            Chaîne en Train-Case
        """
        kebab = self._to_kebab_case(text)
        return kebab.title()

    def _to_dot_case(self, text: str) -> str:
        """
        Convertit en dot.case.

        Args:
            text: Chaîne à convertir

        Returns:
            Chaîne en dot.case
        """
        snake = self._to_snake_case(text)
        return snake.replace('_', '.')

    # ========================================================================
    # VALIDATION
    # ========================================================================

    def validate(self, text: str, validation_type: StringValidation) -> bool:
        """
        Valide une chaîne.

        Args:
            text: Chaîne à valider
            validation_type: Type de validation

        Returns:
            True si valide
        """
        self._update_metrics("validate")
        
        if validation_type == StringValidation.EMAIL:
            return validators.email(text)
        elif validation_type == StringValidation.URL:
            return validators.url(text)
        elif validation_type == StringValidation.UUID:
            return self.is_valid_uuid(text)
        elif validation_type == StringValidation.IP:
            return validators.ipv4(text) or validators.ipv6(text)
        elif validation_type == StringValidation.DOMAIN:
            return validators.domain(text)
        elif validation_type == StringValidation.PHONE:
            return self.is_valid_phone(text)
        elif validation_type == StringValidation.CREDIT_CARD:
            return self.is_valid_credit_card(text)
        elif validation_type == StringValidation.ISBN:
            return self.is_valid_isbn(text)
        elif validation_type == StringValidation.ZIP_CODE:
            return self.is_valid_zip_code(text)
        elif validation_type == StringValidation.HEX_COLOR:
            return self.is_valid_hex_color(text)
        else:
            return False

    def is_valid_uuid(self, text: str, version: int = 4) -> bool:
        """
        Vérifie si une chaîne est un UUID valide.

        Args:
            text: Chaîne à vérifier
            version: Version de l'UUID

        Returns:
            True si valide
        """
        try:
            uuid_obj = UUID(text)
            return uuid_obj.version == version
        except ValueError:
            return False

    def is_valid_phone(self, text: str, region: Optional[str] = None) -> bool:
        """
        Vérifie si une chaîne est un numéro de téléphone valide.

        Args:
            text: Chaîne à vérifier
            region: Région (ex: "FR", "US")

        Returns:
            True si valide
        """
        try:
            if region:
                phone = phonenumbers.parse(text, region)
            else:
                phone = phonenumbers.parse(text)
            return phonenumbers.is_valid_number(phone)
        except:
            return False

    def is_valid_credit_card(self, text: str) -> bool:
        """
        Vérifie si une chaîne est un numéro de carte de crédit valide.

        Args:
            text: Chaîne à vérifier

        Returns:
            True si valide
        """
        # Supprimer les espaces et tirets
        text = re.sub(r'[\s-]', '', text)
        
        if not text.isdigit():
            return False
        
        # Algorithme de Luhn
        def luhn_check(card_number: str) -> bool:
            total = 0
            alt = False
            for digit in reversed(card_number):
                n = int(digit)
                if alt:
                    n *= 2
                    if n > 9:
                        n -= 9
                total += n
                alt = not alt
            return total % 10 == 0
        
        return luhn_check(text)

    def is_valid_isbn(self, text: str) -> bool:
        """
        Vérifie si une chaîne est un ISBN valide.

        Args:
            text: Chaîne à vérifier

        Returns:
            True si valide
        """
        text = text.replace('-', '').replace(' ', '')
        
        if len(text) == 10:
            return self._is_valid_isbn10(text)
        elif len(text) == 13:
            return self._is_valid_isbn13(text)
        return False

    def _is_valid_isbn10(self, isbn: str) -> bool:
        """Vérifie un ISBN-10."""
        total = 0
        for i, char in enumerate(isbn):
            if i == 9 and char.lower() == 'x':
                val = 10
            elif char.isdigit():
                val = int(char)
            else:
                return False
            total += val * (10 - i)
        return total % 11 == 0

    def _is_valid_isbn13(self, isbn: str) -> bool:
        """Vérifie un ISBN-13."""
        if not isbn.isdigit():
            return False
        
        total = 0
        for i, char in enumerate(isbn):
            val = int(char)
            if i % 2 == 0:
                total += val
            else:
                total += val * 3
        return total % 10 == 0

    def is_valid_zip_code(self, text: str, country: str = "US") -> bool:
        """
        Vérifie si une chaîne est un code postal valide.

        Args:
            text: Chaîne à vérifier
            country: Pays

        Returns:
            True si valide
        """
        patterns = {
            "US": r"^\d{5}(-\d{4})?$",
            "FR": r"^\d{5}$",
            "UK": r"^[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}$",
            "CA": r"^[A-Z]\d[A-Z]\s?\d[A-Z]\d$",
            "DE": r"^\d{5}$",
            "JP": r"^\d{3}-\d{4}$"
        }
        
        pattern = patterns.get(country.upper())
        if pattern:
            return bool(re.match(pattern, text))
        
        # Si le pays n'est pas supporté
        return text.isdigit() and len(text) >= 4 and len(text) <= 6

    def is_valid_hex_color(self, text: str) -> bool:
        """
        Vérifie si une chaîne est une couleur hexadécimale valide.

        Args:
            text: Chaîne à vérifier

        Returns:
            True si valide
        """
        pattern = r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$"
        return bool(re.match(pattern, text))

    # ========================================================================
    # NETTOYAGE ET NORMALISATION
    # ========================================================================

    def normalize(self, text: str, remove_accents: bool = True) -> str:
        """
        Normalise une chaîne.

        Args:
            text: Chaîne à normaliser
            remove_accents: Supprimer les accents

        Returns:
            Chaîne normalisée
        """
        self._update_metrics("normalize")
        
        if remove_accents:
            # Suppression des accents
            nfkd_form = unicodedata.normalize('NFKD', text)
            text = ''.join([c for c in nfkd_form if not unicodedata.combining(c)])
        
        # Normalisation des espaces
        text = re.sub(r'\s+', ' ', text)
        
        # Suppression des espaces en début/fin
        text = text.strip()
        
        return text

    def slugify(self, text: str, separator: str = "-") -> str:
        """
        Transforme une chaîne en slug.

        Args:
            text: Chaîne à transformer
            separator: Séparateur

        Returns:
            Slug
        """
        self._update_metrics("slugify")
        return slugify(text, separator=separator)

    def remove_emoji(self, text: str) -> str:
        """
        Supprime les émojis d'une chaîne.

        Args:
            text: Chaîne à traiter

        Returns:
            Chaîne sans émojis
        """
        self._update_metrics("remove_emoji")
        return emoji.demojize(text, delimiters=("", ""), language='alias')

    def sanitize(self, text: str, allow_html: bool = False) -> str:
        """
        Nettoie une chaîne (protection XSS).

        Args:
            text: Chaîne à nettoyer
            allow_html: Autoriser le HTML

        Returns:
            Chaîne nettoyée
        """
        self._update_metrics("sanitize")
        
        if not allow_html:
            # Échappement HTML
            import html
            text = html.escape(text)
        
        # Suppression des caractères dangereux
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        return text

    def mask(self, text: str, start: int = 0, end: int = 0, char: str = "*") -> str:
        """
        Masque une partie d'une chaîne.

        Args:
            text: Chaîne à masquer
            start: Position de début
            end: Position de fin
            char: Caractère de masquage

        Returns:
            Chaîne masquée
        """
        self._update_metrics("mask")
        
        if start < 0:
            start = 0
        if end < 0:
            end = 0
        if start + end > len(text):
            end = len(text) - start
        
        visible_start = text[:start]
        masked = char * (len(text) - start - end)
        visible_end = text[-end:] if end > 0 else ""
        
        return visible_start + masked + visible_end

    # ========================================================================
    # ANALYSE ET STATISTIQUES
    # ========================================================================

    def get_stats(self, text: str) -> StringStats:
        """
        Analyse une chaîne et retourne des statistiques.

        Args:
            text: Chaîne à analyser

        Returns:
            Statistiques de la chaîne
        """
        self._update_metrics("get_stats")
        
        char_count = {}
        for char in text:
            if char in char_count:
                char_count[char] += 1
            else:
                char_count[char] = 1
        
        words = re.findall(r'\w+', text)
        sentences = re.split(r'[.!?]+', text)
        sentences = [s for s in sentences if s.strip()]
        
        digits = sum(c.isdigit() for c in text)
        letters = sum(c.isalpha() for c in text)
        punctuation = sum(c in self.PUNCTUATION for c in text)
        whitespace = sum(c.isspace() for c in text)
        
        avg_word_len = sum(len(w) for w in words) / len(words) if words else 0
        
        return StringStats(
            length=len(text),
            word_count=len(words),
            sentence_count=len(sentences),
            char_count=char_count,
            unique_chars=len(char_count),
            digit_count=digits,
            letter_count=letters,
            punctuation_count=punctuation,
            whitespace_count=whitespace,
            average_word_length=avg_word_len
        )

    def word_frequency(self, text: str, stop_words: bool = True) -> Dict[str, int]:
        """
        Calcule la fréquence des mots.

        Args:
            text: Chaîne à analyser
            stop_words: Exclure les mots communs

        Returns:
            Fréquence des mots
        """
        self._update_metrics("word_frequency")
        
        words = re.findall(r'\w+', text.lower())
        
        if stop_words:
            words = [w for w in words if w not in self.STOP_WORDS]
        
        freq = {}
        for word in words:
            if word in freq:
                freq[word] += 1
            else:
                freq[word] = 1
        
        return dict(sorted(freq.items(), key=lambda x: x[1], reverse=True))

    def count_sentences(self, text: str) -> int:
        """
        Compte le nombre de phrases.

        Args:
            text: Chaîne à analyser

        Returns:
            Nombre de phrases
        """
        self._update_metrics("count_sentences")
        sentences = re.split(r'[.!?]+', text)
        return len([s for s in sentences if s.strip()])

    def count_words(self, text: str) -> int:
        """
        Compte le nombre de mots.

        Args:
            text: Chaîne à analyser

        Returns:
            Nombre de mots
        """
        self._update_metrics("count_words")
        words = re.findall(r'\w+', text)
        return len(words)

    # ========================================================================
    # GÉNÉRATION
    # ========================================================================

    def generate_random_string(
        self,
        length: int = 16,
        include_digits: bool = True,
        include_letters: bool = True,
        include_special: bool = False,
        exclude: Optional[str] = None
    ) -> str:
        """
        Génère une chaîne aléatoire.

        Args:
            length: Longueur
            include_digits: Inclure des chiffres
            include_letters: Inclure des lettres
            include_special: Inclure des caractères spéciaux
            exclude: Caractères à exclure

        Returns:
            Chaîne aléatoire
        """
        self._update_metrics("generate_random_string")
        
        chars = ""
        if include_letters:
            chars += string.ascii_letters
        if include_digits:
            chars += string.digits
        if include_special:
            chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"
        
        if exclude:
            chars = ''.join(c for c in chars if c not in exclude)
        
        return ''.join(self.faker.random.choice(chars) for _ in range(length))

    def generate_password(
        self,
        length: int = 16,
        include_digits: bool = True,
        include_special: bool = True
    ) -> str:
        """
        Génère un mot de passe sécurisé.

        Args:
            length: Longueur
            include_digits: Inclure des chiffres
            include_special: Inclure des caractères spéciaux

        Returns:
            Mot de passe
        """
        self._update_metrics("generate_password")
        
        password = self.generate_random_string(
            length=length - 2,
            include_digits=include_digits,
            include_special=include_special
        )
        
        # Ajout de caractères de sécurité
        if include_letters:
            password += self.faker.random.choice(string.ascii_letters)
        if include_digits:
            password += self.faker.random.choice(string.digits)
        if include_special:
            password += self.faker.random.choice("!@#$%^&*")
        
        return password

    def generate_name(
        self,
        gender: Optional[str] = None,
        first_only: bool = False,
        last_only: bool = False
    ) -> str:
        """
        Génère un nom aléatoire.

        Args:
            gender: Genre ("male", "female")
            first_only: Uniquement le prénom
            last_only: Uniquement le nom

        Returns:
            Nom généré
        """
        self._update_metrics("generate_name")
        
        if first_only:
            return self.faker.first_name() if not gender else self.faker.first_name_male() if gender == "male" else self.faker.first_name_female()
        elif last_only:
            return self.faker.last_name()
        else:
            return self.faker.name()

    def generate_email(
        self,
        domain: Optional[str] = None,
        name: Optional[str] = None
    ) -> str:
        """
        Génère une adresse email aléatoire.

        Args:
            domain: Domaine (optionnel)
            name: Nom (optionnel)

        Returns:
            Email généré
        """
        self._update_metrics("generate_email")
        
        if name:
            email_name = self._to_snake_case(name)
        else:
            email_name = self.faker.user_name()
        
        domain = domain or self.faker.domain_name()
        
        return f"{email_name}@{domain}"

    def generate_phone(self, region: str = "US") -> str:
        """
        Génère un numéro de téléphone aléatoire.

        Args:
            region: Région

        Returns:
            Numéro de téléphone
        """
        self._update_metrics("generate_phone")
        return self.faker.phone_number()

    def generate_uuid(self) -> str:
        """
        Génère un UUID.

        Returns:
            UUID généré
        """
        self._update_metrics("generate_uuid")
        return str(uuid4())

    def generate_slug(self, text: Optional[str] = None) -> str:
        """
        Génère un slug.

        Args:
            text: Texte de base (optionnel)

        Returns:
            Slug généré
        """
        self._update_metrics("generate_slug")
        
        if not text:
            text = self.faker.sentence()
        
        return self.slugify(text)

    # ========================================================================
    # CONVERSIONS
    # ========================================================================

    def to_plural(self, text: str) -> str:
        """
        Convertit un mot au pluriel.

        Args:
            text: Mot à convertir

        Returns:
            Mot au pluriel
        """
        self._update_metrics("to_plural")
        return self.inflect.plural(text)

    def to_singular(self, text: str) -> str:
        """
        Convertit un mot au singulier.

        Args:
            text: Mot à convertir

        Returns:
            Mot au singulier
        """
        self._update_metrics("to_singular")
        return self.inflect.singular_noun(text)

    def to_ordinal(self, number: int) -> str:
        """
        Convertit un nombre en ordinal.

        Args:
            number: Nombre

        Returns:
            Ordinal
        """
        self._update_metrics("to_ordinal")
        return self.inflect.ordinal(number)

    def encode_base64(self, text: str) -> str:
        """
        Encode une chaîne en Base64.

        Args:
            text: Chaîne à encoder

        Returns:
            Chaîne encodée
        """
        self._update_metrics("encode_base64")
        return base64.b64encode(text.encode()).decode()

    def decode_base64(self, text: str) -> str:
        """
        Décode une chaîne Base64.

        Args:
            text: Chaîne à décoder

        Returns:
            Chaîne décodée
        """
        self._update_metrics("decode_base64")
        return base64.b64decode(text.encode()).decode()

    def to_json(self, data: Any, pretty: bool = True) -> str:
        """
        Convertit des données en JSON.

        Args:
            data: Données à convertir
            pretty: Formatage lisible

        Returns:
            JSON
        """
        self._update_metrics("to_json")
        
        if pretty:
            return json.dumps(data, indent=2, default=str)
        else:
            return json.dumps(data, default=str)

    def to_hex(self, text: str) -> str:
        """
        Convertit une chaîne en hexadécimal.

        Args:
            text: Chaîne à convertir

        Returns:
            Hexadécimal
        """
        self._update_metrics("to_hex")
        return text.encode().hex()

    def from_hex(self, hex_str: str) -> str:
        """
        Convertit de l'hexadécimal en chaîne.

        Args:
            hex_str: Hexadécimal à convertir

        Returns:
            Chaîne
        """
        self._update_metrics("from_hex")
        return bytes.fromhex(hex_str).decode()

    def to_md5(self, text: str) -> str:
        """
        Calcule le hash MD5 d'une chaîne.

        Args:
            text: Chaîne à hacher

        Returns:
            Hash MD5
        """
        self._update_metrics("to_md5")
        return hashlib.md5(text.encode()).hexdigest()

    def to_sha256(self, text: str) -> str:
        """
        Calcule le hash SHA-256 d'une chaîne.

        Args:
            text: Chaîne à hacher

        Returns:
            Hash SHA-256
        """
        self._update_metrics("to_sha256")
        return hashlib.sha256(text.encode()).hexdigest()

    # ========================================================================
    # RECHERCHE ET REMPLACEMENT
    # ========================================================================

    def contains(self, text: str, search: str, case_sensitive: bool = True) -> bool:
        """
        Vérifie si une chaîne contient une sous-chaîne.

        Args:
            text: Chaîne à vérifier
            search: Sous-chaîne à chercher
            case_sensitive: Sensible à la casse

        Returns:
            True si trouvé
        """
        self._update_metrics("contains")
        
        if not case_sensitive:
            return search.lower() in text.lower()
        return search in text

    def count_occurrences(self, text: str, search: str) -> int:
        """
        Compte le nombre d'occurrences d'une sous-chaîne.

        Args:
            text: Chaîne à analyser
            search: Sous-chaîne à compter

        Returns:
            Nombre d'occurrences
        """
        self._update_metrics("count_occurrences")
        return text.count(search)

    def find_all(self, text: str, pattern: str) -> List[str]:
        """
        Trouve toutes les occurrences d'un pattern.

        Args:
            text: Chaîne à analyser
            pattern: Pattern à chercher

        Returns:
            Liste des occurrences
        """
        self._update_metrics("find_all")
        return re.findall(pattern, text)

    def replace_all(self, text: str, replacements: Dict[str, str]) -> str:
        """
        Remplace plusieurs paires dans une chaîne.

        Args:
            text: Chaîne à modifier
            replacements: Dictionnaire des remplacements

        Returns:
            Chaîne modifiée
        """
        self._update_metrics("replace_all")
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    def _update_metrics(self, operation: str) -> None:
        """
        Met à jour les métriques.

        Args:
            operation: Type d'opération
        """
        self._metrics["total_operations"] += 1
        
        if operation not in self._metrics["by_type"]:
            self._metrics["by_type"][operation] = 0
        self._metrics["by_type"][operation] += 1
        
        self._metrics["last_operation"] = datetime.now().isoformat()

    def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_operations": self._metrics["total_operations"],
                "by_type": self._metrics["by_type"],
                "last_operation": self._metrics["last_operation"],
                "default_locale": self.default_locale,
                "random_seed": self.random_seed,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de StringUtils...")
        self._metrics.clear()
        logger.info("StringUtils fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_string_utils(
    default_locale: str = "en_US",
    random_seed: Optional[int] = None
) -> StringUtils:
    """
    Crée une instance de StringUtils.

    Args:
        default_locale: Locale par défaut
        random_seed: Seed pour la reproductibilité

    Returns:
        Instance de StringUtils
    """
    return StringUtils(
        default_locale=default_locale,
        random_seed=random_seed
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "StringCase",
    "StringValidation",
    "StringStats",
    "StringUtils",
    "create_string_utils"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation de StringUtils."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT STRING UTILS")
    print("=" * 60)

    # Création de l'instance
    string_utils = create_string_utils(
        default_locale="fr_FR",
        random_seed=42
    )

    print(f"\n✅ StringUtils initialisé")

    # Transformation de casse
    text = "Hello World String Utils"
    print(f"\n📝 Transformation de casse:")
    print(f"   Original: {text}")
    print(f"   Snake: {string_utils.to_case(text, StringCase.SNAKE)}")
    print(f"   Camel: {string_utils.to_case(text, StringCase.CAMEL)}")
    print(f"   Pascal: {string_utils.to_case(text, StringCase.PASCAL)}")
    print(f"   Kebab: {string_utils.to_case(text, StringCase.KEBAB)}")

    # Validation
    print(f"\n✅ Validation:")
    print(f"   Email valid: {string_utils.validate('test@example.com', StringValidation.EMAIL)}")
    print(f"   UUID valid: {string_utils.validate('123e4567-e89b-12d3-a456-426614174000', StringValidation.UUID)}")
    print(f"   Phone valid: {string_utils.validate('+33123456789', StringValidation.PHONE)}")

    # Normalisation
    text_with_accents = "Café Noël"
    print(f"\n🔤 Normalisation:")
    print(f"   Original: {text_with_accents}")
    print(f"   Normalisé: {string_utils.normalize(text_with_accents)}")
    print(f"   Slug: {string_utils.slugify(text_with_accents)}")

    # Statistiques
    sample_text = "Hello world! This is a test sentence. How are you?"
    stats = string_utils.get_stats(sample_text)
    print(f"\n📊 Statistiques:")
    print(f"   Longueur: {stats.length}")
    print(f"   Mots: {stats.word_count}")
    print(f"   Phrases: {stats.sentence_count}")
    print(f"   Caractères uniques: {stats.unique_chars}")
    print(f"   Longueur moyenne des mots: {stats.average_word_length:.2f}")

    # Génération
    print(f"\n🎲 Génération:")
    print(f"   Nom: {string_utils.generate_name()}")
    print(f"   Email: {string_utils.generate_email()}")
    print(f"   Password: {string_utils.generate_password()}")
    print(f"   UUID: {string_utils.generate_uuid()}")

    # Conversion
    print(f"\n🔄 Conversion:")
    print(f"   Plural: {string_utils.to_plural('child')}")
    print(f"   Singular: {string_utils.to_singular('children')}")
    print(f"   Ordinal: {string_utils.to_ordinal(42)}")
    print(f"   Base64: {string_utils.encode_base64('Hello World')}")

    # Santé du service
    health = string_utils.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Opérations: {health['total_operations']}")
    print(f"   Dernière opération: {health['last_operation']}")

    # Fermeture
    await string_utils.close()

    print("\n" + "=" * 60)
    print("StringUtils NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
