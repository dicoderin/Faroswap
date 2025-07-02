#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pharos Username Minter v7.4-fixed
Single-file release – kompatibel Web3.py v5 & v6
"""

import os
import sys
import json
import time
import math
import random
import string
import secrets
import logging
import traceback
import statistics
from uuid import uuid4

import requests
from hexbytes import HexBytes
from dotenv import load_dotenv
from eth_utils import keccak, to_bytes, to_checksum_address
from eth_abi import encode
from web3 import Web3
from web3.exceptions import ContractLogicError, TimeExhausted
from web3.middleware import geth_poa_middleware

# --------------------------------------------------------------------------- #
#                              Konfigurasi logging                            #
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("PharosMinter")

# --------------------------------------------------------------------------- #
#                           Muat variabel lingkungan                          #
# --------------------------------------------------------------------------- #
load_dotenv()

# --------------------------------------------------------------------------- #
#                                   ABI                                       #
# --------------------------------------------------------------------------- #
CONTRACT_ABI = json.loads("""[
  {"inputs":[{"internalType":"bytes32","name":"commitment","type":"bytes32"}],
   "name":"commit","outputs":[],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"internalType":"string","name":"name","type":"string"},
             {"internalType":"address","name":"owner","type":"address"},
             {"internalType":"bytes32","name":"secret","type":"bytes32"}],
   "name":"register","outputs":[],"stateMutability":"payable","type":"function"},
  {"inputs":[{"internalType":"string","name":"name","type":"string"}],
   "name":"available","outputs":[{"internalType":"bool","name":"","type":"bool"}],
   "stateMutability":"view","type":"function"},
  {"inputs":[],"name":"minCommitmentAge",
   "outputs":[{"internalType":"uint256","name":"","type":"uint256"}],
   "stateMutability":"view","type":"function"},
  {"inputs":[],"name":"mintingFee",
   "outputs":[{"internalType":"uint256","name":"","type":"uint256"}],
   "stateMutability":"view","type":"function"}
]""")

# --------------------------------------------------------------------------- #
#                        Fungsi bantuan versi Web3                            #
# --------------------------------------------------------------------------- #
def solidity_keccak(types, values):
    """
    Re-implementasi Web3.solidity_keccak yang hilang di Web3.py v6.
    """
    encoded = encode(types, values)
    return keccak(encoded)

def inject_middlewares(w3: Web3) -> None:
    """
    POA + retry + cache (jika tersedia pada versi Web3).
    """
    try:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        log.debug("POA middleware injected")
    except Exception:
        pass

    # retry middleware hanya ada di v6↑
    try:
        from web3.middleware import http_retry_request_middleware
        w3.middleware_onion.inject(http_retry_request_middleware, layer=0)
    except Exception:
        pass

# --------------------------------------------------------------------------- #
#                             Kelas utama minter                              #
# --------------------------------------------------------------------------- #
class PharosMinter:
    def __init__(self, private_key: str, user_agent: str | None = None):
        if not private_key or private_key == "0x" + "0" * 64:
            raise ValueError("Private-key tidak valid")

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent or self.random_ua(),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Request-ID": str(uuid4())
        })

        self.rpc_urls = [url for url in
                         [os.getenv("RPC_URL"),
                          os.getenv("RPC_URL_FALLBACK_1"),
                          os.getenv("RPC_URL_FALLBACK_2")]
                         if url]

        if not self.rpc_urls:
            self.rpc_urls = ["https://testnet.dplabs-internal.com"]

        self.w3 = self._connect_rpc(self.rpc_urls)
        self.account = self.w3.eth.account.from_key(private_key)

        self.contract_addr = to_checksum_address(
            os.getenv("CONTRACT_ADDRESS",
                      "0x51be1ef20a1fd5179419738fc71d95a8b6f8a175")
        )
        self.contract = self.w3.eth.contract(
            address=self.contract_addr, abi=CONTRACT_ABI
        )

        self.chain_id = int(os.getenv("CHAIN_ID", "688688"))

        # cache
        self.minting_fee = self._safe_call(
            lambda: self.contract.functions.mintingFee().call(),
            default=Web3.to_wei(0.01, "ether")
        )
        self.min_age = self._safe_call(
            lambda: self.contract.functions.minCommitmentAge().call(),
            default=60
        )

        self.gas_history: list[int] = []

    # ---------------------------- fungsi utilitas --------------------------- #
    def _connect_rpc(self, urls: list[str]) -> Web3:
        for url in urls:
            provider = Web3.HTTPProvider(url, request_kwargs={"timeout": 60})
            w3 = Web3(provider)
            inject_middlewares(w3)
            if w3.is_connected():
                log.info(f"Terhubung ke RPC {url}")
                return w3
            log.warning(f"Gagal konek {url}")
        raise ConnectionError("Semua RPC gagal dihubungi")

    @staticmethod
    def random_ua() -> str:
        ios = random.choice(["16_6", "17_0", "17_1"])
        ver = ios.replace("_", ".")
        return (f"Mozilla/5.0 (iPhone; CPU iPhone OS {ios} like Mac OS X) "
                f"AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{ver} "
                f"Mobile/15E148 Safari/604.1")

    @staticmethod
    def _safe_call(func, default=None, retries: int = 3):
        for _ in range(retries):
            try:
                return func()
            except Exception:
                time.sleep(1)
        return default

    # --------------------------- komponen keccak --------------------------- #
    @staticmethod
    def _gen_secret() -> bytes:
        return secrets.token_bytes(32)

    def _commit_hash(self, name: str, secret: bytes) -> bytes:
        namehash = solidity_keccak(["string"], [name])
        return solidity_keccak(["bytes32", "bytes32"], [namehash, secret])

    # --------------------------- gas helper ---------------------------------#
    def _current_gas(self) -> int:
        gp = self._safe_call(lambda: self.w3.eth.gas_price,
                             default=Web3.to_wei(20, "gwei"))
        self.gas_history.append(gp)
        self.gas_history = self.gas_history[-5:]
        median = statistics.median(self.gas_history)
        return int(median * random.uniform(1.1, 1.3))

    # ------------------------------ logic -----------------------------------#
    def is_available(self, domain: str) -> bool:
        return self._safe_call(
            lambda: self.contract.functions.available(domain).call(),
            default=False
        )

    def _build_send(self, tx_dict: dict, label: str) -> HexBytes | None:
        signed = self.account.sign_transaction(tx_dict)
        try:
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            log.info(f"{label} tx sent → {tx_hash.hex()}")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            if receipt.status == 1:
                log.info(f"{label} sukses ✅")
            else:
                log.error(f"{label} gagal ❌ (status 0)")
            return tx_hash
        except Exception as e:
            log.error(f"{label} error: {e}")
            return None

    # ------------------------ proses mint 2-langkah -------------------------#
    def mint(self, attempts: int = 7):
        for _ in range(attempts):
            name = ''.join(random.choice(string.ascii_lowercase)
                           for _ in range(random.randint(5, 8)))
            domain = f"{name}.phrs"
            if not self.is_available(domain):
                log.debug(f"{domain} sudah terpakai")
                continue

            log.info(f"Mencoba {domain}")

            # 1. Commit
            secret = self._gen_secret()
            commitment = self._commit_hash(domain, secret)

            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self._current_gas()
            commit_tx = self.contract.functions.commit(commitment).build_transaction({
                "chainId": self.chain_id,
                "from": self.account.address,
                "nonce": nonce,
                "gas": 200_000,
                "gasPrice": gas_price
            })

            if not self._build_send(commit_tx, "Commit"):
                continue

            # tunggu minCommitmentAge + margin 15 s
            wait_sec = max(self.min_age, 60) + 15
            log.info(f"Tunggu {wait_sec}s agar commitment matang…")
            time.sleep(wait_sec)

            if not self.is_available(domain):
                log.warning(f"{domain} direbut orang 🤷🏻‍♂️")
                continue

            # 2. Register
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self._current_gas()
            reg_tx = self.contract.functions.register(
                domain, self.account.address, secret
            ).build_transaction({
                "chainId": self.chain_id,
                "from": self.account.address,
                "nonce": nonce,
                "value": self.minting_fee,
                "gas": 600_000,
                "gasPrice": gas_price
            })

            tx_hash = self._build_send(reg_tx, "Register")
            if tx_hash:
                return {
                    "status": "success",
                    "domain": domain,
                    "tx": tx_hash.hex()
                }
        return {"status": "failed", "reason": "tidak ada nama tersedia"}

# --------------------------------------------------------------------------- #
#                                 util env                                    #
# --------------------------------------------------------------------------- #
def load_accounts() -> list[dict]:
    accs = []
    for idx in (1, 2):
        pk = os.getenv(f"PRIVATE_KEY_{idx}")
        if pk and pk != "0x" + "0" * 64:
            accs.append({
                "pk": pk,
                "ua": os.getenv(f"USER_AGENT_{idx}", None),
                "label": f"Akun {idx}"
            })
    if not accs:
        raise ValueError("PRIVATE_KEY_1 belum di-set di .env")
    return accs

# --------------------------------------------------------------------------- #
#                                    main                                     #
# --------------------------------------------------------------------------- #
def main():
    print(r"""
