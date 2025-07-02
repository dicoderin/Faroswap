const Web3 = require('web3');
const dotenv = require('dotenv');
const crypto = require('crypto');
const { v4: uuidv4 } = require('uuid');
const { randomFillSync } = require('crypto');

dotenv.config();

// =============================================
// CONTRACT ABI
// =============================================
const CONTRACT_ABI = [
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
];

// =============================================
// UTILITY FUNCTIONS
// =============================================
function injectPoaMiddleware(web3Instance) {
    const Web3HttpProvider = require('web3-providers-http');
    web3Instance.currentProvider = new Web3HttpProvider(Web3HttpProvider, { gasPrice: 'auto' });
    
    const POAMiddleware = require('web3-provider-engine/subproviders/vanilla.js');
    const providerEngine = new (require('web3-provider-engine'));
    const provider = new POAMiddleware((req, callback) => {
        web3Instance.currentProvider.sendAsync(req, callback);
    });
    providerEngine.addProvider(provider);
    providerEngine.on('error', (e) => { console.log('Provider Error:', e); });
    providerEngine.start();
    
    web3Instance.setProvider(providerEngine);

    console.log("✅ POA middleware injected");
}

function printBanner() {
    console.log(`
██████╗ ██╗  ██╗ █████╗ ██████╗  ██████╗ ███████╗
██╔══██╗██║  ██║██╔══██╗██╔══██╗██╔═══██╗██╔════╝
██████╔╝███████║███████║██████╔╝██║   ██║███████╗
██╔═══╝ ██╔══██║██╔══██║██╔══██╗██║   ██║╚════██║
██║     ██║  ██║██║  ██║██║  ██║╚██████╔╝███████║
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
    `);
    console.log("Pharos Username Minter v7.2 | Two-Step Commit-Register (FIXED)");
    console.log("=".repeat(60));
    console.log(`Blockchain: Pharos Testnet (Chain ID: ${process.env.CHAIN_ID || '688688'})`);
    console.log("="repeat(60));
}

// =============================================
// MAIN MINTER CLASS
// =============================================
class PharosMultiMinter {
    constructor(privateKey, userAgent = null) {
        if (!privateKey || privateKey === '0x'.concat('0'.repeat(64))) {
            throw new Error("Invalid private key");
        }
        
        console.log('\n'.concat('=').repeat(50));
        console.log(`Node.js version: ${process.version}`);
        console.log(`Web3 version: ${Web3.version}`);
        console.log('=').repeat(50);
        
        const headers = {
            'User-Agent': userAgent || this.generateRandomUserAgent(),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Request-ID': uuidv4()
        };
        
        const rpcUrl = process.env.RPC_URL || 'https://testnet.dplabs-internal.com';
        console.log(`🔗 Connecting to RPC: ${rpcUrl}`);
        
        this.web3 = new Web3(new Web3.providers.HttpProvider(rpcUrl, { headers, timeout: 120000 }));
        
        injectPoaMiddleware(this.web3);
            
        if (!this.web3.isConnected()) {
            throw new Error("❌ Failed to connect to RPC endpoint");
        }
        console.log("✅ Connected to blockchain");
        
        this.account = this.web3.eth.accounts.privateKeyToAccount(privateKey);
        this.contractAddress = this.web3.utils.toChecksumAddress(
            process.env.CONTRACT_ADDRESS || '0x51be1ef20a1fd5179419738fc71d95a8b6f8a175'
        );
        
        try {
            this.contract = new this.web3.eth.Contract(
                CONTRACT_ABI,
                this.contractAddress
            );
            console.log(`📜 Contract loaded: ${this.contractAddress}`);
        } catch (e) {
            throw new Error(`❌ Contract initialization failed: ${e.message}`);
        }
            
        this.gasPriceHistory = [];
        this.maxHistorySize = 5;
        this.chainId = parseInt(process.env.CHAIN_ID, 10) || 688688;
    }

