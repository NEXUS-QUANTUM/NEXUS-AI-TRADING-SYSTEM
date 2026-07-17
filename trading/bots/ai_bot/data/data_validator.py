"""
NEXUS AI TRADING SYSTEM - Data Validator for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/data/data_validator.py
Description: Validateur de données pour le bot AI.
             Supporte la validation de types, de plages, de patterns,
             de cohérence, d'intégrité et de qualité des données.
             Gère les données manquantes, les outliers, les doublons
             et les anomalies avec des règles configurables.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

import numpy as np
import pandas as pd
from scipy import stats

from shared.exceptions import ValidationError
from shared.helpers.number_helpers import round_decimal
from shared.helpers.date_helpers import timestamp_to_datetime

# Configuration du logging
logger = logging.getLogger(__name__)


class ValidationRuleType(Enum):
    """Types de règles de validation."""
    TYPE = "type"                  # Type de données
    RANGE = "range"                # Plage de valeurs
    PATTERN = "pattern"            # Expression régulière
    REQUIRED = "required"          # Colonne requise
    UNIQUE = "unique"              # Valeurs uniques
    FORMAT = "format"              # Format de date/heure
    CORRELATION = "correlation"    # Corrélation entre colonnes
    CUSTOM = "custom"              # Règle personnalisée
    OUTLIER = "outlier"            # Détection d'outliers
    NULL = "null"                  # Valeurs nulles
    DUPLICATE = "duplicate"        # Doublons
    CONSISTENCY = "consistency"    # Cohérence logique
    SEQUENCE = "sequence"          # Séquence continue


class ValidationSeverity(Enum):
    """Niveaux de sévérité des règles."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationRule:
    """
    Règle de validation.
    """
    name: str
    type: ValidationRuleType
    severity: ValidationSeverity = ValidationSeverity.ERROR
    description: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'name': self.name,
            'type': self.type.value,
            'severity': self.severity.value,
            'description': self.description,
            'params': self.params,
            'enabled': self.enabled
        }


@dataclass
class ValidationConfig:
    """
    Configuration de la validation.
    """
    # Règles par défaut
    default_rules: List[ValidationRule] = field(default_factory=list)
    
    # Paramètres de validation
    strict_mode: bool = True
    max_errors: int = 100
    stop_on_error: bool = False
    
    # Paramètres de qualité des données
    max_null_ratio: float = 0.1  # 10%
    max_duplicate_ratio: float = 0.05  # 5%
    max_outlier_ratio: float = 0.01  # 1%
    min_completeness: float = 0.9  # 90%
    
    # Paramètres de détection
    outlier_method: str = "iqr"  # 'iqr', 'zscore', 'mad'
    outlier_threshold: float = 3.0
    sequence_tolerance: float = 0.01
    
    # Paramètres de correction
    auto_fix: bool = False
    fix_missing: str = "mean"  # 'mean', 'median', 'mode', 'zero', 'ffill'
    fix_outliers: str = "clip"  # 'clip', 'remove', 'winsorize'
    
    # Paramètres de reporting
    generate_report: bool = True
    report_detail: str = "normal"  # 'minimal', 'normal', 'detailed'
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.max_errors < 1:
            raise ValidationError("max_errors doit être >= 1")
        
        if self.max_null_ratio < 0 or self.max_null_ratio > 1:
            raise ValidationError("max_null_ratio doit être entre 0 et 1")
        
        if self.outlier_method not in ['iqr', 'zscore', 'mad']:
            raise ValidationError("outlier_method doit être 'iqr', 'zscore' ou 'mad'")


