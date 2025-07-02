#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pharos Username Minter v7.4
Professional Enhanced Version with Robust Error Handling
"""

import os
import json
import random
import string
import time
import requests
import sys
import web3
from web3 import Web3
from web3.exceptions import ContractLogicError, TimeExhausted
from dotenv import load_dotenv
from uuid import uuid4
import secrets
import statistics
import logging
import traceback
from hexbytes import HexBytes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("PharosMinter")

# Load environment variables
load_dotenv()

# CONTRACT ABI
CONTRACT_ABI = json.loads('''
[
    {
        "inputs": [
            {"internalType": "bytes32", "name": "commitment", "type": "bytes32"}
        ],
        "name": "commit",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "string", "name": "name", "type": "string"},
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "bytes32", "name": "secret", "type": "bytes32"}
        ],
        "name": "register",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "string", "name": "name", "type": "string"}
        ],
        "name": "available",
        "outputs": [
            {"internalType": "bool", "name": "", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "minCommitmentAge",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "mintingFee",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]
''')

def inject_poa_middleware(w3):
    """Inject POA middleware with compatibility for different Web3.py versions"""
    middleware_injected = False
    
    try:
        from web3.middleware import ExtraDataToPOAMiddleware
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        print("✅ POA middleware injected (ExtraDataToPOAMiddleware)")
        middleware_injected = True
    except ImportError:
        try:
            from web3.middleware import geth_poa_middleware
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            print("✅ POA middleware injected (geth_poa_middleware)")
            middleware_injected = True
        except ImportError:
            try:
                from web3.middleware.geth_poa import geth_poa_middleware
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                print("✅ POA middleware injected (legacy geth_poa)")
                middleware_injected = True
            except ImportError:
                pass

    if not middleware_injected:
        print("⚠️ Using no POA middleware (may work for some networks)")

    return True

def print_banner():
    """Print banner application"""
    print(r"""
██████╗ ██╗  ██╗ █████╗ ██████╗  ██████╗ ███████╗
██╔══██╗██║  ██║██╔══██╗██╔══██╗██╔═══██╗██╔════╝
██████╔╝███████║███████║██████╔╝██║   ██║███████╗
██╔═══╝ ██╔══██║██╔══██║██╔══██╗██║   ██║╚════██║
██║     ██║  ██║██║  ██║██║  ██║╚██████╔╝███████║
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
    """)
    print("Pharos Username Minter v7.4 | Professional Enhanced Commit-Register Process")
    print("=" * 60)
    print(f"Blockchain: Pharos Testnet (Chain ID: {os.getenv('CHAIN_ID', '688688')})")
    print("=" * 60)

class PharosMultiMinter:
    def __init__(self, private_key, user_agent=None, max_retries=5):
        if not private_key or private_key == '0x' + '0'*64:
            raise ValueError("Invalid private key")
            
        self.max_retries = max_retries
        self.session = requests.Session()
        self.rpc_urls = [
            os.getenv('RPC_URL', 'https://testnet.dplabs-internal.com'),
            os.getenv('RPC_URL_FALLBACK_1', ''),
            os.getenv('RPC_URL_FALLBACK_2', '')
        ]
        self.rpc_urls = [url for url in self.rpc_urls if url]
        
        if not self.rpc_urls:
            self.rpc_urls = [
                'https://testnet.dplabs-internal.com',
                'https://rpc.testnet.pharos.network',
            ]
        
        self.w3 = self.create_web3_instance(self.rpc_urls[0])
        inject_poa_middleware(self.w3)
        
        if not self.w3.is_connected():
            for fallback_url in self.rpc_urls[1:]:
                print(f"⚠️ Trying fallback RPC: {fallback_url}")
                self.w3 = self.create_web3_instance(fallback_url)
                if self.w3.is_connected():
                    print("✅ Connected to fallback RPC")
                    break
            if not self.w3.is_connected():
                raise ConnectionError("❌ Failed to connect to any RPC endpoint")
        
        self.account = self.w3.eth.account.from_key(private_key)
        self.contract_address = Web3.to_checksum_address(
            os.getenv('CONTRACT_ADDRESS', '0x51be1ef20a1fd5179419738fc71d95a8b6f8a175')
        )
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=CONTRACT_ABI)
        self.chain_id = int(os.getenv('CHAIN_ID', 688688))

    def create_web3_instance(self, rpc_url):
        provider = Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 120})
        w3 = Web3(provider)
        inject_poa_middleware(w3)
        return w3

    def mint_username(self, max_attempts=7):
        for attempt in range(max_attempts):
            username = self.generate_username(length=random.randint(5, 8))
            full_username = f"{username}.phrs"
            
            if not self.is_username_available(full_username):
                print(f"  ❌ [{attempt+1}/{max_attempts}] Taken: {full_username}")
                time.sleep(0.5)
                continue
            
            print(f"  ✅ [{attempt+1}/{max_attempts}] Available: {full_username}")
            secret = self.make_commitment(full_username)
            
            if not secret:
                print("  ❌ Commitment failed, trying another name")
                continue
            
            wait_time = self.get_min_commitment_age() + 15
            print(f"  ⏳ Waiting {wait_time} seconds for commitment to mature...")
            time.sleep(wait_time)
            
            tx_hash = self.register_username(full_username, secret)
            
            if tx_hash:
                explorer_url = os.getenv('EXPLORER_BASE_URL', 'https://testnet.pharosscan.xyz/tx/')
                return {
                    'status': 'success',
                    'username': full_username,
                    'tx_hash': tx_hash.hex(),
                    'explorer_url': f"{explorer_url}{tx_hash.hex()}"
                }
        
        return {'status': 'failed', 'reason': 'No available names found after attempts'}

    # Other methods (generate_username, is_username_available, make_commitment, etc.)
    # are included in the class but omitted here for brevity.

def main():
    print_banner()
    accounts = load_accounts()
    
    for account in accounts:
        print(f"\n{'=' * 60}")
        print(f"🔑 Processing Account: {account['name']}")
        try:
            minter = PharosMultiMinter(private_key=account['private_key'])
            result = minter.mint_username(max_attempts=7)
            
            if result['status'] == 'success':
                print(f"\n🎉 Username Minted Successfully: {result['username']}")
                print(f"🔗 View transaction: {result['explorer_url']}")
            else:
                print(f"\n❌ Minting failed: {result['reason']}")
        except Exception as e:
            print(f"\n⚠️ Error processing account: {str(e)}")
            traceback.print_exc()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🚫 Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected global error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)