    static generateRandomUserAgent() {
        const iosVersions = ['16.0', '16.1', '16.2', '16.3', '16.4', '16.5', '16.6', '17.0', '17.1'];
        const safariVersions = ['604.1', '605.1.15', '606.1.36', '607.1.40'];
        
        return `Mozilla/5.0 (iPhone; CPU iPhone OS ${iosVersions[Math.floor(Math.random() * iosVersions.length)].replace('.', '_')} like Mac OS X) ` +
            `AppleWebKit/${safariVersions[Math.floor(Math.random() * safariVersions.length)]} ` +
            `(KHTML, like Gecko) Version/${iosVersions[Math.floor(Math.random() * iosVersions.length)]} ` +
            `Mobile/15E148 Safari/${safariVersions[Math.floor(Math.random() * safariVersions.length)]}`;
    }

    static generateUsername(length = 5) {
        const characters = 'abcdefghijklmnopqrstuvwxyz';
        return new Array(length).fill(0).map(() => characters[Math.floor(Math.random() * characters.length)]).join('');
    }

    static generateSecret() {
        const buffer = Buffer.alloc(32);
        randomFillSync(buffer);
        return buffer;
    }

    generateCommitment(name, secret) {
        const nameHash = this.web3.utils.soliditySha3({ t: 'string', v: name });
        const commitment = this.web3.utils.soliditySha3({ t: 'bytes32', v: nameHash }, { t: 'bytes32', v: secret });
        return commitment;
    }

    async getMinCommitmentAge() {
        try {
            return await this.contract.methods.minCommitmentAge().call();
        } catch (e) {
            console.warn(`⚠️ Failed to get min commitment age: ${e.message}`);
            return 60; // Default to 60 seconds
        }
    }

    async getMintingFee() {
        try {
            return await this.contract.methods.mintingFee().call();
        } catch (e) {
            console.warn(`⚠️ Failed to get minting fee: ${e.message}`);
            return this.web3.utils.toWei('0.01', 'ether'); // Default fee if failed
        }
    }

    async getBalance() {
        try {
            const balance = await this.web3.eth.getBalance(this.account.address);
            return this.web3.utils.fromWei(balance, 'ether');
        } catch (e) {
            console.warn(`⚠️ Failed to get balance: ${e.message}`);
            return 0.0;
        }
    }

    async isUsernameAvailable(fullUsername) {
        try {
            const available = await this.contract.methods.available(fullUsername).call();
            return available;
        } catch (e) {
            console.warn(`⚠️ 'available' function error: ${e.message}`);
            return false;
        }
    }

    async getGasPrice() {
        const gasPrices = [];

        try {
            const gasPrice = await this.web3.eth.getGasPrice();
            gasPrices.push(parseInt(gasPrice));
            console.log(`  💡 Method 1 gas price: ${this.web3.utils.fromWei(gasPrice, 'gwei')} gwei`);
        } catch (e) {
            console.warn(`  ⚠️ Method 1 failed: ${e.message}`);
        }

        try {
            const gasPrice = await this.web3.eth.getGasPrice();
            gasPrices.push(parseInt(gasPrice));
            console.log(`  💡 Method 2 gas price: ${this.web3.utils.fromWei(gasPrice, 'gwei')} gwei`);
        } catch (e) {
            console.warn(`  ⚠️ Method 2 failed: ${e.message}`);
        }

        if (this.gasPriceHistory.length) {
            const historicalAvg = this.gasPriceHistory.sort((a, b) => a - b)[Math.floor(this.gasPriceHistory.length / 2)];
            gasPrices.push(historicalAvg);
            console.log(`  💡 Method 3 historical median: ${this.web3.utils.fromWei(historicalAvg, 'gwei')} gwei`);
        }

        if (gasPrices.length) {
            let finalGasPrice = gasPrices.sort((a, b) => a - b)[Math.floor(gasPrices.length / 2)];
            const adjustment = Math.random() * 0.1 + 0.95;
            finalGasPrice = Math.floor(finalGasPrice * adjustment);

            this.gasPriceHistory.push(finalGasPrice);
            if (this.gasPriceHistory.length > this.maxHistorySize) {
                this.gasPriceHistory.shift();
            }

            console.log(`  ⛽ Final gas price: ${this.web3.utils.fromWei(finalGasPrice, 'gwei')} gwei`);
            return finalGasPrice;
        } else {
            const defaultGas = this.web3.utils.toWei('20', 'gwei');
            console.log(`  ⚠️ All methods failed, using default: ${this.web3.utils.fromWei(defaultGas, 'gwei')} gwei`);
            return defaultGas;
        }
    }

