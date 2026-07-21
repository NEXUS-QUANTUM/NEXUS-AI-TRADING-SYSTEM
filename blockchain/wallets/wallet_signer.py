"""
NEXUS AI TRADING SYSTEM - WALLET SIGNER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de signature de transactions pour wallets multi-blockchain.
Support des signatures ECDSA, Ed25519, et multi-signatures.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import base64
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import coincurve
import ed25519
from eth_account import Account
from eth_account.messages import encode_defunct, encode_typed_data
from web3 import Web3
from web3.auto import w3
from eth_utils import keccak as eth_keccak
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.message import Message
from solders.transaction import Transaction
from solders.instruction import Instruction, AccountMeta
from solders.system_program import transfer, TransferParams
from solders.hash import Hash
from solders.signature import Signature
from solana.rpc.types import TxOpts

from .base_wallet import (
    BaseWallet,
    WalletConfig,
    WalletBalance,
    Transaction as WalletTransaction,
    TransactionType,
    TransactionStatus,
    BlockchainNetwork,
    WalletStatus,
    WalletType
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class SignatureType(Enum):
    """Types de signature."""
    ECDSA = "ecdsa"
    ECDSA_RECOVERABLE = "ecdsa_recoverable"
    ED25519 = "ed25519"
    SECP256K1 = "secp256k1"
    ETHEREUM = "ethereum"
    SOLANA = "solana"
    TRON = "tron"


class SigningStatus(Enum):
    """Statuts de signature."""
    PENDING = "pending"
    SIGNED = "signed"
    VERIFIED = "verified"
    FAILED = "failed"
    REJECTED = "rejected"
    MULTISIG_PENDING = "multisig_pending"
    MULTISIG_COMPLETE = "multisig_complete"


@dataclass
class SigningRequest:
    """Requête de signature."""
    request_id: UUID
    wallet_id: UUID
    user_id: UUID
    message: Union[str, bytes]
    signature_type: SignatureType
    chain: str
    network: str
    status: SigningStatus = SigningStatus.PENDING
    signature: Optional[str] = None
    signer_address: Optional[str] = None
    required_signers: int = 1
    current_signers: List[str] = field(default_factory=list)
    multisig_addresses: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "request_id": str(self.request_id),
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "message": self.message if isinstance(self.message, str) else base64.b64encode(self.message).decode('utf-8'),
            "signature_type": self.signature_type.value,
            "chain": self.chain,
            "network": self.network,
            "status": self.status.value,
            "signature": self.signature,
            "signer_address": self.signer_address,
            "required_signers": self.required_signers,
            "current_signers": self.current_signers,
            "multisig_addresses": self.multisig_addresses,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "error_message": self.error_message
        }


@dataclass
class SignedTransaction:
    """Transaction signée."""
    tx_hash: str
    wallet_id: UUID
    user_id: UUID
    chain: str
    network: str
    raw_transaction: str
    signed_transaction: str
    signature: str
    signer_address: str
    signature_type: SignatureType
    status: TransactionStatus = TransactionStatus.PENDING
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    gas_price: Optional[Decimal] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    broadcasted_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "tx_hash": self.tx_hash,
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "chain": self.chain,
            "network": self.network,
            "raw_transaction": self.raw_transaction,
            "signed_transaction": self.signed_transaction,
            "signature": self.signature,
            "signer_address": self.signer_address,
            "signature_type": self.signature_type.value,
            "status": self.status.value,
            "block_number": self.block_number,
            "gas_used": self.gas_used,
            "gas_price": str(self.gas_price) if self.gas_price else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "broadcasted_at": self.broadcasted_at.isoformat() if self.broadcasted_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None
        }


# ============================================================================
# CLASSE WALLET SIGNER
# ============================================================================

class WalletSigner:
    """
    Service de signature de transactions multi-blockchain.
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le service de signature.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        
        # Cache
        self._signing_requests: Dict[UUID, SigningRequest] = {}
        self._signed_transactions: Dict[str, SignedTransaction] = {}
        self._multisig_requests: Dict[UUID, Dict] = {}
        
        # Métriques
        self._metrics = {
            "total_requests": 0,
            "total_signatures": 0,
            "total_verified": 0,
            "total_failed": 0,
            "total_multisig": 0,
            "by_chain": {},
            "by_type": {},
            "last_signature": None
        }

        logger.info("WalletSigner initialisé avec succès")

    # ========================================================================
    # SIGNATURE DE MESSAGES
    # ========================================================================

    async def sign_message(
        self,
        wallet: BaseWallet,
        message: Union[str, bytes],
        signer_address: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> SigningRequest:
        """
        Signe un message avec un wallet.

        Args:
            wallet: Wallet
            message: Message à signer
            signer_address: Adresse du signataire (optionnel)
            metadata: Métadonnées

        Returns:
            Requête de signature
        """
        try:
            request_id = uuid4()
            chain = wallet.config.blockchain.lower()
            
            # Détermination du type de signature
            signature_type = self._get_signature_type(chain)
            
            # Création de la requête
            request = SigningRequest(
                request_id=request_id,
                wallet_id=wallet.config.wallet_id,
                user_id=wallet.config.user_id,
                message=message,
                signature_type=signature_type,
                chain=chain,
                network=wallet.config.network.value if hasattr(wallet.config.network, 'value') else str(wallet.config.network),
                signer_address=signer_address or wallet.config.address,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=30),
                metadata=metadata or {}
            )

            # Vérification de la clé privée
            if not wallet.config.private_key_encrypted:
                request.status = SigningStatus.FAILED
                request.error_message = "Aucune clé privée disponible"
                self._signing_requests[request_id] = request
                return request

            # Signature du message
            try:
                if chain in ["ethereum", "bsc", "polygon", "avalanche", "arbitrum", "optimism"]:
                    signature = await self._sign_ethereum_message(
                        wallet.config.private_key_encrypted,
                        message
                    )
                elif chain == "solana":
                    signature = await self._sign_solana_message(
                        wallet.config.private_key_encrypted,
                        message
                    )
                elif chain == "tron":
                    signature = await self._sign_tron_message(
                        wallet.config.private_key_encrypted,
                        message
                    )
                else:
                    raise ValueError(f"Blockchain non supportée: {chain}")

                request.signature = signature
                request.status = SigningStatus.SIGNED
                request.completed_at = datetime.now()

                # Vérification de la signature
                verified = await self.verify_signature(
                    message,
                    signature,
                    request.signer_address,
                    chain
                )

                if verified:
                    request.status = SigningStatus.VERIFIED

                # Mise à jour des métriques
                self._metrics["total_requests"] += 1
                self._metrics["total_signatures"] += 1
                if verified:
                    self._metrics["total_verified"] += 1
                else:
                    self._metrics["total_failed"] += 1
                self._metrics["last_signature"] = datetime.now().isoformat()

            except Exception as e:
                request.status = SigningStatus.FAILED
                request.error_message = str(e)
                self._metrics["total_failed"] += 1

            self._signing_requests[request_id] = request

            # Sauvegarde dans Redis
            if self.redis:
                key = f"signer:request:{request_id}"
                await self.redis.setex(
                    key,
                    3600,  # 1 heure
                    json.dumps(request.to_dict())
                )

            return request

        except Exception as e:
            logger.error(f"Erreur lors de la signature du message: {e}")
            raise

    async def _sign_ethereum_message(
        self,
        private_key: str,
        message: Union[str, bytes]
    ) -> str:
        """
        Signe un message avec Ethereum.

        Args:
            private_key: Clé privée
            message: Message à signer

        Returns:
            Signature
        """
        try:
            if isinstance(message, str):
                message_bytes = message.encode('utf-8')
            else:
                message_bytes = message

            # Création du message signable
            msg_hash = encode_defunct(message_bytes)
            
            # Signature
            account = Account.from_key(private_key)
            signed = account.sign_message(msg_hash)
            
            return signed.signature.hex()

        except Exception as e:
            logger.error(f"Erreur lors de la signature Ethereum: {e}")
            raise

    async def _sign_solana_message(
        self,
        private_key: str,
        message: Union[str, bytes]
    ) -> str:
        """
        Signe un message avec Solana.

        Args:
            private_key: Clé privée
            message: Message à signer

        Returns:
            Signature
        """
        try:
            # Conversion de la clé privée
            private_key_bytes = base58.b58decode(private_key)
            keypair = Keypair.from_bytes(private_key_bytes)
            
            if isinstance(message, str):
                message_bytes = message.encode('utf-8')
            else:
                message_bytes = message

            # Signature avec Ed25519
            signature = keypair.sign_message(message_bytes)
            
            return base58.b58encode(signature).decode('utf-8')

        except Exception as e:
            logger.error(f"Erreur lors de la signature Solana: {e}")
            raise

    async def _sign_tron_message(
        self,
        private_key: str,
        message: Union[str, bytes]
    ) -> str:
        """
        Signe un message avec Tron.

        Args:
            private_key: Clé privée
            message: Message à signer

        Returns:
            Signature
        """
        try:
            from tronpy.keys import PrivateKey
            
            if isinstance(message, str):
                message_bytes = message.encode('utf-8')
            else:
                message_bytes = message

            # Signature avec Tron
            key = PrivateKey.fromhex(private_key)
            signature = key.sign_message(message_bytes)
            
            return signature.hex()

        except Exception as e:
            logger.error(f"Erreur lors de la signature Tron: {e}")
            raise

    # ========================================================================
    # VÉRIFICATION DE SIGNATURES
    # ========================================================================

    async def verify_signature(
        self,
        message: Union[str, bytes],
        signature: str,
        address: str,
        chain: str
    ) -> bool:
        """
        Vérifie une signature.

        Args:
            message: Message signé
            signature: Signature
            address: Adresse du signataire
            chain: Blockchain

        Returns:
            True si la signature est valide
        """
        try:
            if chain in ["ethereum", "bsc", "polygon", "avalanche", "arbitrum", "optimism"]:
                return await self._verify_ethereum_signature(
                    message, signature, address
                )
            elif chain == "solana":
                return await self._verify_solana_signature(
                    message, signature, address
                )
            elif chain == "tron":
                return await self._verify_tron_signature(
                    message, signature, address
                )
            else:
                logger.warning(f"Vérification non supportée pour {chain}")
                return False

        except Exception as e:
            logger.error(f"Erreur lors de la vérification de la signature: {e}")
            return False

    async def _verify_ethereum_signature(
        self,
        message: Union[str, bytes],
        signature: str,
        address: str
    ) -> bool:
        """
        Vérifie une signature Ethereum.

        Args:
            message: Message signé
            signature: Signature
            address: Adresse du signataire

        Returns:
            True si la signature est valide
        """
        try:
            if isinstance(message, str):
                message_bytes = message.encode('utf-8')
            else:
                message_bytes = message

            msg_hash = encode_defunct(message_bytes)
            recovered_address = Account.recover_message(msg_hash, signature=signature)
            
            return recovered_address.lower() == address.lower()

        except Exception as e:
            logger.error(f"Erreur lors de la vérification Ethereum: {e}")
            return False

    async def _verify_solana_signature(
        self,
        message: Union[str, bytes],
        signature: str,
        address: str
    ) -> bool:
        """
        Vérifie une signature Solana.

        Args:
            message: Message signé
            signature: Signature
            address: Adresse du signataire

        Returns:
            True si la signature est valide
        """
        try:
            pubkey = Pubkey.from_string(address)
            signature_bytes = base58.b58decode(signature)
            
            if isinstance(message, str):
                message_bytes = message.encode('utf-8')
            else:
                message_bytes = message

            # Vérification avec Ed25519
            return ed25519.verify(pubkey.to_bytes(), message_bytes, signature_bytes)

        except Exception as e:
            logger.error(f"Erreur lors de la vérification Solana: {e}")
            return False

    async def _verify_tron_signature(
        self,
        message: Union[str, bytes],
        signature: str,
        address: str
    ) -> bool:
        """
        Vérifie une signature Tron.

        Args:
            message: Message signé
            signature: Signature
            address: Adresse du signataire

        Returns:
            True si la signature est valide
        """
        try:
            from tronpy.keys import PrivateKey
            
            if isinstance(message, str):
                message_bytes = message.encode('utf-8')
            else:
                message_bytes = message

            # Vérification avec Tron
            signature_bytes = bytes.fromhex(signature)
            public_key = PrivateKey.recover(signature_bytes, message_bytes)
            derived_address = public_key.to_base58check_address()
            
            return derived_address == address

        except Exception as e:
            logger.error(f"Erreur lors de la vérification Tron: {e}")
            return False

    # ========================================================================
    # SIGNATURE DE TRANSACTIONS
    # ========================================================================

    async def sign_transaction(
        self,
        wallet: BaseWallet,
        transaction: WalletTransaction,
        signer_address: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> SignedTransaction:
        """
        Signe une transaction.

        Args:
            wallet: Wallet
            transaction: Transaction à signer
            signer_address: Adresse du signataire (optionnel)
            metadata: Métadonnées

        Returns:
            Transaction signée
        """
        try:
            chain = wallet.config.blockchain.lower()
            signature_type = self._get_signature_type(chain)
            
            # Construction de la transaction brute
            raw_tx = await self._build_raw_transaction(
                wallet,
                transaction,
                signer_address or wallet.config.address
            )
            
            # Signature de la transaction
            if chain in ["ethereum", "bsc", "polygon", "avalanche", "arbitrum", "optimism"]:
                signed_tx = await self._sign_ethereum_transaction(
                    wallet.config.private_key_encrypted,
                    raw_tx
                )
                signature = signed_tx.get("signature", "")
                signed_raw = signed_tx.get("signed_transaction", "")
                tx_hash = signed_tx.get("tx_hash", "")
                
            elif chain == "solana":
                signed_tx = await self._sign_solana_transaction(
                    wallet.config.private_key_encrypted,
                    raw_tx
                )
                signature = signed_tx.get("signature", "")
                signed_raw = signed_tx.get("signed_transaction", "")
                tx_hash = signed_tx.get("tx_hash", "")
                
            elif chain == "tron":
                signed_tx = await self._sign_tron_transaction(
                    wallet.config.private_key_encrypted,
                    raw_tx
                )
                signature = signed_tx.get("signature", "")
                signed_raw = signed_tx.get("signed_transaction", "")
                tx_hash = signed_tx.get("tx_hash", "")
                
            else:
                raise ValueError(f"Blockchain non supportée: {chain}")

            # Création de l'objet SignedTransaction
            signed = SignedTransaction(
                tx_hash=tx_hash,
                wallet_id=wallet.config.wallet_id,
                user_id=wallet.config.user_id,
                chain=chain,
                network=wallet.config.network.value if hasattr(wallet.config.network, 'value') else str(wallet.config.network),
                raw_transaction=raw_tx,
                signed_transaction=signed_raw,
                signature=signature,
                signer_address=signer_address or wallet.config.address,
                signature_type=signature_type,
                status=TransactionStatus.PENDING,
                metadata=metadata or {}
            )

            # Stockage
            self._signed_transactions[tx_hash] = signed
            
            # Mise à jour des métriques
            self._metrics["total_signatures"] += 1
            
            if chain not in self._metrics["by_chain"]:
                self._metrics["by_chain"][chain] = 0
            self._metrics["by_chain"][chain] += 1

            return signed

        except Exception as e:
            logger.error(f"Erreur lors de la signature de la transaction: {e}")
            raise

    async def _build_raw_transaction(
        self,
        wallet: BaseWallet,
        transaction: WalletTransaction,
        signer_address: str
    ) -> str:
        """
        Construit une transaction brute.

        Args:
            wallet: Wallet
            transaction: Transaction
            signer_address: Adresse du signataire

        Returns:
            Transaction brute
        """
        # Implémentation dépend de la blockchain
        # Pour l'exemple, on retourne un JSON simplifié
        return json.dumps({
            "from": signer_address,
            "to": transaction.to_address,
            "value": str(transaction.amount),
            "data": transaction.metadata.get("data", "0x"),
            "gas": transaction.metadata.get("gas", 21000),
            "gasPrice": str(transaction.metadata.get("gas_price", 0)),
            "nonce": transaction.metadata.get("nonce", 0)
        })

    async def _sign_ethereum_transaction(
        self,
        private_key: str,
        raw_transaction: str
    ) -> Dict[str, Any]:
        """
        Signe une transaction Ethereum.

        Args:
            private_key: Clé privée
            raw_transaction: Transaction brute

        Returns:
            Transaction signée
        """
        try:
            # Pour l'exemple, on utilise une signature simulée
            tx_data = json.loads(raw_transaction)
            account = Account.from_key(private_key)
            
            # Construction de la transaction
            tx = {
                'nonce': tx_data.get('nonce', 0),
                'to': tx_data['to'],
                'value': int(tx_data.get('value', 0)),
                'gas': tx_data.get('gas', 21000),
                'gasPrice': int(tx_data.get('gasPrice', 0)),
                'data': tx_data.get('data', '0x'),
                'chainId': 1
            }
            
            # Signature
            signed = account.sign_transaction(tx)
            
            return {
                "signature": signed.signature.hex(),
                "signed_transaction": signed.rawTransaction.hex(),
                "tx_hash": signed.hash.hex()
            }

        except Exception as e:
            logger.error(f"Erreur lors de la signature Ethereum: {e}")
            raise

    async def _sign_solana_transaction(
        self,
        private_key: str,
        raw_transaction: str
    ) -> Dict[str, Any]:
        """
        Signe une transaction Solana.

        Args:
            private_key: Clé privée
            raw_transaction: Transaction brute

        Returns:
            Transaction signée
        """
        try:
            # Pour l'exemple, on utilise une signature simulée
            private_key_bytes = base58.b58decode(private_key)
            keypair = Keypair.from_bytes(private_key_bytes)
            
            tx_data = json.loads(raw_transaction)
            
            # Construction de la transaction simplifiée
            # Note: En production, utiliser solana.rpc
            tx_hash = hashlib.sha256(private_key_bytes).hexdigest()[:32]
            signature = keypair.sign_message(tx_hash.encode())
            
            return {
                "signature": base58.b58encode(signature).decode('utf-8'),
                "signed_transaction": raw_transaction,  # Simplifié
                "tx_hash": tx_hash
            }

        except Exception as e:
            logger.error(f"Erreur lors de la signature Solana: {e}")
            raise

    async def _sign_tron_transaction(
        self,
        private_key: str,
        raw_transaction: str
    ) -> Dict[str, Any]:
        """
        Signe une transaction Tron.

        Args:
            private_key: Clé privée
            raw_transaction: Transaction brute

        Returns:
            Transaction signée
        """
        try:
            from tronpy.keys import PrivateKey
            
            tx_data = json.loads(raw_transaction)
            key = PrivateKey.fromhex(private_key)
            
            # Signature de la transaction
            # Note: En production, utiliser tronpy
            tx_hash = hashlib.sha256(private_key.encode()).hexdigest()
            signature = key.sign_message(tx_hash.encode())
            
            return {
                "signature": signature.hex(),
                "signed_transaction": raw_transaction,  # Simplifié
                "tx_hash": tx_hash
            }

        except Exception as e:
            logger.error(f"Erreur lors de la signature Tron: {e}")
            raise

    # ========================================================================
    # MULTI-SIGNATURE
    # ========================================================================

    async def create_multisig_request(
        self,
        wallet_id: UUID,
        user_id: UUID,
        message: Union[str, bytes],
        signers: List[str],
        required_signers: int,
        metadata: Optional[Dict] = None
    ) -> SigningRequest:
        """
        Crée une requête multi-signature.

        Args:
            wallet_id: ID du wallet
            user_id: ID de l'utilisateur
            message: Message à signer
            signers: Liste des signataires
            required_signers: Nombre de signataires requis
            metadata: Métadonnées

        Returns:
            Requête de signature
        """
        try:
            request_id = uuid4()
            
            request = SigningRequest(
                request_id=request_id,
                wallet_id=wallet_id,
                user_id=user_id,
                message=message,
                signature_type=SignatureType.ECDSA,
                chain="ethereum",  # Par défaut
                network="mainnet",
                required_signers=required_signers,
                multisig_addresses=signers,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=24),
                metadata=metadata or {}
            )
            
            self._multisig_requests[request_id] = request

            # Sauvegarde dans Redis
            if self.redis:
                key = f"signer:multisig:{request_id}"
                await self.redis.setex(
                    key,
                    86400,  # 24 heures
                    json.dumps(request.to_dict())
                )

            return request

        except Exception as e:
            logger.error(f"Erreur lors de la création de la requête multi-signature: {e}")
            raise

    async def add_multisig_signature(
        self,
        request_id: UUID,
        signature: str,
        signer_address: str
    ) -> bool:
        """
        Ajoute une signature à une requête multi-signature.

        Args:
            request_id: ID de la requête
            signature: Signature
            signer_address: Adresse du signataire

        Returns:
            True si la signature a été ajoutée
        """
        try:
            request = self._multisig_requests.get(request_id)
            if not request:
                if self.redis:
                    key = f"signer:multisig:{request_id}"
                    data = await self.redis.get(key)
                    if data:
                        request_dict = json.loads(data)
                        request = SigningRequest(**request_dict)
                        self._multisig_requests[request_id] = request

            if not request:
                return False

            # Vérification du signataire
            if signer_address not in request.multisig_addresses:
                return False

            # Vérification si déjà signé
            if signer_address in request.current_signers:
                return False

            # Ajout de la signature
            request.current_signers.append(signer_address)

            # Vérification si le seuil est atteint
            if len(request.current_signers) >= request.required_signers:
                request.status = SigningStatus.MULTISIG_COMPLETE
                request.completed_at = datetime.now()
                self._metrics["total_multisig"] += 1

            # Sauvegarde
            if self.redis:
                key = f"signer:multisig:{request_id}"
                await self.redis.setex(
                    key,
                    86400,
                    json.dumps(request.to_dict())
                )

            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de la signature multi-signature: {e}")
            return False

    # ========================================================================
    # MÉTHODES UTILITAIRES
    # ========================================================================

    def _get_signature_type(self, chain: str) -> SignatureType:
        """
        Récupère le type de signature pour une blockchain.

        Args:
            chain: Blockchain

        Returns:
            Type de signature
        """
        type_map = {
            "ethereum": SignatureType.ETHEREUM,
            "bsc": SignatureType.ETHEREUM,
            "polygon": SignatureType.ETHEREUM,
            "avalanche": SignatureType.ETHEREUM,
            "arbitrum": SignatureType.ETHEREUM,
            "optimism": SignatureType.ETHEREUM,
            "solana": SignatureType.SOLANA,
            "tron": SignatureType.TRON,
            "bitcoin": SignatureType.ECDSA
        }
        return type_map.get(chain, SignatureType.ECDSA)

    # ========================================================================
    # RÉCUPÉRATION DES SIGNATURES
    # ========================================================================

    async def get_signing_request(
        self,
        request_id: UUID
    ) -> Optional[SigningRequest]:
        """
        Récupère une requête de signature.

        Args:
            request_id: ID de la requête

        Returns:
            Requête de signature ou None
        """
        try:
            # Vérification du cache
            if request_id in self._signing_requests:
                return self._signing_requests[request_id]

            # Récupération depuis Redis
            if self.redis:
                key = f"signer:request:{request_id}"
                data = await self.redis.get(key)
                if data:
                    request_dict = json.loads(data)
                    # Conversion des champs spéciaux
                    request_dict["signature_type"] = SignatureType(request_dict["signature_type"])
                    request_dict["status"] = SigningStatus(request_dict["status"])
                    request = SigningRequest(**request_dict)
                    self._signing_requests[request_id] = request
                    return request

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la requête de signature: {e}")
            return None

    async def get_signed_transaction(
        self,
        tx_hash: str
    ) -> Optional[SignedTransaction]:
        """
        Récupère une transaction signée.

        Args:
            tx_hash: Hash de la transaction

        Returns:
            Transaction signée ou None
        """
        return self._signed_transactions.get(tx_hash)

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_requests": self._metrics["total_requests"],
                "total_signatures": self._metrics["total_signatures"],
                "total_verified": self._metrics["total_verified"],
                "total_failed": self._metrics["total_failed"],
                "total_multisig": self._metrics["total_multisig"],
                "by_chain": self._metrics["by_chain"],
                "by_type": self._metrics["by_type"],
                "last_signature": self._metrics["last_signature"],
                "pending_requests": len([r for r in self._signing_requests.values() if r.status == SigningStatus.PENDING]),
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
        logger.info("Fermeture de WalletSigner...")
        self._signing_requests.clear()
        self._signed_transactions.clear()
        self._multisig_requests.clear()
        logger.info("WalletSigner fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_wallet_signer(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None
) -> WalletSigner:
    """
    Crée une instance du service de signature.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API

    Returns:
        Instance du service
    """
    import redis.asyncio as redis
    import base58
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return WalletSigner(
        redis_client=redis_client,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "SignatureType",
    "SigningStatus",
    "SigningRequest",
    "SignedTransaction",
    "WalletSigner",
    "create_wallet_signer"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du service de signature."""
    print("=" * 60)
    print("NEXUS AI TRADING - WALLET SIGNER MODULE")
    print("=" * 60)

    # Création du service
    signer = create_wallet_signer()

    # Création d'un wallet exemple
    from .ethereum_wallet import create_ethereum_wallet
    from uuid import UUID
    
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    wallet = create_ethereum_wallet(
        user_id=user_id,
        name="Signer Wallet"
    )
    
    await wallet.initialize()

    print(f"\n✅ Wallet créé:")
    print(f"   Adresse: {wallet.config.address}")

    # Signature d'un message
    message = "Hello NEXUS AI Trading!"
    request = await signer.sign_message(wallet, message)
    print(f"\n✍️ Signature du message:")
    print(f"   Request ID: {request.request_id}")
    print(f"   Status: {request.status.value}")
    print(f"   Signature: {request.signature[:32] if request.signature else 'N/A'}...")
    print(f"   Vérifié: {request.status == SigningStatus.VERIFIED}")

    # Vérification de la signature
    if request.signature:
        verified = await signer.verify_signature(
            message,
            request.signature,
            wallet.config.address,
            "ethereum"
        )
        print(f"\n✅ Vérification de la signature: {verified}")

    # Signature d'une transaction
    from .base_wallet import Transaction, TransactionType, TransactionStatus
    
    tx = Transaction(
        tx_id=uuid4(),
        wallet_id=wallet.config.wallet_id,
        user_id=user_id,
        blockchain="ethereum",
        network=BlockchainNetwork.ETHEREUM_MAINNET,
        tx_type=TransactionType.SEND,
        from_address=wallet.config.address,
        to_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        amount=Decimal("0.1"),
        amount_usd=Decimal("30"),
        status=TransactionStatus.PENDING
    )
    
    signed_tx = await signer.sign_transaction(wallet, tx)
    print(f"\n📝 Transaction signée:")
    print(f"   TX Hash: {signed_tx.tx_hash[:16]}...")
    print(f"   Signature: {signed_tx.signature[:32]}...")
    print(f"   Statut: {signed_tx.status.value}")

    # Santé du service
    health = await signer.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Requêtes: {health['total_requests']}")
    print(f"   Signatures: {health['total_signatures']}")
    print(f"   Vérifiées: {health['total_verified']}")

    # Fermeture
    await signer.close()
    await wallet.close()

    print("\n" + "=" * 60)
    print("WalletSigner NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import base58
    import secrets
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
