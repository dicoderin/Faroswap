#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pharos Username Minter v7.2
Automated two-step commit-register process for minting usernames on Pharos.
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

# Load environment variables
load_dotenv()

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
    """Inject POA middleware for compatibility"""
    try:
        from web3.middleware import geth_poa_middleware
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        print("âœ… POA middleware injected (geth_poa_middleware)")
    except ImportError:
        print("âš ï¸ POA middleware injection failed. Ensure web3.py is up to date.")

def print_banner():
    """Print application banner"""
    print(r"""
â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ•—  â–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—  â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—
â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â•â•â•
â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—
â–ˆâ–ˆâ•”â•â•â•â• â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â•šâ•â•â•â•â–ˆâ–ˆâ•‘
â–ˆâ–ˆâ•‘     â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â•šâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘
â•šâ•â•     â•šâ•â•  â•šâ•â•â•šâ•â•  â•šâ•â•â•šâ•â•  â•šâ•â• â•šâ•â•â•â•â•â• â•šâ•â•â•â•â•â•â•
    """)
    print("Pharos Username Minter v7.2 | Two-Step Commit-Register (FIXED)")
    print("=" * 60)
    print(f"Blockchain: Pharos Testnet (Chain ID: {os.getenv('CHAIN_ID', '688688')}")
    print("=" * 60)

