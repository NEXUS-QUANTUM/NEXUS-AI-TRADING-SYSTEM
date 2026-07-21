"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Documentation
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Documentation complète du bot d'arbitrage NEXUS
"""

# ============================================================
# PACKAGE METADATA
# ============================================================
__version__ = "2.0.0"
__author__ = "NEXUS QUANTUM TEAM"
__description__ = "Documentation complète du bot d'arbitrage NEXUS"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"
__license__ = "Proprietary"

# ============================================================
# IMPORTS
# ============================================================
import os
import sys
import json
import yaml
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class DocCategory(Enum):
    """Catégories de documentation"""
    GENERAL = "general"
    SETUP = "setup"
    TRADING = "trading"
    OPS = "ops"
    REFERENCE = "reference"
    META = "meta"

class DocStatus(Enum):
    """Statuts de documentation"""
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class DocMetadata:
    """Métadonnées de documentation"""
    title: str
    description: str
    category: DocCategory
    status: DocStatus
    version: str
    author: str
    created: datetime
    updated: datetime
    tags: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

@dataclass
class DocSection:
    """Section de documentation"""
    title: str
    level: int
    content: str
    subsections: List['DocSection'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Documentation:
    """Documentation complète"""
    name: str
    title: str
    description: str
    category: DocCategory
    status: DocStatus
    version: str
    path: Path
    sections: List[DocSection]
    metadata: DocMetadata
    content: str = ""
    toc: List[Dict[str, Any]] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    created: datetime = field(default_factory=datetime.now)
    updated: datetime = field(default_factory=datetime.now)

# ============================================================
# DOCUMENTATION STRUCTURE
# ============================================================

DOCS_STRUCTURE = {
    "readme": {
        "path": "README.md",
        "title": "Documentation Principale",
        "description": "Vue d'ensemble du système NEXUS AI Trading",
        "order": 0,
        "category": DocCategory.GENERAL,
        "icon": "📚",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    },
    "getting_started": {
        "path": "GETTING_STARTED.md",
        "title": "Guide de Démarrage Rapide",
        "description": "Introduction rapide au système",
        "order": 1,
        "category": DocCategory.GENERAL,
        "icon": "🚀",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    },
    "configuration": {
        "path": "CONFIGURATION.md",
        "title": "Guide de Configuration",
        "description": "Configuration détaillée du système",
        "order": 2,
        "category": DocCategory.SETUP,
        "icon": "⚙️",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    },
    "deployment": {
        "path": "DEPLOYMENT.md",
        "title": "Guide de Déploiement",
        "description": "Déploiement en production",
        "order": 3,
        "category": DocCategory.SETUP,
        "icon": "🏗️",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    },
    "exchanges": {
        "path": "EXCHANGES.md",
        "title": "Guide des Exchanges",
        "description": "Intégration et configuration des exchanges",
        "order": 4,
        "category": DocCategory.TRADING,
        "icon": "🏦",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    },
    "strategies": {
        "path": "STRATEGIES.md",
        "title": "Guide des Stratégies",
        "description": "Types de stratégies d'arbitrage disponibles",
        "order": 5,
        "category": DocCategory.TRADING,
        "icon": "📈",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    },
    "risk_management": {
        "path": "RISK_MANAGEMENT.md",
        "title": "Guide de Gestion des Risques",
        "description": "Gestion des risques et sécurité",
        "order": 6,
        "category": DocCategory.TRADING,
        "icon": "🛡️",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    },
    "monitoring": {
        "path": "MONITORING.md",
        "title": "Guide de Monitoring",
        "description": "Monitoring et alertes",
        "order": 7,
        "category": DocCategory.OPS,
        "icon": "📊",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    },
    "maintenance": {
        "path": "MAINTENANCE.md",
        "title": "Guide de Maintenance",
        "description": "Maintenance et mise à jour",
        "order": 8,
        "category": DocCategory.OPS,
        "icon": "🔧",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    },
    "backup": {
        "path": "BACKUP.md",
        "title": "Guide de Backup et Recovery",
        "description": "Sauvegarde et récupération",
        "order": 9,
        "category": DocCategory.OPS,
        "icon": "💾",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    },
    "api": {
        "path": "API.md",
        "title": "Référence API",
        "description": "Documentation complète de l'API",
        "order": 10,
        "category": DocCategory.REFERENCE,
        "icon": "🔌",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    },
    "troubleshooting": {
        "path": "TROUBLESHOOTING.md",
        "title": "Guide de Dépannage",
        "description": "Résolution des problèmes courants",
        "order": 11,
        "category": DocCategory.REFERENCE,
        "icon": "🔍",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    },
    "changelog": {
        "path": "CHANGELOG.md",
        "title": "Journal des Modifications",
        "description": "Historique des versions et des changements",
        "order": 12,
        "category": DocCategory.META,
        "icon": "📝",
        "status": DocStatus.PUBLISHED,
        "version": "2.0.0"
    }
}

DOCS_CATEGORIES = {
    "general": {
        "title": "📚 Général",
        "description": "Vue d'ensemble et introduction",
        "icon": "📚",
        "order": 0
    },
    "setup": {
        "title": "⚙️ Configuration",
        "description": "Installation et configuration du système",
        "icon": "⚙️",
        "order": 1
    },
    "trading": {
        "title": "📈 Trading",
        "description": "Stratégies de trading et gestion des risques",
        "icon": "📈",
        "order": 2
    },
    "ops": {
        "title": "🔧 Opérations",
        "description": "Monitoring, maintenance et backup",
        "icon": "🔧",
        "order": 3
    },
    "reference": {
        "title": "🔍 Référence",
        "description": "Documentation technique et API",
        "icon": "🔍",
        "order": 4
    },
    "meta": {
        "title": "📝 Métadonnées",
        "description": "Informations sur le projet",
        "icon": "📝",
        "order": 5
    }
}

# ============================================================
# DOCUMENTATION LOADER
# ============================================================

class DocumentationLoader:
    """
    Chargeur de documentation complet
    
    Permet de charger, parser, valider et gérer la documentation du système
    """
    
    def __init__(self, docs_dir: Optional[Union[str, Path]] = None):
        """
        Initialise le chargeur de documentation
        
        Args:
            docs_dir: Répertoire de documentation
        """
        self.docs_dir = Path(docs_dir) if docs_dir else Path(__file__).parent
        self._cache: Dict[str, Documentation] = {}
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._toc_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._validators: Dict[str, Callable] = {}
        
        # Créer les répertoires nécessaires
        self._ensure_dirs()
        
        # Charger les validateurs
        self._register_validators()
        
        logger.info(f"DocumentationLoader initialized with docs_dir: {self.docs_dir}")
    
    def _ensure_dirs(self):
        """Crée les répertoires nécessaires"""
        (self.docs_dir / "assets").mkdir(exist_ok=True)
        (self.docs_dir / "assets" / "images").mkdir(exist_ok=True)
        (self.docs_dir / "assets" / "diagrams").mkdir(exist_ok=True)
        (self.docs_dir / "examples").mkdir(exist_ok=True)
        (self.docs_dir / "api").mkdir(exist_ok=True)
        (self.docs_dir / "guides").mkdir(exist_ok=True)
        (self.docs_dir / "reference").mkdir(exist_ok=True)
    
    def _register_validators(self):
        """Enregistre les validateurs de documentation"""
        self._validators = {
            "required_fields": self._validate_required_fields,
            "link_check": self._validate_links,
            "image_check": self._validate_images,
            "section_structure": self._validate_section_structure,
            "metadata": self._validate_metadata,
            "version": self._validate_version,
        }
    
    def _validate_required_fields(self, doc: Documentation) -> List[str]:
        """Valide les champs requis"""
        errors = []
        if not doc.title:
            errors.append("Title is required")
        if not doc.description:
            errors.append("Description is required")
        if not doc.path.exists():
            errors.append(f"File not found: {doc.path}")
        return errors
    
    def _validate_links(self, doc: Documentation) -> List[str]:
        """Valide les liens"""
        errors = []
        # Implémentation de validation des liens
        return errors
    
    def _validate_images(self, doc: Documentation) -> List[str]:
        """Valide les images"""
        errors = []
        # Implémentation de validation des images
        return errors
    
    def _validate_section_structure(self, doc: Documentation) -> List[str]:
        """Valide la structure des sections"""
        errors = []
        if not doc.sections:
            errors.append("No sections found")
        return errors
    
    def _validate_metadata(self, doc: Documentation) -> List[str]:
        """Valide les métadonnées"""
        errors = []
        if not doc.metadata.version:
            errors.append("Version is required")
        if not doc.metadata.author:
            errors.append("Author is required")
        return errors
    
    def _validate_version(self, doc: Documentation) -> List[str]:
        """Valide la version"""
        errors = []
        if doc.metadata.version != __version__:
            errors.append(f"Version mismatch: {doc.metadata.version} != {__version__}")
        return errors
    
    def get_doc_path(self, doc_name: str) -> Path:
        """
        Récupère le chemin d'un document
        
        Args:
            doc_name: Nom du document
            
        Returns:
            Path: Chemin du document
        """
        if doc_name in DOCS_STRUCTURE:
            return self.docs_dir / DOCS_STRUCTURE[doc_name]["path"]
        return self.docs_dir / f"{doc_name}.md"
    
    def get_doc_info(self, doc_name: str) -> Dict[str, Any]:
        """
        Récupère les informations d'un document
        
        Args:
            doc_name: Nom du document
            
        Returns:
            Dict[str, Any]: Informations du document
        """
        if doc_name in DOCS_STRUCTURE:
            return DOCS_STRUCTURE[doc_name].copy()
        
        return {
            "path": f"{doc_name}.md",
            "title": doc_name.replace("_", " ").title(),
            "description": "",
            "order": 999,
            "category": DocCategory.REFERENCE,
            "icon": "📄",
            "status": DocStatus.DRAFT,
            "version": __version__
        }
    
    def load_doc(self, doc_name: str, force_reload: bool = False) -> Documentation:
        """
        Charge un document avec ses métadonnées
        
        Args:
            doc_name: Nom du document
            force_reload: Forcer le rechargement
            
        Returns:
            Documentation: Document chargé
        """
        if not force_reload and doc_name in self._cache:
            return self._cache[doc_name]
        
        doc_path = self.get_doc_path(doc_name)
        info = self.get_doc_info(doc_name)
        
        # Créer les métadonnées
        metadata = DocMetadata(
            title=info["title"],
            description=info.get("description", ""),
            category=info.get("category", DocCategory.GENERAL),
            status=info.get("status", DocStatus.PUBLISHED),
            version=info.get("version", __version__),
            author=__author__,
            created=datetime.now(),
            updated=datetime.now(),
            tags=[],
            references=[],
            examples=[]
        )
        
        if not doc_path.exists():
            content = self._generate_missing_doc(doc_name, info)
            sections = []
        else:
            content, parsed_metadata = self._parse_document(doc_path)
            # Mettre à jour les métadonnées avec les données parsées
            if 'title' in parsed_metadata:
                metadata.title = parsed_metadata['title']
            if 'description' in parsed_metadata:
                metadata.description = parsed_metadata['description']
            if 'tags' in parsed_metadata:
                metadata.tags = parsed_metadata['tags']
            if 'references' in parsed_metadata:
                metadata.references = parsed_metadata['references']
            
            sections = self._parse_sections(content)
        
        # Générer la table des matières
        toc = self._generate_toc(content)
        
        # Créer le document
        doc = Documentation(
            name=doc_name,
            title=metadata.title,
            description=metadata.description,
            category=metadata.category,
            status=metadata.status,
            version=metadata.version,
            path=doc_path,
            sections=sections,
            metadata=metadata,
            content=content,
            toc=toc,
            references=metadata.references,
            examples=metadata.examples,
            created=datetime.fromtimestamp(doc_path.stat().st_mtime) if doc_path.exists() else datetime.now(),
            updated=datetime.fromtimestamp(doc_path.stat().st_mtime) if doc_path.exists() else datetime.now()
        )
        
        self._cache[doc_name] = doc
        return doc
    
    def _generate_missing_doc(self, doc_name: str, info: Dict[str, Any]) -> str:
        """Génère un document manquant"""
        return f"""# {info['title']}