██████╗ ██╗  ██╗ █████╗ ██████╗  ██████╗ ███████╗
██╔══██╗██║  ██║██╔══██╗██╔══██╗██╔═══██╗██╔════╝
██████╔╝███████║███████║██████╔╝██║   ██║███████╗
██╔═══╝ ██╔══██║██╔══██║██╔══██╗██║   ██║╚════██║
██║     ██║  ██║██║  ██║██║  ██║╚██████╔╝███████║
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
""")
    log.info(f"Python {sys.version.split()[0]} | Web3 {Web3.__version__}")

    try:
        accounts = load_accounts()
    except ValueError as e:
        log.error(e)
        sys.exit(1)

    for acc in accounts:
        print("\n" + "-" * 60)
        log.info(f"Memproses {acc['label']}")
        try:
            minter = PharosMinter(acc["pk"], acc["ua"])
            balance = Web3.from_wei(minter.w3.eth.get_balance(minter.account.address),
                                    "ether")
            log.info(f"Alamat  : {minter.account.address}")
            log.info(f"Saldo   : {balance:.4f} PHRS")
            log.info(f"Fee mint: {Web3.from_wei(minter.minting_fee, 'ether')} PHRS")

            if balance < Web3.from_wei(minter.minting_fee, 'ether'):
                log.error("Saldo kurang ❌")
                continue

            res = minter.mint()
            if res["status"] == "success":
                log.info(f"🎉  {res['domain']} berhasil!")
                log.info(f"Tx: {os.getenv('EXPLORER_BASE_URL','https://testnet.pharosscan.xyz/tx/')}{res['tx']}")
            else:
                log.error("Mint gagal : " + res.get("reason", "unknown"))

        except Exception as ex:
            log.error(f"Error fatal akun {acc['label']}: {ex}")
            traceback.print_exc()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.warning("Dibatalkan user")