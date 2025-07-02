#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pharos Username Minter v7.3
Enhanced version with robust error handling and improved registration process
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
from eth_account.messages import encode_defunct
import logging

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
        
    except Exception as e:
        print(f"⚠️ POA middleware error: {str(e)}")

    # Always inject retry and timeout middleware
    try:
        from web3.middleware import http_retry_request_middleware
        w3.middleware_onion.inject(http_retry_request_middleware, layer=0)
        print("✅ Retry middleware injected")
    except Exception:
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
    print("Pharos Username Minter v7.3 | Enhanced Commit-Register Process")
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
        print(f"Python version: {sys.version.split()[0]}")
        print(f"Web3 version: {web3.__version__}")
        print("="*50)
        
        # Create custom session with headers
        self.session = requests.Session()
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
        
        # Use multiple RPC endpoints if available for fallback
        self.rpc_urls = [
            rpc_url,
            os.getenv('RPC_URL_FALLBACK_1', ''),
            os.getenv('RPC_URL_FALLBACK_2', '')
        ]
        self.rpc_urls = [url for url in self.rpc_urls if url]  # Filter empty URLs
        
        # Initialize with primary RPC
        self.w3 = Web3(Web3.HTTPProvider(
            self.rpc_urls[0],
            session=self.session,
            request_kwargs={'timeout': 120}
        ))
        
        # Inject POA middleware
        inject_poa_middleware(self.w3)
            
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
                self.w3 = Web3(Web3.HTTPProvider(
                    fallback_url,
                    session=self.session,
                    request_kwargs={'timeout': 120}
                ))
                inject_poa_middleware(self.w3)
                
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
        
        # Initialize cached values
        self.cached_minting_fee = None
        self.cached_min_commitment_age = None
        
        # Initialize chain ID
        self.chain_id = int(os.getenv('CHAIN_ID', 688688))
        
        # Success tracking
        self.registration_attempts = 0
        self.registration_successes = 0

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
                    from Crypto.Hash import keccak
                    name_bytes = name.encode('utf-8')
                    namehash = keccak.new(digest_bits=256).update(name_bytes).digest()
                    commitment = keccak.new(digest_bits=256).update(namehash + secret).digest()
                
                return commitment
            except Exception as e:
                print(f"⚠️ Commitment generation method {attempt+1} failed: {str(e)}")
                continue
                
        # If all methods fail, raise exception
        raise ValueError("Failed to generate commitment hash using any method")
    
    def retry_operation(self, operation, max_retries=None, retry_delay=1, 
                        backoff_factor=1.5, operation_name="Operation"):
        """Generic retry wrapper for operations that might fail temporarily"""
        if max_retries is None:
            max_retries = self.max_retries
            
        errors = []
        for attempt in range(max_retries):
            try:
                result = operation()
                if attempt > 0:
                    print(f"✅ {operation_name} succeeded on attempt {attempt+1}")
                return result
            except Exception as e:
                delay = retry_delay * (backoff_factor ** attempt)
                errors.append(str(e))
                print(f"⚠️ {operation_name} attempt {attempt+1}/{max_retries} failed: {str(e)}")
                print(f"   Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
        
        # All retries failed
        print(f"❌ {operation_name} failed after {max_retries} attempts")
        print(f"   Errors: {', '.join(errors[:3])}" + 
              (f" and {len(errors)-3} more" if len(errors) > 3 else ""))
        return None
    
    def get_min_commitment_age(self):
        """Get minimum commitment age in seconds with caching and retry"""
        # Use cached value if available
        if self.cached_min_commitment_age is not None:
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
            print("⚠️ Using default min commitment age of 60 seconds")
            return 60  # Default to 60 seconds
    
    def get_minting_fee(self):
        """Get minting fee in wei with caching and retry"""
        # Use cached value if available
        if self.cached_minting_fee is not None:
            return self.cached_minting_fee
            
        # Function to get fee
        def get_fee():
            return self.contract.functions.mintingFee().call()
        
        # Retry the operation
        fee = self.retry_operation(
            get_fee,
            max_retries=3,
            operation_name="Get minting fee"
        )
        
        if fee is not None:
            # Cache the value for future use
            self.cached_minting_fee = fee
            return fee
        else:
            # Return default fee if failed
            default_fee = Web3.to_wei(0.01, 'ether')
            print(f"⚠️ Using default minting fee of {Web3.from_wei(default_fee, 'ether')} PHRS")
            return default_fee

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
        
        # Choose final gas price
        if gas_prices:
            # Use the median to avoid outliers
            final_gas_price = statistics.median(gas_prices)
            
            # Add small random adjustment to avoid stuck transactions (±5%)
            adjustment = random.uniform(1.05, 1.15)  # Increase by 5-15% to ensure transactions go through
            final_gas_price = int(final_gas_price * adjustment)
            
            # Update history for future use
            self.gas_price_history.append(final_gas_price)
            if len(self.gas_price_history) > self.max_history_size:
                self.gas_price_history.pop(0)
            
            print(f"  ⛽ Final gas price: {Web3.from_wei(final_gas_price, 'gwei')} gwei")
            return final_gas_price
        else:
            # Fallback to safe default (30 gwei)
            default_gas = Web3.to_wei(30, 'gwei')
            print(f"  ⚠️ All methods failed, using default: {Web3.from_wei(default_gas, 'gwei')} gwei")
            return default_gas
    
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
            # Add 50% buffer for commit (up from 30% for more safety)
            gas_limit = int(gas_estimate * 1.5)
            print(f"  ⛽ Commit gas estimate: {gas_estimate} (using {gas_limit})")
            return gas_limit
        else:
            # Return safe default if estimation fails
            default_gas = 200000
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
            # Add 70% buffer for register (up from 50% for more safety)
            gas_limit = int(gas_estimate * 1.7)
            print(f"  ⛽ Register gas estimate: {gas_estimate} (using {gas_limit})")
            return gas_limit
        else:
            # Return higher default for register
            default_gas = 500000
            print(f"  ⚠️ Using default register gas limit: {default_gas}")
            return default_gas
    
    def sign_and_send_transaction(self, tx, operation_name="Transaction"):
        """Sign and send transaction with compatibility for various versions"""
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
            
            # Define send function
            def send_tx():
                return self.w3.eth.send_raw_transaction(raw_tx)
            
            # Retry send operation
            tx_hash = self.retry_operation(
                send_tx,
                max_retries=3,
                operation_name=f"Send {operation_name}"
            )
            
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
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.get_gas_price()
            
            # Estimate gas for commit (auto)
            gas_limit = self.estimate_commit_gas(commitment)
            
            tx_params = {
                'chainId': self.chain_id,
                'from': self.account.address,
                'nonce': nonce,
                'gasPrice': gas_price,
                'gas': gas_limit,
                # Add max fee per gas and priority fee for EIP-1559 support
                'maxFeePerGas': int(gas_price * 1.5),
                'maxPriorityFeePerGas': int(gas_price * 0.5)
            }
            
            # Remove EIP-1559 params if not supported
            if not hasattr(self.w3.eth, 'fee_history'):
                tx_params.pop('maxFeePerGas', None)
                tx_params.pop('maxPriorityFeePerGas', None)
            
            # Build transaction
            tx = self.contract.functions.commit(commitment).build_transaction(tx_params)
            
            # Sign and send transaction
            tx_hash = self.sign_and_send_transaction(tx, "Commit")
            if not tx_hash:
                return None
                
            print(f"  🔗 Commit transaction sent: {tx_hash.hex()}")
            
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
                    return secret
                else:
                    print("  ❌ Commitment failed (receipt status 0)")
                    return None
            else:
                print("  ⏱️ Commit confirmation timed out, but continuing...")
                # Return secret anyway as the transaction might still confirm
                return secret
                
        except Exception as e:
            print(f"  ⚠️ Commitment failed: {str(e)}")
            return None

    def register_username(self, full_username, secret):
        """Register username after commitment"""
        try:
            self.registration_attempts += 1
            fee = self.get_minting_fee()
            
            # Double-check if username is still available before registering
            if not self.is_username_available(full_username):
                print(f"  ⚠️ Username {full_username} is no longer available")
                return None
                
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.get_gas_price()
            
            # Estimate gas for register (auto)
            gas_limit = self.estimate_register_gas(
                full_username, 
                self.account.address, 
                secret, 
                fee
            )
            
            tx_params = {
                'chainId': self.chain_id,
                'from': self.account.address,
                'value': fee,
                'nonce': nonce,
                'gasPrice': gas_price,
                'gas': gas_limit,
                # Add max fee per gas and priority fee for EIP-1559 support
                'maxFeePerGas': int(gas_price * 1.5),
                'maxPriorityFeePerGas': int(gas_price * 0.5)
            }
            
            # Remove EIP-1559 params if not supported
            if not hasattr(self.w3.eth, 'fee_history'):
                tx_params.pop('maxFeePerGas', None)
                tx_params.pop('maxPriorityFeePerGas', None)
            
            # Build register transaction
            tx = self.contract.functions.register(
                full_username,
                self.account.address,
                secret
            ).build_transaction(tx_params)
            
            # Sign and send transaction
            tx_hash = self.sign_and_send_transaction(tx, "Register")
            if not tx_hash:
                return None
                
            print(f"  🔗 Register transaction sent: {tx_hash.hex()}")
            
            # Wait for register confirmation
            def wait_for_receipt():
                return self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            receipt = self.retry_operation(
                wait_for_receipt,
                max_retries=3,
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

    def mint_username(self, max_attempts=7):
        """
        Mint new username with two-step commit-register process
        Will try up to max_attempts times to find an available name
        """
        for attempt in range(max_attempts):
            # Generate longer username for better availability
            username = self.generate_username(length=random.randint(5, 8))
            full_username = f"{username}.phrs"
            
            # Check availability
            try:
                if not self.is_username_available(full_username):
                    print(f"  ❌ [{attempt+1}/{max_attempts}] Taken: {full_username}")
                    time.sleep(0.5)  # Short delay between checks
                    continue
            except Exception as e:
                print(f"  ⚠️ Availability check failed: {str(e)}")
                time.sleep(1)
                continue
            
            print(f"  ✅ [{attempt+1}/{max_attempts}] Available: {full_username}")
            
            # Step 1: Make commitment
            print("  🔐 Making commitment...")
            secret = self.make_commitment(full_username)
            if not secret:
                print("  ❌ Commitment failed, trying another name")
                time.sleep(1)
                continue
                
            # Wait for commitment to mature (prevent front-running)
            min_age = self.get_min_commitment_age()
            wait_time = max(min_age, 60)  # Minimum 60 seconds
            
            # Add safety margin (10 seconds) to ensure commitment is mature
            wait_time += 10
            
            print(f"  ⏳ Waiting {wait_time} seconds for commitment to mature...")
            
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
            print("  🔍 Verifying username is still available...")
            if not self.is_username_available(full_username):
                print(f"  ⚠️ Username {full_username} is no longer available, trying another")
                time.sleep(1)
                continue
            
            # Step 2: Register username
            print("  🔏 Registering username...")
            
            # Try register with retry logic
            for reg_attempt in range(3):  # 3 registration attempts per username
                tx_hash = self.register_username(full_username, secret)
                
                if tx_hash:
                    explorer_url = os.getenv(
                        'EXPLORER_BASE_URL', 
                        'https://testnet.pharosscan.xyz/tx/'
                    )
                    explorer_link = f"{explorer_url}{tx_hash.hex()}"
                    
                    return {
                        'status': 'success',
                        'username': full_username,
                        'tx_hash': tx_hash.hex(),
                        'explorer_url': explorer_link
                    }
                
                print(f"  ⚠️ Registration attempt {reg_attempt+1}/3 failed, retrying...")
                time.sleep(2)  # Wait before retry
            
            print("  ❌ All registration attempts failed for this username, trying another")
            time.sleep(1.5)  # Delay between mint attempts
        
        return {'status': 'failed', 'reason': 'No available names found after attempts'}

def load_accounts():
    """Load account configuration from environment"""
    accounts = []
    
    # Account 1 (iPhone 16 Pro Max)
    pk1 = os.getenv('PRIVATE_KEY_1')
    if pk1 and pk1 != '0x' + '0'*64:
        ua1 = os.getenv('USER_AGENT_1', "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        accounts.append({
            'name': 'Account 1 (iPhone 16 Pro Max)',
            'private_key': pk1,
            'user_agent': ua1
        })
    
    # Account 2 (iPhone 15)
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
    total_pending = 0
    
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
                
                # Get minting fee
                fee = minter.get_minting_fee()
                fee_eth = Web3.from_wei(fee, 'ether')
                
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
            
            # Start minting
            print("\n🚀 Starting two-step minting process...")
            start_time = time.time()
            result = minter.mint_username(max_attempts=7)
            elapsed = time.time() - start_time
            
            if result and result['status'] == 'success':
                print(f"\n🎉 Username Minted Successfully in {elapsed:.2f}s!")
                print(f"📝 Username: {result['username']}")
                print(f"🔗 View transaction: {result['explorer_url']}")
                total_success += 1
            elif result and result['status'] == 'pending':
                print(f"\n⏱️ Transaction pending after {elapsed:.2f}s")
                print(f"🔗 Track transaction: {result.get('explorer_url', 'N/A')}")
                total_pending += 1
            else:
                print(f"\n❌ Minting failed after {elapsed:.2f}s")
                reason = result.get('reason', 'Unknown error') if result else 'No result returned'
                print(f"Reason: {reason}")
                total_failed += 1
            
            print(f"\n⏱️ Account processing time: {elapsed:.2f} seconds")
            
        except Exception as e:
            print(f"\n⚠️ Critical error in account processing: {str(e)}")
            import traceback
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
    print(f"   ⏱️ Pending: {total_pending}")
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
        sys.exit(1)