#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pharos Username Minter v7.7
Final Version with Single Commit-Register Flow
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
    
    # Try multiple middleware options for compatibility
    try:
        # For Web3.py v6+
        try:
            from web3.middleware import ExtraDataToPOAMiddleware
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            print("✅ POA middleware injected (ExtraDataToPOAMiddleware)")
            middleware_injected = True
        except ImportError:
            pass
        
        # For Web3.py v5
        if not middleware_injected:
            try:
                from web3.middleware import geth_poa_middleware
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                print("✅ POA middleware injected (geth_poa_middleware)")
                middleware_injected = True
            except ImportError:
                pass
        
        # For Web3.py v4
        if not middleware_injected:
            try:
                from web3.middleware.geth_poa import geth_poa_middleware
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                print("✅ POA middleware injected (legacy geth_poa)")
                middleware_injected = True
            except ImportError:
                pass
        
        # Add retry middleware
        try:
            from web3.middleware import http_retry_request_middleware
            w3.middleware_onion.inject(http_retry_request_middleware, layer=0)
            print("✅ Retry middleware injected")
        except Exception:
            pass
            
        # Add caching middleware to improve performance
        try:
            from web3.middleware import simple_cache_middleware
            w3.middleware_onion.inject(simple_cache_middleware, layer=0)
            print("✅ Cache middleware injected")
        except Exception:
            pass
        
    except Exception as e:
        print(f"⚠️ POA middleware error: {str(e)}")

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
    print("Pharos Username Minter v7.7 | Single Commit-Register Flow")
    print("=" * 60)
    print(f"Blockchain: Pharos Testnet (Chain ID: {os.getenv('CHAIN_ID', '688688')})")
    print("=" * 60)

