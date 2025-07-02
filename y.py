import os
import random
from web3 import Web3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
RPC_URL = "https://polygon-mumbai.g.alchemy.com/v2/your-api-key"  # Ganti dengan RPC URL Anda
CONTRACT_ADDRESS = "0xYourContractAddressHere"  # Ganti dengan alamat kontrak sebenarnya
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CHAIN_ID = 80001  # Polygon Mumbai Testnet

# Minimal ABI for register function
PHAROS_ABI = [
    {
        "inputs": [{"internalType": "string", "name": "name", "type": "string"}],
        "name": "register",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# Initialize Web3
web3 = Web3(Web3.HTTPProvider(RPC_URL))
assert web3.is_connected(), "Failed to connect to RPC"

def wrap_phrs():
    print("Wrap PHRS functionality not implemented yet")

def unwrap_wphrs():
    print("Unwrap WPHRS functionality not implemented yet")

def auto_all():
    print("Auto All functionality not implemented yet")

def swap_tokens():
    print("Swap Tokens functionality not implemented yet")

def mint_pharos_name():
    try:
        count = int(input("How Many Names to Mint?: "))
    except ValueError:
        print("Invalid input. Please enter a number.")
        return

    account = web3.eth.account.from_key(PRIVATE_KEY)
    print(f"\nProcessing Account: {account.address[0:4]}...{account.address[-4:]}")
    
    for i in range(count):
        # Generate random name
        name = f"pharos-{random.randint(1000,9999)}"
        
        # Prepare contract interaction
        contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=PHAROS_ABI)
        nonce = web3.eth.get_transaction_count(account.address)
        
        try:
            # Build transaction
            tx = contract.functions.register(name).build_transaction({
                'chainId': CHAIN_ID,
                'gas': 200000,
                'gasPrice': web3.to_wei('10', 'gwei'),
                'nonce': nonce,
            })
            
            # Sign and send transaction
            signed_tx = account.sign_transaction(tx)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            
            print(f"✅ Successfully minted '{name}'!")
            print(f"Transaction Hash: {receipt.transactionHash.hex()}")
            print(f"Block: {receipt.blockNumber} | Gas Used: {receipt.gasUsed}\n")
        
        except Exception as e:
            print(f"❌ Error minting name: {str(e)}")

def main():
    while True:
        print("\n" + "="*40)
        print("PharosSwap Interface")
        print("="*40)
        print("1. Wrap PHRS to WPHRS")
        print("2. Unwrap WPHRS to PHRS")
        print("3. Auto All (Wrap, Unwrap, Swap, Liquidity)")
        print("4. Swap Tokens")
        print("5. Mint Pharos Name")
        print("6. Exit")
        print("="*40)
        
        choice = input("Enter your choice (1-6): ")
        
        if choice == '1':
            wrap_phrs()
        elif choice == '2':
            unwrap_wphrs()
        elif choice == '3':
            auto_all()
        elif choice == '4':
            swap_tokens()
        elif choice == '5':
            mint_pharos_name()
        elif choice == '6':
            print("Exiting program...")
            break
        else:
            print("Invalid choice. Please enter 1-6.")

if __name__ == "__main__":
    main()
