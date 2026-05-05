"""Async Solana testnet client for audit hash anchoring.

This module owns all direct Solana RPC communication for the audit anchoring
subsystem. Anchoring is best-effort by design: failures are logged by callers
at the task layer and must never affect the main application request path.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional


DEFAULT_SOLANA_RPC_URL = 'https://api.testnet.solana.com'
DEFAULT_SOLANA_KEYPAIR_PATH = '~/.config/solana/testnet.json'
MEMO_PROGRAM_ID = 'MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr'

_CLIENT: Optional['SolanaClient'] = None
log = logging.getLogger(__name__)


def build_memo_string(
    event_type: str,
    key_field: str,
    sensitivity_level: int,
    event_hash: str,
) -> str:
    """
    Builds a human-readable memo string for the
    Solana transaction. Visible on Solana Explorer
    without exposing any PII or sensitive content.

    Format:
        {"app":"arkive","v":1,"type":"...","action":"...","sev":0,"hash":"..."}

    Examples:
        {"app":"arkive","v":1,"type":"policy_decision","action":"block","sev":2,"hash":"c824988b..."}
        {"app":"arkive","v":1,"type":"auth_event","action":"signin","sev":0,"hash":"25814cef..."}
        {"app":"arkive","v":1,"type":"file_upload","action":"pdf","sev":1,"hash":"78589c1f..."}

    Rules:
    - event_type: lowercase, underscores only
    - key_field: the single most meaningful
      non-sensitive descriptor for this event
      (decision value, action type, file type,
      model id, etc.) - never a user ID or hash
    - sensitivity_level: 0-3 integer
    - event_hash: full 64-char SHA-256 hex string

    Total memo length must stay under 566 bytes
    (Solana memo program limit).
    Truncate key_field to 32 chars if needed.
    """
    safe_key = str(key_field or 'unknown')[:32]
    safe_key = safe_key.replace(':', '-')
    memo = json.dumps(
        {
            'app': 'arkive',
            'v': 1,
            'type': event_type,
            'action': safe_key,
            'sev': sensitivity_level,
            'hash': event_hash,
        },
        sort_keys=True,
        separators=(',', ':'),
    )
    return memo


class SolanaClient:
    """Small async wrapper around Solana RPC memo transactions."""

    def __init__(self, rpc_url: str, keypair_path: str):
        self.rpc_url = rpc_url
        self.keypair_path = keypair_path

    def _load_keypair(self):
        from solders.keypair import Keypair

        path = Path(os.path.expanduser(self.keypair_path))
        with path.open('r', encoding='utf-8') as keypair_file:
            raw_keypair = json.load(keypair_file)

        if isinstance(raw_keypair, dict):
            raw_keypair = (
                raw_keypair.get('secretKey')
                or raw_keypair.get('secret_key')
                or raw_keypair.get('keypair')
                or raw_keypair.get('private_key')
            )

        if isinstance(raw_keypair, str):
            return Keypair.from_base58_string(raw_keypair)

        if not isinstance(raw_keypair, list):
            raise ValueError('Solana keypair file must contain a JSON array of secret key bytes or a base58 secret key')

        return Keypair.from_bytes(bytes(raw_keypair))

    async def anchor(
        self,
        hash_str: str,
        event_type: str = 'unknown',
        key_field: str = 'unknown',
        sensitivity_level: int = 0,
    ) -> str | None:
        """Submit a SHA-256 hash string as a Solana memo transaction."""
        try:
            from solana.rpc.async_api import AsyncClient
            from solana.rpc.types import TxOpts
            from solders.instruction import Instruction
            from solders.message import MessageV0
            from solders.pubkey import Pubkey
            from solders.transaction import VersionedTransaction

            payer = self._load_keypair()
            memo_text = build_memo_string(
                event_type=event_type,
                key_field=key_field,
                sensitivity_level=sensitivity_level,
                event_hash=hash_str,
            )
            memo_instruction = Instruction(
                Pubkey.from_string(MEMO_PROGRAM_ID),
                memo_text.encode('utf-8'),
                [],
            )

            async with AsyncClient(self.rpc_url) as rpc_client:
                latest_blockhash = await rpc_client.get_latest_blockhash()
                message = MessageV0.try_compile(
                    payer.pubkey(),
                    [memo_instruction],
                    [],
                    latest_blockhash.value.blockhash,
                )
                transaction = VersionedTransaction(message, [payer])
                response = await rpc_client.send_transaction(
                    transaction,
                    opts=TxOpts(
                        skip_preflight=False,
                        preflight_commitment='confirmed',
                        max_retries=3,
                    ),
                )

            signature = getattr(response, 'value', None)
            tx_id = str(signature) if signature else None
            if tx_id:
                log.info(
                    f'[solana_client] anchored '
                    f'memo={memo_text[:60]}... '
                    f'tx_id={tx_id}'
                )
            return tx_id
        except Exception:
            return None

    async def fetch_memo(self, tx_id: str) -> str | None:
        """
        Fetch the memo string stored in a confirmed transaction.
        Returns the memo text if found, None otherwise.
        Used by the audit viewer verify endpoint to confirm on-chain presence.
        """
        try:
            from solana.rpc.async_api import AsyncClient
            from solders.signature import Signature

            sig = Signature.from_string(tx_id)
            async with AsyncClient(self.rpc_url) as rpc_client:
                resp = await rpc_client.get_transaction(
                    sig,
                    encoding='json',
                    max_supported_transaction_version=0,
                )
            tx = getattr(resp, 'value', None)
            if not tx:
                return None
            meta = getattr(tx, 'transaction', None) or tx
            log_messages = (
                getattr(getattr(meta, 'meta', None), 'log_messages', None) or []
            )
            for line in log_messages:
                if 'Program log: Memo' in str(line):
                    return str(line).split('Memo (len', 1)[-1].split('): ', 1)[-1] if ': ' in str(line) else str(line)
            return tx_id
        except Exception as exc:
            log.warning(f'[solana_client] fetch_memo failed tx_id={tx_id}: {exc}')
            return None

    async def health_check(self) -> bool:
        """Return True when the configured Solana RPC endpoint is reachable."""
        try:
            from solana.rpc.async_api import AsyncClient

            async with AsyncClient(self.rpc_url) as rpc_client:
                if hasattr(rpc_client, 'get_health'):
                    response = await rpc_client.get_health()
                    value = getattr(response, 'value', None)
                    return value == 'ok' or value is True

                response = await rpc_client.get_latest_blockhash()
                return getattr(response, 'value', None) is not None
        except Exception:
            return False


def get_client() -> SolanaClient:
    """Return a module-level SolanaClient singleton configured from env."""
    global _CLIENT

    if _CLIENT is None:
        _CLIENT = SolanaClient(
            rpc_url=os.environ.get('SOLANA_RPC_URL', DEFAULT_SOLANA_RPC_URL),
            keypair_path=os.environ.get('SOLANA_KEYPAIR_PATH', DEFAULT_SOLANA_KEYPAIR_PATH),
        )

    return _CLIENT