## 📋 Description

{info['description'] or f"Documentation pour {doc_name}"}

## 📖 Contenu

Ce document est en cours de rédaction. Veuillez consulter les autres documents de la documentation.

## 🏷️ Métadonnées

- **Version**: {info.get('version', __version__)}
- **Catégorie**: {info.get('category', 'general').value if hasattr(info.get('category', 'general'), 'value') else info.get('category', 'general')}
- **Statut**: {info.get('status', 'draft').value if hasattr(info.get('status', 'draft'), 'value') else info.get('status', 'draft')}

## 🔗 Liens Connexes

- [Documentation Principale](README.md)
- [Guide de Démarrage Rapide](GETTING_STARTED.md)
- [Guide de Configuration](CONFIGURATION.md)

---

*© 2026 NEXUS QUANTUM LTD - Tous droits réservés*
"""
    
    def _parse_document(self, doc_path: Path) -> Tuple[str, Dict[str, Any]]:
        """Parse un document pour en extraire les métadonnées"""
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metadata = {}
        
        # Extraire le titre du premier heading
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                metadata['title'] = line[2:].strip()
                break
        
        # Extraire la description (premier paragraphe après le titre)
        in_description = False
        desc_lines = []
        for line in lines:
            if line.startswith('## '):
                break
            if in_description and line.strip():
                desc_lines.append(line.strip())
            if not in_description and line.strip() and not line.startswith('# '):
                in_description = True
        
        if desc_lines:
            metadata['description'] = ' '.join(desc_lines)
        
        # Extraire les tags
        tags = []
        for line in lines:
            if '**Tags**:' in line or '*Tags*:' in line:
                tag_part = line.split(':')[-1].strip()
                tags = [t.strip() for t in tag_part.split(',')]
                break
        if tags:
            metadata['tags'] = tags
        
        # Extraire les références
        references = []
        for line in lines:
            if '**References**:' in line or '*References*:' in line:
                ref_part = line.split(':')[-1].strip()
                references = [r.strip() for r in ref_part.split(',')]
                break
        if references:
            metadata['references'] = references
        
        # Compter les sections
        sections = [line for line in lines if line.strip().startswith('## ')]
        metadata['sections_count'] = len(sections)
        
        # Compter les mots
        text_content = ' '.join(lines)
        words = [w for w in text_content.split() if len(w) > 1]
        metadata['word_count'] = len(words)
        
        return content, metadata
    
    def _parse_sections(self, content: str) -> List[DocSection]:
        """Parse les sections du document"""
        sections = []
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            if line.startswith('## '):
                if current_section:
                    current_section.content = '\n'.join(current_content)
                    sections.append(current_section)
                current_section = DocSection(
                    title=line[3:].strip(),
                    level=2,
                    content=''
                )
                current_content = []
            elif line.startswith('### '):
                if current_section:
                    subsection = DocSection(
                        title=line[4:].strip(),
                        level=3,
                        content=''
                    )
                    current_section.subsections.append(subsection)
                else:
                    current_content.append(line)
            else:
                current_content.append(line)
        
        if current_section:
            current_section.content = '\n'.join(current_content)
            sections.append(current_section)
        
        return sections
    
    def _generate_toc(self, content: str) -> List[Dict[str, Any]]:
        """Génère une table des matières à partir du contenu"""
        toc = []
        lines = content.split('\n')
        
        for line in lines:
            if line.startswith('## '):
                title = line[3:].strip()
                anchor = title.lower().replace(' ', '-')
                anchor = ''.join(c for c in anchor if c.isalnum() or c == '-')
                toc.append({
                    'level': 2,
                    'title': title,
                    'anchor': anchor
                })
            elif line.startswith('### '):
                title = line[4:].strip()
                anchor = title.lower().replace(' ', '-')
                anchor = ''.join(c for c in anchor if c.isalnum() or c == '-')
                toc.append({
                    'level': 3,
                    'title': title,
                    'anchor': anchor
                })
        
        return toc
    
    def get_all_docs(self, force_reload: bool = False) -> Dict[str, Documentation]:
        """
        Charge tous les documents
        
        Args:
            force_reload: Forcer le rechargement
            
        Returns:
            Dict[str, Documentation]: Documents par nom
        """
        docs = {}
        for doc_name in DOCS_STRUCTURE:
            docs[doc_name] = self.load_doc(doc_name, force_reload)
        return docs
    
    def get_docs_by_category(self, category: Union[str, DocCategory]) -> List[Documentation]:
        """
        Récupère les documents par catégorie
        
        Args:
            category: Catégorie
            
        Returns:
            List[Documentation]: Documents de la catégorie
        """
        if isinstance(category, str):
            category = DocCategory(category)
        
        docs = []
        for doc_name, info in DOCS_STRUCTURE.items():
            if info.get("category") == category:
                doc = self.load_doc(doc_name)
                docs.append(doc)
        return sorted(docs, key=lambda x: x.metadata.title)
    
    def get_categories(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère les catégories de documentation
        
        Returns:
            Dict[str, Dict[str, Any]]: Catégories
        """
        return DOCS_CATEGORIES.copy()
    
    def get_doc_summary(self) -> Dict[str, Any]:
        """
        Récupère le résumé de la documentation
        
        Returns:
            Dict[str, Any]: Résumé de la documentation
        """
        summary = {
            "version": __version__,
            "generated": datetime.now().isoformat(),
            "total_docs": len(DOCS_STRUCTURE),
            "total_size": 0,
            "total_words": 0,
            "categories": {},
            "docs": {},
            "status": {
                "published": 0,
                "draft": 0,
                "review": 0,
                "deprecated": 0,
                "archived": 0
            }
        }
        
        for category, info in DOCS_CATEGORIES.items():
            docs = self.get_docs_by_category(category)
            summary["categories"][category] = {
                "title": info["title"],
                "description": info["description"],
                "icon": info.get("icon", "📄"),
                "count": len(docs)
            }
        
        for doc_name, info in DOCS_STRUCTURE.items():
            doc = self.load_doc(doc_name)
            summary["docs"][doc_name] = {
                "title": doc.title,
                "description": doc.description,
                "category": doc.category.value if hasattr(doc.category, 'value') else str(doc.category),
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "version": doc.version,
                "icon": info.get("icon", "📄"),
                "order": info.get("order", 999),
                "size": doc.path.stat().st_size if doc.path.exists() else 0,
                "sections": len(doc.sections),
                "words": len(doc.content.split()),
                "exists": doc.path.exists()
            }
            summary["total_size"] += summary["docs"][doc_name]["size"]
            summary["total_words"] += summary["docs"][doc_name]["words"]
            
            status_key = summary["docs"][doc_name]["status"]
            if status_key in summary["status"]:
                summary["status"][status_key] += 1
        
        return summary
    
    def get_docs_list(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des documents
        
        Returns:
            List[Dict[str, Any]]: Liste des documents
        """
        docs = []
        for doc_name, info in DOCS_STRUCTURE.items():
            doc = self.load_doc(doc_name)
            docs.append({
                "name": doc_name,
                "title": doc.title,
                "description": doc.description,
                "category": doc.category.value if hasattr(doc.category, 'value') else str(doc.category),
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "version": doc.version,
                "order": info.get("order", 999),
                "icon": info.get("icon", "📄"),
                "path": str(doc.path),
                "size": doc.path.stat().st_size if doc.path.exists() else 0,
                "sections": len(doc.sections),
                "exists": doc.path.exists()
            })
        return sorted(docs, key=lambda x: x.get("order", 999))
    
    def search_docs(self, query: str) -> List[Dict[str, Any]]:
        """
        Recherche dans la documentation
        
        Args:
            query: Requête de recherche
            
        Returns:
            List[Dict[str, Any]]: Résultats de recherche
        """
        results = []
        query_lower = query.lower()
        
        for doc_name in DOCS_STRUCTURE:
            doc = self.load_doc(doc_name)
            content_lower = doc.content.lower()
            
            if query_lower in content_lower:
                # Trouver les lignes contenant la requête
                lines = doc.content.split('\n')
                matches = []
                for i, line in enumerate(lines):
                    if query_lower in line.lower():
                        matches.append({
                            "line": i + 1,
                            "text": line.strip()
                        })
                
                results.append({
                    "doc": doc_name,
                    "title": doc.title,
                    "matches": len(matches),
                    "preview": matches[:3],
                    "score": len(matches) / (len(lines) / 100)  # Score simple
                })
        
        return sorted(results, key=lambda x: x["score"], reverse=True)
    
    def validate_doc(self, doc_name: str) -> Tuple[bool, List[str]]:
        """
        Valide un document
        
        Args:
            doc_name: Nom du document
            
        Returns:
            Tuple[bool, List[str]]: (valide, erreurs)
        """
        doc = self.load_doc(doc_name)
        errors = []
        
        for validator_name, validator in self._validators.items():
            try:
                validator_errors = validator(doc)
                errors.extend(validator_errors)
            except Exception as e:
                errors.append(f"Validator {validator_name} error: {e}")
        
        return len(errors) == 0, errors
    
    def generate_index(self) -> str:
        """
        Génère l'index de la documentation
        
        Returns:
            str: Index de la documentation
        """
        lines = [
            "# NEXUS AI Trading System Documentation Index",
            "",
            f"**Version**: {__version__}",
            f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 📚 Table des Matières",
            ""
        ]
        
        for category, info in DOCS_CATEGORIES.items():
            lines.append(f"### {info['title']}")
            lines.append(f"*{info['description']}*")
            lines.append("")
            
            docs = self.get_docs_by_category(category)
            for doc in docs:
                status_icon = {
                    'published': '✅',
                    'draft': '📝',
                    'review': '🔍',
                    'deprecated': '⚠️',
                    'archived': '📦'
                }.get(doc.status.value if hasattr(doc.status, 'value') else str(doc.status), '📄')
                
                lines.append(f"- **{status_icon} [{doc.title}]({doc.path.name})**")
                if doc.description:
                    lines.append(f"  {doc.description}")
                lines.append(f"  *Version: {doc.version}*")
                lines.append("")
        
        lines.append("---")
        lines.append("")
        lines.append("*© 2026 NEXUS QUANTUM LTD - Tous droits réservés*")
        
        return "\n".join(lines)
    
    def generate_sitemap(self) -> Dict[str, Any]:
        """
        Génère un sitemap de la documentation
        
        Returns:
            Dict[str, Any]: Sitemap
        """
        return {
            "version": __version__,
            "generated": datetime.now().isoformat(),
            "categories": DOCS_CATEGORIES,
            "documents": self.get_docs_list()
        }
    
    def export_metadata(self, format: str = "json") -> str:
        """
        Exporte les métadonnées de la documentation
        
        Args:
            format: Format d'export ('json', 'yaml')
            
        Returns:
            str: Métadonnées exportées
        """
        data = {
            "version": __version__,
            "generated": datetime.now().isoformat(),
            "categories": DOCS_CATEGORIES,
            "documents": self.get_docs_list()
        }
        
        if format == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)
        elif format == "yaml":
            return yaml.dump(data, default_flow_style=False, allow_unicode=True)
        else:
            return json.dumps(data, indent=2, ensure_ascii=False)
    
    def generate_static_site(self, output_dir: Union[str, Path]) -> Path:
        """
        Génère un site statique de la documentation
        
        Args:
            output_dir: Répertoire de sortie
            
        Returns:
            Path: Répertoire du site généré
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Générer l'index
        index_content = self.generate_index()
        (output_dir / "index.md").write_text(index_content, encoding='utf-8')
        
        # Copier tous les documents
        for doc_name, info in DOCS_STRUCTURE.items():
            doc = self.load_doc(doc_name)
            if doc.path.exists():
                dest_path = output_dir / doc.path.name
                import shutil
                shutil.copy2(doc.path, dest_path)
        
        # Générer un fichier JSON avec les métadonnées
        metadata = self.export_metadata("json")
        (output_dir / "metadata.json").write_text(metadata, encoding='utf-8')
        
        logger.info(f"Static site generated at {output_dir}")
        return output_dir

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_doc_loader: Optional[DocumentationLoader] = None

def get_doc_loader() -> DocumentationLoader:
    """
    Récupère le chargeur de documentation (singleton)
    
    Returns:
        DocumentationLoader: Chargeur de documentation
    """
    global _doc_loader
    if _doc_loader is None:
        _doc_loader = DocumentationLoader()
    return _doc_loader

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Metadata
    '__version__',
    '__author__',
    '__description__',
    '__copyright__',
    '__license__',
    
    # Enums
    'DocCategory',
    'DocStatus',
    
    # Data Classes
    'DocMetadata',
    'DocSection',
    'Documentation',
    
    # Constants
    'DOCS_STRUCTURE',
    'DOCS_CATEGORIES',
    
    # Classes
    'DocumentationLoader',
    
    # Functions
    'get_doc_loader',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info(f"Documentation module initialized (v{__version__})")

# ============================================================
# MODULE TESTING
# ============================================================

if __name__ == "__main__":
    # Test du module de documentation
    loader = get_doc_loader()
    
    print("=" * 80)
    print("NEXUS AI Trading System - Documentation Module")
    print("=" * 80)
    
    print("\n📚 Documentation Structure:")
    for doc_name, info in DOCS_STRUCTURE.items():
        status = info.get('status', DocStatus.DRAFT)
        status_label = status.value if hasattr(status, 'value') else str(status)
        print(f"  {info['icon']} {info['title']} ({info['category']}) [{status_label}]")
    
    print("\n📊 Summary:")
    summary = loader.get_doc_summary()
    print(f"  Version: {summary['version']}")
    print(f"  Total Docs: {summary['total_docs']}")
    print(f"  Total Size: {summary['total_size'] / 1024:.2f} KB")
    print(f"  Total Words: {summary['total_words']:,}")
    
    print("\n  Status:")
    for status, count in summary['status'].items():
        print(f"    {status}: {count}")
    
    print("\n  Categories:")
    for category, info in summary['categories'].items():
        print(f"    {info['icon']} {category}: {info['count']} docs")
    
    print("\n📖 Documents List:")
    for doc in loader.get_docs_list():
        status_icon = {
            'published': '✅',
            'draft': '📝',
            'review': '🔍',
            'deprecated': '⚠️',
            'archived': '📦'
        }.get(doc['status'], '📄')
        exists = "✅" if doc['exists'] else "❌"
        print(f"  {exists} {status_icon} {doc['icon']} {doc['title']} (v{doc['version']})")
    
    print("\n🔍 Search Test:")
    results = loader.search_docs("configuration")
    for result in results[:3]:
        print(f"  {result['title']}: {result['matches']} matches")
    
    print("\n✅ Documentation module test completed")
