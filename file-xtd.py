#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pharos Username Minter v7.2
A tool for registering usernames on the Pharos blockchain using the two-step commit-register process.
"""

import os
import json
import random
import string
import time
import requests
import sys
import web3
import logging
import argparse
from web3 import Web3
from web3.exceptions import ContractLogicError, TimeExhausted
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv
from uuid import uuid4
import secrets
import statistics
import traceback

# =============================================
# CONFIGURATION AND LOGGING SETUP
# =============================================

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pharos_minter.log")
    ]
)
logger = logging.getLogger("pharos_minter")

# Load environment variables from .env file
load_dotenv()

# Default configuration
DEFAULT_CONFIG = {
    'RPC_URL': 'https://testnet.dplabs-internal.com',
    'CHAIN_ID': 688688,
    'CONTRACT_ADDRESS': '0x51be1ef20a1fd5179419738fc71d95a8b6f8a175',
    'EXPLORER_BASE_URL': 'https://testnet.pharosscan.xyz/tx/',
    'DEFAULT_GAS_PRICE': 20,  # in gwei
    'GAS_PRICE_ADJUSTMENT': 0.05,  # 5% adjustment
    'COMMIT_GAS_BUFFER': 1.3,  # 30% buffer
    'REGISTER_GAS_BUFFER': 1.5,  # 50% buffer
    'MAX_TX_RETRIES': 3,
    'POLLING_INTERVAL': 5,  # seconds
    'WAIT_BETWEEN_ACCOUNTS': 15,  # seconds
    'MAX_ATTEMPTS_PER_ACCOUNT': 7
}

# =============================================
# CONTRACT ABI
# =============================================
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

# =============================================
# UTILITY FUNCTIONS
# =============================================
def inject_poa_middleware(w3):
    """Custom POA middleware injection with version compatibility"""
    try:
        # For Web3.py v6+
        try:
            from web3.middleware import ExtraDataToPOAMiddleware
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            logger.info("✅ POA middleware injected (ExtraDataToPOAMiddleware)")
            return True
        except ImportError:
            pass
        
        # For Web3.py v5
        try:
            from web3.middleware import geth_poa_middleware
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            logger.info("✅ POA middleware injected (geth_poa_middleware)")
            return True
        except ImportError:
            pass
        
        # For Web3.py v4
        try:
            from web3.middleware.geth_poa import geth_poa_middleware
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            logger.info("✅ POA middleware injected (legacy geth_poa)")
            return True
        except ImportError:
            pass
        
    except Exception as e:
        logger.warning(f"⚠️ POA middleware error: {str(e)}")

    logger.warning("⚠️ Using no POA middleware (may work for some networks)")
    return True

def generate_random_user_agent():
    """Generate a random mobile user agent"""
    ios_versions = ['16.0', '16.1', '16.2', '16.3', '16.4', '16.5', '16.6', '17.0', '17.1']
    safari_versions = ['604.1', '605.1.15', '606.1.36', '607.1.40']
    
    return (f"Mozilla/5.0 (iPhone; CPU iPhone OS {random.choice(ios_versions).replace('.', '_')} "
            f"like Mac OS X) AppleWebKit/{random.choice(safari_versions)} "
            f"(KHTML, like Gecko) Version/{random.choice(ios_versions)} "
            f"Mobile/15E148 Safari/{random.choice(safari_versions)}")

def get_env_value(key, default=None, required=False):
    """Get environment variable with fallback to default"""
    value = os.getenv(key, default)
    if required and not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value

def print_banner():
    """Print the application banner"""
    banner = r"""