    async estimateCommitGas(commitment) {
        try {
            const gasEstimate = await this.contract.methods.commit(commitment).estimateGas({ from: this.account.address });
            const gasLimit = Math.floor(gasEstimate * 1.3);
            console.log(`  ⛽ Commit gas estimate: ${gasEstimate} (using ${gasLimit})`);
            return gasLimit;
        } catch (e) {
            console.warn(`  ⚠️ Commit gas estimation failed: ${e.message}`);
            return 150000;
        }
    }

    async estimateRegisterGas(fullUsername, owner, secret, fee) {
        try {
            const gasEstimate = await this.contract.methods.register(fullUsername, owner, secret).estimateGas({
                from: this.account.address,
                value: fee
            });
            const gasLimit = Math.floor(gasEstimate * 1.5);
            console.log(`  ⛽ Register gas estimate: ${gasEstimate} (using ${gasLimit})`);
            return gasLimit;
        } catch (e) {
            console.warn(`  ⚠️ Register gas estimation failed: ${e.message}`);
            return 450000;
        }
    }

    async signAndSendTransaction(tx) {
        try {
            const signedTx = await this.account.signTransaction(tx);
            const txHash = await this.web3.eth.sendSignedTransaction(signedTx.rawTransaction);
            console.log(`  🔗 Commit/Rgster tx sent: ${txHash}`);
            return txHash;
        } catch (e) {
            console.error(`  ❌ Tx signing/sending failed: ${e.message}`);
            return null;
        }
    }

    async makeCommitment(fullUsername) {
        const secret = PharosMultiMinter.generateSecret();
        const commitment = this.generateCommitment(fullUsername, secret);

        try {
            const nonce = await this.web3.eth.getTransactionCount(this.account.address);
            const gasPrice = await this.getGasPrice();
            const gasLimit = await this.estimateCommitGas(commitment);

            const tx = {
                chainId: this.chainId,
                from: this.account.address,
                nonce: nonce,
                gasPrice: gasPrice,
                gas: gasLimit,
                data: this.contract.methods.commit(commitment).encodeABI()
            };

            try {
                const txHash = await this.signAndSendTransaction(tx);
                if (!txHash) return null;
                console.log(`  🔗 Commit transaction sent: ${txHash}`);

                try {
                    const receipt = await this.web3.eth.getTransactionReceipt(txHash, { timeout: 180 });
                    if (receipt.status) {
                        console.log("  ✅ Commitment confirmed");
                        return secret;
                    } else {
                        console.log("  ❌ Commitment failed");
                        return null;
                    }
                } catch (e) {
                    console.log("  ⏱️ Commit tx timeout, but continuing...");
                    return secret;
                }
            } catch (e) {
                console.warn(`  ⚠️ Commitment failed: ${e.message}`);
                return null;
            }
        } catch (e) {
            console.warn(`  ⚠️ Commitment failed: ${e.message}`);
            return null;
        }
    }

