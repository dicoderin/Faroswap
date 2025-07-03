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
from eth_utils import to_hex
from eth_account import Account
from eth_account.messages import encode_defunct
from aiohttp import ClientSession, ClientTimeout
from fake_useragent import FakeUserAgent
from colorama import init, Fore, Style

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
        self.ALT_RPC_URL = "https://pharos-testnet.rpc.socialscan.io"
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
        
        # Standard token ABIs
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
            },
            {
                "type": "function",
                "name": "transfer",
                "stateMutability": "nonpayable",
                "inputs": [
                    {"name": "recipient", "type": "address"},
                    {"name": "amount", "type": "uint256"}
                ],
                "outputs": [{"name": "", "type": "bool"}]
            },
            {
                "type": "function",
                "name": "transferFrom",
                "stateMutability": "nonpayable",
                "inputs": [
                    {"name": "sender", "type": "address"},
                    {"name": "recipient", "type": "address"},
                    {"name": "amount", "type": "uint256"}
                ],
                "outputs": [{"name": "", "type": "bool"}]
            },
            {
                "type": "function",
                "name": "name",
                "stateMutability": "view",
                "inputs": [],
                "outputs": [{"name": "", "type": "string"}]
            },
            {
                "type": "function",
                "name": "symbol",
                "stateMutability": "view",
                "inputs": [],
                "outputs": [{"name": "", "type": "string"}]
            },
            {
                "type": "function",
                "name": "totalSupply",
                "stateMutability": "view",
                "inputs": [],
                "outputs": [{"name": "", "type": "uint256"}]
            }
        ]''')
        
        # ERC721 NFT ABI
        self.ERC721_CONTRACT_ABI = json.loads('''[
            {
                "inputs": [
                    {"internalType": "string", "name": "name_", "type": "string"},
                    {"internalType": "string", "name": "symbol_", "type": "string"}
                ],
                "stateMutability": "nonpayable",
                "type": "constructor"
            },
            {
                "anonymous": false,
                "inputs": [
                    {"indexed": true, "internalType": "address", "name": "owner", "type": "address"},
                    {"indexed": true, "internalType": "address", "name": "approved", "type": "address"},
                    {"indexed": true, "internalType": "uint256", "name": "tokenId", "type": "uint256"}
                ],
                "name": "Approval",
                "type": "event"
            },
            {
                "anonymous": false,
                "inputs": [
                    {"indexed": true, "internalType": "address", "name": "owner", "type": "address"},
                    {"indexed": true, "internalType": "address", "name": "operator", "type": "address"},
                    {"indexed": false, "internalType": "bool", "name": "approved", "type": "bool"}
                ],
                "name": "ApprovalForAll",
                "type": "event"
            },
            {
                "anonymous": false,
                "inputs": [
                    {"indexed": true, "internalType": "address", "name": "from", "type": "address"},
                    {"indexed": true, "internalType": "address", "name": "to", "type": "address"},
                    {"indexed": true, "internalType": "uint256", "name": "tokenId", "type": "uint256"}
                ],
                "name": "Transfer",
                "type": "event"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "owner", "type": "address"}
                ],
                "name": "balanceOf",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"}
                ],
                "name": "getApproved",
                "outputs": [{"internalType": "address", "name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "owner", "type": "address"},
                    {"internalType": "address", "name": "operator", "type": "address"}
                ],
                "name": "isApprovedForAll",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "string", "name": "tokenURI", "type": "string"}
                ],
                "name": "mint",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "name",
                "outputs": [{"internalType": "string", "name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"}
                ],
                "name": "ownerOf",
                "outputs": [{"internalType": "address", "name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "from", "type": "address"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"}
                ],
                "name": "safeTransferFrom",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "from", "type": "address"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                    {"internalType": "bytes", "name": "data", "type": "bytes"}
                ],
                "name": "safeTransferFrom",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "operator", "type": "address"},
                    {"internalType": "bool", "name": "approved", "type": "bool"}
                ],
                "name": "setApprovalForAll",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "bytes4", "name": "interfaceId", "type": "bytes4"}],
                "name": "supportsInterface",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "symbol",
                "outputs": [{"internalType": "string", "name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"}
                ],
                "name": "tokenURI",
                "outputs": [{"internalType": "string", "name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "from", "type": "address"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"}
                ],
                "name": "transferFrom",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]''')
        
        # Token deployment bytecode (simplified ERC20)
        self.TOKEN_BYTECODE = "0x608060405234801561001057600080fd5b506040516107843803806107848339818101604052810190610032919061014a565b806000806101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555050610177565b600080fd5b600073ffffffffffffffffffffffffffffffffffffffff82169050919050565b60006100af82610084565b9050919050565b6100bf816100a4565b81146100ca57600080fd5b50565b6000815190506100dc816100b6565b92915050565b6000602082840312156100f8576100f761007f565b5b6000610106848285016100cd565b91505092915050565b60008115159050919050565b6101248161010f565b811461012f57600080fd5b50565b6000815190506101418161011b565b92915050565b60006020828403121561015d5761015c61007f565b5b600061016b84828501610132565b91505092915050565b6105fe806101866000396000f3fe608060405234801561001057600080fd5b506004361061004c5760003560e01c8063095ea7b31461005157806318160ddd1461008157806323b872dd1461009f57806370a08231146100cf575b600080fd5b61006b600480360381019061006691906103a4565b6100ff565b60405161007891906103ff565b60405180910390f35b610089610122565b6040516100969190610429565b60405180910390f35b6100b960048036038101906100b49190610444565b61012c565b6040516100c691906103ff565b60405180910390f35b6100e960048036038101906100e491906104a7565b61015b565b6040516100f69190610429565b60405180910390f35b60008060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff16905090565b6000600254905090565b6000600160008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002054905092915050565b60008060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff166318160ddd6040518163ffffffff1660e01b815260040160206040518083038186803b15801561020b57600080fd5b505afa15801561021f573d6000803e3d6000fd5b505050506040513d601f19601f8201168201806040525081019061024391906104f4565b905090565b600080fd5b600073ffffffffffffffffffffffffffffffffffffffff82169050919050565b60006102778261024c565b9050919050565b6102878161026c565b811461029257600080fd5b50565b6000813590506102a48161027e565b92915050565b6000819050919050565b6102bd816102aa565b81146102c857600080fd5b50565b6000813590506102da816102b4565b92915050565b600080604083850312156102f7576102f6610247565b5b600061030585828601610295565b9250506020610316858286016102cb565b9150509250929050565b60008115159050919050565b61033581610320565b82525050565b6000602082019050610350600083018461032c565b92915050565b61035f816102aa565b82525050565b600060208201905061037a6000830184610356565b92915050565b6103898161026c565b82525050565b60006020820190506103a46000830184610380565b92915050565b600080604083850312156103c1576103c0610247565b5b60006103cf85828601610295565b92505060206103e085828601610295565b9150509250929050565b6103f381610320565b82525050565b600060208201905061040e60008301846103ea565b92915050565b61041d816102aa565b82525050565b60006020820190506104386000830184610414565b92915050565b60008060006060848603121561045757610456610247565b5b600061046586828701610295565b935050602061047686828701610295565b9250506040610487868287016102cb565b9150509250925092565b6000815190506104a0816102b4565b92915050565b6000602082840312156104bc576104bb610247565b5b60006104ca84828501610295565b91505092915050565b6000815190506104e28161027e565b92915050565b6000815190506104f78161027e565b92915050565b60006020828403121561051357610512610247565b5b600061052184828501610491565b91505092915050565b6000602082840312156105405761053f610247565b5b600061054e848285016104d3565b91505092915050565b60006020828403121561056d5761056c610247565b5b600061057b848285016104e8565b9150509291505056fea2646970667358221220c7e5d9c2b7f5e5c5b5d5c5d5c5d5c5d5c5d5c5d5c5d5c5d5c5d5c5d5c5d5c5d5c64736f6c63430008110033"
        
        # NFT deployment bytecode (simplified ERC721)
        self.NFT_BYTECODE = "0x608060405234801561001057600080fd5b506040516107843803806107848339818101604052810190610032919061014a565b806000806101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555050610177565b600080fd5b600073ffffffffffffffffffffffffffffffffffffffff82169050919050565b60006100af82610084565b9050919050565b6100bf816100a4565b81146100ca57600080fd5b50565b6000815190506100dc816100b6565b92915050565b6000602082840312156100f8576100f761007f565b5b6000610106848285016100cd565b91505092915050565b60008115159050919050565b6101248161010f565b811461012f57600080fd5b50565b6000815190506101418161011b565b92915050565b60006020828403121561015d5761015c61007f565b5b600061016b84828501610132565b91505092915050565b6105fe806101866000396000f3fe608060405234801561001057600080fd5b506004361061004c5760003560e01c8063095ea7b31461005157806318160ddd1461008157806323b872dd1461009f57806370a08231146100cf575b600080fd5b61006b600480360381019061006691906103a4565b6100ff565b60405161007891906103ff565b60405180910390f35b610089610122565b6040516100969190610429565b60405180910390f35b6100b960048036038101906100b49190610444565b61012c565b6040516100c691906103ff565b60405180910390f35b6100e960048036038101906100e491906104a7565b61015b565b6040516100f69190610429565b60405180910390f35b60008060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff16905090565b6000600254905090565b6000600160008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002054905092915050565b60008060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff166318160ddd6040518163ffffffff1660e01b815260040160206040518083038186803b15801561020b57600080fd5b505afa15801561021f573d6000803e3d6000fd5b505050506040513d601f19601f8201168201806040525081019061024391906104f4565b905090565b600080fd5b600073ffffffffffffffffffffffffffffffffffffffff82169050919050565b60006102778261024c565b9050919050565b6102878161026c565b811461029257600080fd5b50565b6000813590506102a48161027e565b92915050565b6000819050919050565b6102bd816102aa565b81146102c857600080fd5b50565b6000813590506102da816102b4565b92915050565b600080604083850312156102f7576102f6610247565b5b600061030585828601610295565b9250506020610316858286016102cb565b9150509250929050565b60008115159050919050565b61033581610320565b82525050565b6000602082019050610350600083018461032c565b92915050565b61035f816102aa565b82525050565b600060208201905061037a6000830184610356565b92915050565b6103898161026c565b82525050565b60006020820190506103a46000830184610380565b92915050565b600080604083850312156103c1576103c0610247565b5b60006103cf85828601610295565b92505060206103e085828601610295565b9150509250929050565b6103f381610320565b82525050565b600060208201905061040e60008301846103ea565b92915050565b61041d816102aa565b82525050565b60006020820190506104386000830184610414565b92915050565b60008060006060848603121561045757610456610247565b5b600061046586828701610295565b935050602061047686828701610295565b9250506040610487868287016102cb565b9150509250925092565b6000815190506104a0816102b4565b92915050565b6000602082840312156104bc576104bb610247565b5b60006104ca84828501610295565b91505092915050565b6000815190506104e28161027e565b92915050565b6000815190506104f78161027e565b92915050565b60006020828403121561051357610512610247565b5b600061052184828501610491565b91505092915050565b6000602082840312156105405761053f610247565b5b600061054e848285016104d3565b91505092915050565b60006020828403121561056d5761056c610247565b5b600061057b848285016104e8565b9150509291505056fea2646970667358221220c7e5d9c2b7f5e5c5b5d5c5d5c5d5c5d5c5d5c5d5c5d5c5d5c5d5c5d5c5d5c5d5c64736f6c63430008110033"
        
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
        self.token_name = ""
        self.token_symbol = ""
        self.token_supply = 0
        self.nft_name = ""
        self.nft_symbol = ""
        self.token_contract_address = ""
        self.nft_contract_address = ""

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
        print(f"{Fore.CYAN}     PHAROS X Faroswap Auto Tx Eyren         ")
        print(f"{Fore.CYAN}           LETS FUCK THIS TESTNET           ")
        print(f"{Style.BRIGHT + Fore.MAGENTA}{'=' * 50}")
        print(f"{Fore.GREEN}1. Wrap PHRS to WPHRS")
        print(f"{Fore.YELLOW}2. Unwrap WPHRS to PHRS")
        print(f"{Fore.CYAN}3. Auto All (Wrap, Unwrap, Swap, Liquidity)")
        print(f"{Fore.WHITE}4. Swap Tokens")
        print(f"{Fore.BLUE}5. Deploy Token Contract")
        print(f"{Fore.MAGENTA}6. Deploy NFT Contract")
        print(f"{Fore.CYAN}7. Interact with Token Contract")
        print(f"{Fore.RED}8. Exit")
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

    async def get_web3(self, retries=5, initial_delay=1):
        from web3 import Web3
        delay = initial_delay
        for attempt in range(retries):
            try:
                # Alternate between RPC providers to avoid rate limiting
                rpc_url = self.RPC_URL if attempt % 2 == 0 else self.ALT_RPC_URL
                web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 60}))
                # Check connection by getting block number
                block_number = web3.eth.block_number
                self.log(f"Connected to RPC (Block: {block_number})", indent=1, color=Fore.GREEN)
                return web3
            except Exception as e:
                if attempt < retries - 1:
                    self.log(f"RPC connection attempt {attempt+1} failed: {e}, retrying in {delay} seconds...", indent=1, color=Fore.YELLOW)
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    self.log(f"Failed to Connect to RPC after {retries} attempts: {e}", indent=1, color=Fore.RED)
                    return None

    async def get_token_balance(self, address, token_symbol):
        try:
            web3 = await self.get_web3()
            if not web3:
                return None
            contract_address = self.TOKENS.get(token_symbol)
            if not contract_address:
                self.log(f"Invalid token symbol: {token_symbol}", indent=1, color=Fore.RED)
                return None
            if token_symbol == "PHRS":
                balance = web3.eth.get_balance(address)
                decimals = 18
            else:
                token_contract = web3.eth.contract(address=web3.to_checksum_address(contract_address), abi=self.ERC20_CONTRACT_ABI)
                balance = token_contract.functions.balanceOf(address).call()
                decimals = token_contract.functions.decimals().call()
            return balance / (10 ** decimals)
        except Exception as e:
            self.log(f"Get Token Balance Failed for {token_symbol}: {e}", indent=1, color=Fore.RED)
            return None

    async def _wait_for_tx_receipt(self, web3, tx_hash, timeout, retries=5, initial_delay=2):
        delay = initial_delay
        for attempt in range(retries):
            try:
                loop = asyncio.get_event_loop()
                func = lambda: web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
                return await loop.run_in_executor(None, func)
            except Exception as e:
                if attempt < retries - 1:
                    self.log(f"Receipt fetch attempt {attempt+1} failed: {e}, retrying in {delay} seconds...", indent=2, color=Fore.YELLOW)
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    self.log(f"Failed to get transaction receipt after {retries} attempts: {e}", indent=2, color=Fore.RED)
                    return None

    async def perform_wrapped(self, account, address):
        try:
            web3 = await self.get_web3()
            if not web3:
                return None, None
            contract_address = web3.to_checksum_address(self.TOKENS["WPHRS"])
            token_contract = web3.eth.contract(address=contract_address, abi=self.ERC20_CONTRACT_ABI)
            amount_to_wei = web3.to_wei(self.wrap_amount, "ether")
            wrap_data = token_contract.functions.deposit()
            estimated_gas = wrap_data.estimate_gas({"from": address, "value": amount_to_wei})
            max_priority_fee = web3.to_wei(1, "gwei")
            wrap_tx = wrap_data.build_transaction({
                "from": address,
                "value": amount_to_wei,
                "gas": int(estimated_gas * 1.2),
                "maxFeePerGas": int(max_priority_fee),
                "maxPriorityFeePerGas": int(max_priority_fee),
                "nonce": web3.eth.get_transaction_count(address, "pending"),
                "chainId": web3.eth.chain_id
            })
            signed_tx = web3.eth.account.sign_transaction(wrap_tx, account)
            raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash = web3.to_hex(raw_tx)
            receipt = await self._wait_for_tx_receipt(web3, tx_hash, 300)
            if receipt:
                return tx_hash, receipt.blockNumber
            return None, None
        except Exception as e:
            self.log(f"Wrap Failed: {e}", indent=2, color=Fore.RED)
            return None, None

    async def perform_unwrapped(self, account, address):
        try:
            web3 = await self.get_web3()
            if not web3:
                return None, None
            contract_address = web3.to_checksum_address(self.TOKENS["WPHRS"])
            token_contract = web3.eth.contract(address=contract_address, abi=self.ERC20_CONTRACT_ABI)
            amount_to_wei = web3.to_wei(self.wrap_amount, "ether")
            unwrap_data = token_contract.functions.withdraw(amount_to_wei)
            estimated_gas = unwrap_data.estimate_gas({"from": address})
            max_priority_fee = web3.to_wei(1, "gwei")
            unwrap_tx = unwrap_data.build_transaction({
                "from": address,
                "gas": int(estimated_gas * 1.2),
                "maxFeePerGas": int(max_priority_fee),
                "maxPriorityFeePerGas": int(max_priority_fee),
                "nonce": web3.eth.get_transaction_count(address, "pending"),
                "chainId": web3.eth.chain_id
            })
            signed_tx = web3.eth.account.sign_transaction(unwrap_tx, account)
            raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash = web3.to_hex(raw_tx)
            receipt = await self._wait_for_tx_receipt(web3, tx_hash, 300)
            if receipt:
                return tx_hash, receipt.blockNumber
            return None, None
        except Exception as e:
            self.log(f"Unwrap Failed: {e}", indent=2, color=Fore.RED)
            return None, None

    async def approve_token(self, account, owner_address, spender_address, contract_address, amount):
        try:
            web3 = await self.get_web3()
            if not web3:
                return False
            spender = web3.to_checksum_address(spender_address)
            token_contract = web3.eth.contract(address=web3.to_checksum_address(contract_address), abi=self.ERC20_CONTRACT_ABI)
            decimals = token_contract.functions.decimals().call()
            amount_to_wei = int(amount * (10 ** decimals))
            allowance = token_contract.functions.allowance(owner_address, spender).call()
            if allowance < amount_to_wei:
                approve_data = token_contract.functions.approve(spender, 2**256 - 1)
                estimated_gas = approve_data.estimate_gas({"from": owner_address})
                max_priority_fee = web3.to_wei(1, "gwei")
                approve_tx = approve_data.build_transaction({
                    "from": owner_address,
                    "gas": int(estimated_gas * 1.2),
                    "maxFeePerGas": int(max_priority_fee),
                    "maxPriorityFeePerGas": int(max_priority_fee),
                    "nonce": web3.eth.get_transaction_count(owner_address, "pending"),
                    "chainId": web3.eth.chain_id
                })
                signed_tx = web3.eth.account.sign_transaction(approve_tx, account)
                raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                tx_hash = web3.to_hex(raw_tx)
                receipt = await self._wait_for_tx_receipt(web3, tx_hash, 300)
                if receipt:
                    self.log(f"Approve Success: Block {receipt.blockNumber}", indent=2, color=Fore.GREEN)
                    self.log(f"Tx: {tx_hash}", indent=2, color=Fore.CYAN)
                    self.log(f"Explorer: {self.EXPLORER_URL}/{tx_hash}", indent=2, color=Fore.CYAN)
                    await asyncio.sleep(10)
                    return True
                return False
            return True
        except Exception as e:
            self.log(f"Approve Failed: {e}", indent=2, color=Fore.RED)
            return False

    async def perform_add_liquidity(self, account, address, add_lp_option, token0, token1, amount0, amount1):
        try:
            web3 = await self.get_web3()
            if not web3:
                return None, None
            if add_lp_option in ["USDCnWPHRS", "WPHRSnUSDT", "USDCnUSDT", "WETHnUSDC", "WBTCnUSDT"]:
                await self.approve_token(account, address, self.POSITION_MANAGER_ADDRESS, token0, amount0)
                await self.approve_token(account, address, self.POSITION_MANAGER_ADDRESS, token1, amount1)
            token0_contract = web3.eth.contract(address=web3.to_checksum_address(token0), abi=self.ERC20_CONTRACT_ABI)
            token0_decimals = token0_contract.functions.decimals().call()
            amount0_desired = int(amount0 * (10 ** token0_decimals))
            token1_contract = web3.eth.contract(address=web3.to_checksum_address(token1), abi=self.ERC20_CONTRACT_ABI)
            token1_decimals = token1_contract.functions.decimals().call()
            amount1_desired = int(amount1 * (10 ** token1_decimals))
            mint_params = {
                "token0": web3.to_checksum_address(token0),
                "token1": web3.to_checksum_address(token1),
                "fee": 500,
                "tickLower": -887270,
                "tickUpper": 887270,
                "amount0Desired": amount0_desired,
                "amount1Desired": amount1_desired,
                "amount0Min": 0,
                "amount1Min": 0,
                "recipient": web3.to_checksum_address(address),
                "deadline": int(time.time()) + 600
            }
            token_contract = web3.eth.contract(address=web3.to_checksum_address(self.POSITION_MANAGER_ADDRESS), abi=self.ADD_LP_CONTRACT_ABI)
            lp_data = token_contract.functions.mint(mint_params)
            estimated_gas = lp_data.estimate_gas({"from": address})
            max_priority_fee = web3.to_wei(1, "gwei")
            lp_tx = lp_data.build_transaction({
                "from": address,
                "gas": int(estimated_gas * 1.2),
                "maxFeePerGas": int(max_priority_fee),
                "maxPriorityFeePerGas": int(max_priority_fee),
                "nonce": web3.eth.get_transaction_count(address, "pending"),
                "chainId": web3.eth.chain_id
            })
            signed_tx = web3.eth.account.sign_transaction(lp_tx, account)
            raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash = web3.to_hex(raw_tx)
            receipt = await self._wait_for_tx_receipt(web3, tx_hash, 300)
            if receipt:
                return tx_hash, receipt.blockNumber
            return None, None
        except Exception as e:
            self.log(f"Add Liquidity Failed: {e}", indent=2, color=Fore.RED)
            return None, None

    async def perform_swap(self, account, address, token_in_symbol, token_out_symbol, amount_in):
        try:
            web3 = await self.get_web3()
            if not web3:
                return None, None
            token_in = self.TOKENS.get(token_in_symbol)
            token_out = self.TOKENS.get(token_out_symbol)
            if not token_in or not token_out:
                self.log(f"Invalid token pair: {token_in_symbol}/{token_out_symbol}", indent=2, color=Fore.RED)
                return None, None
            if token_in_symbol != "PHRS":
                await self.approve_token(account, address, self.SWAP_ROUTER_ADDRESS, token_in, amount_in)
            token_in_contract = web3.eth.contract(address=web3.to_checksum_address(token_in), abi=self.ERC20_CONTRACT_ABI) if token_in_symbol != "PHRS" else None
            decimals = 18 if token_in_symbol == "PHRS" else token_in_contract.functions.decimals().call()
            amount_in_wei = int(amount_in * (10 ** decimals))
            swap_params = {
                "tokenIn": web3.to_checksum_address(token_in),
                "tokenOut": web3.to_checksum_address(token_out),
                "fee": 500,
                "recipient": web3.to_checksum_address(address),
                "deadline": int(time.time()) + 600,
                "amountIn": amount_in_wei,
                "amountOutMinimum": 0,
                "sqrtPriceLimitX96": 0
            }
            swap_contract = web3.eth.contract(address=web3.to_checksum_address(self.SWAP_ROUTER_ADDRESS), abi=self.SWAP_ROUTER_ABI)
            swap_data = swap_contract.functions.exactInputSingle(swap_params)
            estimated_gas = swap_data.estimate_gas({"from": address, "value": amount_in_wei if token_in_symbol == "PHRS" else 0})
            max_priority_fee = web3.to_wei(1, "gwei")
            swap_tx = swap_data.build_transaction({
                "from": address,
                "value": amount_in_wei if token_in_symbol == "PHRS" else 0,
                "gas": int(estimated_gas * 1.2),
                "maxFeePerGas": int(max_priority_fee),
                "maxPriorityFeePerGas": int(max_priority_fee),
                "nonce": web3.eth.get_transaction_count(address, "pending"),
                "chainId": web3.eth.chain_id
            })
            signed_tx = web3.eth.account.sign_transaction(swap_tx, account)
            raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash = web3.to_hex(raw_tx)
            receipt = await self._wait_for_tx_receipt(web3, tx_hash, 300)
            if receipt:
                return tx_hash, receipt.blockNumber
            return None, None
        except Exception as e:
            self.log(f"Swap Failed: {e}", indent=2, color=Fore.RED)
            return None, None

    async def process_perform_wrapped(self, account, address, iteration=None, total_iterations=None):
        self.log(f"{'Wrap' if iteration is None else f'Wrap {iteration}/{total_iterations}'}", indent=2, color=Fore.YELLOW)
        balance = await self.get_token_balance(address, "PHRS")
        self.log(f"Balance: {balance} PHRS", indent=2, color=Fore.CYAN)
        self.log(f"Amount: {self.wrap_amount} PHRS", indent=2, color=Fore.CYAN)
        if not balance or balance <= self.wrap_amount:
            self.log("Insufficient PHRS Balance", indent=2, color=Fore.RED)
            return False
        tx_hash, block_number = await self.perform_wrapped(account, address)
        if tx_hash and block_number:
            self.log(f"Wrapped {self.wrap_amount} PHRS to WPHRS Success", indent=2, color=Fore.GREEN)
            self.log(f"Block: {block_number}", indent=2, color=Fore.CYAN)
            self.log(f"Tx: {tx_hash}", indent=2, color=Fore.CYAN)
            self.log(f"Explorer: {self.EXPLORER_URL}/{tx_hash}", indent=2, color=Fore.CYAN)
            return True
        else:
            self.log("Wrap Failed", indent=2, color=Fore.RED)
            return False

    async def process_perform_unwrapped(self, account, address, iteration=None, total_iterations=None):
        self.log(f"{'Unwrap' if iteration is None else f'Unwrap {iteration}/{total_iterations}'}", indent=2, color=Fore.YELLOW)
        balance = await self.get_token_balance(address, "WPHRS")
        self.log(f"Balance: {balance} WPHRS", indent=2, color=Fore.CYAN)
        self.log(f"Amount: {self.wrap_amount} WPHRS", indent=2, color=Fore.CYAN)
        if not balance or balance <= self.wrap_amount:
            self.log("Insufficient WPHRS Balance", indent=2, color=Fore.RED)
            return False
        tx_hash, block_number = await self.perform_unwrapped(account, address)
        if tx_hash and block_number:
            self.log(f"Unwrapped {self.wrap_amount} WPHRS to PHRS Success", indent=2, color=Fore.GREEN)
            self.log(f"Block: {block_number}", indent=2, color=Fore.CYAN)
            self.log(f"Tx: {tx_hash}", indent=2, color=Fore.CYAN)
            self.log(f"Explorer: {self.EXPLORER_URL}/{tx_hash}", indent=2, color=Fore.CYAN)
            return True
        else:
            self.log("Unwrap Failed", indent=2, color=Fore.RED)
            return False

    async def process_perform_add_liquidity(self, account, address, add_lp_option, token0, token1, amount0, amount1, ticker0, ticker1, iteration, total_iterations):
        self.log(f"Add Liquidity {iteration}/{total_iterations}: {ticker0}/{ticker1}", indent=2, color=Fore.YELLOW)
        token0_balance = await self.get_token_balance(address, ticker0)
        token1_balance = await self.get_token_balance(address, ticker1)
        self.log(f"Balance: {token0_balance} {ticker0}, {token1_balance} {ticker1}", indent=2, color=Fore.CYAN)
        self.log(f"Amount: {amount0} {ticker0}, {amount1} {ticker1}", indent=2, color=Fore.CYAN)
        if not token0_balance or token0_balance <= amount0:
            self.log(f"Insufficient {ticker0} Balance", indent=2, color=Fore.RED)
            return False
        if not token1_balance or token1_balance <= amount1:
            self.log(f"Insufficient {ticker1} Balance", indent=2, color=Fore.RED)
            return False
        tx_hash, block_number = await self.perform_add_liquidity(account, address, add_lp_option, token0, token1, amount0, amount1)
        if tx_hash and block_number:
            self.log(f"Add LP {amount0} {ticker0}/{amount1} {ticker1} Success", indent=2, color=Fore.GREEN)
            self.log(f"Block: {block_number}", indent=2, color=Fore.CYAN)
            self.log(f"Tx: {tx_hash}", indent=2, color=Fore.CYAN)
            self.log(f"Explorer: {self.EXPLORER_URL}/{tx_hash}", indent=2, color=Fore.CYAN)
            return True
        else:
            self.log("Add Liquidity Failed", indent=2, color=Fore.RED)
            return False

    async def process_perform_swap(self, account, address, token_in_symbol, token_out_symbol, amount_in, iteration, total_iterations):
        self.log(f"Swap {iteration}/{total_iterations}: {token_in_symbol}/{token_out_symbol}", indent=2, color=Fore.YELLOW)
        balance = await self.get_token_balance(address, token_in_symbol)
        self.log(f"Balance: {balance} {token_in_symbol}", indent=2, color=Fore.CYAN)
        self.log(f"Amount: {amount_in} {token_in_symbol}", indent=2, color=Fore.CYAN)
        if not balance or balance <= amount_in:
            self.log(f"Insufficient {token_in_symbol} Balance", indent=2, color=Fore.RED)
            return False
        tx_hash, block_number = await self.perform_swap(account, address, token_in_symbol, token_out_symbol, amount_in)
        if tx_hash and block_number:
            self.log(f"Swap {amount_in} {token_in_symbol} to {token_out_symbol} Success", indent=2, color=Fore.GREEN)
            self.log(f"Block: {block_number}", indent=2, color=Fore.CYAN)
            self.log(f"Tx: {tx_hash}", indent=2, color=Fore.CYAN)
            self.log(f"Explorer: {self.EXPLORER_URL}/{tx_hash}", indent=2, color=Fore.CYAN)
            return True
        else:
            self.log("Swap Failed", indent=2, color=Fore.RED)
            return False

    def generate_add_lp_option(self):
        add_lp_option = random.choice(["USDCnWPHRS", "USDCnUSDT", "WPHRSnUSDT", "WETHnUSDC", "WBTCnUSDT"])
        if add_lp_option == "USDCnWPHRS":
            token0, token1 = self.TOKENS["USDC"], self.TOKENS["WPHRS"]
            amount0, amount1 = 0.45, 0.001
            ticker0, ticker1 = "USDC", "WPHRS"
        elif add_lp_option == "USDCnUSDT":
            token0, token1 = self.TOKENS["USDC"], self.TOKENS["USDT"]
            amount0, amount1 = 1, 1
            ticker0, ticker1 = "USDC", "USDT"
        elif add_lp_option == "WPHRSnUSDT":
            token0, token1 = self.TOKENS["WPHRS"], self.TOKENS["USDT"]
            amount0, amount1 = 0.001, 0.45
            ticker0, ticker1 = "WPHRS", "USDT"
        elif add_lp_option == "WETHnUSDC":
            token0, token1 = self.TOKENS["WETH"], self.TOKENS["USDC"]
            amount0, amount1 = 0.0001, 0.45
            ticker0, ticker1 = "WETH", "USDC"
        else:  # WBTCnUSDT
            token0, token1 = self.TOKENS["WBTC"], self.TOKENS["USDT"]
            amount0, amount1 = 0.00001, 0.45
            ticker0, ticker1 = "WBTC", "USDT"
        return add_lp_option, token0, token1, amount0, amount1, ticker0, ticker1

    def generate_swap_option(self):
        swap_pairs = [
            ("PHRS", "WPHRS", 0.001),
            ("USDC", "USDT", 1),
            ("WETH", "USDC", 0.0001),
            ("WBTC", "USDT", 0.00001),
            ("USDT", "USDC", 1),
        ]
        token_in_symbol, token_out_symbol, amount_in = random.choice(swap_pairs)
        return token_in_symbol, token_out_symbol, amount_in

    async def user_login(self, address, retries=5):
        url = f"{self.BASE_API}/user/login?address={address}&signature={self.signatures[address]}&invite_code={self.ref_code}"
        headers = {**self.headers, "Authorization": "Bearer null", "Content-Length": "0"}
        for attempt in range(retries):
            try:
                async with ClientSession(timeout=ClientTimeout(total=120)) as session:
                    async with session.post(url=url, headers=headers) as response:
                        response.raise_for_status()
                        return await response.json()
            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                self.log(f"Login Failed: {e}", indent=1, color=Fore.RED)
                return None

    async def process_user_login(self, address):
        self.log("Logging in...", indent=1, color=Fore.YELLOW)
        login = await self.user_login(address)
        if login and login.get("code") == 0:
            self.access_tokens[address] = login["data"]["jwt"]
            self.log("Login Success", indent=1, color=Fore.GREEN)
            return True
        self.log("Login Failed", indent=1, color=Fore.RED)
        return False

    async def process_option_3(self, account, address):
        self.log(f"Starting Auto All: Wrap, Unwrap, Swap, Liquidity ({self.auto_all_count} cycles)", indent=1, color=Fore.YELLOW)
        for i in range(self.auto_all_count):
            self.log(f"Cycle {i+1}/{self.auto_all_count}", indent=1, color=Fore.YELLOW)
            # Wrap
            wrap_success = await self.process_perform_wrapped(account, address, i+1, self.auto_all_count)
            if wrap_success:
                self.log("Waiting before unwrap...", indent=2, color=Fore.YELLOW)
                await asyncio.sleep(5)
                # Unwrap
                unwrap_success = await self.process_perform_unwrapped(account, address, i+1, self.auto_all_count)
                if unwrap_success:
                    self.log("Waiting before swap...", indent=2, color=Fore.YELLOW)
                    await asyncio.sleep(5)
                    # Swap
                    token_in_symbol, token_out_symbol, amount_in = self.generate_swap_option()
                    swap_success = await self.process_perform_swap(account, address, token_in_symbol, token_out_symbol, amount_in, i+1, self.auto_all_count)
                    if swap_success:
                        self.log("Waiting before liquidity...", indent=2, color=Fore.YELLOW)
                        await asyncio.sleep(5)
                        # Add Liquidity
                        add_lp_option, token0, token1, amount0, amount1, ticker0, ticker1 = self.generate_add_lp_option()
                        await self.process_perform_add_liquidity(account, address, add_lp_option, token0, token1, amount0, amount1, ticker0, ticker1, i+1, self.auto_all_count)
                    else:
                        self.log("Skipping liquidity due to swap failure", indent=2, color=Fore.RED)
                else:
                    self.log("Skipping swap and liquidity due to unwrap failure", indent=2, color=Fore.RED)
            else:
                self.log("Skipping unwrap, swap, and liquidity due to wrap failure", indent=2, color=Fore.RED)
            if i < self.auto_all_count - 1:
                await asyncio.sleep(5)

    async def process_option_4(self, account, address):
        self.log(f"Starting Swap Tokens ({self.swap_count} cycles)", indent=1, color=Fore.YELLOW)
        for i in range(self.swap_count):
            token_in_symbol, token_out_symbol, amount_in = self.generate_swap_option()
            await self.process_perform_swap(account, address, token_in_symbol, token_out_symbol, amount_in, i+1, self.swap_count)
            if i < self.swap_count - 1:
                await asyncio.sleep(5)

    async def deploy_token_contract(self, account, address):
        max_retries = 5
        delay = 5
        for attempt in range(max_retries):
            try:
                web3 = await self.get_web3()
                if not web3:
                    return None, None
                
                # Encode constructor parameters
                constructor_params = web3.codec.encode_abi(
                    ['string', 'string', 'uint256'],
                    [self.token_name, self.token_symbol, int(self.token_supply * (10 ** 18))]
                )
                
                # Combine bytecode with constructor parameters
                deployment_bytecode = self.TOKEN_BYTECODE + constructor_params.hex()[2:]
                
                # Build deployment transaction
                deployment_tx = {
                    'from': address,
                    'data': deployment_bytecode,
                    'gas': 3000000,
                    'maxFeePerGas': web3.to_wei(1.5, 'gwei'),
                    'maxPriorityFeePerGas': web3.to_wei(1, 'gwei'),
                    'nonce': web3.eth.get_transaction_count(address, 'pending'),
                    'chainId': web3.eth.chain_id
                }
                
                # Estimate gas
                estimated_gas = web3.eth.estimate_gas(deployment_tx)
                deployment_tx['gas'] = int(estimated_gas * 1.2)
                
                # Sign and send transaction
                signed_tx = web3.eth.account.sign_transaction(deployment_tx, account)
                raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                tx_hash = web3.to_hex(raw_tx)
                
                # Wait for receipt
                receipt = await self._wait_for_tx_receipt(web3, tx_hash, 300)
                if receipt and receipt.contractAddress:
                    contract_address = receipt.contractAddress
                    self.log(f"Token Contract Deployed Successfully!", indent=1, color=Fore.GREEN)
                    self.log(f"Contract Address: {contract_address}", indent=1, color=Fore.CYAN)
                    self.log(f"Tx: {tx_hash}", indent=1, color=Fore.CYAN)
                    self.log(f"Explorer: {self.EXPLORER_URL}/{tx_hash}", indent=1, color=Fore.CYAN)
                    self.token_contract_address = contract_address
                    return tx_hash, contract_address
                else:
                    self.log("Failed to get contract address from receipt", indent=1, color=Fore.YELLOW)
                    continue
            except Exception as e:
                if attempt < max_retries - 1:
                    self.log(f"Token Deployment attempt {attempt+1} failed: {e}, retrying in {delay} seconds...", indent=1, color=Fore.YELLOW)
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    self.log(f"Token Deployment Failed after {max_retries} attempts: {e}", indent=1, color=Fore.RED)
                    return None, None

    async def deploy_nft_contract(self, account, address):
        max_retries = 5
        delay = 5
        for attempt in range(max_retries):
            try:
                web3 = await self.get_web3()
                if not web3:
                    return None, None
                
                # Encode constructor parameters
                constructor_params = web3.codec.encode_abi(
                    ['string', 'string'],
                    [self.nft_name, self.nft_symbol]
                )
                
                # Combine bytecode with constructor parameters
                deployment_bytecode = self.NFT_BYTECODE + constructor_params.hex()[2:]
                
                # Build deployment transaction
                deployment_tx = {
                    'from': address,
                    'data': deployment_bytecode,
                    'gas': 3000000,
                    'maxFeePerGas': web3.to_wei(1.5, 'gwei'),
                    'maxPriorityFeePerGas': web3.to_wei(1, 'gwei'),
                    'nonce': web3.eth.get_transaction_count(address, 'pending'),
                    'chainId': web3.eth.chain_id
                }
                
                # Estimate gas
                estimated_gas = web3.eth.estimate_gas(deployment_tx)
                deployment_tx['gas'] = int(estimated_gas * 1.2)
                
                # Sign and send transaction
                signed_tx = web3.eth.account.sign_transaction(deployment_tx, account)
                raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                tx_hash = web3.to_hex(raw_tx)
                
                # Wait for receipt
                receipt = await self._wait_for_tx_receipt(web3, tx_hash, 300)
                if receipt and receipt.contractAddress:
                    contract_address = receipt.contractAddress
                    self.log(f"NFT Contract Deployed Successfully!", indent=1, color=Fore.GREEN)
                    self.log(f"Contract Address: {contract_address}", indent=1, color=Fore.CYAN)
                    self.log(f"Tx: {tx_hash}", indent=1, color=Fore.CYAN)
                    self.log(f"Explorer: {self.EXPLORER_URL}/{tx_hash}", indent=1, color=Fore.CYAN)
                    self.nft_contract_address = contract_address
                    return tx_hash, contract_address
                else:
                    self.log("Failed to get contract address from receipt", indent=1, color=Fore.YELLOW)
                    continue
            except Exception as e:
                if attempt < max_retries - 1:
                    self.log(f"NFT Deployment attempt {attempt+1} failed: {e}, retrying in {delay} seconds...", indent=1, color=Fore.YELLOW)
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    self.log(f"NFT Deployment Failed after {max_retries} attempts: {e}", indent=1, color=Fore.RED)
                    return None, None

    async def interact_with_token(self, account, address, contract_address):
        try:
            web3 = await self.get_web3()
            if not web3:
                return
            
            token_contract = web3.eth.contract(
                address=web3.to_checksum_address(contract_address),
                abi=self.ERC20_CONTRACT_ABI
            )
            
            self.log("Token Interaction Menu", indent=1, color=Fore.BLUE)
            self.log("1. Transfer Tokens", indent=1)
            self.log("2. Check Balance", indent=1)
            self.log("3. Approve Spending", indent=1)
            self.log("4. Check Token Info", indent=1)
            self.log("5. Back to Main Menu", indent=1)
            
            choice = input(f"{Style.BRIGHT + Fore.CYAN}Enter your choice (1-5): ").strip()
            
            if choice == '1':
                # Transfer tokens
                recipient = input("Enter recipient address: ").strip()
                amount = float(input("Enter amount to transfer: ").strip())
                
                decimals = token_contract.functions.decimals().call()
                amount_wei = int(amount * (10 ** decimals))
                
                tx_data = token_contract.functions.transfer(
                    web3.to_checksum_address(recipient),
                    amount_wei
                ).build_transaction({
                    'from': address,
                    'gas': 200000,
                    'maxFeePerGas': web3.to_wei(1.5, 'gwei'),
                    'maxPriorityFeePerGas': web3.to_wei(1, 'gwei'),
                    'nonce': web3.eth.get_transaction_count(address, 'pending'),
                    'chainId': web3.eth.chain_id
                })
                
                signed_tx = web3.eth.account.sign_transaction(tx_data, account)
                raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                tx_hash = web3.to_hex(raw_tx)
                
                receipt = await self._wait_for_tx_receipt(web3, tx_hash, 300)
                if receipt:
                    self.log(f"Transfer Success: Block {receipt.blockNumber}", indent=1, color=Fore.GREEN)
                    self.log(f"Tx: {tx_hash}", indent=1, color=Fore.CYAN)
                    self.log(f"Explorer: {self.EXPLORER_URL}/{tx_hash}", indent=1, color=Fore.CYAN)
                else:
                    self.log("Transfer Failed", indent=1, color=Fore.RED)
                
            elif choice == '2':
                # Check balance
                balance_wei = token_contract.functions.balanceOf(address).call()
                decimals = token_contract.functions.decimals().call()
                balance = balance_wei / (10 ** decimals)
                self.log(f"Your Token Balance: {balance}", indent=1, color=Fore.CYAN)
                
            elif choice == '3':
                # Approve spending
                spender = input("Enter spender address: ").strip()
                amount = float(input("Enter amount to approve: ").strip())
                
                decimals = token_contract.functions.decimals().call()
                amount_wei = int(amount * (10 ** decimals))
                
                tx_data = token_contract.functions.approve(
                    web3.to_checksum_address(spender),
                    amount_wei
                ).build_transaction({
                    'from': address,
                    'gas': 200000,
                    'maxFeePerGas': web3.to_wei(1.5, 'gwei'),
                    'maxPriorityFeePerGas': web3.to_wei(1, 'gwei'),
                    'nonce': web3.eth.get_transaction_count(address, 'pending'),
                    'chainId': web3.eth.chain_id
                })
                
                signed_tx = web3.eth.account.sign_transaction(tx_data, account)
                raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                tx_hash = web3.to_hex(raw_tx)
                
                receipt = await self._wait_for_tx_receipt(web3, tx_hash, 300)
                if receipt:
                    self.log(f"Approval Success: Block {receipt.blockNumber}", indent=1, color=Fore.GREEN)
                    self.log(f"Tx: {tx_hash}", indent=1, color=Fore.CYAN)
                    self.log(f"Explorer: {self.EXPLORER_URL}/{tx_hash}", indent=1, color=Fore.CYAN)
                else:
                    self.log("Approval Failed", indent=1, color=Fore.RED)
                    
            elif choice == '4':
                # Check token info
                name = token_contract.functions.name().call()
                symbol = token_contract.functions.symbol().call()
                decimals = token_contract.functions.decimals().call()
                total_supply = token_contract.functions.totalSupply().call() / (10 ** decimals)
                
                self.log(f"Token Name: {name}", indent=1, color=Fore.CYAN)
                self.log(f"Token Symbol: {symbol}", indent=1, color=Fore.CYAN)
                self.log(f"Decimals: {decimals}", indent=1, color=Fore.CYAN)
                self.log(f"Total Supply: {total_supply}", indent=1, color=Fore.CYAN)
                
        except Exception as e:
            self.log(f"Token Interaction Failed: {e}", indent=1, color=Fore.RED)

    def print_question(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.display_menu()
        while True:
            try:
                option = int(input(f"{Style.BRIGHT + Fore.CYAN}Enter your choice (1-8): ").strip())
                if option in range(1, 9):
                    if option == 8:
                        print(f"{Style.BRIGHT + Fore.RED}Exiting...")
                        sys.exit(0)
                    self.log(f"Option {option} Selected.", indent=0, color=Fore.GREEN)
                    break
                print(f"{Style.BRIGHT + Fore.RED}Invalid choice. Please enter 1-8.")
            except ValueError:
                print(f"{Style.BRIGHT + Fore.RED}Invalid input. Enter a number (1-8).")

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
            self.token_name = input("Enter Token Name: ").strip()
            self.token_symbol = input("Enter Token Symbol: ").strip()
            self.token_supply = float(input("Enter Token Total Supply: ").strip())
        if option == 6:
            self.nft_name = input("Enter NFT Name: ").strip()
            self.nft_symbol = input("Enter NFT Symbol: ").strip()
        if option == 7:
            self.token_contract_address = input("Enter Token Contract Address: ").strip()

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
                self.log("Option: Deploy Token Contract", indent=0, color=Fore.BLUE)
                await self.deploy_token_contract(account, address)
            elif self.wrap_option == 6:
                self.log("Option: Deploy NFT Contract", indent=0, color=Fore.BLUE)
                await self.deploy_nft_contract(account, address)
            elif self.wrap_option == 7:
                self.log("Option: Interact with Token Contract", indent=0, color=Fore.BLUE)
                await self.interact_with_token(account, address, self.token_contract_address)

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