@dataclass
class ValidationReport:
    """
    Rapport de validation.
    """
    # Statut global
    is_valid: bool = True
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    
    # Résultats par colonne
    column_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Résultats par règle
    rule_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Détails des erreurs
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    
    # Statistiques
    total_rows: int = 0
    total_columns: int = 0
    missing_count: int = 0
    duplicate_count: int = 0
    outlier_count: int = 0
    
    # Correction
    corrections_applied: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'is_valid': self.is_valid,
            'total_checks': self.total_checks,
            'passed_checks': self.passed_checks,
            'failed_checks': self.failed_checks,
            'total_rows': self.total_rows,
            'total_columns': self.total_columns,
            'missing_count': self.missing_count,
            'duplicate_count': self.duplicate_count,
            'outlier_count': self.outlier_count,
            'corrections_applied': self.corrections_applied,
            'errors': self.errors[:10],  # Limitation
            'warnings': self.warnings[:10],
            'column_results': self.column_results,
            'rule_results': self.rule_results
        }
    
    def summary(self) -> str:
        """Retourne un résumé lisible."""
        lines = []
        lines.append("=" * 60)
        lines.append("VALIDATION REPORT")
        lines.append("=" * 60)
        lines.append(f"Status: {'✓ VALID' if self.is_valid else '✗ INVALID'}")
        lines.append(f"Total Checks: {self.total_checks}")
        lines.append(f"Passed: {self.passed_checks}")
        lines.append(f"Failed: {self.failed_checks}")
        lines.append(f"Rows: {self.total_rows}")
        lines.append(f"Columns: {self.total_columns}")
        lines.append(f"Missing Values: {self.missing_count}")
        lines.append(f"Duplicates: {self.duplicate_count}")
        lines.append(f"Outliers: {self.outlier_count}")
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
        lines.append("=" * 60)
        return "\n".join(lines)