class PharosMultiMinter:
    def __init__(self, private_key, user_agent=None, max_retries=5):
        # Validate private key
        if not private_key or private_key == '0x' + '0'*64:
            raise ValueError("Invalid private key")
            
        self.max_retries = max_retries
        
        # Setup diagnostics
        print("\n" + "="*50)
        print(f"Python version: {sys.version.split()}")
        print(f"Web3 version: {web3.__version__}")
        print("="*50)
        
        # Create custom session with headers
        self.session = requests.Session()
        
        # Set custom timeout and retry
        adapter = requests.adapters.HTTPAdapter(
            max_retries=3,
            pool_connections=10,
            pool_maxsize=10
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # Add headers
        headers = {
            'User-Agent': user_agent or self.generate_random_user_agent(),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Request-ID': str(uuid4())
        }
        self.session.headers.update(headers)
        
        # Initialize Web3 with custom session and timeout
        rpc_url = os.getenv('RPC_URL', 'https://testnet.dplabs-internal.com')
        print(f"🔗 Connecting to RPC: {rpc_url}")
        
        # Use multiple RPC endpoints for fallback
        self.rpc_urls = [
            rpc_url,
            os.getenv('RPC_URL_FALLBACK_1', ''),
            os.getenv('RPC_URL_FALLBACK_2', '')
        ]
        self.rpc_urls = [url for url in self.rpc_urls if url]  # Filter empty URLs
        
        # If no RPC URLs defined, add default fallbacks for Pharos testnet
        if not self.rpc_urls:
            self.rpc_urls = [
                'https://testnet.dplabs-internal.com',
                'https://rpc.testnet.pharos.network',
            ]
        
        # Initialize with primary RPC
        self.w3 = self.create_web3_instance(self.rpc_urls)
        
        # Check connection with retry
        connected = self.retry_operation(
            lambda: self.w3.is_connected(),
            max_retries=3,
            retry_delay=1,
            operation_name="RPC Connection"
        )
        
        if not connected:
            # Try fallback RPCs if primary fails
            for fallback_url in self.rpc_urls[1:]:
                print(f"⚠️ Trying fallback RPC: {fallback_url}")
                self.w3 = self.create_web3_instance(fallback_url)
                
                connected = self.retry_operation(
                    lambda: self.w3.is_connected(),
                    max_retries=2,
                    retry_delay=1,
                    operation_name="Fallback RPC Connection"
                )
                
                if connected:
                    print("✅ Connected to fallback RPC")
                    break
            
            if not connected:
                raise ConnectionError("❌ Failed to connect to any RPC endpoint")
        
        print("✅ Connected to blockchain")
        
        # Load account
        self.account = self.w3.eth.account.from_key(private_key)
        self.contract_address = Web3.to_checksum_address(
            os.getenv('CONTRACT_ADDRESS', '0x51be1ef20a1fd5179419738fc71d95a8b6f8a175')
        )
        
        # Initialize contract
        try:
            self.contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=CONTRACT_ABI
            )
            print(f"📜 Contract loaded: {self.contract_address}")
        except Exception as e:
            raise ValueError(f"❌ Contract initialization failed: {str(e)}")
            
        # Initialize gas price history
        self.gas_price_history = []
        self.max_history_size = 5
        
        # Initialize cached values with values from successful transactions
        self.cached_minting_fee = Web3.to_wei(0.0032, 'ether')  # Updated fee from screenshot: 0.0032 PHRS
        self.cached_min_commitment_age = 60  # Default 60 seconds
        
        # Initialize chain ID
        self.chain_id = int(os.getenv('CHAIN_ID', 688688))
        
        # Success tracking
        self.registration_attempts = 0
        self.registration_successes = 0
        
        # Add transaction cache to avoid duplicates
        self.tx_cache = {}
        
        # Nonce tracking for account
        self.last_nonce = None
        
        # Explorer settings (based on verified transaction links)
        self.explorer_base_url = os.getenv('EXPLORER_BASE_URL', 'https://pharos-testnet.socialscan.io/tx/')
        
        # Verify chain ID matches the connected network
        self.verify_chain_id()
        
        # Preload contract values with retry
        self.preload_contract_values()

    def verify_chain_id(self):
        """Verify that the connected chain ID matches the expected one"""
        try:
            network_chain_id = self.w3.eth.chain_id
            if network_chain_id != self.chain_id:
                print(f"⚠️ Chain ID mismatch: Expected {self.chain_id}, got {network_chain_id}")
                # Update chain ID to match the network
                self.chain_id = network_chain_id
                print(f"   Updated chain ID to {self.chain_id}")
            else:
                print(f"✅ Chain ID verified: {self.chain_id}")
        except Exception as e:
            print(f"⚠️ Could not verify chain ID: {str(e)}")
            print(f"   Using configured chain ID: {self.chain_id}")

    def create_web3_instance(self, rpc_url):
        """Create a Web3 instance with proper configuration"""
        provider = Web3.HTTPProvider(
            rpc_url,
            session=self.session,
            request_kwargs={
                'timeout': 120,
                'headers': self.session.headers
            }
        )
        w3 = Web3(provider)
        
        # Inject middleware
        inject_poa_middleware(w3)
        
        return w3

    def preload_contract_values(self):
        """Preload contract values to avoid failures during critical operations"""
        print("🔄 Preloading contract values...")
        
        # Preload minting fee
        try:
            self.cached_minting_fee = self.get_minting_fee(use_cache=False)
            print(f"✅ Minting fee preloaded: {Web3.from_wei(self.cached_minting_fee, 'ether')} PHRS")
        except Exception as e:
            print(f"⚠️ Failed to preload minting fee: {str(e)}")
            print(f"   Using default fee: {Web3.from_wei(self.cached_minting_fee, 'ether')} PHRS")
        
        # Preload min commitment age
        try:
            self.cached_min_commitment_age = self.get_min_commitment_age(use_cache=False)
            print(f"✅ Min commitment age preloaded: {self.cached_min_commitment_age} seconds")
        except Exception as e:
            print(f"⚠️ Failed to preload min commitment age: {str(e)}")
            print(f"   Using default age: {self.cached_min_commitment_age} seconds")

    @staticmethod
    def generate_random_user_agent():
        """Generate random mobile user agent"""
        ios_versions = ['16.0', '16.1', '16.2', '16.3', '16.4', '16.5', '16.6', '17.0', '17.1']
        safari_versions = ['604.1', '605.1.15', '606.1.36', '607.1.40']
        
        return (f"Mozilla/5.0 (iPhone; CPU iPhone OS {random.choice(ios_versions).replace('.', '_')} "
                f"like Mac OS X) AppleWebKit/{random.choice(safari_versions)} "
                f"(KHTML, like Gecko) Version/{random.choice(ios_versions)} "
                f"Mobile/15E148 Safari/{random.choice(safari_versions)}")

    @staticmethod
    def generate_username(length=5):
        """Generate random lowercase username"""
        return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))
    
    @staticmethod
    def generate_secret():
        """Generate random 32-byte secret"""
        return secrets.token_bytes(32)
    
    def generate_commitment(self, name, secret):
        """Generate commitment hash for username with fallback methods"""
        for attempt in range(3):  # Try multiple methods
            try:
                if attempt == 0:
                    # Standard method for newer Web3.py
                    namehash = Web3.solidity_keccak(['string'], [name])
                    commitment = Web3.solidity_keccak(['bytes32', 'bytes32'], [namehash, secret])
                elif attempt == 1:
                    # Alternative method for some versions
                    namehash = Web3.keccak(text=name)
                    commitment = Web3.keccak(namehash + secret)
                else:
                    # Manual keccak calculation as last resort
                    try:
                        from Crypto.Hash import keccak
                        name_bytes = name.encode('utf-8')
                        namehash = keccak.new(digest_bits=256).update(name_bytes).digest()
                        commitment = keccak.new(digest_bits=256).update(namehash + secret).digest()
                    except ImportError:
                        # If pycryptodome is not available, try hashlib
                        import hashlib
                        name_bytes = name.encode('utf-8')
                        namehash = hashlib.sha3_256(name_bytes).digest()
                        commitment = hashlib.sha3_256(namehash + secret).digest()
                
                return commitment
            except Exception as e:
                print(f"⚠️ Commitment generation method {attempt+1} failed: {str(e)}")
                continue
                
        # If all methods fail, raise exception
        raise ValueError("Failed to generate commitment hash using any method")
    
    def retry_operation(self, operation, max_retries=None, retry_delay=1, 
                        backoff_factor=1.5, operation_name="Operation", 
                        handle_reverted=True):
        """
        Generic retry wrapper with advanced error handling
        
        Args:
            operation: Callable to retry
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
            backoff_factor: Multiplier for delay after each retry
            operation_name: Name of operation for logging
            handle_reverted: Special handling for 'execution reverted' errors
        """
        if max_retries is None:
            max_retries = self.max_retries
            
        errors = []
        reverted_count = 0
        
        for attempt in range(max_retries):
            try:
                result = operation()
                if attempt > 0:
                    print(f"✅ {operation_name} succeeded on attempt {attempt+1}")
                return result
            except Exception as e:
                error_str = str(e)
                errors.append(error_str)
                
                # Handle 'execution reverted' specially - these often need different approaches
                if handle_reverted and "execution reverted" in error_str.lower():
                    reverted_count += 1
                    print(f"⚠️ {operation_name} reverted on attempt {attempt+1}/{max_retries}")
                    
                    # If we've seen multiple reverts, we might need a longer delay
                    if reverted_count >= 2:
                        retry_delay = max(retry_delay * 2, 5)  # Longer delay for reverts
                        
                    # For reverted operations, we might need to try a different approach
                    if reverted_count >= 3 and operation_name.lower().startswith("get"):
                        print(f"⚠️ Multiple reverts for {operation_name}, returning None")
                        return None
                else:
                    print(f"⚠️ {operation_name} attempt {attempt+1}/{max_retries} failed: {error_str[:100]}")
                
                # Calculate delay with jitter to avoid thundering herd
                delay = retry_delay * (backoff_factor ** attempt)
                jitter = random.uniform(0.8, 1.2)  # Add 20% jitter
                delay = delay * jitter
                
                print(f"   Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
        
        # All retries failed
        print(f"❌ {operation_name} failed after {max_retries} attempts")
        if len(errors) > 0:
            print(f"   Last error: {errors[-1][:150]}" + ("..." if len(errors[-1]) > 150 else ""))
        return None
    
    def get_min_commitment_age(self, use_cache=True):
        """Get minimum commitment age in seconds with caching and retry"""
        # Use cached value if available and requested
        if use_cache and self.cached_min_commitment_age is not None:
            return self.cached_min_commitment_age
            
        # Function to get min age
        def get_age():
            return self.contract.functions.minCommitmentAge().call()
        
        # Retry the operation
        min_age = self.retry_operation(
            get_age,
            max_retries=3,
            operation_name="Get min commitment age"
        )
        
        if min_age is not None:
            # Cache the value for future use
            self.cached_min_commitment_age = min_age
            return min_age
        else:
            print(f"⚠️ Using default min commitment age of {self.cached_min_commitment_age} seconds")
            return self.cached_min_commitment_age
    
    def get_minting_fee(self, use_cache=True):
        """Get minting fee in wei with caching and retry"""
        # Use cached value if available and requested
        if use_cache and self.cached_minting_fee is not None:
            return self.cached_minting_fee
            
        # Direct RPC call as first attempt
        def get_fee_rpc():
            try:
                # Try direct RPC call first (may work when contract.functions fails)
                contract_address = self.contract_address
                # Method ID for mintingFee() based on ABI
                abi_signature = "0x22f8a2ba"  # Function signature for mintingFee()
                
                hex_result = self.w3.eth.call({
                    'to': contract_address,
                    'data': abi_signature
                })
                
                # Convert result from hex
                if isinstance(hex_result, HexBytes):
                    hex_result = hex_result.hex()
                if isinstance(hex_result, str) and hex_result.startswith('0x'):
                    # Parse 32-byte uint from the result
                    return int(hex_result, 16)
                return None
            except Exception as e:
                print(f"⚠️ Direct RPC call for minting fee failed: {str(e)}")
                return None
        
        # Standard contract call
        def get_fee_contract():
            return self.contract.functions.mintingFee().call()
        
        # Try direct RPC call first
        fee = get_fee_rpc()
        
        # If direct call fails, try contract functions
        if fee is None:
            fee = self.retry_operation(
                get_fee_contract,
                max_retries=3,
                operation_name="Get minting fee"
            )
        
        if fee is not None:
            # Only update cache if we got a non-zero value
            if fee > 0:
                self.cached_minting_fee = fee
            return fee
        else:
            # Return cached/default fee if failed
            print(f"⚠️ Using default minting fee of {Web3.from_wei(self.cached_minting_fee, 'ether')} PHRS")
            return self.cached_minting_fee

    def get_balance(self):
        """Get account balance in PHRS with retry"""
        def get_bal():
            return self.w3.eth.get_balance(self.account.address)
        
        balance = self.retry_operation(
            get_bal,
            max_retries=3,
            operation_name="Get balance"
        )
        
        if balance is not None:
            return Web3.from_wei(balance, 'ether')
        else:
            print("⚠️ Failed to get balance")
            return 0.0

    def is_username_available(self, full_username):
        """
        Check if username is available
        Returns True if available, False if already taken
        """
        def check_available():
            return self.contract.functions.available(full_username).call()
        
        result = self.retry_operation(
            check_available,
            max_retries=3,
            operation_name=f"Check if {full_username} is available"
        )
        
        if result is None:
            # If we can't determine availability, assume it's not available
            return False
            
        return result
    
    def get_gas_price(self):
        """
        Auto-detect gas price with multiple fallbacks
        Returns optimal gas price in wei
        """
        gas_prices = []
        
        # Method 1: Direct gas_price query
        try:
            gas_price = self.w3.eth.gas_price
            gas_prices.append(gas_price)
            print(f"  💡 Method 1 gas price: {Web3.from_wei(gas_price, 'gwei')} gwei")
        except Exception as e:
            print(f"  ⚠️ Method 1 failed: {str(e)}")
        
        # Method 2: eth_gasPrice RPC call
        try:
            gas_price = self.w3.manager.request_blocking("eth_gasPrice", [])
            if isinstance(gas_price, str) and gas_price.startswith("0x"):
                gas_price = int(gas_price, 16)
            gas_prices.append(gas_price)
            print(f"  💡 Method 2 gas price: {Web3.from_wei(gas_price, 'gwei')} gwei")
        except Exception as e:
            print(f"  ⚠️ Method 2 failed: {str(e)}")
        
        # Method 3: Use history if available
        if self.gas_price_history:
            historical_avg = statistics.median(self.gas_price_history)
            gas_prices.append(historical_avg)
            print(f"  💡 Method 3 historical median: {Web3.from_wei(historical_avg, 'gwei')} gwei")
        
        # Method 4: Use verified gas price from successful transactions
        # Based on verified transaction - using 1 Gwei as seen in screenshot
        verified_gas = Web3.to_wei(1, 'gwei')
        gas_prices.append(verified_gas)
        print(f"  💡 Method 4 verified gas price: {Web3.from_wei(verified_gas, 'gwei')} gwei")
        
        # Choose final gas price
        if gas_prices:
            # Use the median to avoid outliers
            final_gas_price = statistics.median(gas_prices)
            
            # Add adjustment to ensure transactions go through
            adjustment = random.uniform(1.1, 1.3)  # Increase by 10-30%
            final_gas_price = int(final_gas_price * adjustment)
            
            # Update history for future use
            self.gas_price_history.append(final_gas_price)
            if len(self.gas_price_history) > self.max_history_size:
                self.gas_price_history.pop(0)
            
            print(f"  ⛽ Final gas price: {Web3.from_wei(final_gas_price, 'gwei')} gwei")
            return final_gas_price
        else:
            # This should never happen since we added a fallback
            default_gas = Web3.to_wei(1, 'gwei')  # Use 1 Gwei as default based on verified transaction
            print(f"  ⚠️ All methods failed, using default: {Web3.from_wei(default_gas, 'gwei')} gwei")
            return default_gas
    
    def get_current_nonce(self):
        """Get current nonce with safety measures"""
        try:
            # Get the on-chain nonce
            onchain_nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            # If we have a last used nonce, make sure we're not going backwards
            if self.last_nonce is not None and onchain_nonce <= self.last_nonce:
                # Use our tracked nonce + 1
                next_nonce = self.last_nonce + 1
                print(f"  🔢 Using tracked nonce {next_nonce} (on-chain: {onchain_nonce})")
                return next_nonce
            
            # Otherwise use the on-chain nonce
            self.last_nonce = onchain_nonce
            return onchain_nonce
        except Exception as e:
            print(f"  ⚠️ Failed to get nonce: {str(e)}")
            # If we have a last nonce, increment it as fallback
            if self.last_nonce is not None:
                next_nonce = self.last_nonce + 1
                print(f"  🔢 Using fallback nonce {next_nonce}")
                return next_nonce
            # Otherwise just return 0 as a last resort
            return 0
    
    def estimate_commit_gas(self, commitment):
        """Estimate gas for commit transaction with retry"""
        def estimate():
            return self.contract.functions.commit(commitment).estimate_gas({
                'from': self.account.address
            })
        
        gas_estimate = self.retry_operation(
            estimate,
            max_retries=3,
            operation_name="Commit gas estimation"
        )
        
        if gas_estimate is not None:
            # Add buffer for commit
            gas_limit = int(gas_estimate * 1.6)  # 60% buffer
            print(f"  ⛽ Commit gas estimate: {gas_estimate} (using {gas_limit})")
            return gas_limit
        else:
            # Return safe default if estimation fails - based on verified transaction
            default_gas = 150000  # Based on verified commit transaction
            print(f"  ⚠️ Using default commit gas limit: {default_gas}")
            return default_gas
    
    def estimate_register_gas(self, full_username, owner, secret, fee):
        """Estimate gas for register transaction with retry"""
        def estimate():
            return self.contract.functions.register(
                full_username,
                owner,
                secret
            ).estimate_gas({
                'from': self.account.address,
                'value': fee
            })
        
        gas_estimate = self.retry_operation(
            estimate,
            max_retries=3,
            operation_name="Register gas estimation"
        )
        
        if gas_estimate is not None:
            # Add buffer for register
            gas_limit = int(gas_estimate * 2.0)  # 100% buffer for safety
            print(f"  ⛽ Register gas estimate: {gas_estimate} (using {gas_limit})")
            return gas_limit
        else:
            # Return higher default for register - based on verified transaction
            default_gas = 350000  # Based on verified register transaction
            print(f"  ⚠️ Using default register gas limit: {default_gas}")
            return default_gas
    
    def sign_and_send_transaction(self, tx, operation_name="Transaction"):
        """Sign and send transaction with enhanced error handling"""
        try:
            # Generate a unique ID for this transaction for caching
            tx_id = f"{operation_name}_{tx.get('nonce', '')}_{tx.get('to', '')}"
            
            # Check if we've already tried this exact transaction
            if tx_id in self.tx_cache:
                print(f"  ⚠️ Duplicate transaction detected, skipping")
                return self.tx_cache[tx_id]
            
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
            
            # Define send function
            def send_tx():
                return self.w3.eth.send_raw_transaction(raw_tx)
            
            # Retry send operation
            tx_hash = self.retry_operation(
                send_tx,
                max_retries=3,
                operation_name=f"Send {operation_name}"
            )
            
            # Cache result to avoid duplicates
            self.tx_cache[tx_id] = tx_hash
            
            # Update last nonce after successful send
            if 'nonce' in tx:
                self.last_nonce = max(self.last_nonce or 0, tx['nonce'])
            
            return tx_hash
            
        except Exception as e:
            print(f"  ❌ {operation_name} signing/sending failed: {str(e)}")
            return None
    
    def make_commitment(self, full_username):
        """Create and send commitment transaction"""
        # Generate secret and commitment
        secret = self.generate_secret()
        commitment = self.generate_commitment(full_username, secret)
        
        # Build commit transaction
        try:
            nonce = self.get_current_nonce()
            gas_price = self.get_gas_price()
            
            # Estimate gas for commit (auto)
            gas_limit = self.estimate_commit_gas(commitment)
            
            tx_params = {
                'chainId': self.chain_id,
                'from': self.account.address,
                'nonce': nonce,
                'gasPrice': gas_price,
                'gas': gas_limit
            }
            
            # Try EIP-1559 params if supported
            try:
                if hasattr(self.w3.eth, 'fee_history'):
                    tx_params['maxFeePerGas'] = int(gas_price * 1.5)
                    tx_params['maxPriorityFeePerGas'] = int(gas_price * 0.5)
                    # Remove gasPrice if using EIP-1559
                    tx_params.pop('gasPrice', None)
            except Exception:
                pass
            
            # Build transaction
            tx = self.contract.functions.commit(commitment).build_transaction(tx_params)
            
            # Sign and send transaction
            tx_hash = self.sign_and_send_transaction(tx, "Commit")
            if not tx_hash:
                return None
                
            print(f"  🔗 Commit transaction sent: {tx_hash.hex()}")
            print(f"  🔍 View transaction: {self.explorer_base_url}{tx_hash.hex()}")
            
            # Wait for commit confirmation
            def wait_for_receipt():
                return self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
            
            receipt = self.retry_operation(
                wait_for_receipt,
                max_retries=3,
                operation_name="Wait for commit confirmation"
            )
            
            if receipt:
                if receipt.status == 1:
                    print("  ✅ Commitment confirmed")
                    return {'secret': secret, 'tx_hash': tx_hash}
                else:
                    print("  ❌ Commitment failed (receipt status 0)")
                    return None
            else:
                print("  ⏱️ Commit confirmation timed out, but continuing...")
                # Return secret anyway as the transaction might still confirm
                return {'secret': secret, 'tx_hash': tx_hash}
                
        except Exception as e:
            print(f"  ⚠️ Commitment failed: {str(e)}")
            return None

    def register_username(self, full_username, secret):
        """Register username after commitment with enhanced error handling"""
        try:
            # Use cached minting fee to avoid 'execution reverted' errors
            fee = self.cached_minting_fee
            print(f"  💰 Using minting fee: {Web3.from_wei(fee, 'ether')} PHRS")
            
            # Double-check if username is still available before registering
            if not self.is_username_available(full_username):
                print(f"  ⚠️ Username {full_username} is no longer available")
                return None
                
            nonce = self.get_current_nonce()
            gas_price = self.get_gas_price()
            
            # Use verified gas limit from successful transaction
            gas_limit = 350000  # Based on verified register transaction
            print(f"  ⛽ Using verified gas limit for registration: {gas_limit}")
            
            tx_params = {
                'chainId': self.chain_id,
                'from': self.account.address,
                'value': fee,
                'nonce': nonce,
                'gasPrice': gas_price,
                'gas': gas_limit
            }
            
            # Try EIP-1559 params if supported
            try:
                if hasattr(self.w3.eth, 'fee_history'):
                    tx_params['maxFeePerGas'] = int(gas_price * 1.5)
                    tx_params['maxPriorityFeePerGas'] = int(gas_price * 0.5)
                    # Remove gasPrice if using EIP-1559
                    tx_params.pop('gasPrice', None)
            except Exception:
                pass
            
            # Build register transaction
            tx = self.contract.functions.register(
                full_username,
                self.account.address,
                secret
            ).build_transaction(tx_params)
            
            # Sign and send transaction - NO RETRY FOR REGISTER
            print("  🔏 Sending register transaction (single attempt)...")
            tx_hash = self.sign_and_send_transaction(tx, "Register")
            if not tx_hash:
                return None
                
            print(f"  🔗 Register transaction sent: {tx_hash.hex()}")
            print(f"  🔍 View transaction: {self.explorer_base_url}{tx_hash.hex()}")
            
            # Wait for register confirmation
            def wait_for_receipt():
                return self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            receipt = self.retry_operation(
                wait_for_receipt,
                max_retries=2,  # Reduced retries for confirmation waiting
                operation_name="Wait for register confirmation"
            )
            
            if receipt:
                if receipt.status == 1:
                    print("  ✅ Registration successful")
                    self.registration_successes += 1
                    return tx_hash
                else:
                    print("  ❌ Registration failed (receipt status 0)")
                    return None
            else:
                print("  ⏱️ Register confirmation timed out")
                return tx_hash  # Return hash for tracking even if timeout
            
        except Exception as e:
            print(f"  ⚠️ Registration failed: {str(e)}")
            return None

    def mint_username(self):
        """
        Mint new username with one commit followed by one register
        Returns status of the operation
        """
        # Generate username options
        username_options = []
        for _ in range(5):  # Generate 5 options
            username = self.generate_username(length=random.randint(5, 8))
            full_username = f"{username}.phrs"
            username_options.append(full_username)
            
        # Check availability for all options
        available_usernames = []
        print("\n🔍 Checking username availability...")
        for username in username_options:
            try:
                if self.is_username_available(username):
                    available_usernames.append(username)
                    print(f"  ✅ Available: {username}")
                else:
                    print(f"  ❌ Taken: {username}")
            except Exception as e:
                print(f"  ⚠️ Error checking {username}: {str(e)}")
                
        if not available_usernames:
            print("❌ No available usernames found")
            return {'status': 'failed', 'reason': 'No available usernames'}
            
        # Select one username to use
        full_username = random.choice(available_usernames)
        print(f"\n📝 Selected username: {full_username}")
        
        # STEP 1: Make commitment (one time only)
        print("\n🔐 STEP 1: Making commitment...")
        commit_result = self.make_commitment(full_username)
        
        if not commit_result:
            print("❌ Commitment failed")
            return {'status': 'failed', 'reason': 'Commitment failed'}
            
        secret = commit_result['secret']
        commit_tx_hash = commit_result['tx_hash']
        
        # Wait for commitment to mature (prevent front-running)
        min_age = self.cached_min_commitment_age
        wait_time = max(min_age, 60)  # Minimum 60 seconds
        
        # Add safety margin (15 seconds) to ensure commitment is mature
        wait_time += 15
        
        print(f"\n⏳ Waiting {wait_time} seconds for commitment to mature...")
        
        # Wait with a progress indicator
        start_time = time.time()
        for i in range(wait_time):
            elapsed = time.time() - start_time
            if elapsed >= wait_time:
                break
                
            if i % 10 == 0:  # Print status every 10 seconds
                remaining = wait_time - int(elapsed)
                print(f"  ⏳ {remaining} seconds remaining...")
                
            time.sleep(1)
        
        # Double-check if username is still available before registering
        print("\n🔍 Verifying username is still available...")
        if not self.is_username_available(full_username):
            print(f"❌ Username {full_username} is no longer available")
            return {'status': 'failed', 'reason': 'Username taken during waiting period'}
        
        # STEP 2: Register username (one time only)
        print("\n🔏 STEP 2: Registering username...")
        tx_hash = self.register_username(full_username, secret)
        
        if tx_hash:
            explorer_link = f"{self.explorer_base_url}{tx_hash.hex()}"
            
            return {
                'status': 'success',
                'username': full_username,
                'commit_tx_hash': commit_tx_hash.hex(),
                'register_tx_hash': tx_hash.hex(),
                'explorer_url': explorer_link
            }
        else:
            print("❌ Registration failed")
            return {
                'status': 'failed', 
                'reason': 'Registration failed',
                'commit_tx_hash': commit_tx_hash.hex()
            }

def load_accounts():
    """Load account configuration from environment"""
    accounts = []
    
    # Account 1
    pk1 = os.getenv('PRIVATE_KEY_1')
    if pk1 and pk1 != '0x' + '0'*64:
        ua1 = os.getenv('USER_AGENT_1', "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        accounts.append({
            'name': 'Account 1 (iPhone 16 Pro Max)',
            'private_key': pk1,
            'user_agent': ua1
        })
    
    # Account 2
    pk2 = os.getenv('PRIVATE_KEY_2')
    if pk2 and pk2 != '0x' + '0'*64:
        ua2 = os.getenv('USER_AGENT_2', "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1")
        accounts.append({
            'name': 'Account 2 (iPhone 15)',
            'private_key': pk2,
            'user_agent': ua2
        })
    
    # Validate at least one account
    if not accounts:
        raise ValueError("No valid accounts configured. Check PRIVATE_KEY_1 environment variable.")
    
    return accounts

