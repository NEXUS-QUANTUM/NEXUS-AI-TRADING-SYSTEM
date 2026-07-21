"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot File Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de gestion de fichiers pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import os
import sys
import json
import yaml
import csv
import pickle
import shutil
import tempfile
import hashlib
import zipfile
import tarfile
import gzip
import bz2
import lzma
import zlib
import base64
import io
import re
import fnmatch
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    Iterator,
    Generator,
    BinaryIO,
    TextIO,
    IO
)
from datetime import datetime
from enum import Enum
import stat
import filecmp
import mimetypes
import magic
import threading
import asyncio
import aiofiles
from contextlib import contextmanager, asynccontextmanager

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_CHUNK_SIZE = 8192
DEFAULT_BUFFER_SIZE = 1024 * 1024  # 1MB

# ============================================================
# FILE ENUMS
# ============================================================

class FileMode(Enum):
    """Modes d'ouverture de fichiers"""
    READ = 'r'
    WRITE = 'w'
    APPEND = 'a'
    READ_BINARY = 'rb'
    WRITE_BINARY = 'wb'
    APPEND_BINARY = 'ab'
    READ_TEXT = 'rt'
    WRITE_TEXT = 'wt'
    APPEND_TEXT = 'at'

class FileType(Enum):
    """Types de fichiers"""
    TEXT = 'text'
    BINARY = 'binary'
    JSON = 'json'
    YAML = 'yaml'
    CSV = 'csv'
    PICKLE = 'pickle'
    XML = 'xml'
    HTML = 'html'
    IMAGE = 'image'
    VIDEO = 'video'
    AUDIO = 'audio'
    ARCHIVE = 'archive'
    COMPRESSED = 'compressed'

# ============================================================
# FILE UTILITIES
# ============================================================