    async registerUsername(fullUsername, secret) {
        try {
            const fee = await this.getMintingFee();
            const nonce = await this.web3.eth.getTransactionCount(this.account.address);
            const gasPrice = await this.getGasPrice();
            const gasLimit = await this.estimateRegisterGas(fullUsername, this.account.address, secret, fee);

            const tx = {
                chainId: this.chainId,
                from: this.account.address,
                nonce: nonce,
                value: fee,
                gasPrice: gasPrice,
                gas: gasLimit,
                data: this.contract.methods.register(fullUsername, this.account.address, secret).encodeABI()
            };

            try {
                const txHash = await this.signAndSendTransaction(tx);
                if (!txHash) return null;
                console.log(`  🔗 Register transaction sent: ${txHash}`);

                try {
                    const receipt = await this.web3.eth.getTransactionReceipt(txHash, { timeout: 300 });
                    if (receipt.status) {
                        console.log("  ✅ Registration successful");
                        return txHash;
                    } else {
                        console.log("  ❌ Registration failed");
                        return null;
                    }
                } catch (e) {
                    console.log("  ⏱️ Register tx timeout");
                    return txHash;
                }
            } catch (e) {
                console.warn(`  ⚠️ Registration failed: ${e.message}`);
                return null;
            }
        } catch (e) {
            console.warn(`  ⚠️ Registration failed: ${e.message}`);
            return null;
        }
    }

    async mintUsername(maxAttempts = 5) {
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            const username = PharosMultiMinter.generateUsername();
            const fullUsername = `${username}.phrs`;

            try {
                if (!await this.isUsernameAvailable(fullUsername)) {
                    console.log(`  ❌ [${attempt + 1}/${maxAttempts}] Taken: ${fullUsername}`);
                    await new Promise(resolve => setTimeout(resolve, 500)); // Short delay between checks
                    continue;
                }
            } catch (e) {
                console.warn(`  ⚠️ Availability check failed: ${e.message}`);
                await new Promise(resolve => setTimeout(resolve, 1000));
                continue;
            }

            console.log(`  ✅ [${attempt + 1}/${maxAttempts}] Available: ${fullUsername}`);

            console.log("  🔐 Making commitment...");
            let secret = await this.makeCommitment(fullUsername);
            if (!secret) {
                console.log("  ❌ Commitment failed, trying another name");
                await new Promise(resolve => setTimeout(resolve, 1000));
                continue;
            }

            const minAge = await this.getMinCommitmentAge();
            const waitTime = Math.max(minAge, 60); // Minimum 60 seconds
            console.log(`  ⏳ Waiting ${waitTime} seconds for commitment to mature...`);
            await new Promise(resolve => setTimeout(resolve, waitTime * 1000));

            console.log("  📝 Registering username...");
            const txHash = await this.registerUsername(fullUsername, secret);

            if (txHash) {
                const explorerUrl = process.env.EXPLORER_BASE_URL || 'https://testnet.pharosscan.xyz/tx/';
                const explorerLink = `${explorerUrl}${txHash}`;

                return {
                    status: 'success',
                    username: fullUsername,
                    txHash: txHash,
                    explorerUrl: explorerLink
                };
            }

            await new Promise(resolve => setTimeout(resolve, 1500)); // Delay between mint attempts
        }

        return { status: 'failed', reason: 'No available names found after attempts' };
    }
}

// =============================================
// LOAD ACCOUNTS FUNCTION
// =============================================
function loadAccounts() {
    const accounts = [];

    const pk1 = process.env.PRIVATE_KEY_1;
    if (pk1 && pk1 !== '0x'.concat('0'.repeat(64))) {
        const ua1 = process.env.USER_AGENT_1 || "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";
        accounts.push({
            name: 'Account 1 (iPhone 16 Pro Max)',
            privateKey: pk1,
            userAgent: ua1
        });
    }

    const pk2 = process.env.PRIVATE_KEY_2;
    if (pk2 && pk2 !== '0x'.concat('0'.repeat(64))) {
        const ua2 = process.env.USER_AGENT_2 || "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1";
        accounts.push({
            name: 'Account 2 (iPhone 15)',
            privateKey: pk2,
            userAgent: ua2
        });
    }

    if (!accounts.length) {
        throw new Error("No valid accounts configured. Check PRIVATE_KEY_1 environment variable.");
    }

    return accounts;
}