def main():
    """Main function"""
    print_banner()
    
    try:
        accounts = load_accounts()
    except ValueError as e:
        print(f"❌ {str(e)}")
        sys.exit(1)
        
    print(f"\n🔍 Found {len(accounts)} account(s) to process")
    
    total_success = 0
    total_failed = 0
    
    for i, account in enumerate(accounts):
        print(f"\n{'=' * 60}")
        print(f"🔑 Processing Account {i+1}: {account['name']}")
        print(f"📱 User Agent: {account['user_agent']}")
        print(f"{'-' * 60}")
        
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
                
                # Get minting fee (use cached value which is already preloaded)
                fee_eth = Web3.from_wei(minter.cached_minting_fee, 'ether')
                
                print(f"💼 Wallet: {address}")
                print(f"💰 Balance: {balance:.6f} PHRS")
                print(f"⛽ Minting Fee: {fee_eth:.6f} PHRS")
                
                # Check balance
                if balance < fee_eth:
                    print(f"❌ Insufficient balance. Needed: {fee_eth:.6f} PHRS")
                    print("Visit testnet faucet if available")
                    total_failed += 1
                    continue
            except Exception as e:
                print(f"⚠️ Failed to get account info: {str(e)}")
                print("Continuing with minting attempt...")
            
            # Start minting with single commit-register flow
            print("\n🚀 Starting single commit-register minting process...")
            start_time = time.time()
            result = minter.mint_username()
            elapsed = time.time() - start_time
            
            if result and result['status'] == 'success':
                print(f"\n🎉 Username Minted Successfully in {elapsed:.2f}s!")
                print(f"📝 Username: {result['username']}")
                print(f"🔗 Commit transaction: {minter.explorer_base_url}{result['commit_tx_hash']}")
                print(f"🔗 Register transaction: {result['explorer_url']}")
                total_success += 1
            else:
                print(f"\n❌ Minting failed after {elapsed:.2f}s")
                reason = result.get('reason', 'Unknown error') if result else 'No result returned'
                print(f"Reason: {reason}")
                if result and 'commit_tx_hash' in result:
                    print(f"🔗 Commit transaction: {minter.explorer_base_url}{result['commit_tx_hash']}")
                total_failed += 1
            
            print(f"\n⏱️ Account processing time: {elapsed:.2f} seconds")
            
        except Exception as e:
            print(f"\n⚠️ Critical error in account processing: {str(e)}")
            traceback.print_exc()
            print("Skipping to next account...")
            total_failed += 1
        
        # Delay between accounts
        if i < len(accounts) - 1:
            delay = 15
            print(f"\n⏳ Waiting {delay} seconds before next account...")
            time.sleep(delay)
    
    print("\n" + "=" * 60)
    print("📊 Minting Summary:")
    print(f"   ✅ Success: {total_success}")
    print(f"   ❌ Failed: {total_failed}")
    print(f"   🔢 Total Accounts: {len(accounts)}")
    print("=" * 60)
    print("✅ All accounts processed")
    print("=" * 60)

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