class FileUtils:
    """Utilitaires de gestion de fichiers"""
    
    @staticmethod
    def get_file_path(file_path: Union[str, Path]) -> Path:
        """
        Convertit en Path et résout les chemins relatifs
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            Path: Chemin résolu
        """
        path = Path(file_path)
        
        # Résoudre les chemins relatifs
        if not path.is_absolute():
            # Si le chemin contient ~, remplacer par le home
            if str(path).startswith('~'):
                path = Path(os.path.expanduser(str(path)))
            else:
                # Résoudre par rapport au répertoire de l'appelant
                frame = inspect.currentframe().f_back
                if frame:
                    caller_file = Path(frame.f_code.co_filename)
                    path = caller_file.parent / path
        
        return path.resolve()
    
    @staticmethod
    def ensure_directory(directory: Union[str, Path]) -> Path:
        """
        Crée le répertoire si nécessaire
        
        Args:
            directory: Chemin du répertoire
            
        Returns:
            Path: Chemin du répertoire
        """
        path = FileUtils.get_file_path(directory)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def ensure_file(file_path: Union[str, Path], content: Optional[str] = None) -> Path:
        """
        Crée le fichier s'il n'existe pas
        
        Args:
            file_path: Chemin du fichier
            content: Contenu optionnel
            
        Returns:
            Path: Chemin du fichier
        """
        path = FileUtils.get_file_path(file_path)
        FileUtils.ensure_directory(path.parent)
        
        if not path.exists():
            with open(path, 'w') as f:
                if content is not None:
                    f.write(content)
        
        return path
    
    @staticmethod
    def read_file(
        file_path: Union[str, Path],
        mode: FileMode = FileMode.READ_TEXT,
        encoding: str = 'utf-8'
    ) -> Union[str, bytes]:
        """
        Lit un fichier
        
        Args:
            file_path: Chemin du fichier
            mode: Mode d'ouverture
            encoding: Encodage
            
        Returns:
            Union[str, bytes]: Contenu du fichier
        """
        path = FileUtils.get_file_path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if mode in [FileMode.READ_TEXT, FileMode.READ]:
            with open(path, mode.value, encoding=encoding) as f:
                return f.read()
        else:
            with open(path, mode.value) as f:
                return f.read()
    
    @staticmethod
    def write_file(
        file_path: Union[str, Path],
        content: Union[str, bytes],
        mode: FileMode = FileMode.WRITE_TEXT,
        encoding: str = 'utf-8'
    ):
        """
        Écrit un fichier
        
        Args:
            file_path: Chemin du fichier
            content: Contenu
            mode: Mode d'ouverture
            encoding: Encodage
        """
        path = FileUtils.get_file_path(file_path)
        FileUtils.ensure_directory(path.parent)
        
        if mode in [FileMode.WRITE_TEXT, FileMode.WRITE]:
            with open(path, mode.value, encoding=encoding) as f:
                f.write(content)
        else:
            with open(path, mode.value) as f:
                f.write(content)
    
    @staticmethod
    def append_file(
        file_path: Union[str, Path],
        content: Union[str, bytes],
        encoding: str = 'utf-8'
    ):
        """
        Ajoute du contenu à un fichier
        
        Args:
            file_path: Chemin du fichier
            content: Contenu
            encoding: Encodage
        """
        path = FileUtils.get_file_path(file_path)
        FileUtils.ensure_directory(path.parent)
        
        if isinstance(content, str):
            with open(path, 'a', encoding=encoding) as f:
                f.write(content)
        else:
            with open(path, 'ab') as f:
                f.write(content)
    
    @staticmethod
    def read_lines(
        file_path: Union[str, Path],
        encoding: str = 'utf-8',
        strip: bool = True
    ) -> List[str]:
        """
        Lit les lignes d'un fichier
        
        Args:
            file_path: Chemin du fichier
            encoding: Encodage
            strip: Supprimer les espaces en début/fin
            
        Returns:
            List[str]: Lignes du fichier
        """
        path = FileUtils.get_file_path(file_path)
        lines = []
        
        with open(path, 'r', encoding=encoding) as f:
            for line in f:
                if strip:
                    line = line.strip()
                if line:
                    lines.append(line)
        
        return lines
    
    @staticmethod
    def read_json(file_path: Union[str, Path], encoding: str = 'utf-8') -> Any:
        """
        Lit un fichier JSON
        
        Args:
            file_path: Chemin du fichier
            encoding: Encodage
            
        Returns:
            Any: Données JSON
        """
        path = FileUtils.get_file_path(file_path)
        
        with open(path, 'r', encoding=encoding) as f:
            return json.load(f)
    
    @staticmethod
    def write_json(
        file_path: Union[str, Path],
        data: Any,
        indent: int = 2,
        encoding: str = 'utf-8'
    ):
        """
        Écrit un fichier JSON
        
        Args:
            file_path: Chemin du fichier
            data: Données à écrire
            indent: Indentation
            encoding: Encodage
        """
        path = FileUtils.get_file_path(file_path)
        FileUtils.ensure_directory(path.parent)
        
        with open(path, 'w', encoding=encoding) as f:
            json.dump(data, f, indent=indent, default=str)
    
    @staticmethod
    def read_yaml(file_path: Union[str, Path], encoding: str = 'utf-8') -> Any:
        """
        Lit un fichier YAML
        
        Args:
            file_path: Chemin du fichier
            encoding: Encodage
            
        Returns:
            Any: Données YAML
        """
        path = FileUtils.get_file_path(file_path)
        
        with open(path, 'r', encoding=encoding) as f:
            return yaml.safe_load(f)
    
    @staticmethod
    def write_yaml(
        file_path: Union[str, Path],
        data: Any,
        default_flow_style: bool = False,
        encoding: str = 'utf-8'
    ):
        """
        Écrit un fichier YAML
        
        Args:
            file_path: Chemin du fichier
            data: Données à écrire
            default_flow_style: Style d'écriture
            encoding: Encodage
        """
        path = FileUtils.get_file_path(file_path)
        FileUtils.ensure_directory(path.parent)
        
        with open(path, 'w', encoding=encoding) as f:
            yaml.dump(data, f, default_flow_style=default_flow_style, allow_unicode=True)
    
    @staticmethod
    def read_csv(
        file_path: Union[str, Path],
        delimiter: str = ',',
        encoding: str = 'utf-8'
    ) -> List[Dict[str, Any]]:
        """
        Lit un fichier CSV
        
        Args:
            file_path: Chemin du fichier
            delimiter: Délimiteur
            encoding: Encodage
            
        Returns:
            List[Dict[str, Any]]: Données CSV
        """
        path = FileUtils.get_file_path(file_path)
        data = []
        
        with open(path, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                # Convertir les valeurs numériques
                for key, value in row.items():
                    if value:
                        try:
                            row[key] = int(value)
                        except ValueError:
                            try:
                                row[key] = float(value)
                            except ValueError:
                                pass
                data.append(row)
        
        return data
    
    @staticmethod
    def write_csv(
        file_path: Union[str, Path],
        data: List[Dict[str, Any]],
        delimiter: str = ',',
        encoding: str = 'utf-8'
    ):
        """
        Écrit un fichier CSV
        
        Args:
            file_path: Chemin du fichier
            data: Données à écrire
            delimiter: Délimiteur
            encoding: Encodage
        """
        path = FileUtils.get_file_path(file_path)
        FileUtils.ensure_directory(path.parent)
        
        if not data:
            return
        
        fieldnames = list(data[0].keys())
        
        with open(path, 'w', encoding=encoding, newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
            writer.writeheader()
            writer.writerows(data)
    
    @staticmethod
    def read_pickle(file_path: Union[str, Path]) -> Any:
        """
        Lit un fichier pickle
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            Any: Données pickle
        """
        path = FileUtils.get_file_path(file_path)
        
        with open(path, 'rb') as f:
            return pickle.load(f)
    
    @staticmethod
    def write_pickle(file_path: Union[str, Path], data: Any):
        """
        Écrit un fichier pickle
        
        Args:
            file_path: Chemin du fichier
            data: Données à écrire
        """
        path = FileUtils.get_file_path(file_path)
        FileUtils.ensure_directory(path.parent)
        
        with open(path, 'wb') as f:
            pickle.dump(data, f)
    
    @staticmethod
    def get_file_info(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Récupère les informations d'un fichier
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            Dict[str, Any]: Informations du fichier
        """
        path = FileUtils.get_file_path(file_path)
        
        if not path.exists():
            return {}
        
        stats = path.stat()
        
        return {
            'path': str(path),
            'name': path.name,
            'stem': path.stem,
            'suffix': path.suffix,
            'size': stats.st_size,
            'created': datetime.fromtimestamp(stats.st_ctime),
            'modified': datetime.fromtimestamp(stats.st_mtime),
            'accessed': datetime.fromtimestamp(stats.st_atime),
            'is_file': path.is_file(),
            'is_dir': path.is_dir(),
            'is_symlink': path.is_symlink(),
            'mode': stat.filemode(stats.st_mode),
            'permissions': {
                'read': bool(stats.st_mode & stat.S_IRUSR),
                'write': bool(stats.st_mode & stat.S_IWUSR),
                'execute': bool(stats.st_mode & stat.S_IXUSR),
            }
        }
    
    @staticmethod
    def get_file_type(file_path: Union[str, Path]) -> FileType:
        """
        Détermine le type d'un fichier
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            FileType: Type du fichier
        """
        path = FileUtils.get_file_path(file_path)
        
        if not path.exists():
            return FileType.BINARY
        
        # Par extension
        suffix = path.suffix.lower()
        if suffix in ['.json']:
            return FileType.JSON
        elif suffix in ['.yaml', '.yml']:
            return FileType.YAML
        elif suffix in ['.csv']:
            return FileType.CSV
        elif suffix in ['.pickle', '.pkl']:
            return FileType.PICKLE
        elif suffix in ['.xml', '.xhtml']:
            return FileType.XML
        elif suffix in ['.html', '.htm']:
            return FileType.HTML
        elif suffix in ['.txt', '.log', '.md']:
            return FileType.TEXT
        elif suffix in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg']:
            return FileType.IMAGE
        elif suffix in ['.mp4', '.avi', '.mov', '.wmv']:
            return FileType.VIDEO
        elif suffix in ['.mp3', '.wav', '.flac', '.aac']:
            return FileType.AUDIO
        elif suffix in ['.zip', '.rar', '.7z']:
            return FileType.ARCHIVE
        elif suffix in ['.gz', '.bz2', '.xz']:
            return FileType.COMPRESSED
        
        # Par contenu
        try:
            mime_type = magic.from_file(str(path), mime=True)
            if mime_type:
                if mime_type.startswith('text/'):
                    return FileType.TEXT
                elif mime_type.startswith('image/'):
                    return FileType.IMAGE
                elif mime_type.startswith('video/'):
                    return FileType.VIDEO
                elif mime_type.startswith('audio/'):
                    return FileType.AUDIO
        except:
            pass
        
        return FileType.BINARY
    
    @staticmethod
    def get_file_hash(
        file_path: Union[str, Path],
        algorithm: str = 'sha256',
        chunk_size: int = DEFAULT_CHUNK_SIZE
    ) -> str:
        """
        Calcule le hash d'un fichier
        
        Args:
            file_path: Chemin du fichier
            algorithm: Algorithme de hash
            chunk_size: Taille des morceaux
            
        Returns:
            str: Hash du fichier
        """
        path = FileUtils.get_file_path(file_path)
        hash_func = hashlib.new(algorithm)
        
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    
    @staticmethod
    def copy_file(
        src: Union[str, Path],
        dst: Union[str, Path],
        overwrite: bool = True
    ):
        """
        Copie un fichier
        
        Args:
            src: Chemin source
            dst: Chemin destination
            overwrite: Écraser si existe
        """
        src_path = FileUtils.get_file_path(src)
        dst_path = FileUtils.get_file_path(dst)
        
        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {src_path}")
        
        if dst_path.exists() and not overwrite:
            raise FileExistsError(f"Destination file exists: {dst_path}")
        
        FileUtils.ensure_directory(dst_path.parent)
        shutil.copy2(src_path, dst_path)
    
    @staticmethod
    def move_file(
        src: Union[str, Path],
        dst: Union[str, Path],
        overwrite: bool = True
    ):
        """
        Déplace un fichier
        
        Args:
            src: Chemin source
            dst: Chemin destination
            overwrite: Écraser si existe
        """
        src_path = FileUtils.get_file_path(src)
        dst_path = FileUtils.get_file_path(dst)
        
        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {src_path}")
        
        if dst_path.exists() and not overwrite:
            raise FileExistsError(f"Destination file exists: {dst_path}")
        
        FileUtils.ensure_directory(dst_path.parent)
        shutil.move(str(src_path), str(dst_path))
    
    @staticmethod
    def delete_file(file_path: Union[str, Path], force: bool = False):
        """
        Supprime un fichier
        
        Args:
            file_path: Chemin du fichier
            force: Forcer la suppression
        """
        path = FileUtils.get_file_path(file_path)
        
        if not path.exists():
            if force:
                return
            raise FileNotFoundError(f"File not found: {path}")
        
        if path.is_dir():
            if force:
                shutil.rmtree(path, ignore_errors=True)
                return
            raise IsADirectoryError(f"Path is a directory: {path}")
        
        path.unlink()
    
    @staticmethod
    def list_files(
        directory: Union[str, Path],
        pattern: str = '*',
        recursive: bool = False,
        include_dirs: bool = False
    ) -> List[Path]:
        """
        Liste les fichiers d'un répertoire
        
        Args:
            directory: Chemin du répertoire
            pattern: Filtre de nom
            recursive: Parcourir les sous-répertoires
            include_dirs: Inclure les répertoires
            
        Returns:
            List[Path]: Liste des chemins
        """
        path = FileUtils.get_file_path(directory)
        
        if not path.exists():
            return []
        
        if not path.is_dir():
            return []
        
        if recursive:
            files = []
            for root, dirs, filenames in os.walk(path):
                for filename in filenames:
                    if fnmatch.fnmatch(filename, pattern):
                        files.append(Path(root) / filename)
                if include_dirs:
                    for dirname in dirs:
                        if fnmatch.fnmatch(dirname, pattern):
                            files.append(Path(root) / dirname)
            return files
        else:
            files = []
            for item in path.iterdir():
                if item.is_file() and fnmatch.fnmatch(item.name, pattern):
                    files.append(item)
                elif include_dirs and item.is_dir() and fnmatch.fnmatch(item.name, pattern):
                    files.append(item)
            return sorted(files)
    
    @staticmethod
    def get_size(file_path: Union[str, Path], recursive: bool = True) -> int:
        """
        Calcule la taille d'un fichier ou répertoire
        
        Args:
            file_path: Chemin du fichier
            recursive: Inclure les sous-répertoires
            
        Returns:
            int: Taille en bytes
        """
        path = FileUtils.get_file_path(file_path)
        
        if not path.exists():
            return 0
        
        if path.is_file():
            return path.stat().st_size
        
        if path.is_dir() and recursive:
            total = 0
            for root, dirs, files in os.walk(path):
                for f in files:
                    file_path = Path(root) / f
                    total += file_path.stat().st_size
            return total
        
        return 0
    
    @staticmethod
    def compress_file(
        file_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        compression: str = 'gzip'
    ) -> Path:
        """
        Compresse un fichier
        
        Args:
            file_path: Chemin du fichier
            output_path: Chemin de sortie
            compression: Type de compression ('gzip', 'bz2', 'xz')
            
        Returns:
            Path: Chemin du fichier compressé
        """
        path = FileUtils.get_file_path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if output_path is None:
            output_path = path.with_suffix(path.suffix + f'.{compression}')
        else:
            output_path = FileUtils.get_file_path(output_path)
        
        FileUtils.ensure_directory(output_path.parent)
        
        if compression == 'gzip':
            with open(path, 'rb') as f_in:
                with gzip.open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif compression == 'bz2':
            with open(path, 'rb') as f_in:
                with bz2.open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif compression == 'xz':
            with open(path, 'rb') as f_in:
                with lzma.open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            raise ValueError(f"Unsupported compression: {compression}")
        
        return output_path
    
    @staticmethod
    def decompress_file(
        file_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None
    ) -> Path:
        """
        Décompresse un fichier
        
        Args:
            file_path: Chemin du fichier
            output_path: Chemin de sortie
            
        Returns:
            Path: Chemin du fichier décompressé
        """
        path = FileUtils.get_file_path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if output_path is None:
            # Supprimer l'extension de compression
            output_path = path.with_suffix('')
        else:
            output_path = FileUtils.get_file_path(output_path)
        
        FileUtils.ensure_directory(output_path.parent)
        
        suffix = path.suffix.lower()
        
        if suffix == '.gz':
            with gzip.open(path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif suffix == '.bz2':
            with bz2.open(path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif suffix == '.xz':
            with lzma.open(path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            raise ValueError(f"Unsupported compression: {suffix}")
        
        return output_path
    
    @staticmethod
    def create_archive(
        file_paths: List[Union[str, Path]],
        output_path: Union[str, Path],
        archive_type: str = 'zip',
        compression: str = 'deflated'
    ) -> Path:
        """
        Crée une archive
        
        Args:
            file_paths: Liste des chemins
            output_path: Chemin de sortie
            archive_type: Type d'archive ('zip', 'tar')
            compression: Compression
            
        Returns:
            Path: Chemin de l'archive
        """
        output_path = FileUtils.get_file_path(output_path)
        FileUtils.ensure_directory(output_path.parent)
        
        # Résoudre les chemins
        paths = [FileUtils.get_file_path(p) for p in file_paths]
        
        if archive_type == 'zip':
            compression_map = {
                'deflated': zipfile.ZIP_DEFLATED,
                'stored': zipfile.ZIP_STORED,
                'bzip2': zipfile.ZIP_BZIP2,
                'lzma': zipfile.ZIP_LZMA,
            }
            
            compression_method = compression_map.get(compression, zipfile.ZIP_DEFLATED)
            
            with zipfile.ZipFile(output_path, 'w', compression=compression_method) as archive:
                for path in paths:
                    if path.is_dir():
                        for root, dirs, files in os.walk(path):
                            for file in files:
                                file_path = Path(root) / file
                                arcname = file_path.relative_to(path.parent)
                                archive.write(file_path, arcname)
                    else:
                        archive.write(path, path.name)
        
        elif archive_type == 'tar':
            compression_map = {
                'none': '',
                'gzip': 'gz',
                'bz2': 'bz2',
                'xz': 'xz',
            }
            
            compression_ext = compression_map.get(compression, '')
            mode = f"w:{compression_ext}" if compression_ext else "w"
            
            with tarfile.open(output_path, mode) as archive:
                for path in paths:
                    if path.is_dir():
                        archive.add(path, arcname=path.name, recursive=True)
                    else:
                        archive.add(path, arcname=path.name)
        
        else:
            raise ValueError(f"Unsupported archive type: {archive_type}")
        
        return output_path
    
    @staticmethod
    def extract_archive(
        archive_path: Union[str, Path],
        output_dir: Union[str, Path]
    ) -> Path:
        """
        Extrait une archive
        
        Args:
            archive_path: Chemin de l'archive
            output_dir: Répertoire de sortie
            
        Returns:
            Path: Répertoire d'extraction
        """
        archive_path = FileUtils.get_file_path(archive_path)
        output_dir = FileUtils.get_file_path(output_dir)
        
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")
        
        FileUtils.ensure_directory(output_dir)
        
        suffix = archive_path.suffix.lower()
        
        if suffix == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as archive:
                archive.extractall(output_dir)
        
        elif suffix in ['.tar', '.gz', '.bz2', '.xz']:
            # Vérifier si c'est un tar compressé
            if suffix == '.gz':
                if archive_path.stem.endswith('.tar'):
                    mode = 'r:gz'
                else:
                    mode = 'r:gz'
            elif suffix == '.bz2':
                if archive_path.stem.endswith('.tar'):
                    mode = 'r:bz2'
                else:
                    mode = 'r:bz2'
            elif suffix == '.xz':
                if archive_path.stem.endswith('.tar'):
                    mode = 'r:xz'
                else:
                    mode = 'r:xz'
            else:
                mode = 'r'
            
            with tarfile.open(archive_path, mode) as archive:
                archive.extractall(output_dir)
        
        else:
            raise ValueError(f"Unsupported archive: {suffix}")
        
        return output_dir

# ============================================================
# ASYNC FILE UTILITIES
# ============================================================

class AsyncFileUtils:
    """Utilitaires asynchrones de gestion de fichiers"""
    
    @staticmethod
    async def read_file(
        file_path: Union[str, Path],
        encoding: str = 'utf-8'
    ) -> str:
        """
        Lit un fichier de manière asynchrone
        
        Args:
            file_path: Chemin du fichier
            encoding: Encodage
            
        Returns:
            str: Contenu du fichier
        """
        path = FileUtils.get_file_path(file_path)
        
        async with aiofiles.open(path, 'r', encoding=encoding) as f:
            return await f.read()
    
    @staticmethod
    async def write_file(
        file_path: Union[str, Path],
        content: str,
        encoding: str = 'utf-8'
    ):
        """
        Écrit un fichier de manière asynchrone
        
        Args:
            file_path: Chemin du fichier
            content: Contenu
            encoding: Encodage
        """
        path = FileUtils.get_file_path(file_path)
        FileUtils.ensure_directory(path.parent)
        
        async with aiofiles.open(path, 'w', encoding=encoding) as f:
            await f.write(content)
    
    @staticmethod
    async def read_json(file_path: Union[str, Path]) -> Any:
        """
        Lit un fichier JSON de manière asynchrone
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            Any: Données JSON
        """
        content = await AsyncFileUtils.read_file(file_path)
        return json.loads(content)
    
    @staticmethod
    async def write_json(
        file_path: Union[str, Path],
        data: Any,
        indent: int = 2
    ):
        """
        Écrit un fichier JSON de manière asynchrone
        
        Args:
            file_path: Chemin du fichier
            data: Données à écrire
            indent: Indentation
        """
        content = json.dumps(data, indent=indent, default=str)
        await AsyncFileUtils.write_file(file_path, content)


# ============================================================
# CONTEXT MANAGERS
# ============================================================

@contextmanager
def open_file(
    file_path: Union[str, Path],
    mode: str = 'r',
    encoding: str = 'utf-8',
    **kwargs
) -> IO:
    """
    Context manager pour ouvrir un fichier
    
    Args:
        file_path: Chemin du fichier
        mode: Mode d'ouverture
        encoding: Encodage
        **kwargs: Arguments supplémentaires
        
    Yields:
        IO: Fichier ouvert
    """
    path = FileUtils.get_file_path(file_path)
    FileUtils.ensure_directory(path.parent)
    
    with open(path, mode, encoding=encoding, **kwargs) as f:
        yield f


@asynccontextmanager
async def async_open_file(
    file_path: Union[str, Path],
    mode: str = 'r',
    encoding: str = 'utf-8',
    **kwargs
) -> AsyncIterator:
    """
    Context manager asynchrone pour ouvrir un fichier
    
    Args:
        file_path: Chemin du fichier
        mode: Mode d'ouverture
        encoding: Encodage
        **kwargs: Arguments supplémentaires
        
    Yields:
        AsyncIO: Fichier ouvert
    """
    path = FileUtils.get_file_path(file_path)
    FileUtils.ensure_directory(path.parent)
    
    async with aiofiles.open(path, mode, encoding=encoding, **kwargs) as f:
        yield f


@contextmanager
def temporary_file(
    suffix: str = '',
    prefix: str = '',
    dir: Optional[Union[str, Path]] = None,
    text: bool = False,
    content: Optional[Union[str, bytes]] = None
) -> Path:
    """
    Context manager pour créer un fichier temporaire
    
    Args:
        suffix: Suffixe du fichier
        prefix: Préfixe du fichier
        dir: Répertoire
        text: Mode texte
        content: Contenu initial
        
    Yields:
        Path: Chemin du fichier temporaire
    """
    with tempfile.NamedTemporaryFile(
        suffix=suffix,
        prefix=prefix,
        dir=dir,
        delete=False,
        mode='w' if text else 'wb'
    ) as f:
        if content is not None:
            f.write(content)
            f.flush()
        
        path = Path(f.name)
        try:
            yield path
        finally:
            if path.exists():
                path.unlink()


@contextmanager
def temporary_directory(
    suffix: str = '',
    prefix: str = '',
    dir: Optional[Union[str, Path]] = None
) -> Path:
    """
    Context manager pour créer un répertoire temporaire
    
    Args:
        suffix: Suffixe du répertoire
        prefix: Préfixe du répertoire
        dir: Répertoire
        
    Yields:
        Path: Chemin du répertoire temporaire
    """
    path = Path(tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir))
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'FileMode',
    'FileType',
    
    # Classes
    'FileUtils',
    'AsyncFileUtils',
    
    # Context managers
    'open_file',
    'async_open_file',
    'temporary_file',
    'temporary_directory',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("File utilities module initialized")