// =============================================
// MAIN FUNCTION
// =============================================
async function main() {
    printBanner();

    try {
        const accounts = loadAccounts();
        console.log(`\n🔍 Found ${accounts.length} account(s) to process`);
        
        let totalSuccess = 0;
        let totalFailed = 0;
        let totalPending = 0;

        for (let i = 0; i < accounts.length; i++) {
            const account = accounts[i];
            console.log(`\n${'='.repeat(60)}`);
            console.log(`🔑 Processing Account ${i + 1}: ${account.name}`);
            console.log(`📱 User Agent: ${account.userAgent}`);
            console.log(`-${'-'.repeat(58)}`);

            try {
                const minter = new PharosMultiMinter(account.privateKey, account.userAgent);

                const address = minter.account.address;
                try {
                    const balance = await minter.getBalance();
                    const fee = await minter.getMintingFee();
                    const feeEth = minter.web3.utils.fromWei(fee, 'ether');

                    console.log(`💼 Wallet: ${address}`);
                    console.log(`💰 Balance: ${balance.toFixed(6)} PHRS`);
                    console.log(`⛽ Minting Fee: ${feeEth.toFixed(6)} PHRS`);

                    if (balance < feeEth) {
                        console.log(`❌ Insufficient balance. Needed: ${feeEth.toFixed(6)} PHRS`);
                        console.log("Visit testnet faucet if available");
                        totalFailed += 1;
                        continue;
                    }
                } catch (e) {
                    console.warn(`⚠️ Failed to get account info: ${e.message}`);
                    console.log("Continuing with minting attempt...");
                }

                console.log("\n🚀 Starting two-step minting process...");
                const startTime = Date.now() / 1000;
                const result = await minter.mintUsername(7);
                const elapsed = (Date.now() / 1000) - startTime;

                if (result && result.status === 'success') {
                    console.log(`\n🎉 Username Minted Successfully in ${elapsed.toFixed(2)}s!`);
                    console.log(`🔑 Username: ${result.username}`);
                    console.log(`🔗 View transaction: ${result.explorerUrl}`);
                    totalSuccess += 1;
                } else if (result && result.status === 'pending') {
                    console.log(`\n⏱️ Transaction pending after ${elapsed.toFixed(2)}s`);
                    console.log(`🔗 Track transaction: ${result.explorerUrl || 'N/A'}`);
                    totalPending += 1;
                } else {
                    console.log(`\n❌ Minting failed after ${elapsed.toFixed(2)}s`);
                    const reason = result ? result.reason || 'Unknown error' : 'No result returned';
                    console.log(`Reason: ${reason}`);
                    totalFailed += 1;
                }

                console.log(`\n⏱️ Account processing time: ${elapsed.toFixed(2)} seconds`);
            } catch (e) {
                console.warn(`\n⚠️ Critical error in account processing: ${e.message}`);
                console.error(e.stack);
                console.log("Skipping to next account...");
                totalFailed += 1;
            }

            if (i < accounts.length - 1) {
                const delay = 15;
                console.log(`\n⏳ Waiting ${delay} seconds before next account...`);
                await new Promise(resolve => setTimeout(resolve, delay * 1000));
            }
        }

        console.log(`\n${'='.repeat(60)}`);
        console.log("📊 Minting Summary:");
        console.log(`   ✅ Success: ${totalSuccess}`);
        console.log(`   ⏱️ Pending: ${totalPending}`);
        console.log(`   ❌ Failed: ${totalFailed}`);
        console.log(`   🔢 Total Accounts: ${accounts.length}`);
        console.log(`=${'='.repeat(58)}`);
        console.log("✅ All accounts processed");
        console.log(`=${'='.repeat(58)}`);
        process.exit(0);
    } catch (e) {
        console.error(`\n💥 Unexpected global error: ${e.message}`);
        process.exit(1);
    }
}

process.on('SIGINT', () => {
    console.log('\n🚫 Operation cancelled by user');
    process.exit(0);
});

main();