# trading/bots/hedge_bot/hedge_bot_data_public_cloud.py

import asyncio
import json
import logging
import time
import uuid
import hashlib
import base64
import gzip
import zlib
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable, BinaryIO
from decimal import Decimal
from collections import defaultdict
import io
import struct

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    from botocore.config import Config
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    from google.cloud import storage
    from google.cloud.storage import Client, Bucket, Blob
    from google.auth.exceptions import DefaultCredentialsError
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False

try:
    from azure.storage.blob import (
        BlobServiceClient,
        ContainerClient,
        BlobClient,
        generate_blob_sas,
        BlobSasPermissions
    )
    from azure.core.exceptions import AzureError, ResourceNotFoundError
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

try:
    import aiohttp
    import aiofiles
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

logger = logging.getLogger(__name__)


class CloudProvider(str, Enum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    DO = "digital_ocean"
    LINODE = "linode"
    VULTR = "vultr"
    OVH = "ovh"
    SCALEWAY = "scaleway"
    HETZNER = "hetzner"
    UPCLOUD = "upcloud"
    EXOSCALE = "exoscale"
    CLOUDINARY = "cloudinary"
    BACKBLAZE = "backblaze"
    WASABI = "wasabi"
    MINIO = "minio"
    R2 = "cloudflare_r2"


class CloudService(str, Enum):
    S3 = "s3"
    GCS = "gcs"
    AZURE_BLOB = "azure_blob"
    CDN = "cdn"
    COMPUTE = "compute"
    DATABASE = "database"
    MESSAGE_QUEUE = "message_queue"
    PUBSUB = "pubsub"
    FUNCTION = "function"
    ML = "ml"
    ANALYTICS = "analytics"
    MONITORING = "monitoring"
    LOGGING = "logging"
    SECRETS = "secrets"
    KEY_MANAGEMENT = "key_management"
    IAM = "iam"
    DNS = "dns"
    LOAD_BALANCER = "load_balancer"
    CACHE = "cache"
    SEARCH = "search"
    AI = "ai"
    NLP = "nlp"
    VISION = "vision"
    SPEECH = "speech"
    TRANSLATION = "translation"


@dataclass
class CloudCredentials:
    provider: CloudProvider
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    region: Optional[str] = None
    bucket_name: Optional[str] = None
    container_name: Optional[str] = None
    project_id: Optional[str] = None
    service_account: Optional[str] = None
    account_name: Optional[str] = None
    account_key: Optional[str] = None
    connection_string: Optional[str] = None
    endpoint_url: Optional[str] = None
    use_ssl: bool = True
    timeout: int = 30
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CloudObject:
    key: str
    bucket: str
    size: int
    last_modified: datetime
    etag: str
    content_type: str
    storage_class: str
    owner: Optional[str] = None
    version_id: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    public_url: Optional[str] = None
    signed_url: Optional[str] = None
    expires_at: Optional[datetime] = None


@dataclass
class CloudDownload:
    key: str
    bucket: str
    size: int
    content: bytes
    content_type: str
    etag: str
    last_modified: datetime
    metadata: Dict[str, str] = field(default_factory=dict)
    url: Optional[str] = None


@dataclass
class CloudUpload:
    key: str
    bucket: str
    size: int
    etag: str
    version_id: Optional[str] = None
    public_url: Optional[str] = None
    signed_url: Optional[str] = None
    upload_id: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class CloudBucket:
    name: str
    provider: CloudProvider
    region: str
    creation_date: datetime
    versioning_enabled: bool
    encryption_enabled: bool
    lifecycle_rules: List[Dict[str, Any]]
    tags: Dict[str, str] = field(default_factory=dict)
    size: Optional[int] = None
    object_count: Optional[int] = None


@dataclass
class CloudPresignedURL:
    url: str
    expires_at: datetime
    method: str
    key: str
    bucket: str


@dataclass
class CloudMultipartUpload:
    upload_id: str
    key: str
    bucket: str
    provider: CloudProvider
    parts: List[Dict[str, Any]]
    started_at: datetime
    expires_at: Optional[datetime] = None
    etags: List[str] = field(default_factory=list)
    completed: bool = False


class PublicCloudDataManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._clients: Dict[CloudProvider, Any] = {}
        self._credentials: Dict[CloudProvider, CloudCredentials] = {}
        self._buckets: Dict[str, CloudBucket] = {}
        self._multipart_uploads: Dict[str, CloudMultipartUpload] = {}
        self._presigned_urls: Dict[str, CloudPresignedURL] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300
        self._session: Optional[aiohttp.ClientSession] = None
        
        self._initialize_clients()

    def _initialize_clients(self) -> None:
        aws_config = self.config.get("aws", {})
        if aws_config and BOTO3_AVAILABLE:
            try:
                self._init_aws_client(aws_config)
            except Exception as e:
                logger.error(f"Failed to initialize AWS client: {e}")

        gcp_config = self.config.get("gcp", {})
        if gcp_config and GOOGLE_CLOUD_AVAILABLE:
            try:
                self._init_gcp_client(gcp_config)
            except Exception as e:
                logger.error(f"Failed to initialize GCP client: {e}")

        azure_config = self.config.get("azure", {})
        if azure_config and AZURE_AVAILABLE:
            try:
                self._init_azure_client(azure_config)
            except Exception as e:
                logger.error(f"Failed to initialize Azure client: {e}")

    def _init_aws_client(self, config: Dict[str, Any]) -> None:
        if not BOTO3_AVAILABLE:
            return

        creds = CloudCredentials(
            provider=CloudProvider.AWS,
            access_key=config.get("access_key"),
            secret_key=config.get("secret_key"),
            region=config.get("region", "us-east-1"),
            bucket_name=config.get("bucket_name"),
            timeout=config.get("timeout", 30),
            max_retries=config.get("max_retries", 3)
        )

        self._credentials[CloudProvider.AWS] = creds

        boto_config = Config(
            region_name=creds.region,
            max_pool_connections=50,
            retries={
                'max_attempts': creds.max_retries,
                'mode': 'adaptive'
            }
        )

        if creds.access_key and creds.secret_key:
            client = boto3.client(
                's3',
                aws_access_key_id=creds.access_key,
                aws_secret_access_key=creds.secret_key,
                config=boto_config,
                endpoint_url=config.get("endpoint_url")
            )
        else:
            client = boto3.client('s3', config=boto_config)

        self._clients[CloudProvider.AWS] = client
        logger.info("AWS S3 client initialized")

    def _init_gcp_client(self, config: Dict[str, Any]) -> None:
        if not GOOGLE_CLOUD_AVAILABLE:
            return

        creds = CloudCredentials(
            provider=CloudProvider.GCP,
            project_id=config.get("project_id"),
            service_account=config.get("service_account"),
            bucket_name=config.get("bucket_name"),
            region=config.get("region", "us-central1"),
            timeout=config.get("timeout", 30),
            max_retries=config.get("max_retries", 3)
        )

        self._credentials[CloudProvider.GCP] = creds

        if config.get("service_account"):
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(
                config["service_account"]
            )
            client = storage.Client(
                project=creds.project_id,
                credentials=credentials
            )
        else:
            client = storage.Client(project=creds.project_id)

        self._clients[CloudProvider.GCP] = client
        logger.info("GCP Storage client initialized")

    def _init_azure_client(self, config: Dict[str, Any]) -> None:
        if not AZURE_AVAILABLE:
            return

        creds = CloudCredentials(
            provider=CloudProvider.AZURE,
            account_name=config.get("account_name"),
            account_key=config.get("account_key"),
            connection_string=config.get("connection_string"),
            container_name=config.get("container_name"),
            region=config.get("region", "eastus"),
            timeout=config.get("timeout", 30),
            max_retries=config.get("max_retries", 3)
        )

        self._credentials[CloudProvider.AZURE] = creds

        if creds.connection_string:
            client = BlobServiceClient.from_connection_string(
                creds.connection_string,
                max_retries=creds.max_retries
            )
        elif creds.account_name and creds.account_key:
            client = BlobServiceClient(
                account_url=f"https://{creds.account_name}.blob.core.windows.net",
                credential=creds.account_key,
                max_retries=creds.max_retries
            )
        else:
            from azure.identity import DefaultAzureCredential
            client = BlobServiceClient(
                account_url=f"https://{creds.account_name}.blob.core.windows.net",
                credential=DefaultAzureCredential(),
                max_retries=creds.max_retries
            )

        self._clients[CloudProvider.AZURE] = client
        logger.info("Azure Blob Storage client initialized")

    async def _ensure_session(self) -> None:
        if self._session is None and AIOHTTP_AVAILABLE:
            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "Nexus-HedgeBot/3.0"}
            )

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def upload_file(
        self,
        provider: CloudProvider,
        bucket: str,
        key: str,
        data: Union[bytes, str, BinaryIO],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        encryption: bool = True,
        storage_class: str = "STANDARD",
        part_size: int = 8 * 1024 * 1024
    ) -> CloudUpload:
        async with self._lock:
            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]

            if isinstance(data, str):
                data = data.encode('utf-8')
            elif hasattr(data, 'read'):
                data = data.read()

            if not content_type:
                content_type = self._guess_content_type(key)

            metadata = metadata or {}
            metadata['uploaded_by'] = 'nexus_hedge_bot'
            metadata['uploaded_at'] = datetime.now().isoformat()

            if provider == CloudProvider.AWS:
                return await self._upload_aws(client, bucket, key, data, content_type, metadata, storage_class, encryption, part_size)
            elif provider == CloudProvider.GCP:
                return await self._upload_gcp(client, bucket, key, data, content_type, metadata, storage_class, encryption)
            elif provider == CloudProvider.AZURE:
                return await self._upload_azure(client, bucket, key, data, content_type, metadata, storage_class, encryption)
            else:
                raise ValueError(f"Unsupported provider: {provider.value}")

    async def _upload_aws(
        self,
        client: Any,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Dict[str, str],
        storage_class: str,
        encryption: bool,
        part_size: int
    ) -> CloudUpload:
        extra_args = {
            'ContentType': content_type,
            'StorageClass': storage_class,
            'Metadata': metadata
        }

        if encryption:
            extra_args['ServerSideEncryption'] = 'AES256'

        if len(data) > part_size:
            upload_id = await self._initiate_multipart_upload_aws(client, bucket, key, extra_args)
            parts = await self._upload_parts_aws(client, bucket, key, upload_id, data, part_size)
            etag = await self._complete_multipart_upload_aws(client, bucket, key, upload_id, parts)

            return CloudUpload(
                key=key,
                bucket=bucket,
                size=len(data),
                etag=etag,
                upload_id=upload_id,
                metadata=metadata,
                public_url=self._get_public_url_aws(bucket, key)
            )
        else:
            response = client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                **extra_args
            )

            return CloudUpload(
                key=key,
                bucket=bucket,
                size=len(data),
                etag=response.get('ETag', '').strip('"'),
                version_id=response.get('VersionId'),
                metadata=metadata,
                public_url=self._get_public_url_aws(bucket, key)
            )

    async def _upload_gcp(
        self,
        client: Any,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Dict[str, str],
        storage_class: str,
        encryption: bool
    ) -> CloudUpload:
        bucket_obj = client.bucket(bucket)
        blob = bucket_obj.blob(key)

        if metadata:
            blob.metadata = metadata

        blob.content_type = content_type
        blob.storage_class = storage_class

        if encryption:
            blob.encryption_key = None

        blob.upload_from_string(
            data,
            content_type=content_type,
            client=client
        )

        return CloudUpload(
            key=key,
            bucket=bucket,
            size=len(data),
            etag=blob.etag,
            version_id=blob.generation,
            metadata=metadata,
            public_url=self._get_public_url_gcp(bucket, key)
        )

    async def _upload_azure(
        self,
        client: Any,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Dict[str, str],
        storage_class: str,
        encryption: bool
    ) -> CloudUpload:
        container_client = client.get_container_client(bucket)
        blob_client = container_client.get_blob_client(key)

        blob_client.upload_blob(
            data,
            blob_type="BlockBlob",
            metadata=metadata,
            content_type=content_type,
            overwrite=True
        )

        properties = blob_client.get_blob_properties()

        return CloudUpload(
            key=key,
            bucket=bucket,
            size=len(data),
            etag=properties.etag,
            version_id=properties.version_id,
            metadata=metadata,
            public_url=self._get_public_url_azure(bucket, key)
        )

    async def download_file(
        self,
        provider: CloudProvider,
        bucket: str,
        key: str,
        check_cache: bool = True
    ) -> CloudDownload:
        async with self._lock:
            cache_key = f"{provider.value}:{bucket}:{key}"
            if check_cache and cache_key in self._cache:
                cached = self._cache[cache_key]
                if time.time() - cached.get('timestamp', 0) < self._cache_ttl:
                    return cached['data']

            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]

            if provider == CloudProvider.AWS:
                return await self._download_aws(client, bucket, key, cache_key)
            elif provider == CloudProvider.GCP:
                return await self._download_gcp(client, bucket, key, cache_key)
            elif provider == CloudProvider.AZURE:
                return await self._download_azure(client, bucket, key, cache_key)
            else:
                raise ValueError(f"Unsupported provider: {provider.value}")

    async def _download_aws(self, client: Any, bucket: str, key: str, cache_key: str) -> CloudDownload:
        response = client.get_object(Bucket=bucket, Key=key)

        content = response['Body'].read()
        etag = response.get('ETag', '').strip('"')
        last_modified = response.get('LastModified', datetime.now())
        content_type = response.get('ContentType', 'application/octet-stream')
        size = response.get('ContentLength', len(content))
        metadata = response.get('Metadata', {})

        download = CloudDownload(
            key=key,
            bucket=bucket,
            size=size,
            content=content,
            content_type=content_type,
            etag=etag,
            last_modified=last_modified,
            metadata=metadata
        )

        self._cache[cache_key] = {
            'data': download,
            'timestamp': time.time()
        }

        return download

    async def _download_gcp(self, client: Any, bucket: str, key: str, cache_key: str) -> CloudDownload:
        bucket_obj = client.bucket(bucket)
        blob = bucket_obj.blob(key)

        content = blob.download_as_bytes()
        etag = blob.etag
        last_modified = blob.updated if blob.updated else datetime.now()
        content_type = blob.content_type or 'application/octet-stream'
        size = blob.size or len(content)
        metadata = blob.metadata or {}

        download = CloudDownload(
            key=key,
            bucket=bucket,
            size=size,
            content=content,
            content_type=content_type,
            etag=etag,
            last_modified=last_modified,
            metadata=metadata
        )

        self._cache[cache_key] = {
            'data': download,
            'timestamp': time.time()
        }

        return download

    async def _download_azure(self, client: Any, bucket: str, key: str, cache_key: str) -> CloudDownload:
        container_client = client.get_container_client(bucket)
        blob_client = container_client.get_blob_client(key)

        stream = blob_client.download_blob()
        content = stream.readall()
        properties = blob_client.get_blob_properties()

        download = CloudDownload(
            key=key,
            bucket=bucket,
            size=properties.size,
            content=content,
            content_type=properties.content_settings.content_type,
            etag=properties.etag,
            last_modified=properties.last_modified,
            metadata=properties.metadata or {}
        )

        self._cache[cache_key] = {
            'data': download,
            'timestamp': time.time()
        }

        return download

    async def delete_file(
        self,
        provider: CloudProvider,
        bucket: str,
        key: str
    ) -> bool:
        async with self._lock:
            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]

            try:
                if provider == CloudProvider.AWS:
                    client.delete_object(Bucket=bucket, Key=key)
                elif provider == CloudProvider.GCP:
                    bucket_obj = client.bucket(bucket)
                    blob = bucket_obj.blob(key)
                    blob.delete()
                elif provider == CloudProvider.AZURE:
                    container_client = client.get_container_client(bucket)
                    blob_client = container_client.get_blob_client(key)
                    blob_client.delete_blob()

                cache_key = f"{provider.value}:{bucket}:{key}"
                self._cache.pop(cache_key, None)

                return True

            except Exception as e:
                logger.error(f"Error deleting {key} from {provider.value}: {e}")
                return False

    async def list_files(
        self,
        provider: CloudProvider,
        bucket: str,
        prefix: str = "",
        max_keys: int = 1000,
        delimiter: str = ""
    ) -> List[CloudObject]:
        async with self._lock:
            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]
            objects = []

            if provider == CloudProvider.AWS:
                paginator = client.get_paginator('list_objects_v2')
                for page in paginator.paginate(
                    Bucket=bucket,
                    Prefix=prefix,
                    Delimiter=delimiter,
                    MaxKeys=max_keys
                ):
                    for obj in page.get('Contents', []):
                        objects.append(
                            CloudObject(
                                key=obj['Key'],
                                bucket=bucket,
                                size=obj['Size'],
                                last_modified=obj['LastModified'],
                                etag=obj['ETag'].strip('"'),
                                content_type=obj.get('ContentType', 'application/octet-stream'),
                                storage_class=obj.get('StorageClass', 'STANDARD'),
                                owner=obj.get('Owner', {}).get('ID')
                            )
                        )

            elif provider == CloudProvider.GCP:
                bucket_obj = client.bucket(bucket)
                blobs = bucket_obj.list_blobs(prefix=prefix, max_results=max_keys)
                for blob in blobs:
                    objects.append(
                        CloudObject(
                            key=blob.name,
                            bucket=bucket,
                            size=blob.size or 0,
                            last_modified=blob.updated if blob.updated else datetime.now(),
                            etag=blob.etag,
                            content_type=blob.content_type or 'application/octet-stream',
                            storage_class=blob.storage_class or 'STANDARD'
                        )
                    )

            elif provider == CloudProvider.AZURE:
                container_client = client.get_container_client(bucket)
                blobs = container_client.list_blobs(
                    name_starts_with=prefix,
                    max_results=max_keys
                )
                for blob in blobs:
                    objects.append(
                        CloudObject(
                            key=blob.name,
                            bucket=bucket,
                            size=blob.size,
                            last_modified=blob.last_modified,
                            etag=blob.etag,
                            content_type=blob.content_settings.content_type if blob.content_settings else 'application/octet-stream',
                            storage_class=blob.blob_tier or 'STANDARD',
                            metadata=blob.metadata or {}
                        )
                    )

            return objects

    async def generate_presigned_url(
        self,
        provider: CloudProvider,
        bucket: str,
        key: str,
        method: str = "GET",
        expires_in: int = 3600,
        content_type: Optional[str] = None
    ) -> CloudPresignedURL:
        async with self._lock:
            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]
            expires_at = datetime.now() + timedelta(seconds=expires_in)

            if provider == CloudProvider.AWS:
                url = client.generate_presigned_url(
                    ClientMethod=f'{method.lower()}_object',
                    Params={'Bucket': bucket, 'Key': key},
                    ExpiresIn=expires_in,
                    HttpMethod=method
                )

            elif provider == CloudProvider.GCP:
                bucket_obj = client.bucket(bucket)
                blob = bucket_obj.blob(key)
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=expires_in,
                    method=method
                )

            elif provider == CloudProvider.AZURE:
                container_client = client.get_container_client(bucket)
                blob_client = container_client.get_blob_client(key)

                from azure.storage.blob import generate_blob_sas, BlobSasPermissions
                sas_token = generate_blob_sas(
                    account_name=client.account_name,
                    container_name=bucket,
                    blob_name=key,
                    account_key=client.credential,
                    permission=BlobSasPermissions(read=True) if method.upper() == "GET" else BlobSasPermissions(write=True),
                    expiry=expires_at
                )
                url = f"{blob_client.url}?{sas_token}"

            else:
                raise ValueError(f"Unsupported provider: {provider.value}")

            presigned = CloudPresignedURL(
                url=url,
                expires_at=expires_at,
                method=method,
                key=key,
                bucket=bucket
            )

            cache_key = f"presigned:{provider.value}:{bucket}:{key}"
            self._presigned_urls[cache_key] = presigned

            return presigned

    async def copy_file(
        self,
        provider: CloudProvider,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        async with self._lock:
            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]

            try:
                if provider == CloudProvider.AWS:
                    copy_source = {'Bucket': source_bucket, 'Key': source_key}
                    client.copy_object(
                        Bucket=dest_bucket,
                        Key=dest_key,
                        CopySource=copy_source,
                        Metadata=metadata or {},
                        MetadataDirective='REPLACE'
                    )

                elif provider == CloudProvider.GCP:
                    source_bucket_obj = client.bucket(source_bucket)
                    source_blob = source_bucket_obj.blob(source_key)
                    dest_bucket_obj = client.bucket(dest_bucket)
                    dest_bucket_obj.copy_blob(source_blob, dest_bucket_obj, dest_key)

                elif provider == CloudProvider.AZURE:
                    source_container = client.get_container_client(source_bucket)
                    source_blob = source_container.get_blob_client(source_key)
                    dest_container = client.get_container_client(dest_bucket)
                    dest_blob = dest_container.get_blob_client(dest_key)

                    source_url = source_blob.url
                    dest_blob.start_copy_from_url(source_url)

                cache_key = f"{provider.value}:{dest_bucket}:{dest_key}"
                self._cache.pop(cache_key, None)

                return True

            except Exception as e:
                logger.error(f"Error copying file: {e}")
                return False

    async def get_bucket_info(
        self,
        provider: CloudProvider,
        bucket: str
    ) -> Optional[CloudBucket]:
        async with self._lock:
            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]

            try:
                if provider == CloudProvider.AWS:
                    response = client.head_bucket(Bucket=bucket)
                    versioning = client.get_bucket_versioning(Bucket=bucket)
                    lifecycle = client.get_bucket_lifecycle_configuration(Bucket=bucket)

                    return CloudBucket(
                        name=bucket,
                        provider=provider,
                        region=self._credentials[provider].region or 'us-east-1',
                        creation_date=response.get('CreationDate', datetime.now()),
                        versioning_enabled=versioning.get('Status') == 'Enabled',
                        encryption_enabled=True,
                        lifecycle_rules=lifecycle.get('Rules', [])
                    )

                elif provider == CloudProvider.GCP:
                    bucket_obj = client.bucket(bucket)
                    versioning = bucket_obj.get_versioning()
                    lifecycle = bucket_obj.get_lifecycle_rules()

                    return CloudBucket(
                        name=bucket,
                        provider=provider,
                        region=client.location,
                        creation_date=bucket_obj.time_created,
                        versioning_enabled=versioning.get('enabled') if versioning else False,
                        encryption_enabled=True,
                        lifecycle_rules=[rule._properties for rule in lifecycle] if lifecycle else []
                    )

                elif provider == CloudProvider.AZURE:
                    container_client = client.get_container_client(bucket)
                    properties = container_client.get_container_properties()

                    return CloudBucket(
                        name=bucket,
                        provider=provider,
                        region=self._credentials[provider].region or 'eastus',
                        creation_date=properties.last_modified,
                        versioning_enabled=properties.has_immutability_policy,
                        encryption_enabled=properties.has_encryption_scope,
                        lifecycle_rules=[]
                    )

            except Exception as e:
                logger.error(f"Error getting bucket info: {e}")
                return None

    async def create_bucket(
        self,
        provider: CloudProvider,
        bucket: str,
        region: Optional[str] = None,
        versioning: bool = False,
        encryption: bool = True,
        public: bool = False
    ) -> bool:
        async with self._lock:
            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]

            try:
                if provider == CloudProvider.AWS:
                    params = {'Bucket': bucket}
                    if region:
                        params['CreateBucketConfiguration'] = {'LocationConstraint': region}

                    client.create_bucket(**params)

                    if versioning:
                        client.put_bucket_versioning(
                            Bucket=bucket,
                            VersioningConfiguration={'Status': 'Enabled'}
                        )

                    if not public:
                        client.put_bucket_acl(
                            Bucket=bucket,
                            ACL='private'
                        )

                elif provider == CloudProvider.GCP:
                    bucket_obj = client.bucket(bucket)
                    bucket_obj.create(location=region or client.location)

                    if versioning:
                        bucket_obj.versioning_enabled = True

                elif provider == CloudProvider.AZURE:
                    client.create_container(bucket)

                self._buckets[bucket] = await self.get_bucket_info(provider, bucket)
                return True

            except Exception as e:
                logger.error(f"Error creating bucket: {e}")
                return False

    async def delete_bucket(
        self,
        provider: CloudProvider,
        bucket: str,
        force: bool = False
    ) -> bool:
        async with self._lock:
            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]

            try:
                if force:
                    objects = await self.list_files(provider, bucket, max_keys=1000)
                    for obj in objects:
                        await self.delete_file(provider, bucket, obj.key)

                if provider == CloudProvider.AWS:
                    client.delete_bucket(Bucket=bucket)
                elif provider == CloudProvider.GCP:
                    bucket_obj = client.bucket(bucket)
                    bucket_obj.delete()
                elif provider == CloudProvider.AZURE:
                    client.delete_container(bucket)

                self._buckets.pop(bucket, None)
                return True

            except Exception as e:
                logger.error(f"Error deleting bucket: {e}")
                return False

    async def get_signed_url(
        self,
        provider: CloudProvider,
        bucket: str,
        key: str,
        expires_in: int = 3600
    ) -> Optional[str]:
        result = await self.generate_presigned_url(
            provider=provider,
            bucket=bucket,
            key=key,
            method="GET",
            expires_in=expires_in
        )
        return result.url

    async def upload_large_file(
        self,
        provider: CloudProvider,
        bucket: str,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        part_size: int = 8 * 1024 * 1024
    ) -> CloudUpload:
        if len(data) <= part_size:
            return await self.upload_file(
                provider, bucket, key, data,
                content_type, metadata
            )

        if provider == CloudProvider.AWS:
            return await self._upload_large_aws(
                self._clients[provider], bucket, key,
                data, content_type, metadata, part_size
            )
        else:
            return await self.upload_file(
                provider, bucket, key, data,
                content_type, metadata
            )

    async def _upload_large_aws(
        self,
        client: Any,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Dict[str, str],
        part_size: int
    ) -> CloudUpload:
        extra_args = {'ContentType': content_type or 'application/octet-stream'}
        if metadata:
            extra_args['Metadata'] = metadata

        mpu = client.create_multipart_upload(
            Bucket=bucket,
            Key=key,
            **extra_args
        )

        upload_id = mpu['UploadId']
        parts = []
        part_number = 1
        offset = 0

        while offset < len(data):
            chunk = data[offset:offset + part_size]
            part = client.upload_part(
                Bucket=bucket,
                Key=key,
                PartNumber=part_number,
                UploadId=upload_id,
                Body=chunk
            )
            parts.append({
                'PartNumber': part_number,
                'ETag': part['ETag']
            })
            offset += part_size
            part_number += 1

        result = client.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts}
        )

        return CloudUpload(
            key=key,
            bucket=bucket,
            size=len(data),
            etag=result['ETag'].strip('"'),
            version_id=result.get('VersionId'),
            upload_id=upload_id,
            metadata=metadata or {},
            public_url=self._get_public_url_aws(bucket, key)
        )

    def _guess_content_type(self, key: str) -> str:
        ext = os.path.splitext(key)[1].lower()
        content_types = {
            '.txt': 'text/plain',
            '.csv': 'text/csv',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
            '.pdf': 'application/pdf',
            '.zip': 'application/zip',
            '.gz': 'application/gzip',
            '.tar': 'application/x-tar',
            '.mp3': 'audio/mpeg',
            '.mp4': 'video/mp4',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.wav': 'audio/wav',
            '.parquet': 'application/parquet',
            '.orc': 'application/orc',
            '.feather': 'application/feather',
            '.pickle': 'application/octet-stream',
            '.pkl': 'application/octet-stream',
            '.pt': 'application/octet-stream',
            '.pth': 'application/octet-stream',
            '.h5': 'application/octet-stream',
            '.hdf5': 'application/x-hdf5',
            '.onnx': 'application/onnx',
            '.tensorflow': 'application/tensorflow'
        }
        return content_types.get(ext, 'application/octet-stream')

    def _get_public_url_aws(self, bucket: str, key: str) -> str:
        region = self._credentials.get(CloudProvider.AWS, CloudCredentials(provider=CloudProvider.AWS)).region or 'us-east-1'
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

    def _get_public_url_gcp(self, bucket: str, key: str) -> str:
        return f"https://storage.googleapis.com/{bucket}/{key}"

    def _get_public_url_azure(self, bucket: str, key: str) -> str:
        account = self._credentials.get(CloudProvider.AZURE, CloudCredentials(provider=CloudProvider.AZURE)).account_name or ''
        return f"https://{account}.blob.core.windows.net/{bucket}/{key}"

    def get_cache_stats(self) -> Dict[str, Any]:
        return {
            "cache_size": len(self._cache),
            "cache_ttl": self._cache_ttl,
            "presigned_urls": len(self._presigned_urls),
            "multipart_uploads": len(self._multipart_uploads),
            "buckets": len(self._buckets),
            "clients": list(self._clients.keys())
        }

    async def clear_cache(self) -> None:
        self._cache.clear()
        self._presigned_urls.clear()

    async def get_object_metadata(
        self,
        provider: CloudProvider,
        bucket: str,
        key: str
    ) -> Optional[Dict[str, str]]:
        async with self._lock:
            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]

            try:
                if provider == CloudProvider.AWS:
                    response = client.head_object(Bucket=bucket, Key=key)
                    return response.get('Metadata', {})

                elif provider == CloudProvider.GCP:
                    bucket_obj = client.bucket(bucket)
                    blob = bucket_obj.blob(key)
                    blob.reload()
                    return blob.metadata or {}

                elif provider == CloudProvider.AZURE:
                    container_client = client.get_container_client(bucket)
                    blob_client = container_client.get_blob_client(key)
                    properties = blob_client.get_blob_properties()
                    return properties.metadata or {}

                return {}

            except Exception as e:
                logger.error(f"Error getting object metadata: {e}")
                return None

    async def set_object_metadata(
        self,
        provider: CloudProvider,
        bucket: str,
        key: str,
        metadata: Dict[str, str]
    ) -> bool:
        async with self._lock:
            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]

            try:
                if provider == CloudProvider.AWS:
                    client.copy_object(
                        Bucket=bucket,
                        Key=key,
                        CopySource={'Bucket': bucket, 'Key': key},
                        Metadata=metadata,
                        MetadataDirective='REPLACE'
                    )

                elif provider == CloudProvider.GCP:
                    bucket_obj = client.bucket(bucket)
                    blob = bucket_obj.blob(key)
                    blob.metadata = metadata
                    blob.patch()

                elif provider == CloudProvider.AZURE:
                    container_client = client.get_container_client(bucket)
                    blob_client = container_client.get_blob_client(key)
                    blob_client.set_blob_metadata(metadata)

                cache_key = f"{provider.value}:{bucket}:{key}"
                self._cache.pop(cache_key, None)
                return True

            except Exception as e:
                logger.error(f"Error setting object metadata: {e}")
                return False

    async def get_versioning_status(
        self,
        provider: CloudProvider,
        bucket: str
    ) -> Optional[bool]:
        async with self._lock:
            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]

            try:
                if provider == CloudProvider.AWS:
                    response = client.get_bucket_versioning(Bucket=bucket)
                    return response.get('Status') == 'Enabled'

                elif provider == CloudProvider.GCP:
                    bucket_obj = client.bucket(bucket)
                    versioning = bucket_obj.get_versioning()
                    return versioning.get('enabled') if versioning else False

                elif provider == CloudProvider.AZURE:
                    container_client = client.get_container_client(bucket)
                    properties = container_client.get_container_properties()
                    return properties.has_immutability_policy

                return False

            except Exception as e:
                logger.error(f"Error getting versioning status: {e}")
                return None

    async def enable_versioning(
        self,
        provider: CloudProvider,
        bucket: str
    ) -> bool:
        async with self._lock:
            if provider not in self._clients:
                raise ValueError(f"Provider {provider.value} not initialized")

            client = self._clients[provider]

            try:
                if provider == CloudProvider.AWS:
                    client.put_bucket_versioning(
                        Bucket=bucket,
                        VersioningConfiguration={'Status': 'Enabled'}
                    )

                elif provider == CloudProvider.GCP:
                    bucket_obj = client.bucket(bucket)
                    bucket_obj.versioning_enabled = True
                    bucket_obj.patch()

                elif provider == CloudProvider.AZURE:
                    raise NotImplementedError("Azure versioning not implemented via API")

                return True

            except Exception as e:
                logger.error(f"Error enabling versioning: {e}")
                return False

    async def get_presigned_url_info(self, url_key: str) -> Optional[CloudPresignedURL]:
        return self._presigned_urls.get(url_key)

    async def validate_presigned_url(self, url_key: str) -> bool:
        if url_key not in self._presigned_urls:
            return False
        presigned = self._presigned_urls[url_key]
        return presigned.expires_at > datetime.now()

    async def get_multipart_upload(
        self,
        upload_id: str
    ) -> Optional[CloudMultipartUpload]:
        return self._multipart_uploads.get(upload_id)

    async def list_multipart_uploads(
        self,
        provider: CloudProvider,
        bucket: str
    ) -> List[CloudMultipartUpload]:
        return [
            u for u in self._multipart_uploads.values()
            if u.bucket == bucket and u.provider == provider and not u.completed
        ]

    async def abort_multipart_upload(
        self,
        provider: CloudProvider,
        bucket: str,
        key: str,
        upload_id: str
    ) -> bool:
        if provider not in self._clients:
            raise ValueError(f"Provider {provider.value} not initialized")

        client = self._clients[provider]

        try:
            if provider == CloudProvider.AWS:
                client.abort_multipart_upload(
                    Bucket=bucket,
                    Key=key,
                    UploadId=upload_id
                )

            upload_key = f"{bucket}:{key}:{upload_id}"
            self._multipart_uploads.pop(upload_key, None)
            return True

        except Exception as e:
            logger.error(f"Error aborting multipart upload: {e}")
            return False


__all__ = [
    "CloudProvider",
    "CloudService",
    "CloudCredentials",
    "CloudObject",
    "CloudDownload",
    "CloudUpload",
    "CloudBucket",
    "CloudPresignedURL",
    "CloudMultipartUpload",
    "PublicCloudDataManager"
]