# =============================================
# MAIN MINTER CLASS
# =============================================
class PharosMultiMinter:
    def __init__(self, private_key, user_agent=None):
        # Validate private key
        if not private_key or private_key == '0x' + '0'*64:
            raise ValueError("Invalid private key")

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
        print(f"ðŸ”— Connecting to RPC: {rpc_url}")

        self.w3 = Web3(Web3.HTTPProvider(
            rpc_url,
            session=self.session,
            request_kwargs={'timeout': 120}
        ))

        # Inject POA middleware
        inject_poa_middleware(self.w3)

        # Check connection
        if not self.w3.is_connected():
            raise ConnectionError("âŒ Failed to connect to RPC endpoint")
        print("âœ… Connected to blockchain")

        # Load account
        self.account = self.w3.eth.account.from_key(private_key)
        self.contract_address = Web3.to_checksum_address(
            os.getenv('CONTRACT_ADDRESS', '0x51be1ef20a1fd5179419738fc71d5a8b6f8a175')
        )

        # Initialize contract
        try:
            self.contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=CONTRACT_ABI
            )
            print(f"ðŸ“œ Contract loaded: {self.contract_address}")
        except Exception as e:
            raise ValueError(f"âŒ Contract initialization failed: {str(e)}")

        # Initialize gas price history
        self.gas_price_history = []
        self.max_history_size = 5

        # Initialize chain ID
        self.chain_id = int(os.getenv('CHAIN_ID', 688688))

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
        """Generate commitment hash for username"""
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
                from Crypto.Hash import keccak
                name_bytes = name.encode('utf-8')
                namehash = keccak.new(digest_bits=256).update(name_bytes).digest()
                commitment = keccak.new(digest_bits=256).update(namehash + secret).digest()
                return commitment

    def get_min_commitment_age(self):
        """Get minimum commitment age in seconds"""
        try:
            return self.contract.functions.minCommitmentAge().call()
        except Exception as e:
            print(f"âš ï¸ Failed to get min commitment age: {str(e)}")
            return 60  # Default to 60 seconds

    def get_minting_fee(self):
        """Get minting fee in wei"""
        try:
            return self.contract.functions.mintingFee().call()
        except Exception as e:
            print(f"âš ï¸ Failed to get minting fee: {str(e)}")
            # Return default fee if failed
            return Web3.to_wei(0.01, 'ether')

    def get_balance(self):
        """Get account balance in PHRS"""
        try:
            balance = self.w3.eth.get_balance(self.account.address)
            return Web3.from_wei(balance, 'ether')
        except Exception as e:
            print(f"âš ï¸ Failed to get balance: {str(e)}")
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
            print(f"âš ï¸ 'available' function error: {error_msg}")
            return False
        except Exception as e:
            print(f"âš ï¸ 'available' function error: {str(e)}")
            return False

    def get_gas_price(self):
        """
        Automatically detect gas price with multiple fallbacks
        Returns optimal gas price in wei
        """
        gas_prices = []

        # Method 1: Direct gas_price query
        try:
            gas_price = self.w3.eth.gas_price
            gas_prices.append(gas_price)
            print(f"  ðŸ’¡ Method 1 gas price: {Web3.from_wei(gas_price, 'gwei')} gwei")
        except Exception as e:
            print(f"  âš ï¸ Method 1 failed: {str(e)}")

        # Method 2: eth_gasPrice RPC call
        try:
            gas_price = self.w3.manager.request_blocking("eth_gasPrice", [])
            if isinstance(gas_price, str) and gas_price.startswith("0x"):
                gas_price = int(gas_price, 16)
            gas_prices.append(gas_price)
            print(f"  ðŸ’¡ Method 2 gas price: {Web3.from_wei(gas_price, 'gwei')} gwei")
        except Exception as e:
            print(f"  âš ï¸ Method 2 failed: {str(e)}")

        # Method 3: Use history if available
        if self.gas_price_history:
            historical_avg = statistics.median(self.gas_price_history)
            gas_prices.append(historical_avg)
            print(f"  ðŸ’¡ Method 3 historical median: {Web3.from_wei(historical_avg, 'gwei')} gwei")

        # Choose final gas price
        if gas_prices:
            # Use the median to avoid outliers
            final_gas_price = statistics.median(gas_prices)

            # Add small random adjustment to avoid stuck transactions (Â±5%)
            adjustment = random.uniform(0.95, 1.05)
            final_gas_price = int(final_gas_price * adjustment)

            # Update history for future use
            self.gas_price_history.append(final_gas_price)
            if len(self.gas_price_history) > self.max_history_size:
                self.gas_price_history.pop(0)

            print(f"  â›½ Final gas price: {Web3.from_wei(final_gas_price, 'gwei')} gwei")
            return final_gas_price
        else:
            # Fallback to safe default (20 gwei)
            default_gas = Web3.to_wei(20, 'gwei')
            print(f"  âš ï¸ All methods failed, using default: {Web3.from_wei(default_gas, 'gwei')} gwei")
            return default_gas

    def estimate_commit_gas(self, commitment):
        """Estimate gas for commit transaction"""
        try:
            gas_estimate = self.contract.functions.commit(commitment).estimate_gas({
                'from': self.account.address
            })
            # Add 30% buffer for commit
            gas_limit = int(gas_estimate * 1.3)
            print(f"  â›½ Commit gas estimate: {gas_estimate} (using {gas_limit})")
            return gas_limit
        except Exception as e:
            print(f"  âš ï¸ Commit gas estimation failed: {str(e)}")
            # Return safe default
            return 150000

    def estimate_register_gas(self, full_username, owner, secret, fee):
        """Estimate gas for register transaction"""
        try:
            gas_estimate = self.contract.functions.register(
                full_username,
                owner,
                secret
            ).estimate_gas({
                'from': self.account.address,
                'value': fee
            })
            # Add 50% buffer for register (higher complexity)
            gas_limit = int(gas_estimate * 1.5)
            print(f"  â›½ Register gas estimate: {gas_estimate} (using {gas_limit})")
            return gas_limit
        except Exception as e:
            print(f"  âš ï¸ Register gas estimation failed: {str(e)}")
            # Return higher default for register
            return 450000

    def sign_and_send_transaction(self, tx):
        """Sign and send transaction with compatibility for different Web3.py versions"""
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
            print(f"  âŒ Transaction signing/sending failed: {str(e)}")
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
                'gas': gas_limit
            }

            # Build transaction
            tx = self.contract.functions.commit(commitment).build_transaction(tx_params)

            # Sign and send transaction
            tx_hash = self.sign_and_send_transaction(tx)
            if not tx_hash:
                return None

            print(f"  ðŸ”— Commit transaction sent: {tx_hash.hex()}")

            # Wait for commit confirmation
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
                if receipt.status == 1:
                    print("  âœ… Commitment confirmed")
                    return secret
                else:
                    print("  âŒ Commitment failed")
                    return None
            except TimeExhausted:
                print("  â±ï¸ Commit transaction timeout, but continuing...")
                # Return secret anyway, might still work
                return secret

        except Exception as e:
            print(f"  âš ï¸ Commitment failed: {str(e)}")
            return None

    def register_username(self, full_username, secret):
        """Register username after commitment"""
        try:
            fee = self.get_minting_fee()
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
                'gas': gas_limit
            }

            # Build register transaction
            tx = self.contract.functions.register(
                full_username,
                self.account.address,
                secret
            ).build_transaction(tx_params)

            # Sign and send transaction
            tx_hash = self.sign_and_send_transaction(tx)
            if not tx_hash:
                return None

            print(f"  ðŸ”— Register transaction sent: {tx_hash.hex()}")

            # Wait for register confirmation
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                if receipt.status == 1:
                    print("  âœ… Registration successful")
                    return tx_hash
                else:
                    print("  âŒ Registration failed")
                    return None
            except TimeExhausted:
                print("  â±ï¸ Register transaction timeout")
                return tx_hash  # Return hash even if timeout for tracking

        except Exception as e:
            print(f"  âš ï¸ Registration failed: {str(e)}")
            return None

    def mint_username(self, max_attempts=5):
        """
        Mint a new username using the two-step commit-register process
        Will attempt up to max_attempts times to find an available name
        """
        for attempt in range(max_attempts):
            username = self.generate_username()
            full_username = f"{username}.phrs"

            # Check availability
            try:
                if not self.is_username_available(full_username):
                    print(f"  âŒ [{attempt+1}/{max_attempts}] Taken: {full_username}")
                    time.sleep(0.5)  # Short delay between checks
                    continue
            except Exception as e:
                print(f"  âš ï¸ Availability check failed: {str(e)}")
                time.sleep(1)
                continue

            print(f"  âœ… [{attempt+1}/{max_attempts}] Available: {full_username}")

            # Step 1: Make commitment
            print("  ðŸ” Making commitment...")
            secret = self.make_commitment(full_username)
            if not secret:
                print("  âŒ Commitment failed, trying another name")
                time.sleep(1)
                continue

            # Wait for commitment to mature (prevent front-running)
            min_age = self.get_min_commitment_age()
            wait_time = max(min_age, 60)  # Minimum 60 seconds
            print(f"  â³ Waiting {wait_time} seconds for commitment to mature...")
            time.sleep(wait_time)

            # Step 2: Register username
            print("  ðŸ“ Registering username...")
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

            time.sleep(1.5)  # Delay between mint attempts

        return {'status': 'failed', 'reason': 'No available names found after attempts'}

