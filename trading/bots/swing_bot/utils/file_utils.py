"""
Swing Bot File Utilities Module.
================================

This module provides file utilities for the Swing Bot trading system.
Includes file operations, file management, and file system utilities.
"""

import os
import sys
import json
import yaml
import pickle
import csv
import io
import shutil
import tempfile
import zipfile
import tarfile
import gzip
import bz2
import lzma
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Iterator, BinaryIO, TextIO
from datetime import datetime
import hashlib
import fnmatch
import stat
import logging


class FileUtils:
    """
    Utility class for file operations.
    """
    
    @staticmethod
    def ensure_dir(path: Union[str, Path]) -> Path:
        """
        Ensure a directory exists.
        
        Args:
            path: Directory path
        
        Returns:
            Path object
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def ensure_file(path: Union[str, Path], content: Optional[Union[str, bytes]] = None) -> Path:
        """
        Ensure a file exists.
        
        Args:
            path: File path
            content: Content to write if file doesn't exist
        
        Returns:
            Path object
        """
        path = Path(path)
        FileUtils.ensure_dir(path.parent)
        if not path.exists() and content is not None:
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content)
        return path
    
    @staticmethod
    def read_text(path: Union[str, Path], encoding: str = 'utf-8') -> str:
        """
        Read text from a file.
        
        Args:
            path: File path
            encoding: File encoding
        
        Returns:
            File content as string
        """
        with open(path, 'r', encoding=encoding) as f:
            return f.read()
    
    @staticmethod
    def write_text(path: Union[str, Path], content: str, encoding: str = 'utf-8') -> None:
        """
        Write text to a file.
        
        Args:
            path: File path
            content: Text content
            encoding: File encoding
        """
        path = Path(path)
        FileUtils.ensure_dir(path.parent)
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
    
    @staticmethod
    def read_bytes(path: Union[str, Path]) -> bytes:
        """
        Read bytes from a file.
        
        Args:
            path: File path
        
        Returns:
            File content as bytes
        """
        with open(path, 'rb') as f:
            return f.read()
    
    @staticmethod
    def write_bytes(path: Union[str, Path], content: bytes) -> None:
        """
        Write bytes to a file.
        
        Args:
            path: File path
            content: Bytes content
        """
        path = Path(path)
        FileUtils.ensure_dir(path.parent)
        with open(path, 'wb') as f:
            f.write(content)
    
    @staticmethod
    def read_lines(path: Union[str, Path], encoding: str = 'utf-8') -> List[str]:
        """
        Read lines from a file.
        
        Args:
            path: File path
            encoding: File encoding
        
        Returns:
            List of lines
        """
        with open(path, 'r', encoding=encoding) as f:
            return f.readlines()
    
    @staticmethod
    def write_lines(path: Union[str, Path], lines: List[str], encoding: str = 'utf-8') -> None:
        """
        Write lines to a file.
        
        Args:
            path: File path
            lines: List of lines
            encoding: File encoding
        """
        path = Path(path)
        FileUtils.ensure_dir(path.parent)
        with open(path, 'w', encoding=encoding) as f:
            f.writelines(lines)
    
    @staticmethod
    def read_json(path: Union[str, Path]) -> Any:
        """
        Read JSON from a file.
        
        Args:
            path: File path
        
        Returns:
            JSON data
        """
        with open(path, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def write_json(path: Union[str, Path], data: Any, indent: int = 2) -> None:
        """
        Write JSON to a file.
        
        Args:
            path: File path
            data: Data to write
            indent: Indentation level
        """
        path = Path(path)
        FileUtils.ensure_dir(path.parent)
        with open(path, 'w') as f:
            json.dump(data, f, indent=indent)
    
    @staticmethod
    def read_yaml(path: Union[str, Path]) -> Any:
        """
        Read YAML from a file.
        
        Args:
            path: File path
        
        Returns:
            YAML data
        """
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    
    @staticmethod
    def write_yaml(path: Union[str, Path], data: Any) -> None:
        """
        Write YAML to a file.
        
        Args:
            path: File path
            data: Data to write
        """
        path = Path(path)
        FileUtils.ensure_dir(path.parent)
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
    
    @staticmethod
    def read_pickle(path: Union[str, Path]) -> Any:
        """
        Read pickle from a file.
        
        Args:
            path: File path
        
        Returns:
            Pickled data
        """
        with open(path, 'rb') as f:
            return pickle.load(f)
    
    @staticmethod
    def write_pickle(path: Union[str, Path], data: Any) -> None:
        """
        Write pickle to a file.
        
        Args:
            path: File path
            data: Data to write
        """
        path = Path(path)
        FileUtils.ensure_dir(path.parent)
        with open(path, 'wb') as f:
            pickle.dump(data, f)
    
    @staticmethod
    def read_csv(path: Union[str, Path], delimiter: str = ',', encoding: str = 'utf-8') -> List[Dict[str, str]]:
        """
        Read CSV from a file.
        
        Args:
            path: File path
            delimiter: CSV delimiter
            encoding: File encoding
        
        Returns:
            List of dictionaries
        """
        with open(path, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            return list(reader)
    
    @staticmethod
    def write_csv(path: Union[str, Path], data: List[Dict[str, Any]], delimiter: str = ',') -> None:
        """
        Write CSV to a file.
        
        Args:
            path: File path
            data: List of dictionaries
            delimiter: CSV delimiter
        """
        path = Path(path)
        FileUtils.ensure_dir(path.parent)
        if not data:
            return
        
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys(), delimiter=delimiter)
            writer.writeheader()
            writer.writerows(data)
    
    @staticmethod
    def get_file_size(path: Union[str, Path]) -> int:
        """
        Get file size in bytes.
        
        Args:
            path: File path
        
        Returns:
            File size in bytes
        """
        return Path(path).stat().st_size
    
    @staticmethod
    def get_file_modified_time(path: Union[str, Path]) -> float:
        """
        Get file modification time.
        
        Args:
            path: File path
        
        Returns:
            Modification time as Unix timestamp
        """
        return Path(path).stat().st_mtime
    
    @staticmethod
    def get_file_created_time(path: Union[str, Path]) -> float:
        """
        Get file creation time.
        
        Args:
            path: File path
        
        Returns:
            Creation time as Unix timestamp
        """
        return Path(path).stat().st_ctime
    
    @staticmethod
    def get_file_hash(path: Union[str, Path], algorithm: str = 'sha256') -> str:
        """
        Get hash of a file.
        
        Args:
            path: File path
            algorithm: Hash algorithm
        
        Returns:
            File hash
        """
        hash_func = hashlib.new(algorithm)
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    
    @staticmethod
    def get_file_extension(path: Union[str, Path]) -> str:
        """
        Get file extension.
        
        Args:
            path: File path
        
        Returns:
            File extension (including dot)
        """
        return Path(path).suffix
    
    @staticmethod
    def get_file_name(path: Union[str, Path]) -> str:
        """
        Get file name.
        
        Args:
            path: File path
        
        Returns:
            File name
        """
        return Path(path).name
    
    @staticmethod
    def get_file_name_without_extension(path: Union[str, Path]) -> str:
        """
        Get file name without extension.
        
        Args:
            path: File path
        
        Returns:
            File name without extension
        """
        return Path(path).stem
    
    @staticmethod
    def get_file_dir(path: Union[str, Path]) -> Path:
        """
        Get file directory.
        
        Args:
            path: File path
        
        Returns:
            Directory path
        """
        return Path(path).parent
    
    @staticmethod
    def copy_file(src: Union[str, Path], dst: Union[str, Path]) -> None:
        """
        Copy a file.
        
        Args:
            src: Source path
            dst: Destination path
        """
        src_path = Path(src)
        dst_path = Path(dst)
        FileUtils.ensure_dir(dst_path.parent)
        shutil.copy2(src_path, dst_path)
    
    @staticmethod
    def move_file(src: Union[str, Path], dst: Union[str, Path]) -> None:
        """
        Move a file.
        
        Args:
            src: Source path
            dst: Destination path
        """
        src_path = Path(src)
        dst_path = Path(dst)
        FileUtils.ensure_dir(dst_path.parent)
        shutil.move(src_path, dst_path)
    
    @staticmethod
    def delete_file(path: Union[str, Path]) -> None:
        """
        Delete a file.
        
        Args:
            path: File path
        """
        path = Path(path)
        if path.exists() and path.is_file():
            path.unlink()
    
    @staticmethod
    def delete_dir(path: Union[str, Path]) -> None:
        """
        Delete a directory.
        
        Args:
            path: Directory path
        """
        path = Path(path)
        if path.exists() and path.is_dir():
            shutil.rmtree(path)
    
    @staticmethod
    def list_files(path: Union[str, Path], pattern: Optional[str] = None, recursive: bool = False) -> List[Path]:
        """
        List files in a directory.
        
        Args:
            path: Directory path
            pattern: File pattern (glob)
            recursive: Search recursively
        
        Returns:
            List of file paths
        """
        path = Path(path)
        if not path.exists():
            return []
        
        if recursive:
            if pattern:
                return list(path.glob(f'**/{pattern}'))
            return list(path.glob('**/*'))
        else:
            if pattern:
                return list(path.glob(pattern))
            return list(path.glob('*'))
    
    @staticmethod
    def list_files_by_extension(path: Union[str, Path], extension: str, recursive: bool = False) -> List[Path]:
        """
        List files by extension.
        
        Args:
            path: Directory path
            extension: File extension (e.g., '.txt')
            recursive: Search recursively
        
        Returns:
            List of file paths
        """
        return FileUtils.list_files(path, f'*{extension}', recursive)
    
    @staticmethod
    def find_files(path: Union[str, Path], pattern: str, recursive: bool = True) -> List[Path]:
        """
        Find files matching a pattern.
        
        Args:
            path: Directory path
            pattern: File pattern (glob)
            recursive: Search recursively
        
        Returns:
            List of matching file paths
        """
        return FileUtils.list_files(path, pattern, recursive)
    
    @staticmethod
    def get_temp_dir() -> Path:
        """
        Get a temporary directory.
        
        Returns:
            Temporary directory path
        """
        return Path(tempfile.mkdtemp())
    
    @staticmethod
    def get_temp_file(suffix: Optional[str] = None, prefix: str = 'tmp_') -> Path:
        """
        Get a temporary file.
        
        Args:
            suffix: File suffix
            prefix: File prefix
        
        Returns:
            Temporary file path
        """
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)
        return Path(path)
    
    @staticmethod
    def create_temp_file(content: Union[str, bytes], suffix: Optional[str] = None) -> Path:
        """
        Create a temporary file with content.
        
        Args:
            content: File content
            suffix: File suffix
        
        Returns:
            Temporary file path
        """
        path = FileUtils.get_temp_file(suffix)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
        return path
    
    @staticmethod
    def create_temp_dir() -> Path:
        """
        Create a temporary directory.
        
        Returns:
            Temporary directory path
        """
        return Path(tempfile.mkdtemp())
    
    @staticmethod
    def is_file(path: Union[str, Path]) -> bool:
        """
        Check if a path is a file.
        
        Args:
            path: Path to check
        
        Returns:
            True if file, False otherwise
        """
        return Path(path).is_file()
    
    @staticmethod
    def is_dir(path: Union[str, Path]) -> bool:
        """
        Check if a path is a directory.
        
        Args:
            path: Path to check
        
        Returns:
            True if directory, False otherwise
        """
        return Path(path).is_dir()
    
    @staticmethod
    def is_symlink(path: Union[str, Path]) -> bool:
        """
        Check if a path is a symbolic link.
        
        Args:
            path: Path to check
        
        Returns:
            True if symbolic link, False otherwise
        """
        return Path(path).is_symlink()
    
    @staticmethod
    def exists(path: Union[str, Path]) -> bool:
        """
        Check if a path exists.
        
        Args:
            path: Path to check
        
        Returns:
            True if exists, False otherwise
        """
        return Path(path).exists()
    
    @staticmethod
    def get_absolute_path(path: Union[str, Path]) -> Path:
        """
        Get absolute path.
        
        Args:
            path: Path
        
        Returns:
            Absolute path
        """
        return Path(path).absolute()
    
    @staticmethod
    def get_relative_path(path: Union[str, Path], base: Union[str, Path]) -> Path:
        """
        Get relative path.
        
        Args:
            path: Path
            base: Base path
        
        Returns:
            Relative path
        """
        return Path(path).relative_to(Path(base))
    
    @staticmethod
    def normalize_path(path: Union[str, Path]) -> Path:
        """
        Normalize a path.
        
        Args:
            path: Path
        
        Returns:
            Normalized path
        """
        return Path(os.path.normpath(str(path)))
    
    @staticmethod
    def join_paths(*paths: Union[str, Path]) -> Path:
        """
        Join paths.
        
        Args:
            *paths: Paths to join
        
        Returns:
            Joined path
        """
        return Path(*paths)
    
    @staticmethod
    def split_path(path: Union[str, Path]) -> Tuple[Path, str]:
        """
        Split a path into directory and file name.
        
        Args:
            path: Path
        
        Returns:
            Tuple of (directory, file_name)
        """
        path = Path(path)
        return path.parent, path.name
    
    @staticmethod
    def change_extension(path: Union[str, Path], new_extension: str) -> Path:
        """
        Change file extension.
        
        Args:
            path: File path
            new_extension: New extension (including dot)
        
        Returns:
            Path with new extension
        """
        path = Path(path)
        return path.with_suffix(new_extension)
    
    @staticmethod
    def get_mime_type(path: Union[str, Path]) -> str:
        """
        Get MIME type of a file.
        
        Args:
            path: File path
        
        Returns:
            MIME type
        """
        import mimetypes
        mime_type, _ = mimetypes.guess_type(str(path))
        return mime_type or 'application/octet-stream'
    
    @staticmethod
    def is_text_file(path: Union[str, Path]) -> bool:
        """
        Check if a file is a text file.
        
        Args:
            path: File path
        
        Returns:
            True if text file, False otherwise
        """
        try:
            with open(path, 'r') as f:
                f.read(1024)
            return True
        except UnicodeDecodeError:
            return False
    
    @staticmethod
    def get_line_count(path: Union[str, Path]) -> int:
        """
        Get the number of lines in a file.
        
        Args:
            path: File path
        
        Returns:
            Number of lines
        """
        with open(path, 'r') as f:
            return sum(1 for _ in f)
    
    @staticmethod
    def get_word_count(path: Union[str, Path]) -> int:
        """
        Get the number of words in a file.
        
        Args:
            path: File path
        
        Returns:
            Number of words
        """
        content = FileUtils.read_text(path)
        return len(content.split())
    
    @staticmethod
    def get_char_count(path: Union[str, Path]) -> int:
        """
        Get the number of characters in a file.
        
        Args:
            path: File path
        
        Returns:
            Number of characters
        """
        content = FileUtils.read_text(path)
        return len(content)
    
    @staticmethod
    def compress_file(path: Union[str, Path], format: str = 'gzip', level: int = 6) -> Path:
        """
        Compress a file.
        
        Args:
            path: File path
            format: Compression format ('gzip', 'bzip2', 'xz', 'zip')
            level: Compression level
        
        Returns:
            Compressed file path
        """
        path = Path(path)
        compressed_path = Path(f"{path}.{format}")
        
        if format == 'gzip':
            with open(path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb', compresslevel=level) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif format == 'bzip2':
            with open(path, 'rb') as f_in:
                with bz2.open(compressed_path, 'wb', compresslevel=level) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif format == 'xz':
            with open(path, 'rb') as f_in:
                with lzma.open(compressed_path, 'wb', preset=level) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif format == 'zip':
            compressed_path = Path(f"{path}.zip")
            with zipfile.ZipFile(compressed_path, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(path, path.name)
        else:
            raise ValueError(f"Unsupported compression format: {format}")
        
        return compressed_path
    
    @staticmethod
    def decompress_file(path: Union[str, Path], output_dir: Optional[Union[str, Path]] = None) -> Path:
        """
        Decompress a file.
        
        Args:
            path: Compressed file path
            output_dir: Output directory
        
        Returns:
            Decompressed file path
        """
        path = Path(path)
        output_dir = Path(output_dir) if output_dir else path.parent
        FileUtils.ensure_dir(output_dir)
        
        if path.suffix == '.gz':
            output_path = output_dir / path.stem
            with gzip.open(path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif path.suffix == '.bz2':
            output_path = output_dir / path.stem
            with bz2.open(path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif path.suffix == '.xz':
            output_path = output_dir / path.stem
            with lzma.open(path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif path.suffix == '.zip':
            with zipfile.ZipFile(path, 'r') as zip_file:
                zip_file.extractall(output_dir)
            output_path = output_dir / zip_file.namelist()[0]
        else:
            raise ValueError(f"Unsupported compression format: {path.suffix}")
        
        return output_path
    
    @staticmethod
    def compress_dir(path: Union[str, Path], format: str = 'zip') -> Path:
        """
        Compress a directory.
        
        Args:
            path: Directory path
            format: Compression format ('zip', 'tar', 'tar.gz', 'tar.bz2', 'tar.xz')
        
        Returns:
            Compressed file path
        """
        path = Path(path)
        
        if format == 'zip':
            compressed_path = Path(f"{path}.zip")
            with zipfile.ZipFile(compressed_path, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in path.rglob('*'):
                    if file_path.is_file():
                        zip_file.write(file_path, file_path.relative_to(path))
        elif format == 'tar':
            compressed_path = Path(f"{path}.tar")
            with tarfile.open(compressed_path, 'w') as tar_file:
                tar_file.add(path, arcname=path.name)
        elif format == 'tar.gz':
            compressed_path = Path(f"{path}.tar.gz")
            with tarfile.open(compressed_path, 'w:gz') as tar_file:
                tar_file.add(path, arcname=path.name)
        elif format == 'tar.bz2':
            compressed_path = Path(f"{path}.tar.bz2")
            with tarfile.open(compressed_path, 'w:bz2') as tar_file:
                tar_file.add(path, arcname=path.name)
        elif format == 'tar.xz':
            compressed_path = Path(f"{path}.tar.xz")
            with tarfile.open(compressed_path, 'w:xz') as tar_file:
                tar_file.add(path, arcname=path.name)
        else:
            raise ValueError(f"Unsupported compression format: {format}")
        
        return compressed_path
    
    @staticmethod
    def decompress_dir(path: Union[str, Path], output_dir: Optional[Union[str, Path]] = None) -> Path:
        """
        Decompress a directory.
        
        Args:
            path: Compressed file path
            output_dir: Output directory
        
        Returns:
            Decompressed directory path
        """
        path = Path(path)
        output_dir = Path(output_dir) if output_dir else path.parent
        FileUtils.ensure_dir(output_dir)
        
        if path.suffix == '.zip':
            with zipfile.ZipFile(path, 'r') as zip_file:
                zip_file.extractall(output_dir)
        elif path.suffix == '.tar' or path.suffixes == ['.tar']:
            with tarfile.open(path, 'r') as tar_file:
                tar_file.extractall(output_dir)
        elif path.suffixes == ['.tar', '.gz']:
            with tarfile.open(path, 'r:gz') as tar_file:
                tar_file.extractall(output_dir)
        elif path.suffixes == ['.tar', '.bz2']:
            with tarfile.open(path, 'r:bz2') as tar_file:
                tar_file.extractall(output_dir)
        elif path.suffixes == ['.tar', '.xz']:
            with tarfile.open(path, 'r:xz') as tar_file:
                tar_file.extractall(output_dir)
        else:
            raise ValueError(f"Unsupported compression format: {path.suffix}")
        
        return output_dir


# Function aliases for easier import
ensure_dir = FileUtils.ensure_dir
ensure_file = FileUtils.ensure_file
read_text = FileUtils.read_text
write_text = FileUtils.write_text
read_bytes = FileUtils.read_bytes
write_bytes = FileUtils.write_bytes
read_lines = FileUtils.read_lines
write_lines = FileUtils.write_lines
read_json = FileUtils.read_json
write_json = FileUtils.write_json
read_yaml = FileUtils.read_yaml
write_yaml = FileUtils.write_yaml
read_pickle = FileUtils.read_pickle
write_pickle = FileUtils.write_pickle
read_csv = FileUtils.read_csv
write_csv = FileUtils.write_csv
get_file_size = FileUtils.get_file_size
get_file_modified_time = FileUtils.get_file_modified_time
get_file_created_time = FileUtils.get_file_created_time
get_file_hash = FileUtils.get_file_hash
get_file_extension = FileUtils.get_file_extension
get_file_name = FileUtils.get_file_name
get_file_name_without_extension = FileUtils.get_file_name_without_extension
get_file_dir = FileUtils.get_file_dir
copy_file = FileUtils.copy_file
move_file = FileUtils.move_file
delete_file = FileUtils.delete_file
delete_dir = FileUtils.delete_dir
list_files = FileUtils.list_files
list_files_by_extension = FileUtils.list_files_by_extension
find_files = FileUtils.find_files
get_temp_dir = FileUtils.get_temp_dir
get_temp_file = FileUtils.get_temp_file
create_temp_file = FileUtils.create_temp_file
create_temp_dir = FileUtils.create_temp_dir
is_file = FileUtils.is_file
is_dir = FileUtils.is_dir
is_symlink = FileUtils.is_symlink
exists = FileUtils.exists
get_absolute_path = FileUtils.get_absolute_path
get_relative_path = FileUtils.get_relative_path
normalize_path = FileUtils.normalize_path
join_paths = FileUtils.join_paths
split_path = FileUtils.split_path
change_extension = FileUtils.change_extension
get_mime_type = FileUtils.get_mime_type
is_text_file = FileUtils.is_text_file
get_line_count = FileUtils.get_line_count
get_word_count = FileUtils.get_word_count
get_char_count = FileUtils.get_char_count
compress_file = FileUtils.compress_file
decompress_file = FileUtils.decompress_file
compress_dir = FileUtils.compress_dir
decompress_dir = FileUtils.decompress_dir


__all__ = [
    # Class
    'FileUtils',
    
    # Function aliases
    'ensure_dir',
    'ensure_file',
    'read_text',
    'write_text',
    'read_bytes',
    'write_bytes',
    'read_lines',
    'write_lines',
    'read_json',
    'write_json',
    'read_yaml',
    'write_yaml',
    'read_pickle',
    'write_pickle',
    'read_csv',
    'write_csv',
    'get_file_size',
    'get_file_modified_time',
    'get_file_created_time',
    'get_file_hash',
    'get_file_extension',
    'get_file_name',
    'get_file_name_without_extension',
    'get_file_dir',
    'copy_file',
    'move_file',
    'delete_file',
    'delete_dir',
    'list_files',
    'list_files_by_extension',
    'find_files',
    'get_temp_dir',
    'get_temp_file',
    'create_temp_file',
    'create_temp_dir',
    'is_file',
    'is_dir',
    'is_symlink',
    'exists',
    'get_absolute_path',
    'get_relative_path',
    'normalize_path',
    'join_paths',
    'split_path',
    'change_extension',
    'get_mime_type',
    'is_text_file',
    'get_line_count',
    'get_word_count',
    'get_char_count',
    'compress_file',
    'decompress_file',
    'compress_dir',
    'decompress_dir',
]
