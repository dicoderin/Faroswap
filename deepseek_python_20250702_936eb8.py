#!/usr/bin/env python3
"""
PHAROS X Faroswap Auto Tx Bot - Modern CLI Version

Dependencies: web3, eth-account, aiohttp, fake-useragent, colorama

Install all dependencies with:
    pip install web3 eth-account aiohttp fake-useragent colorama

Put private keys in pkey.txt (one per line)
"""

import asyncio
import json
import os
import random
import time
import sys
import secrets
from eth_utils import to_hex
from eth_account import Account
from eth_account.messages import encode_defunct
from aiohttp import ClientSession, ClientTimeout
from fake_useragent import FakeUserAgent
from colorama import init, Fore, Style
from web3 import Web3
from web3.exceptions import TransactionNotFound

# Initialize colorama for colored output
init(autoreset=True)

class PharosTestnet:
    def __init__(self):
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": "https://testnet.pharosnetwork.xyz",
            "Referer": "https://testnet.pharosnetwork.xyz/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": FakeUserAgent().random
        }
        self.BASE_API = "https://api.pharosnetwork.xyz"
        self.RPC_URL = "https://api.zan.top/node/v1/pharos/testnet/f4a9eb274053406d91e67c193867a80a"
        self.TOKENS = {
            "PHRS": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            "WBTC": "0x8275c526d1bCEc59a31d673929d3cE8d108fF5c7",
            "WETH": "0x4E28826d32F1C398DED160DC16Ac6873357d048f",
            "USDC": "0x72df0bcd7276f2dFbAc900D1CE63c272C4BCcCED",
            "USDT": "0xD4071393f8716661958F766DF660033b3d35fD29",
            "WPHRS": "0x3019B247381c850ab53Dc0EE53bCe7A07Ea9155f"
        }
        self.POSITION_MANAGER_ADDRESS = "0x4b177aded3b8bd1d5d747f91b9e853513838cd49"
        self.SWAP_ROUTER_ADDRESS = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
        self.EXPLORER_URL = "https://pharos-testnet.socialscan.io/tx"
        self.PHAROS_NAME_CONTRACT = "0x51be1ef20a1fd5179419738fc71d95a8b6f8a175"
        self.PHAROS_NAME_API = "https://test.pharosname.com/api/check?name="
        
        # ABI for Pharos Name Service
        self.PHAROS_NAME_ABI = json.loads('''[
            {
                "inputs": [{"internalType": "bytes32", "name": "commitment", "type": "bytes32"}],
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
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]''')
        
        # Existing contract ABIs
        self.ERC20_CONTRACT_ABI = json.loads('''[
            {
                "type": "function",
                "name": "balanceOf",
                "stateMutability": "view",
                "inputs": [{"name": "address", "type": "address"}],
                "outputs": [{"name": "", "type": "uint256"}]
            },
            {
                "type": "function",
                "name": "allowance",
                "stateMutability": "view",
                "inputs": [
                    {"name": "owner", "type": "address"},
                    {"name": "spender", "type": "address"}
                ],
                "outputs": [{"name": "", "type": "uint256"}]
            },
            {
                "type": "function",
                "name": "approve",
                "stateMutability": "nonpayable",
                "inputs": [
                    {"name": "spender", "type": "address"},
                    {"name": "amount", "type": "uint256"}
                ],
                "outputs": [{"name": "", "type": "bool"}]
            },
            {
                "type": "function",
                "name": "decimals",
                "stateMutability": "view",
                "inputs": [],
                "outputs": [{"name": "", "type": "uint8"}]
            },
            {
                "type": "function",
                "name": "deposit",
                "stateMutability": "payable",
                "inputs": [],
                "outputs": []
            },
            {
                "type": "function",
                "name": "withdraw",
                "stateMutability": "nonpayable",
                "inputs": [{"name": "wad", "type": "uint256"}],
                "outputs": []
            }
        ]''')
        self.ADD_LP_CONTRACT_ABI = json.loads('''[
            {
                "inputs": [
                    {
                        "components": [
                            {"internalType": "address", "name": "token0", "type": "address"},
                            {"internalType": "address", "name": "token1", "type": "address"},
                            {"internalType": "uint24", "name": "fee", "type": "uint24"},
                            {"internalType": "int24", "name": "tickLower", "type": "int24"},
                            {"internalType": "int24", "name": "tickUpper", "type": "int24"},
                            {"internalType": "uint256", "name": "amount0Desired", "type": "uint256"},
                            {"internalType": "uint256", "name": "amount1Desired", "type": "uint256"},
                            {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
                            {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
                            {"internalType": "address", "name": "recipient", "type": "address"},
                            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                        ],
                        "internalType": "struct INonfungiblePositionManager.MintParams",
                        "name": "params",
                        "type": "tuple"
                    }
                ],
                "name": "mint",
                "outputs": [
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                    {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
                    {"internalType": "uint256", "name": "amount0", "type": "uint256"},
                    {"internalType": "uint256", "name": "amount1", "type": "uint256"}
                ],
                "stateMutability": "payable",
                "type": "function"
            }
        ]''')
        self.SWAP_ROUTER_ABI = json.loads('''[
            {
                "inputs": [
                    {
                        "components": [
                            {"internalType": "address", "name": "tokenIn", "type": "address"},
                            {"internalType": "address", "name": "tokenOut", "type": "address"},
                            {"internalType": "uint24", "name": "fee", "type": "uint24"},
                            {"internalType": "address", "name": "recipient", "type": "address"},
                            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                            {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                            {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
                        ],
                        "internalType": "struct ISwapRouter.ExactInputSingleParams",
                        "name": "params",
                        "type": "tuple"
                    }
                ],
                "name": "exactInputSingle",
                "outputs": [
                    {"internalType": "uint256", "name": "amountOut", "type": "uint256"}
                ],
                "stateMutability": "payable",
                "type": "function"
            }
        ]''')
        
        self.ref_code = "8G8MJ3zGE5B7tJgP"
        self.signatures = {}
        self.access_tokens = {}
        self.wrap_option = None
        self.wrap_amount = 0
        self.swap_amount = 0
        self.auto_all_count = 0
        self.swap_count = 0
        self.mint_count = 0

    def log(self, message, indent=0, color=Fore.WHITE):
        print(f"{'  ' * indent}{color}{message}{Style.RESET_ALL}")

    def loading_animation(self):
        animation = "|/-\\"
        for i in range(10):
            sys.stdout.write(f"\r{Fore.YELLOW}Initializing{animation[i % len(animation)]}")
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write("\r" + " " * 20 + "\r")
        sys.stdout.flush()

    def display_menu(self):
        banner = """
███████╗ █████╗ ██████╗  ██████╗ ███████╗██╗    ██╗ █████╗ ██████╗ 
██╔════╝██╔══██╗██╔══██╗██╔═══██╗██╔════╝██║    ██║██╔══██╗██╔══██╗
█████╗  ███████║██████╔╝██║   ██║███████╗██║ █╗ ██║███████║██████╔╝
██╔══╝  ██╔══██║██╔══██╗██║   ██║╚════██║██║███╗██║██╔══██║██╔═══╝ 
██║     ██║  ██║██║  ██║╚██████╔╝███████║╚███╔███╔╝██║  ██║██║     
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝     
"""
        print(f"{Style.BRIGHT + Fore.CYAN}{banner}")
        print(f"{Style.BRIGHT + Fore.MAGENTA}{'=' * 50}")
        print(f"{Fore.CYAN}     PHAROS X Faroswap Auto Tx Bot By Kazuha         ")
        print(f"{Fore.CYAN}           LETS FUCK THIS TESTNET           ")
        print(f"{Style.BRIGHT + Fore.MAGENTA}{'=' * 50}")
        print(f"{Fore.GREEN}1. Wrap PHRS to WPHRS")
        print(f"{Fore.YELLOW}2. Unwrap WPHRS to PHRS")
        print(f"{Fore.CYAN}3. Auto All (Wrap, Unwrap, Swap, Liquidity)")
        print(f"{Fore.WHITE}4. Swap Tokens")
        print(f"{Fore.BLUE}5. Mint Pharos Name")
        print(f"{Fore.RED}6. Exit")
        print(f"{Style.BRIGHT + Fore.MAGENTA}{'=' * 50}")

    def generate_address(self, account):
        try:
            account = Account.from_key(account)
            return account.address
        except Exception as e:
            self.log(f"Generate Address Failed: {e}", indent=1, color=Fore.RED)
            return None

    def generate_signature(self, account):
        try:
            encoded_message = encode_defunct(text="pharos")
            signed_message = Account.sign_message(encoded_message, private_key=account)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    return to_hex(signed_message.signature)
                except Exception as e:
                    if attempt < max_retries - 1:
                        self.log(f"Signature attempt {attempt + 1} failed: {e}, retrying...", indent=1, color=Fore.YELLOW)
                        time.sleep(2)
                    else:
                        self.log(f"Generate Signature Failed after {max_retries} attempts: {e}", indent=1, color=Fore.RED)
                        return None
        except Exception as e:
            self.log(f"Generate Signature Failed: {e}", indent=1, color=Fore.RED)
            return None

    def mask_account(self, account):
        try:
            return account[:4] + '*' * 4 + account[-4:]
        except:
            return None

    async def get_web3(self, retries=3, timeout=60):
        for attempt in range(retries):
            try:
                web3 = Web3(Web3.HTTPProvider(self.RPC_URL, request_kwargs={"timeout": timeout}))
                web3.eth.get_block_number()
                return web3
            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(3)
                    continue
                self.log(f"Failed to Connect to RPC: {e}", indent=1, color=Fore.RED)
                return None

    async def _wait_for_tx_receipt(self, web3, tx_hash, timeout):
        loop = asyncio.get_event_loop()
        func = lambda: web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        return await loop.run_in_executor(None, func)

    # ========================
    # PHAROS NAME FUNCTIONS
    # ========================
    
    async def check_username_availability(self, username):
        """Check if a username is available using Pharos Name API"""
        try:
            url = f"{self.PHAROS_NAME_API}{username}"
            async with ClientSession(timeout=ClientTimeout(total=30)) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('available', False)
                    return False
        except Exception as e:
            self.log(f"Username check failed: {e}", indent=2, color=Fore.RED)
            return False

    def generate_5digit_username(self):
        """Generate a random 5-digit username"""
        return ''.join(str(random.randint(0, 9)) for _ in range(5))

    async def find_available_username(self, max_attempts=20):
        """Find an available 5-digit username"""
        attempts = 0
        while attempts < max_attempts:
            username = self.generate_5digit_username()
            if await self.check_username_availability(username):
                return username
            attempts += 1
            await asyncio.sleep(0.5)
        return None

    async def commit_username(self, account, address, secret):
        """Commit username registration"""
        try:
            web3 = await self.get_web3()
            if not web3:
                return None, None
            
            contract = web3.eth.contract(
                address=web3.to_checksum_address(self.PHAROS_NAME_CONTRACT),
                abi=self.PHAROS_NAME_ABI
            )
            
            # Generate commitment hash
            commitment = web3.keccak(text=secret)
            
            # Build commit transaction
            commit_tx = contract.functions.commit(commitment).build_transaction({
                'from': address,
                'nonce': web3.eth.get_transaction_count(address, 'pending'),
                'gas': 200000,
                'gasPrice': web3.to_wei('1.5', 'gwei'),
                'chainId': web3.eth.chain_id
            })
            
            # Sign and send transaction
            signed_tx = web3.eth.account.sign_transaction(commit_tx, account)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_receipt = await self._wait_for_tx_receipt(web3, tx_hash, 300)
            
            return web3.to_hex(tx_hash), tx_receipt.blockNumber
        except Exception as e:
            self.log(f"Commit failed: {e}", indent=2, color=Fore.RED)
            return None, None

    async def register_username(self, account, address, username, secret):
        """Register username after commit"""
        try:
            web3 = await self.get_web3()
            if not web3:
                return None, None
            
            contract = web3.eth.contract(
                address=web3.to_checksum_address(self.PHAROS_NAME_CONTRACT),
                abi=self.PHAROS_NAME_ABI
            )
            
            # Convert secret to bytes32
            secret_bytes = web3.keccak(text=secret)
            
            # Build register transaction
            register_tx = contract.functions.register(
                username,
                address,
                secret_bytes
            ).build_transaction({
                'from': address,
                'nonce': web3.eth.get_transaction_count(address, 'pending'),
                'gas': 300000,
                'gasPrice': web3.to_wei('1.5', 'gwei'),
                'chainId': web3.eth.chain_id
            })
            
            # Sign and send transaction
            signed_tx = web3.eth.account.sign_transaction(register_tx, account)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_receipt = await self._wait_for_tx_receipt(web3, tx_hash, 300)
            
            return web3.to_hex(tx_hash), tx_receipt.blockNumber
        except Exception as e:
            self.log(f"Registration failed: {e}", indent=2, color=Fore.RED)
            return None, None

    async def mint_pharos_name(self, account, address):
        """Full process to mint a Pharos Name"""
        try:
            # Step 1: Find available username
            self.log("Finding available username...", indent=1, color=Fore.YELLOW)
            username = await self.find_available_username()
            
            if not username:
                self.log("Failed to find available username after multiple attempts", indent=1, color=Fore.RED)
                return False
                
            self.log(f"Found available username: {username}", indent=1, color=Fore.GREEN)
            
            # Step 2: Generate random secret
            secret = secrets.token_hex(16)
            
            # Step 3: Commit username
            self.log("Committing username...", indent=1, color=Fore.YELLOW)
            commit_hash, commit_block = await self.commit_username(account, address, secret)
            
            if not commit_hash:
                self.log("Commit transaction failed", indent=1, color=Fore.RED)
                return False
                
            self.log(f"Commit successful! Block: {commit_block}", indent=1, color=Fore.GREEN)
            self.log(f"Tx: {commit_hash}", indent=1, color=Fore.CYAN)
            self.log(f"Explorer: {self.EXPLORER_URL}/{commit_hash}", indent=1, color=Fore.CYAN)
            
            # Wait for commit to be processed
            self.log("Waiting for commit confirmation...", indent=1, color=Fore.YELLOW)
            await asyncio.sleep(15)
            
            # Step 4: Register username
            self.log("Registering username...", indent=1, color=Fore.YELLOW)
            register_hash, register_block = await self.register_username(account, address, username, secret)
            
            if not register_hash:
                self.log("Registration transaction failed", indent=1, color=Fore.RED)
                return False
                
            self.log(f"Registration successful! Block: {register_block}", indent=1, color=Fore.GREEN)
            self.log(f"Tx: {register_hash}", indent=1, color=Fore.CYAN)
            self.log(f"Explorer: {self.EXPLORER_URL}/{register_hash}", indent=1, color=Fore.CYAN)
            self.log(f"Username '{username}' minted successfully!", indent=1, color=Fore.GREEN)
            
            return True
        except Exception as e:
            self.log(f"Minting process failed: {e}", indent=1, color=Fore.RED)
            return False

    # ========================
    # EXISTING FUNCTIONS
    # ========================
    
    async def get_token_balance(self, address, token_symbol):
        # ... (existing implementation) ...
        
    async def perform_wrapped(self, account, address):
        # ... (existing implementation) ...
        
    async def perform_unwrapped(self, account, address):
        # ... (existing implementation) ...
        
    async def approving_token(self, account, address, spender_address, contract_address, amount):
        # ... (existing implementation) ...
        
    async def perform_add_liquidity(self, account, address, add_lp_option, token0, token1, amount0, amount1):
        # ... (existing implementation) ...
        
    async def perform_swap(self, account, address, token_in_symbol, token_out_symbol, amount_in):
        # ... (existing implementation) ...
        
    async def process_perform_wrapped(self, account, address, iteration=None, total_iterations=None):
        # ... (existing implementation) ...
        
    async def process_perform_unwrapped(self, account, address, iteration=None, total_iterations=None):
        # ... (existing implementation) ...
        
    async def process_perform_add_liquidity(self, account, address, add_lp_option, token0, token1, amount0, amount1, ticker0, ticker1, iteration, total_iterations):
        # ... (existing implementation) ...
        
    async def process_perform_swap(self, account, address, token_in_symbol, token_out_symbol, amount_in, iteration, total_iterations):
        # ... (existing implementation) ...
        
    def generate_add_lp_option(self):
        # ... (existing implementation) ...
        
    def generate_swap_option(self):
        # ... (existing implementation) ...
        
    async def user_login(self, address, retries=5):
        # ... (existing implementation) ...
        
    async def process_user_login(self, address):
        # ... (existing implementation) ...
        
    async def process_option_3(self, account, address):
        # ... (existing implementation) ...
        
    async def process_option_4(self, account, address):
        # ... (existing implementation) ...
        
    def print_question(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.display_menu()
        while True:
            try:
                option = int(input(f"{Style.BRIGHT + Fore.CYAN}Enter your choice (1-6): ").strip())
                if option in [1, 2, 3, 4, 5, 6]:
                    if option == 6:
                        print(f"{Style.BRIGHT + Fore.RED}Exiting...")
                        sys.exit(0)
                    self.log(f"Option {option} Selected.", indent=0, color=Fore.GREEN)
                    break
                print(f"{Style.BRIGHT + Fore.RED}Invalid choice. Please enter 1, 2, 3, 4, 5, or 6.")
            except ValueError:
                print(f"{Style.BRIGHT + Fore.RED}Invalid input. Enter a number (1-6).")

        if option in [1, 2, 3]:
            while True:
                try:
                    wrap_amount = float(input(f"{Style.BRIGHT + Fore.CYAN}Enter Amount for Wrap/Unwrap [e.g., 1, 0.01, 0.001]: ").strip())
                    if wrap_amount > 0:
                        self.wrap_amount = wrap_amount
                        break
                    print(f"{Style.BRIGHT + Fore.RED}Amount must be greater than 0.")
                except ValueError:
                    print(f"{Style.BRIGHT + Fore.RED}Invalid input. Enter a float or decimal number.")
            if option == 3:
                while True:
                    try:
                        self.auto_all_count = int(input(f"{Style.BRIGHT + Fore.CYAN}How Many Times for Auto All (Wrap, Unwrap, Swap, Liquidity)?: ").strip())
                        if self.auto_all_count > 0:
                            break
                        print(f"{Style.BRIGHT + Fore.RED}Please enter a positive number.")
                    except ValueError:
                        print(f"{Style.BRIGHT + Fore.RED}Invalid input. Enter a number.")
        if option == 4:
            while True:
                try:
                    self.swap_count = int(input(f"{Style.BRIGHT + Fore.CYAN}How Many Times to Swap Tokens?: ").strip())
                    if self.swap_count > 0:
                        break
                    print(f"{Style.BRIGHT + Fore.RED}Please enter a positive number.")
                except ValueError:
                    print(f"{Style.BRIGHT + Fore.RED}Invalid input. Enter a number.")
        if option == 5:
            while True:
                try:
                    self.mint_count = int(input(f"{Style.BRIGHT + Fore.CYAN}How Many Names to Mint?: ").strip())
                    if self.mint_count > 0:
                        break
                    print(f"{Style.BRIGHT + Fore.RED}Please enter a positive number.")
                except ValueError:
                    print(f"{Style.BRIGHT + Fore.RED}Invalid input. Enter a number.")

        self.wrap_option = option
        return option

    async def process_accounts(self, account, address):
        if await self.process_user_login(address):
            if self.wrap_option == 1:
                self.log("Option: Wrap PHRS to WPHRS", indent=0, color=Fore.BLUE)
                await self.process_perform_wrapped(account, address)
            elif self.wrap_option == 2:
                self.log("Option: Unwrap WPHRS to PHRS", indent=0, color=Fore.BLUE)
                await self.process_perform_unwrapped(account, address)
            elif self.wrap_option == 3:
                self.log("Option: Auto All (Wrap, Unwrap, Swap, Liquidity)", indent=0, color=Fore.BLUE)
                await self.process_option_3(account, address)
            elif self.wrap_option == 4:
                self.log("Option: Swap Tokens", indent=0, color=Fore.BLUE)
                await self.process_option_4(account, address)
            elif self.wrap_option == 5:
                self.log("Option: Mint Pharos Name", indent=0, color=Fore.BLUE)
                for i in range(self.mint_count):
                    self.log(f"Minting name {i+1}/{self.mint_count}", indent=1, color=Fore.YELLOW)
                    await self.mint_pharos_name(account, address)
                    if i < self.mint_count - 1:
                        self.log("Waiting before next mint...", indent=1, color=Fore.YELLOW)
                        await asyncio.sleep(10)

    async def main(self):
        self.loading_animation()
        try:
            with open('pkey.txt', 'r') as file:
                accounts = [line.strip() for line in file if line.strip()]
            self.log(f"Total Accounts: {len(accounts)}", indent=0, color=Fore.BLUE)
            while True:
                option = self.print_question()
                for i, account in enumerate(accounts, 1):
                    self.log(f"\nProcessing Account {i}/{len(accounts)}: {self.mask_account(self.generate_address(account))}", indent=0, color=Fore.BLUE)
                    address = self.generate_address(account)
                    signature = self.generate_signature(account)
                    if not address or not signature:
                        self.log("Invalid Private Key or Library Not Supported", indent=1, color=Fore.RED)
                        continue
                    self.signatures[address] = signature
                    await self.process_accounts(account, address)
                    if i < len(accounts):
                        self.log("Waiting before next account...", indent=1, color=Fore.YELLOW)
                        await asyncio.sleep(5)
                print(f"\n{Style.BRIGHT + Fore.CYAN}Run again? (y/n): ", end='')
                if input().strip().lower() != 'y':
                    print(f"{Style.BRIGHT + Fore.RED}Exiting...")
                    break
        except FileNotFoundError:
            self.log("File 'pkey.txt' Not Found. Create it and add private keys.", indent=0, color=Fore.RED)
        except Exception as e:
            self.log(f"Error: {e}", indent=0, color=Fore.RED)

if __name__ == "__main__":
    try:
        bot = PharosTestnet()
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        print(f"\n{Style.BRIGHT + Fore.RED}Pharos Testnet - BOT Exited")