# =============================================
# LOAD ACCOUNTS
# =============================================
def load_accounts():
    """Load account configurations from environment"""
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

# =============================================
# MAIN FUNCTION
# =============================================
def main():
    """Main function"""
    print_banner()

    try:
        accounts = load_accounts()
    except ValueError as e:
        print(f"âŒ {str(e)}")
        sys.exit(1)

    print(f"\nðŸ” Found {len(accounts)} account(s) to process")

    total_success = 0
    total_failed = 0
    total_pending = 0

    for i, account in enumerate(accounts):
        print(f"\n{'=' * 60}")
        print(f"ðŸ”‘ Processing Account {i+1}: {account['name']}")
        print(f"ðŸ“± User Agent: {account['user_agent']}")
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

                print(f"ðŸ’¼ Wallet: {address}")
                print(f"ðŸ’° Balance: {balance:.6f} PHRS")
                print(f"â›½ Minting Fee: {fee_eth:.6f} PHRS")

                # Check balance
                if balance < fee_eth:
                    print(f"âŒ Insufficient balance. Needed: {fee_eth:.6f} PHRS")
                    print("Visit testnet faucet if available")
                    total_failed += 1
                    continue
            except Exception as e:
                print(f"âš ï¸ Failed to get account info: {str(e)}")
                print("Continuing with minting attempt...")

            # Start minting
            print("\nðŸš€ Starting two-step minting process...")
            start_time = time.time()
            result = minter.mint_username(max_attempts=7)
            elapsed = time.time() - start_time

            if result and result['status'] == 'success':
                print(f"\nðŸŽ‰ Username Minted Successfully in {elapsed:.2f}s!")
                print(f"ðŸ”‘ Username: {result['username']}")
                print(f"ðŸ”— View transaction: {result['explorer_url']}")
                total_success += 1
            elif result and result['status'] == 'pending':
                print(f"\nâ±ï¸ Transaction pending after {elapsed:.2f}s")
                print(f"ðŸ”— Track transaction: {result.get('explorer_url', 'N/A')}")
                total_pending += 1
            else:
                print(f"\nâŒ Minting failed after {elapsed:.2f}s")
                reason = result.get('reason', 'Unknown error') if result else 'No result returned'
                print(f"Reason: {reason}")
                total_failed += 1

            print(f"\nâ±ï¸ Account processing time: {elapsed:.2f} seconds")

        except Exception as e:
            print(f"\nâš ï¸ Critical error in account processing: {str(e)}")
            import traceback
            traceback.print_exc()
            print("Skipping to next account...")
            total_failed += 1

        # Delay between accounts
        if i < len(accounts) - 1:
            delay = 15
            print(f"\nâ³ Waiting {delay} seconds before next account...")
            time.sleep(delay)

    print("\n" + "=" * 60)
    print("ðŸ“Š Minting Summary:")
    print(f"   âœ… Success: {total_success}")
    print(f"   â±ï¸ Pending: {total_pending}")
    print(f"   âŒ Failed: {total_failed}")
    print(f"   ðŸ”¢ Total Accounts: {len(accounts)}")
    print("=" * 60)
    print("âœ… All accounts processed")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nðŸš« Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nðŸ’¥ Unexpected global error: {str(e)}")
        sys.exit(1)