class DataValidator:
    """
    Validateur de données pour le bot AI.
    """
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        """
        Initialise le validateur.
        
        Args:
            config: Configuration de la validation.
        """
        self.config = config or ValidationConfig()
        
        # Règles par défaut
        self._rules: List[ValidationRule] = []
        self._initialize_default_rules()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            'total_validated': 0,
            'total_errors': 0,
            'total_warnings': 0,
            'total_corrections': 0
        }
        
        logger.info(f"DataValidator initialisé - {len(self._rules)} règles")
        logger.info(f"Mode strict: {self.config.strict_mode}")
    
    def _initialize_default_rules(self) -> None:
        """
        Initialise les règles par défaut.
        """
        # Règles de base
        self.add_rule(ValidationRule(
            name="required_columns",
            type=ValidationRuleType.REQUIRED,
            severity=ValidationSeverity.ERROR,
            description="Vérifie la présence des colonnes OHLCV",
            params={'columns': ['open', 'high', 'low', 'close', 'volume']}
        ))
        
        self.add_rule(ValidationRule(
            name="price_positive",
            type=ValidationRuleType.RANGE,
            severity=ValidationSeverity.ERROR,
            description="Les prix doivent être positifs",
            params={
                'columns': ['open', 'high', 'low', 'close'],
                'min': 0.000001,
                'min_inclusive': False
            }
        ))
        
        self.add_rule(ValidationRule(
            name="volume_positive",
            type=ValidationRuleType.RANGE,
            severity=ValidationSeverity.WARNING,
            description="Le volume doit être positif",
            params={
                'columns': ['volume'],
                'min': 0,
                'min_inclusive': True
            }
        ))
        
        self.add_rule(ValidationRule(
            name="high_low_consistency",
            type=ValidationRuleType.CONSISTENCY,
            severity=ValidationSeverity.ERROR,
            description="High doit être >= Low",
            params={
                'condition': 'high >= low'
            }
        ))
        
        self.add_rule(ValidationRule(
            name="price_consistency",
            type=ValidationRuleType.CONSISTENCY,
            severity=ValidationSeverity.ERROR,
            description="Open, High, Low, Close doivent être cohérents",
            params={
                'condition': 'high >= open and high >= close and low <= open and low <= close'
            }
        ))
        
        self.add_rule(ValidationRule(
            name="date_sequence",
            type=ValidationRuleType.SEQUENCE,
            severity=ValidationSeverity.WARNING,
            description="Les dates doivent être continues",
            params={
                'tolerance': 0.01
            }
        ))
        
        self.add_rule(ValidationRule(
            name="no_duplicates",
            type=ValidationRuleType.DUPLICATE,
            severity=ValidationSeverity.WARNING,
            description="Pas de doublons",
            params={}
        ))
        
        # Règles par défaut de la configuration
        for rule in self.config.default_rules:
            self.add_rule(rule)
    
    # ============================================================
    # GESTION DES RÈGLES
    # ============================================================
    
    def add_rule(self, rule: ValidationRule) -> None:
        """
        Ajoute une règle de validation.
        
        Args:
            rule: Règle à ajouter.
        """
        self._rules.append(rule)
        logger.debug(f"Règle ajoutée: {rule.name}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """
        Supprime une règle.
        
        Args:
            rule_name: Nom de la règle.
            
        Returns:
            True si supprimée.
        """
        for i, rule in enumerate(self._rules):
            if rule.name == rule_name:
                self._rules.pop(i)
                logger.debug(f"Règle supprimée: {rule_name}")
                return True
        return False
    
    def enable_rule(self, rule_name: str, enabled: bool = True) -> None:
        """
        Active ou désactive une règle.
        
        Args:
            rule_name: Nom de la règle.
            enabled: État.
        """
        for rule in self._rules:
            if rule.name == rule_name:
                rule.enabled = enabled
                logger.debug(f"Règle {rule_name} {'activée' if enabled else 'désactivée'}")
                return
    
    def get_rules(self, enabled_only: bool = True) -> List[ValidationRule]:
        """
        Retourne les règles.
        
        Args:
            enabled_only: Uniquement les règles activées.
            
        Returns:
            Liste des règles.
        """
        if enabled_only:
            return [r for r in self._rules if r.enabled]
        return self._rules.copy()
    
    # ============================================================
    # VALIDATION PRINCIPALE
    # ============================================================
    
    def validate(
        self,
        data: Union[pd.DataFrame, np.ndarray, Dict, List],
        rules: Optional[List[ValidationRule]] = None
    ) -> Tuple[pd.DataFrame, ValidationReport]:
        """
        Valide les données.
        
        Args:
            data: Données à valider.
            rules: Règles spécifiques (None = toutes les règles).
            
        Returns:
            Tuple (données traitées, rapport de validation).
        """
        start_time = time.time()
        
        # Conversion en DataFrame
        df = self._to_dataframe(data)
        
        if df.empty:
            raise ValidationError("Données vides")
        
        logger.info(f"Validation de {len(df)} lignes, {len(df.columns)} colonnes")
        
        # Création du rapport
        report = ValidationReport(
            total_rows=len(df),
            total_columns=len(df.columns)
        )
        
        # Règles à appliquer
        rules_to_apply = rules or self.get_rules(True)
        report.total_checks = len(rules_to_apply)
        
        # Application des règles
        for rule in rules_to_apply:
            try:
                result = self._apply_rule(df, rule)
                
                if result.get('passed', False):
                    report.passed_checks += 1
                    report.rule_results[rule.name] = {
                        'passed': True,
                        'details': result.get('details', {})
                    }
                else:
                    report.failed_checks += 1
                    report.is_valid = False
                    report.rule_results[rule.name] = {
                        'passed': False,
                        'details': result.get('details', {}),
                        'errors': result.get('errors', [])
                    }
                    
                    if rule.severity == ValidationSeverity.ERROR:
                        report.errors.extend(result.get('errors', []))
                    elif rule.severity == ValidationSeverity.WARNING:
                        report.warnings.extend(result.get('errors', []))
                    
                    # Correction auto
                    if self.config.auto_fix and result.get('fixable', False):
                        df = self._apply_fix(df, rule, result)
                        report.corrections_applied += 1
                    
                    # Arrêt sur erreur
                    if self.config.stop_on_error and rule.severity == ValidationSeverity.CRITICAL:
                        raise ValidationError(f"Erreur critique: {rule.name}")
                    
            except Exception as e:
                logger.error(f"Erreur dans la règle {rule.name}: {e}")
                report.failed_checks += 1
                report.is_valid = False
                report.errors.append({
                    'rule': rule.name,
                    'error': str(e),
                    'severity': rule.severity.value
                })
        
        # Statistiques supplémentaires
        report.missing_count = df.isna().sum().sum()
        report.duplicate_count = df.duplicated().sum()
        report.outlier_count = self._count_outliers(df)
        
        # Mise à jour des statistiques du validateur
        self._stats['total_validated'] += len(df)
        self._stats['total_errors'] += len(report.errors)
        self._stats['total_warnings'] += len(report.warnings)
        self._stats['total_corrections'] += report.corrections_applied
        
        logger.info(f"Validation terminée: {report.passed_checks}/{report.total_checks} réussi")
        logger.info(report.summary())
        
        return df, report
    
    def _apply_rule(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """
        Applique une règle de validation.
        
        Args:
            df: DataFrame à valider.
            rule: Règle à appliquer.
            
        Returns:
            Résultat de la validation.
        """
        if rule.type == ValidationRuleType.REQUIRED:
            return self._check_required(df, rule)
        elif rule.type == ValidationRuleType.RANGE:
            return self._check_range(df, rule)
        elif rule.type == ValidationRuleType.TYPE:
            return self._check_type(df, rule)
        elif rule.type == ValidationRuleType.PATTERN:
            return self._check_pattern(df, rule)
        elif rule.type == ValidationRuleType.UNIQUE:
            return self._check_unique(df, rule)
        elif rule.type == ValidationRuleType.FORMAT:
            return self._check_format(df, rule)
        elif rule.type == ValidationRuleType.CORRELATION:
            return self._check_correlation(df, rule)
        elif rule.type == ValidationRuleType.OUTLIER:
            return self._check_outliers(df, rule)
        elif rule.type == ValidationRuleType.NULL:
            return self._check_null(df, rule)
        elif rule.type == ValidationRuleType.DUPLICATE:
            return self._check_duplicates(df, rule)
        elif rule.type == ValidationRuleType.CONSISTENCY:
            return self._check_consistency(df, rule)
        elif rule.type == ValidationRuleType.SEQUENCE:
            return self._check_sequence(df, rule)
        elif rule.type == ValidationRuleType.CUSTOM:
            return self._check_custom(df, rule)
        else:
            return {'passed': True, 'details': {'message': 'Règle non implémentée'}}
    
    # ============================================================
    # VALIDATION PAR TYPE DE RÈGLE
    # ============================================================
    
    def _check_required(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Vérifie les colonnes requises."""
        required_columns = rule.params.get('columns', [])
        missing = [col for col in required_columns if col not in df.columns]
        
        if missing:
            return {
                'passed': False,
                'errors': [f"Colonnes manquantes: {', '.join(missing)}"],
                'fixable': False
            }
        
        return {'passed': True, 'details': {'columns_present': len(required_columns)}}
    
    def _check_range(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Vérifie les plages de valeurs."""
        columns = rule.params.get('columns', df.columns.tolist())
        min_val = rule.params.get('min', -float('inf'))
        max_val = rule.params.get('max', float('inf'))
        min_inclusive = rule.params.get('min_inclusive', True)
        max_inclusive = rule.params.get('max_inclusive', True)
        
        errors = []
        fixed_data = False
        
        for col in columns:
            if col not in df.columns:
                continue
            
            series = df[col].dropna()
            
            if min_inclusive:
                below_min = series < min_val
            else:
                below_min = series <= min_val
            
            if max_inclusive:
                above_max = series > max_val
            else:
                above_max = series >= max_val
            
            invalid = below_min | above_max
            
            if invalid.any():
                n_invalid = invalid.sum()
                errors.append(f"Colonne {col}: {n_invalid} valeurs hors plage")
                fixed_data = True
        
        return {
            'passed': len(errors) == 0,
            'errors': errors,
            'fixable': fixed_data,
            'details': {'columns_checked': len(columns), 'errors_count': len(errors)}
        }
    
    def _check_type(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Vérifie les types de données."""
        columns = rule.params.get('columns', df.columns.tolist())
        expected_type = rule.params.get('type', 'numeric')
        
        errors = []
        
        for col in columns:
            if col not in df.columns:
                continue
            
            if expected_type == 'numeric':
                if not pd.api.types.is_numeric_dtype(df[col]):
                    errors.append(f"Colonne {col}: type non numérique ({df[col].dtype})")
            elif expected_type == 'datetime':
                if not pd.api.types.is_datetime64_any_dtype(df[col]):
                    errors.append(f"Colonne {col}: type non datetime ({df[col].dtype})")
            elif expected_type == 'string':
                if not pd.api.types.is_string_dtype(df[col]):
                    errors.append(f"Colonne {col}: type non string ({df[col].dtype})")
        
        return {
            'passed': len(errors) == 0,
            'errors': errors,
            'fixable': False,
            'details': {'columns_checked': len(columns)}
        }
    
    def _check_pattern(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Vérifie les motifs (regex)."""
        column = rule.params.get('column')
        pattern = rule.params.get('pattern')
        
        if not column or not pattern:
            return {'passed': True, 'details': {'message': 'Paramètres manquants'}}
        
        if column not in df.columns:
            return {'passed': True, 'details': {'message': f'Colonne {column} non trouvée'}}
        
        regex = re.compile(pattern)
        invalid = ~df[column].astype(str).str.match(regex)
        
        if invalid.any():
            return {
                'passed': False,
                'errors': [f"Colonne {column}: {invalid.sum()} valeurs ne correspondent pas au pattern"],
                'fixable': False
            }
        
        return {'passed': True, 'details': {'matched': len(df) - invalid.sum()}}
    
    def _check_unique(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Vérifie l'unicité des valeurs."""
        columns = rule.params.get('columns', df.columns.tolist())
        
        errors = []
        
        for col in columns:
            if col not in df.columns:
                continue
            
            duplicates = df[col].duplicated()
            if duplicates.any():
                errors.append(f"Colonne {col}: {duplicates.sum()} valeurs dupliquées")
        
        return {
            'passed': len(errors) == 0,
            'errors': errors,
            'fixable': False,
            'details': {'columns_checked': len(columns)}
        }
    
    def _check_format(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Vérifie le format des dates."""
        column = rule.params.get('column')
        format_str = rule.params.get('format', '%Y-%m-%d')
        
        if not column or column not in df.columns:
            return {'passed': True, 'details': {'message': f'Colonne {column} non trouvée'}}
        
        errors = []
        invalid_count = 0
        
        for idx, val in enumerate(df[column]):
            if pd.isna(val):
                continue
            try:
                datetime.strptime(str(val), format_str)
            except:
                invalid_count += 1
                errors.append(f"Ligne {idx}: format invalide ({val})")
        
        return {
            'passed': invalid_count == 0,
            'errors': errors[:10],  # Limiter les erreurs
            'fixable': False,
            'details': {'invalid_count': invalid_count, 'total': len(df)}
        }
    
    def _check_correlation(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Vérifie la corrélation entre colonnes."""
        col1 = rule.params.get('col1')
        col2 = rule.params.get('col2')
        min_corr = rule.params.get('min_correlation', 0.5)
        max_corr = rule.params.get('max_correlation', 1.0)
        
        if not col1 or not col2:
            return {'passed': True, 'details': {'message': 'Paramètres manquants'}}
        
        if col1 not in df.columns or col2 not in df.columns:
            return {'passed': True, 'details': {'message': 'Colonnes non trouvées'}}
        
        corr = df[col1].corr(df[col2])
        
        if pd.isna(corr):
            return {'passed': True, 'details': {'message': 'Corrélation NaN'}}
        
        if corr < min_corr or corr > max_corr:
            return {
                'passed': False,
                'errors': [f"Corrélation {col1}-{col2}: {corr:.4f} (hors plage [{min_corr}, {max_corr}])"],
                'fixable': False,
                'details': {'correlation': corr}
            }
        
        return {'passed': True, 'details': {'correlation': corr}}
    
    def _check_outliers(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Détecte les outliers."""
        columns = rule.params.get('columns', df.select_dtypes(include=[np.number]).columns.tolist())
        method = rule.params.get('method', self.config.outlier_method)
        threshold = rule.params.get('threshold', self.config.outlier_threshold)
        
        errors = []
        outlier_count = 0
        
        for col in columns:
            if col not in df.columns:
                continue
            
            series = df[col].dropna()
            if len(series) < 3:
                continue
            
            if method == 'iqr':
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outliers = (df[col] < lower) | (df[col] > upper)
            elif method == 'zscore':
                zscore = np.abs(stats.zscore(series))
                outliers = zscore > threshold
                outliers = pd.Series(False, index=df.index)
                outliers[series.index] = zscore > threshold
            elif method == 'mad':
                median = series.median()
                mad = np.median(np.abs(series - median))
                mod_zscore = 0.6745 * (series - median) / mad
                outliers = np.abs(mod_zscore) > threshold
                outliers = pd.Series(False, index=df.index)
                outliers[series.index] = np.abs(mod_zscore) > threshold
            else:
                continue
            
            n_outliers = outliers.sum()
            if n_outliers > 0:
                outlier_count += n_outliers
                ratio = n_outliers / len(df)
                if ratio > self.config.max_outlier_ratio:
                    errors.append(f"Colonne {col}: {n_outliers} outliers ({ratio:.2%})")
        
        return {
            'passed': len(errors) == 0,
            'errors': errors,
            'fixable': True,
            'details': {'outlier_count': outlier_count, 'columns_checked': len(columns)}
        }
    
    def _check_null(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Vérifie les valeurs nulles."""
        columns = rule.params.get('columns', df.columns.tolist())
        max_ratio = rule.params.get('max_ratio', self.config.max_null_ratio)
        
        errors = []
        missing_count = 0
        
        for col in columns:
            if col not in df.columns:
                continue
            
            n_null = df[col].isna().sum()
            if n_null > 0:
                missing_count += n_null
                ratio = n_null / len(df)
                if ratio > max_ratio:
                    errors.append(f"Colonne {col}: {n_null} valeurs manquantes ({ratio:.2%})")
        
        return {
            'passed': len(errors) == 0,
            'errors': errors,
            'fixable': True,
            'details': {'missing_count': missing_count}
        }
    
    def _check_duplicates(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Vérifie les doublons."""
        columns = rule.params.get('columns', df.columns.tolist())
        max_ratio = rule.params.get('max_ratio', self.config.max_duplicate_ratio)
        
        duplicates = df.duplicated(subset=columns)
        n_duplicates = duplicates.sum()
        
        if n_duplicates > 0:
            ratio = n_duplicates / len(df)
            if ratio > max_ratio:
                return {
                    'passed': False,
                    'errors': [f"{n_duplicates} lignes dupliquées ({ratio:.2%})"],
                    'fixable': True,
                    'details': {'duplicate_count': n_duplicates}
                }
        
        return {'passed': True, 'details': {'duplicate_count': n_duplicates}}
    
    def _check_consistency(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Vérifie la cohérence des données."""
        condition = rule.params.get('condition', '')
        if not condition:
            return {'passed': True, 'details': {'message': 'Condition manquante'}}
        
        try:
            invalid = ~df.eval(condition)
        except Exception as e:
            return {
                'passed': False,
                'errors': [f"Erreur d'évaluation: {e}"],
                'fixable': False
            }
        
        n_invalid = invalid.sum()
        
        if n_invalid > 0:
            return {
                'passed': False,
                'errors': [f"{n_invalid} lignes inconsistentes"],
                'fixable': False,
                'details': {'invalid_count': n_invalid}
            }
        
        return {'passed': True, 'details': {'valid_rows': len(df)}}
    
    def _check_sequence(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Vérifie la séquence des dates."""
        column = rule.params.get('column', 'timestamp')
        tolerance = rule.params.get('tolerance', self.config.sequence_tolerance)
        
        if column not in df.columns:
            return {'passed': True, 'details': {'message': f'Colonne {column} non trouvée'}}
        
        # Conversion en datetime
        dates = pd.to_datetime(df[column])
        if dates.isna().any():
            return {'passed': False, 'errors': ['Dates invalides'], 'fixable': False}
        
        # Vérification de la séquence
        diff = dates.diff().dropna()
        
        if len(diff) == 0:
            return {'passed': True, 'details': {'message': 'Séquence vide'}}
        
        # Vérification des écarts
        expected = diff.mode().iloc[0] if not diff.empty else timedelta(0)
        deviations = (diff - expected).abs() / (expected + timedelta(seconds=1))
        
        invalid = deviations > tolerance
        
        if invalid.any():
            return {
                'passed': False,
                'errors': [f"{invalid.sum()} écarts dans la séquence"],
                'fixable': False,
                'details': {'deviations': invalid.sum(), 'expected': str(expected)}
            }
        
        return {'passed': True, 'details': {'sequence_valid': True}}
    
    def _check_custom(self, df: pd.DataFrame, rule: ValidationRule) -> Dict[str, Any]:
        """Vérifie une règle personnalisée."""
        func = rule.params.get('function')
        if not callable(func):
            return {'passed': True, 'details': {'message': 'Fonction non définie'}}
        
        try:
            result = func(df)
            if isinstance(result, bool):
                return {
                    'passed': result,
                    'errors': [] if result else ['Règle personnalisée échouée'],
                    'fixable': False
                }
            elif isinstance(result, dict):
                return result
            else:
                return {'passed': True, 'details': {'message': 'Résultat non reconnu'}}
        except Exception as e:
            return {
                'passed': False,
                'errors': [f"Erreur personnalisée: {e}"],
                'fixable': False
            }
    
    # ============================================================
    # CORRECTION DES DONNÉES
    # ============================================================
    
    def _apply_fix(self, df: pd.DataFrame, rule: ValidationRule, result: Dict[str, Any]) -> pd.DataFrame:
        """
        Applique une correction aux données.
        
        Args:
            df: DataFrame original.
            rule: Règle violée.
            result: Résultat de la validation.
            
        Returns:
            DataFrame corrigé.
        """
        df_fixed = df.copy()
        
        if rule.type == ValidationRuleType.OUTLIER:
            return self._fix_outliers(df_fixed, rule)
        elif rule.type == ValidationRuleType.NULL:
            return self._fix_missing(df_fixed, rule)
        elif rule.type == ValidationRuleType.DUPLICATE:
            return self._fix_duplicates(df_fixed, rule)
        elif rule.type == ValidationRuleType.RANGE:
            return self._fix_range(df_fixed, rule)
        
        return df_fixed
    
    def _fix_outliers(self, df: pd.DataFrame, rule: ValidationRule) -> pd.DataFrame:
        """Corrige les outliers."""
        columns = rule.params.get('columns', df.select_dtypes(include=[np.number]).columns.tolist())
        method = self.config.fix_outliers
        
        for col in columns:
            if col not in df.columns:
                continue
            
            if method == 'clip':
                q1 = df[col].quantile(0.01)
                q3 = df[col].quantile(0.99)
                df[col] = df[col].clip(q1, q3)
            elif method == 'winsorize':
                from scipy.stats.mstats import winsorize
                df[col] = winsorize(df[col], limits=[0.01, 0.01])
            elif method == 'remove':
                q1 = df[col].quantile(0.01)
                q3 = df[col].quantile(0.99)
                df = df[(df[col] >= q1) & (df[col] <= q3)]
        
        return df
    
    def _fix_missing(self, df: pd.DataFrame, rule: ValidationRule) -> pd.DataFrame:
        """Corrige les valeurs manquantes."""
        columns = rule.params.get('columns', df.columns.tolist())
        method = self.config.fix_missing
        
        for col in columns:
            if col not in df.columns:
                continue
            
            if method == 'mean':
                df[col] = df[col].fillna(df[col].mean())
            elif method == 'median':
                df[col] = df[col].fillna(df[col].median())
            elif method == 'mode':
                df[col] = df[col].fillna(df[col].mode().iloc[0] if not df[col].mode().empty else 0)
            elif method == 'zero':
                df[col] = df[col].fillna(0)
            elif method == 'ffill':
                df[col] = df[col].fillna(method='ffill').fillna(method='bfill')
        
        return df
    
    def _fix_duplicates(self, df: pd.DataFrame, rule: ValidationRule) -> pd.DataFrame:
        """Corrige les doublons."""
        columns = rule.params.get('columns', df.columns.tolist())
        return df.drop_duplicates(subset=columns)
    
    def _fix_range(self, df: pd.DataFrame, rule: ValidationRule) -> pd.DataFrame:
        """Corrige les valeurs hors plage."""
        columns = rule.params.get('columns', df.columns.tolist())
        min_val = rule.params.get('min', None)
        max_val = rule.params.get('max', None)
        
        for col in columns:
            if col not in df.columns:
                continue
            
            if min_val is not None:
                df[col] = df[col].clip(lower=min_val)
            if max_val is not None:
                df[col] = df[col].clip(upper=max_val)
        
        return df
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def _to_dataframe(self, data: Union[pd.DataFrame, np.ndarray, Dict, List]) -> pd.DataFrame:
        """Convertit en DataFrame."""
        if isinstance(data, pd.DataFrame):
            return data
        elif isinstance(data, np.ndarray):
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            return pd.DataFrame([data])
        elif isinstance(data, list):
            if all(isinstance(x, dict) for x in data):
                return pd.DataFrame(data)
            return pd.DataFrame(data)
        else:
            raise ValidationError(f"Type de données non supporté: {type(data)}")
    
    def _count_outliers(self, df: pd.DataFrame) -> int:
        """Compte les outliers dans le DataFrame."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        count = 0
        
        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) < 3:
                continue
            
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            
            count += ((df[col] < lower) | (df[col] > upper)).sum()
        
        return count
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du validateur.
        
        Returns:
            Statistiques.
        """
        return self._stats.copy()
    
    def reset(self) -> None:
        """
        Réinitialise les statistiques.
        """
        self._stats = {
            'total_validated': 0,
            'total_errors': 0,
            'total_warnings': 0,
            'total_corrections': 0
        }
        logger.info("DataValidator réinitialisé")


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_validator(
    strict_mode: bool = True,
    auto_fix: bool = False,
    **kwargs
) -> DataValidator:
    """
    Crée un validateur avec configuration simplifiée.
    
    Args:
        strict_mode: Mode strict.
        auto_fix: Correction automatique.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance du DataValidator.
    """
    config = ValidationConfig(
        strict_mode=strict_mode,
        auto_fix=auto_fix,
        **kwargs
    )
    return DataValidator(config)


def validate_data(
    data: Union[pd.DataFrame, np.ndarray, Dict, List],
    rules: Optional[List[ValidationRule]] = None,
    **kwargs
) -> Tuple[pd.DataFrame, ValidationReport]:
    """
    Valide rapidement des données.
    
    Args:
        data: Données à valider.
        rules: Règles spécifiques.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Tuple (données traitées, rapport).
    """
    validator = create_validator(**kwargs)
    return validator.validate(data, rules)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'DataValidator',
    'ValidationConfig',
    'ValidationReport',
    'ValidationRule',
    'ValidationRuleType',
    'ValidationSeverity',
    'create_validator',
    'validate_data'
]

# ============================================================
# FIN DU FICHIER
# ============================================================