██████╗ ██╗  ██╗ █████╗ ██████╗  ██████╗ ███████╗
██╔══██╗██║  ██║██╔══██╗██╔══██╗██╔═══██╗██╔════╝
██████╔╝███████║███████║██████╔╝██║   ██║███████╗
██╔═══╝ ██╔══██║██╔══██║██╔══██╗██║   ██║╚════██║
██║     ██║  ██║██║  ██║██║  ██║╚██████╔╝███████║
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
    """
    print(banner)
    print("Pharos Username Minter v7.2 | Two-Step Commit-Register (FIXED)")
    print("=" * 60)
    chain_id = get_env_value('CHAIN_ID', DEFAULT_CONFIG['CHAIN_ID'])
    print(f"Blockchain: Pharos Testnet (Chain ID: {chain_id})")
    print("=" * 60)

# =============================================
# MAIN MINTER CLASS
# =============================================
class PharosMultiMinter:
    def __init__(self, private_key, user_agent=None, config=None):
        """
        Initialize the Pharos Username Minter
        
        Args:
            private_key (str): Private key for the account
            user_agent (str, optional): User agent string to use for requests
            config (dict, optional): Configuration dictionary
        """
        # Initialize configuration
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
            
        # Validate private key
        if not private_key or private_key == '0x' + '0'*64:
            raise ValueError("Invalid private key")
            
        # Setup environment diagnostics
        logger.info("\n" + "="*50)
        logger.info(f"Python version: {sys.version.split()[0]}")
        logger.info(f"Web3 version: {web3.__version__}")
        logger.info("="*50)
        
        # Create custom session with headers
        self.session = requests.Session()
        headers = {
            'User-Agent': user_agent or generate_random_user_agent(),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Request-ID': str(uuid4())
        }
        self.session.headers.update(headers)
        
        # Initialize Web3 with custom session and timeout
        rpc_url = get_env_value('RPC_URL', self.config['RPC_URL'])
        logger.info(f"🔗 Connecting to RPC: {rpc_url}")
        
        self.w3 = Web3(Web3.HTTPProvider(
            rpc_url,
            session=self.session,
            request_kwargs={'timeout': 120}
        ))
        
        # Inject POA middleware with compatibility solution
        inject_poa_middleware(self.w3)
            
        # Check connection
        if not self.w3.is_connected():
            raise ConnectionError("❌ Failed to connect to RPC endpoint")
        logger.info("✅ Connected to blockchain")
        
        # Load account
        self.account = self.w3.eth.account.from_key(private_key)
        self.contract_address = Web3.to_checksum_address(
            get_env_value('CONTRACT_ADDRESS', self.config['CONTRACT_ADDRESS'])
        )
        
        # Initialize contract
        try:
            self.contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=CONTRACT_ABI
            )
            logger.info(f"📜 Contract loaded: {self.contract_address}")
        except Exception as e:
            raise ValueError(f"❌ Contract initialization failed: {str(e)}")
            
        # Initialize gas price history for improved gas price estimation
        self.gas_price_history = []
        self.max_history_size = 5
        
        # Initialize network stats
        self.chain_id = int(get_env_value('CHAIN_ID', self.config['CHAIN_ID']))
        
        # Initialize transaction retry counts
        self.max_tx_retries = self.config['MAX_TX_RETRIES']

    def generate_username(self, length=5):
        """Generate a random lowercase username"""
        return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))
    
    def generate_secret(self):
        """Generate a random 32-byte secret"""
        return secrets.token_bytes(32)
    
    def generate_commitment(self, name, secret):
        """Generate commitment hash for a username"""
        # Use Web3.solidity_keccak for compatibility
        try:
            # For newer Web3.py versions
            namehash = Web3.solidity_keccak(['string'], [name])
            commitment = Web3.solidity_keccak(['bytes32', 'bytes32'], [namehash, secret])
            return commitment
        except AttributeError:
            try:
                # Alternative method for older versions
                namehash = Web3.keccak(text=name)
                commitment = Web3.keccak(namehash + secret)
                return commitment
            except Exception:
                # Manual keccak calculation as fallback
                try:
                    from Crypto.Hash import keccak
                    name_bytes = name.encode('utf-8')
                    namehash = keccak.new(digest_bits=256).update(name_bytes).digest()
                    commitment = keccak.new(digest_bits=256).update(namehash + secret).digest()
                    return commitment
                except ImportError:
                    # Last resort fallback using sha3
                    import hashlib
                    name_bytes = name.encode('utf-8')
                    namehash = hashlib.sha3_256(name_bytes).digest()
                    commitment = hashlib.sha3_256(namehash + secret).digest()
                    return commitment
    
    def get_min_commitment_age(self):
        """Get minimum commitment age in seconds"""
        try:
            return self.contract.functions.minCommitmentAge().call()
        except Exception as e:
            logger.warning(f"⚠️ Failed to get min commitment age: {str(e)}")
            return 60  # Default to 60 seconds
    
    def get_minting_fee(self):
        """Get current minting fee in wei"""
        try:
            return self.contract.functions.mintingFee().call()
        except Exception as e:
            logger.warning(f"⚠️ Failed to get minting fee: {str(e)}")
            # Return default fee if lookup fails
            return Web3.to_wei(0.01, 'ether')

    def get_balance(self):
        """Get account balance in PHRS"""
        try:
            balance = self.w3.eth.get_balance(self.account.address)
            return Web3.from_wei(balance, 'ether')
        except Exception as e:
            logger.warning(f"⚠️ Failed to get balance: {str(e)}")
            return 0.0

    def is_username_available(self, full_username):
        """
        Check if username is available
        Returns True if available, False if taken
        """
        try:
            # Check availability
            available = self.contract.functions.available(full_username).call()
            return available
        except ContractLogicError as e:
            # Handle contract-specific errors
            error_msg = str(e)
            if "already registered" in error_msg.lower() or "exists" in error_msg.lower():
                return False
            logger.warning(f"⚠️ 'available' function error: {error_msg}")
            return False
        except Exception as e:
            logger.warning(f"⚠️ 'available' function error: {str(e)}")
            return False
    
    def get_gas_price(self):
        """
        Enhanced gas price detection with multiple fallbacks and historical data
        Returns optimal gas price in wei based on network conditions
        """
        gas_prices = []
        
        # Try method 1: Direct gas_price query
        try:
            gas_price = self.w3.eth.gas_price
            gas_prices.append(gas_price)
            logger.info(f"  💡 Method 1 gas price: {Web3.from_wei(gas_price, 'gwei')} gwei")
        except Exception as e:
            logger.warning(f"  ⚠️ Method 1 failed: {str(e)}")
        
        # Try method 2: eth_gasPrice RPC call
        try:
            gas_price = self.w3.manager.request_blocking("eth_gasPrice", [])
            if isinstance(gas_price, str) and gas_price.startswith("0x"):
                gas_price = int(gas_price, 16)
            gas_prices.append(gas_price)
            logger.info(f"  💡 Method 2 gas price: {Web3.from_wei(gas_price, 'gwei')} gwei")
        except Exception as e:
            logger.warning(f"  ⚠️ Method 2 failed: {str(e)}")
            
        # Try method 3: fee_history if available
        try:
            fee_history = self.w3.eth.fee_history(1, 'latest', [25, 50, 75])
            if fee_history and 'baseFeePerGas' in fee_history and fee_history['baseFeePerGas']:
                base_fee = fee_history['baseFeePerGas'][0]
                priority_fee = Web3.to_wei(2, 'gwei')  # Add 2 gwei priority fee
                gas_price = base_fee + priority_fee
                gas_prices.append(gas_price)
                logger.info(f"  💡 Method 3 gas price: {Web3.from_wei(gas_price, 'gwei')} gwei")
        except Exception as e:
            logger.warning(f"  ⚠️ Method 3 failed: {str(e)}")
        
        # Try method 4: Use history if available
        if self.gas_price_history:
            historical_avg = statistics.median(self.gas_price_history)
            gas_prices.append(historical_avg)
            logger.info(f"  💡 Method 4 historical median: {Web3.from_wei(historical_avg, 'gwei')} gwei")
        
        # Choose final gas price
        if gas_prices:
            # Use the median to avoid outliers
            final_gas_price = statistics.median(gas_prices)
            
            # Add small random adjustment to avoid stuck transactions
            adjustment = random.uniform(
                1.0 - self.config['GAS_PRICE_ADJUSTMENT'], 
                1.0 + self.config['GAS_PRICE_ADJUSTMENT']
            )
            final_gas_price = int(final_gas_price * adjustment)
            
            # Update history for future use
            self.gas_price_history.append(final_gas_price)
            if len(self.gas_price_history) > self.max_history_size:
                self.gas_price_history.pop(0)
            
            logger.info(f"  ⛽ Final gas price: {Web3.from_wei(final_gas_price, 'gwei')} gwei")
            return final_gas_price
        else:
            # Fallback to safe default
            default_gas = Web3.to_wei(self.config['DEFAULT_GAS_PRICE'], 'gwei')
            logger.warning(f"  ⚠️ All methods failed, using default: {Web3.from_wei(default_gas, 'gwei')} gwei")
            return default_gas
    
    def wait_for_receipt(self, tx_hash, timeout=180, polling_interval=None):
        """
        Wait for transaction receipt with enhanced polling
        
        Args:
            tx_hash: Transaction hash to wait for
            timeout: Maximum time to wait in seconds
            polling_interval: Time between polls in seconds
            
        Returns:
            receipt: Transaction receipt or None if timeout
        """
        if polling_interval is None:
            polling_interval = self.config['POLLING_INTERVAL']
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt is not None:
                    return receipt
            except Exception as e:
                logger.debug(f"Error getting receipt: {str(e)}")
                
            # Check transaction status
            try:
                tx = self.w3.eth.get_transaction(tx_hash)
                if tx and tx.get('blockNumber') is not None:
                    logger.info(f"  📦 Transaction mined in block {tx['blockNumber']}, waiting for receipt...")
            except Exception:
                pass
                
            time.sleep(polling_interval)
            logger.info(f"  ⏳ Waiting for transaction confirmation... ({int(time.time() - start_time)}s elapsed)")
            
        logger.warning(f"  ⏱️ Transaction receipt timeout after {timeout}s")
        return None
    
    def sign_and_send_transaction(self, tx, retry=0):
        """
        Sign and send transaction with retry mechanism
        
        Args:
            tx: Transaction to sign and send
            retry: Current retry count
            
        Returns:
            tx_hash: Transaction hash or None if failed
        """
        if retry > self.max_tx_retries:
            logger.error(f"  ❌ Max retries ({self.max_tx_retries}) exceeded")
            return None
            
        try:
            # Sign transaction
            signed_tx = self.account.sign_transaction(tx)
            
            # Handle different Web3.py versions for raw transaction
            try:
                # For newer versions (v6+)
                raw_tx = signed_tx.rawTransaction
            except AttributeError:
                try:
                    # For some versions
                    raw_tx = signed_tx.raw_transaction
                except AttributeError:
                    # For older versions
                    raw_tx = signed_tx['rawTransaction']
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
            return tx_hash
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Handle specific errors with retry
            if retry < self.max_tx_retries and (
                "nonce too low" in error_str or 
                "already known" in error_str or
                "underpriced" in error_str or
                "replacement transaction underpriced" in error_str
            ):
                logger.warning(f"  ⚠️ Transaction error (retry {retry+1}/{self.max_tx_retries}): {str(e)}")
                
                # Update nonce and gas price for retry
                try:
                    tx['nonce'] = self.w3.eth.get_transaction_count(self.account.address)
                    
                    # Increase gas price by 10% for each retry
                    tx['gasPrice'] = int(tx['gasPrice'] * 1.1)
                    
                    logger.info(f"  🔄 Retrying with nonce {tx['nonce']} and gas price {Web3.from_wei(tx['gasPrice'], 'gwei')} gwei")
                    time.sleep(2)  # Short delay before retry
                    return self.sign_and_send_transaction(tx, retry + 1)
                except Exception as inner_e:
                    logger.error(f"  ❌ Error preparing retry: {str(inner_e)}")
            
            logger.error(f"  ❌ Transaction signing/sending failed: {str(e)}")
            return None
    
    def make_commitment(self, full_username):
        """Create and send commitment transaction"""
        # Generate secret and commitment
        secret = self.generate_secret()
        commitment = self.generate_commitment(full_username, secret)
        
        # Build commit transaction
        try:
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.get_gas_price()
            
            tx_params = {
                'chainId': self.chain_id,
                'from': self.account.address,
                'nonce': nonce,
                'gasPrice': gas_price,
                'gas': 100000  # Initial gas estimate
            }
            
            # Build transaction
            tx = self.contract.functions.commit(commitment).build_transaction(tx_params)
            
            # Estimate gas with error handling
            try:
                gas_estimate = self.contract.functions.commit(commitment).estimate_gas({
                    'from': self.account.address
                })
                # Add buffer
                tx['gas'] = int(gas_estimate * self.config['COMMIT_GAS_BUFFER'])
                logger.info(f"  ⛽ Commit gas estimate: {gas_estimate} (using {tx['gas']})")
            except Exception as e:
                logger.warning(f"  ⚠️ Commit gas estimation failed: {str(e)}")
                tx['gas'] = 150000  # Use safe default
            
            # Sign and send transaction using compatibility method
            tx_hash = self.sign_and_send_transaction(tx)
            if not tx_hash:
                return None
                
            logger.info(f"  🔗 Commit transaction sent: {tx_hash.hex()}")
            
            # Wait for commit confirmation
            receipt = self.wait_for_receipt(tx_hash, timeout=180)
            if receipt and receipt.status == 1:
                logger.info("  ✅ Commitment confirmed")
                return {
                    'secret': secret,
                    'tx_hash': tx_hash.hex(),
                    'receipt': receipt
                }
            elif receipt and receipt.status == 0:
                logger.error("  ❌ Commitment failed")
                return None
            else:
                logger.warning("  ⏱️ Commit transaction timeout, but continuing...")
                # Return data anyway, might still work
                return {
                    'secret': secret,
                    'tx_hash': tx_hash.hex(),
                    'receipt': None
                }
                
        except Exception as e:
            logger.error(f"  ⚠️ Commitment failed: {str(e)}")
            return None

    def register_username(self, full_username, secret):
        """Register username after commitment"""
        try:
            fee = self.get_minting_fee()
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.get_gas_price()
            
            tx_params = {
                'chainId': self.chain_id,
                'from': self.account.address,
                'value': fee,
                'nonce': nonce,
                'gasPrice': gas_price,
                'gas': 300000  # Initial gas estimate
            }
            
            # Build register transaction
            tx = self.contract.functions.register(
                full_username,
                self.account.address,
                secret
            ).build_transaction(tx_params)
            
            # Estimate gas with error handling
            try:
                gas_estimate = self.contract.functions.register(
                    full_username,
                    self.account.address,
                    secret
                ).estimate_gas({
                    'from': self.account.address,
                    'value': fee
                })
                # Add buffer for register
                tx['gas'] = int(gas_estimate * self.config['REGISTER_GAS_BUFFER'])
                logger.info(f"  ⛽ Register gas estimate: {gas_estimate} (using {tx['gas']})")
            except Exception as e:
                logger.warning(f"  ⚠️ Register gas estimation failed: {str(e)}")
                # More aggressive fallback for registration
                tx['gas'] = 450000  # Use safer default
            
            # Sign and send transaction using compatibility method
            tx_hash = self.sign_and_send_transaction(tx)
            if not tx_hash:
                return None
                
            logger.info(f"  🔗 Register transaction sent: {tx_hash.hex()}")
            
            # Wait for register confirmation
            receipt = self.wait_for_receipt(tx_hash, timeout=300)
            if receipt and receipt.status == 1:
                logger.info("  ✅ Registration successful")
                return {
                    'tx_hash': tx_hash.hex(),
                    'receipt': receipt
                }
            elif receipt and receipt.status == 0:
                logger.error("  ❌ Registration failed")
                return None
            else:
                logger.warning("  ⏱️ Register transaction timeout")
                return {
                    'tx_hash': tx_hash.hex(),
                    'receipt': None,
                    'status': 'pending'
                }
            
        except Exception as e:
            logger.error(f"  ⚠️ Registration failed: {str(e)}")
            return None

    def mint_username(self, max_attempts=None):
        """
        Mint a new username with two-step commit-register process
        Will try up to max_attempts times to find an available name
        """
        if max_attempts is None:
            max_attempts = self.config['MAX_ATTEMPTS_PER_ACCOUNT']
            
        for attempt in range(max_attempts):
            username = self.generate_username()
            full_username = f"{username}.phrs"
            
            # Check availability
            try:
                if not self.is_username_available(full_username):
                    logger.info(f"  ❌ [{attempt+1}/{max_attempts}] Taken: {full_username}")
                    time.sleep(0.5)  # Short delay between checks
                    continue
            except Exception as e:
                logger.warning(f"  ⚠️ Availability check failed: {str(e)}")
                time.sleep(1)
                continue
            
            logger.info(f"  ✅ [{attempt+1}/{max_attempts}] Available: {full_username}")
            
            # Step 1: Make commitment
            logger.info("  🔐 Making commitment...")
            commit_result = self.make_commitment(full_username)
            if not commit_result:
                logger.error("  ❌ Commitment failed, trying another name")
                time.sleep(1)
                continue
                
            secret = commit_result['secret']
            
            # Wait for commitment to mature (prevent front-running)
            min_age = self.get_min_commitment_age()
            wait_time = max(min_age, 60)  # Minimum 60 seconds
            logger.info(f"  ⏳ Waiting {wait_time} seconds for commitment to mature...")
            time.sleep(wait_time)
            
            # Step 2: Register username
            logger.info("  📝 Registering username...")
            register_result = self.register_username(full_username, secret)
            
            if register_result:
                tx_hash = register_result['tx_hash']
                explorer_url = get_env_value(
                    'EXPLORER_BASE_URL', 
                    self.config['EXPLORER_BASE_URL']
                )
                explorer_link = f"{explorer_url}{tx_hash}"
                
                status = 'success'
                if register_result.get('status') == 'pending':
                    status = 'pending'
                
                return {
                    'status': status,
                    'username': full_username,
                    'tx_hash': tx_hash,
                    'explorer_url': explorer_link
                }
            
            time.sleep(1.5)  # Delay between mint attempts
        
        return {'status': 'failed', 'reason': 'No available names found after attempts'}

# =============================================
# ACCOUNT MANAGEMENT
# =============================================
def load_accounts():
    """Load account configurations from environment"""
    accounts = []
    
    # Account 1 (iPhone 16 Pro Max)
    pk1 = get_env_value('PRIVATE_KEY_1')
    if pk1 and pk1 != '0x' + '0'*64:
        ua1 = get_env_value('USER_AGENT_1', "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        accounts.append({
            'name': 'Account 1 (iPhone 16 Pro Max)',
            'private_key': pk1,
            'user_agent': ua1
        })
    
    # Account 2 (iPhone 15)
    pk2 = get_env_value('PRIVATE_KEY_2')
    if pk2 and pk2 != '0x' + '0'*64:
        ua2 = get_env_value('USER_AGENT_2', "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1")
        accounts.append({
            'name': 'Account 2 (iPhone 15)',
            'private_key': pk2,
            'user_agent': ua2
        })
    
    # Support for additional accounts (3-10)
    for i in range(3, 11):
        pk = get_env_value(f'PRIVATE_KEY_{i}')
        if pk and pk != '0x' + '0'*64:
            ua = get_env_value(
                f'USER_AGENT_{i}', 
                generate_random_user_agent()
            )
            accounts.append({
                'name': f'Account {i}',
                'private_key': pk,
                'user_agent': ua
            })
    
    # Validate at least one account
    if not accounts:
        raise ValueError("No valid accounts configured. Check PRIVATE_KEY_1 environment variable.")
    
    return accounts

# =============================================
# MAIN EXECUTION
# =============================================
def main():
    """Main execution function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Pharos Username Minter')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--account', type=int, help='Process only specific account number')
    parser.add_argument('--attempts', type=int, default=None, help='Maximum attempts per account')
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    print_banner()
    
    try:
        accounts = load_accounts()
        
        # Filter accounts if requested
        if args.account and args.account > 0:
            if args.account <= len(accounts):
                accounts = [accounts[args.account - 1]]
                logger.info(f"Processing only account {args.account}: {accounts[0]['name']}")
            else:
                raise ValueError(f"Account {args.account} not found. Only {len(accounts)} accounts available.")
    except ValueError as e:
        logger.error(f"❌ {str(e)}")
        sys.exit(1)
        
    logger.info(f"\n🔍 Found {len(accounts)} account(s) to process")
    
    # Statistics tracking
    total_success = 0
    total_failed = 0
    total_pending = 0
    results = []
    
    for i, account in enumerate(accounts):
        logger.info(f"\n{'=' * 60}")
        logger.info(f"🔑 Processing Account {i+1}: {account['name']}")
        logger.info(f"📱 User Agent: {account['user_agent']}")
        logger.info(f"{'-' * 60}")
        
        try:
            minter = PharosMultiMinter(
                private_key=account['private_key'],
                user_agent=account['user_agent']
            )
            
            # Display account info
            address = minter.account.address
            try:
                # Get balance
                balance = minter.get_balance()
                
                # Get minting fee
                fee = minter.get_minting_fee()
                fee_eth = Web3.from_wei(fee, 'ether')
                
                logger.info(f"💼 Wallet: {address}")
                logger.info(f"💰 Balance: {balance:.6f} PHRS")
                logger.info(f"⛽ Minting Fee: {fee_eth:.6f} PHRS")
                
                # Check balance
                if balance < fee_eth:
                    logger.error(f"❌ Insufficient balance. Needed: {fee_eth:.6f} PHRS")
                    logger.info("Visit testnet faucet if available")
                    total_failed += 1
                    results.append({
                        'account': account['name'],
                        'status': 'failed',
                        'reason': 'Insufficient balance'
                    })
                    continue
            except Exception as e:
                logger.warning(f"⚠️ Failed to get account info: {str(e)}")
                logger.info("Continuing with minting attempt...")
            
            # Start minting
            logger.info("\n🚀 Starting two-step minting process...")
            start_time = time.time()
            result = minter.mint_username(max_attempts=args.attempts)
            elapsed = time.time() - start_time
            
            if result and result['status'] == 'success':
                logger.info(f"\n🎉 Username Minted Successfully in {elapsed:.2f}s!")
                logger.info(f"🔑 Username: {result['username']}")
                logger.info(f"🔗 View transaction: {result['explorer_url']}")
                total_success += 1
                results.append({
                    'account': account['name'],
                    'status': 'success',
                    'username': result['username'],
                    'tx_hash': result['tx_hash'],
                    'explorer_url': result['explorer_url']
                })
            elif result and result['status'] == 'pending':
                logger.info(f"\n⏱️ Transaction pending after {elapsed:.2f}s")
                logger.info(f"🔗 Track transaction: {result.get('explorer_url', 'N/A')}")
                total_pending += 1
                results.append({
                    'account': account['name'],
                    'status': 'pending',
                    'username': result.get('username', 'unknown'),
                    'tx_hash': result.get('tx_hash', 'unknown'),
                    'explorer_url': result.get('explorer_url', 'N/A')
                })
            else:
                logger.error(f"\n❌ Minting failed after {elapsed:.2f}s")
                reason = result.get('reason', 'Unknown error') if result else 'No result returned'
                logger.error(f"Reason: {reason}")
                total_failed += 1
                results.append({
                    'account': account['name'],
                    'status': 'failed',
                    'reason': reason
                })
            
            logger.info(f"\n⏱️ Account processing time: {elapsed:.2f} seconds")
            
        except Exception as e:
            logger.error(f"\n⚠️ Critical error in account processing: {str(e)}")
            traceback.print_exc()
            logger.error("Skipping to next account...")
            total_failed += 1
            results.append({
                'account': account['name'],
                'status': 'failed',
                'reason': f'Critical error: {str(e)}'
            })
        
        # Delay between accounts
        if i < len(accounts) - 1:
            delay = get_env_value('WAIT_BETWEEN_ACCOUNTS', DEFAULT_CONFIG['WAIT_BETWEEN_ACCOUNTS'], required=False)
            logger.info(f"\n⏳ Waiting {delay} seconds before next account...")
            time.sleep(int(delay))
    
    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 Minting Summary:")
    logger.info(f"   ✅ Success: {total_success}")
    logger.info(f"   ⏱️ Pending: {total_pending}")
    logger.info(f"   ❌ Failed: {total_failed}")
    logger.info(f"   🔢 Total Accounts: {len(accounts)}")
    logger.info("=" * 60)
    
    # Detailed results
    if total_success > 0 or total_pending > 0:
        logger.info("\n📋 Successful/Pending Registrations:")
        for result in results:
            if result['status'] in ['success', 'pending']:
                status_emoji = "✅" if result['status'] == 'success' else "⏳"
                logger.info(f"   {status_emoji} {result['account']}: {result.get('username', 'N/A')} - {result.get('explorer_url', 'N/A')}")
    
    # Save results to file
    try:
        with open('pharos_results.json', 'w') as f:
            json.dump({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'summary': {
                    'success': total_success,
                    'pending': total_pending,
                    'failed': total_failed,
                    'total': len(accounts)
                },
                'results': results
            }, f, indent=2)
        logger.info("\n💾 Results saved to pharos_results.json")
    except Exception as e:
        logger.warning(f"Could not save results to file: {str(e)}")
    
    logger.info("=" * 60)
    logger.info("✅ All accounts processed")
    logger.info("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\n🚫 Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"\n💥 Unexpected global error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)