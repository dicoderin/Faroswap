const Web3 = require('web3');
const dotenv = require('dotenv');
const crypto = require('crypto');
const { v4: uuidv4 } = require('uuid');
const { randomFillSync } = require('crypto');

dotenv.config();

// =============================================
// PEMERIKSAAN INTEGRITAS PUSTAKA WEB3
// Ini adalah penambahan penting untuk mengatasi error 'Web3.providers.HttpProvider is not a constructor'
// dan 'Web3 version: undefined' yang terlihat di log Anda.
// =============================================
if (typeof Web3 !== 'function' || !Web3.providers || typeof Web3.providers.HttpProvider !== 'function') {
    console.error("ðŸ’¥ Kesalahan Kritis: Pustaka 'web3' tidak dimuat dengan benar atau tidak kompatibel.");
    console.error("ðŸ”Œ 'Web3.providers.HttpProvider' tidak ditemukan sebagai konstruktor.");
    console.error("ðŸ”Œ Pastikan Anda telah menginstal paket 'web3' (misal: 'npm install web3')");
    console.error("ðŸ”Œ dan itu adalah versi yang kompatibel (misal: 1.x.x atau 4.x.x).");
    process.exit(1); // Keluar jika Web3 tidak berfungsi secara fundamental
}

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
    // --- PERBAIKAN FUNGSI INJEKSI MIDDLEWARE POA ---
    // Logika sebelumnya mencoba menginisialisasi ulang currentProvider dengan cara yang salah
    // dan juga secara tidak perlu me-require 'web3-providers-http' di sini.
    // Sekarang, kita akan membungkus provider yang sudah ada dengan ProviderEngine secara benar.

    const ProviderEngine = require('web3-provider-engine');
    const POAMiddleware = require('web3-provider-engine/subproviders/vanilla.js'); // Mengikuti penggunaan Anda sebelumnya

    const engine = new ProviderEngine();

    // Tambahkan provider asli web3Instance sebagai subprovider ke ProviderEngine.
    // POAMiddleware (vanilla.js) adalah passthrough yang mengambil fungsi 'send'.
    // Menggunakan 'send' daripada 'sendAsync' karena 'sendAsync' sudah deprecated di Web3.js modern.
    engine.addProvider(new POAMiddleware((payload, callback) => {
        web3Instance.currentProvider.send(payload, callback);
    }));
    
    engine.on('error', (e) => { console.error('Kesalahan Provider Engine:', e); }); // Mengubah log menjadi error
    engine.start();
    
    web3Instance.setProvider(engine);

    console.log("âœ… Middleware Provider Engine (POA) disuntikkan."); // Pesan lebih deskriptif
}

function printBanner() {
    console.log(`
â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ•—  â–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—  â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—
â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â•â•â•
â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—
â–ˆâ–ˆâ•”â•â•â•â• â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â•šâ•â•â•â•â–ˆâ–ˆâ•‘
â–ˆâ–ˆâ•‘     â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â•šâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘
â•šâ•â•     â•šâ•â•  â•šâ•â•â•šâ•â•  â•šâ•â•â•šâ•â•  â•šâ•â• â•šâ•â•â•â•â•â• â•šâ•â•â•â•â•â•â•
    `);
    console.log("Pharos Username Minter v7.2 | Two-Step Commit-Register (FIXED)");
    console.log("=>".repeat(60));
    console.log(`Blockchain: Pharos Testnet (Chain ID: ${process.env.CHAIN_ID || '688688'})`);
    console.log("=".repeat(60))
}

// =============================================
// MAIN MINTER CLASS
// =============================================
class PharosMultiMinter {
    constructor(privateKey, userAgent = null) {
        if (!privateKey || privateKey === '0x'.concat('0'.repeat(64))) {
            throw new Error("Kunci pribadi tidak valid.");
        }
        
        console.log("=".repeat(60))
        console.log(`Node.js version: ${process.version}`);
        console.log(`Web3 version: ${Web3.version || 'undefined'}`); // Pastikan Web3.version ditampilkan
        console.log("=>".repeat(60));
        
        const headers = {
            'User-Agent': userAgent || this.generateRandomUserAgent(),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Request-ID': uuidv4()
        };
        
        const rpcUrl = process.env.RPC_URL || 'https://testnet.dplabs-internal.com';
        console.log(`ðŸ”— Menghubungkan ke RPC: ${rpcUrl}`);
        
        // Baris ini adalah tempat error awal terjadi.
        // Dengan penambahan pemeriksaan di bagian atas file, seharusnya baris ini
        // hanya akan dieksekusi jika Web3.providers.HttpProvider valid.
        this.web3 = new Web3(new Web3.providers.HttpProvider(rpcUrl, { headers, timeout: 120000 }));
        
        injectPoaMiddleware(this.web3);
            
        // Periksa koneksi web3
        // Beberapa versi Web3.js mungkin tidak memiliki isConnected() lagi
        // Sebuah cara yang lebih modern adalah dengan mencoba memanggil sebuah metode (misal: getChainId)
        // atau melihat jika provider sudah disetel.
        // Untuk tujuan kompatibilitas, kita biarkan saja jika tidak ada, karena error akan muncul pada transaksi.
        try {
            if (this.web3.currentProvider && this.web3.currentProvider.connected) {
                console.log("âœ… Terhubung ke blockchain.");
            } else {
                // Sebagai fallback jika isConnected tidak ada atau bermasalah
                // Ini mungkin tidak mengindikasikan kegagalan koneksi jika node/provider lain berhasil.
                console.warn("âš ï¸ Tidak dapat mengonfirmasi koneksi RPC dengan Web3.js isConnected/connected.");
                console.warn("   Lanjutkan dengan asumsi koneksi akan terbentuk saat transaksi.");
            }
        } catch (e) {
            console.warn(`âš ï¸ Pengecekan koneksi RPC bermasalah: ${e.message}. Lanjutkan dengan asumsi koneksi.`);
        }
        
        this.account = this.web3.eth.accounts.privateKeyToAccount(privateKey);
        this.contractAddress = this.web3.utils.toChecksumAddress(
            process.env.CONTRACT_ADDRESS || '0x51be1ef20a1fd5179419738fc71d95a8b6f8a175'
        );
        
        try {
            this.contract = new this.web3.eth.Contract(
                CONTRACT_ABI,
                this.contractAddress
            );
            console.log(`ðŸ“œ Kontrak dimuat: ${this.contractAddress}`);
        } catch (e) {
            throw new Error(`âŒ Inisialisasi kontrak gagal: ${e.message}`);
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
            console.warn(`âš ï¸ Gagal mendapatkan usia komitmen minimum: ${e.message}`);
            return 60; // Default ke 60 detik
        }
    }

    async getMintingFee() {
        try {
            return await this.contract.methods.mintingFee().call();
        } catch (e) {
            console.warn(`âš ï¸ Gagal mendapatkan biaya pencetakan: ${e.message}`);
            return this.web3.utils.toWei('0.01', 'ether'); // Biaya default jika gagal
        }
    }

    async getBalance() {
        try {
            const balance = await this.web3.eth.getBalance(this.account.address);
            return this.web3.utils.fromWei(balance, 'ether');
        } catch (e) {
            console.warn(`âš ï¸ Gagal mendapatkan saldo: ${e.message}`);
            return 0.0;
        }
    }

    async isUsernameAvailable(fullUsername) {
        try {
            const available = await this.contract.methods.available(fullUsername).call();
            return available;
        } catch (e) {
            console.warn(`âš ï¸ Error fungsi 'available': ${e.message}`);
            return false;
        }
    }

    async getGasPrice() {
        const gasPrices = [];

        try {
            const gasPrice = await this.web3.eth.getGasPrice();
            gasPrices.push(parseInt(gasPrice));
            console.log(`  ðŸ’¡ Harga gas Metode 1: ${this.web3.utils.fromWei(gasPrice, 'gwei')} gwei`);
        } catch (e) {
            console.warn(`  âš ï¸ Metode 1 gagal: ${e.message}`);
        }

        try {
            const gasPrice = await this.web3.eth.getGasPrice();
            gasPrices.push(parseInt(gasPrice));
            console.log(`  ðŸ’¡ Harga gas Metode 2: ${this.web3.utils.fromWei(gasPrice, 'gwei')} gwei`);
        } catch (e) {
            console.warn(`  âš ï¸ Metode 2 gagal: ${e.message}`);
        }

        if (this.gasPriceHistory.length) {
            const historicalAvg = this.gasPriceHistory.sort((a, b) => a - b)[Math.floor(this.gasPriceHistory.length / 2)];
            gasPrices.push(historicalAvg);
            console.log(`  ðŸ’¡ Median historis Metode 3: ${this.web3.utils.fromWei(historicalAvg, 'gwei')} gwei`);
        }

        if (gasPrices.length) {
            let finalGasPrice = gasPrices.sort((a, b) => a - b)[Math.floor(gasPrices.length / 2)];
            const adjustment = Math.random() * 0.1 + 0.95;
            finalGasPrice = Math.floor(finalGasPrice * adjustment);

            this.gasPriceHistory.push(finalGasPrice);
            if (this.gasPriceHistory.length > this.maxHistorySize) {
                this.gasPriceHistory.shift();
            }

            console.log(`  âš¡ Harga gas akhir: ${this.web3.utils.fromWei(finalGasPrice, 'gwei')} gwei`);
            return finalGasPrice;
        } else {
            const defaultGas = this.web3.utils.toWei('20', 'gwei');
            console.log(`  âš ï¸ Semua metode gagal, menggunakan default: ${this.web3.utils.fromWei(defaultGas, 'gwei')} gwei`);
            return defaultGas;
        }
    }

    async estimateCommitGas(commitment) {
        try {
            const gasEstimate = await this.contract.methods.commit(commitment).estimateGas({ from: this.account.address });
            const gasLimit = Math.floor(gasEstimate * 1.3);
            console.log(`  âš¡ Estimasi gas komit: ${gasEstimate} (menggunakan ${gasLimit})`);
            return gasLimit;
        } catch (e) {
            console.warn(`  âš ï¸ Estimasi gas komit gagal: ${e.message}`);
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
            console.log(`  âš¡ Estimasi gas daftar: ${gasEstimate} (menggunakan ${gasLimit})`);
            return gasLimit;
        } catch (e) {
            console.warn(`  âš ï¸ Estimasi gas daftar gagal: ${e.message}`);
            return 450000;
        }
    }

    async signAndSendTransaction(tx) {
        try {
            const signedTx = await this.account.signTransaction(tx);
            const txHash = await this.web3.eth.sendSignedTransaction(signedTx.rawTransaction);
            console.log(`  ðŸ”— Tx komit/daftar dikirim: ${txHash.transactionHash}`); // Mengambil hash dari objek respons
            return txHash.transactionHash;
        } catch (e) {
            console.error(`  âŒ Penandatanganan/pengiriman Tx gagal: ${e.message}`);
            return null;
        }
    }

    async makeCommitment(fullUsername) {
        const secret = PharosMultiMinter.generateSecret();
        const commitment = this.generateCommitment(fullUsername, secret);

        try {
            const nonce = await this.web3.eth.getTransactionCount(this.account.address, 'pending'); // Gunakan 'pending' untuk nonce terbaru
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
                console.log(`  ðŸ”— Transaksi komit dikirim: ${txHash}`);

                try {
                    const receipt = await this.web3.eth.getTransactionReceipt(txHash); // Tidak perlu timeout jika Anda ingin menunggu sampai selesai
                    if (receipt && receipt.status) {
                        console.log("  âœ… Komitmen dikonfirmasi.");
                        return secret;
                    } else {
                        console.log("  âŒ Komitmen gagal.");
                        return null;
                    }
                } catch (e) {
                    console.warn(`  âš ï¸ Gagal mendapatkan receipt komit (mungkin timeout): ${e.message}`);
                    return secret; // Tetap kembalikan secret, karena transaksi mungkin masih diproses
                }
            } catch (e) {
                console.warn(`  âš ï¸ Komitmen gagal: ${e.message}`);
                return null;
            }
        } catch (e) {
            console.warn(`  âš ï¸ Komitmen gagal pada tahap persiapan: ${e.message}`);
            return null;
        }
    }

    async registerUsername(fullUsername, secret) {
        try {
            const fee = await this.getMintingFee();
            const nonce = await this.web3.eth.getTransactionCount(this.account.address, 'pending'); // Gunakan 'pending' untuk nonce terbaru
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
                console.log(`  ðŸ”— Transaksi daftar dikirim: ${txHash}`);

                try {
                    const receipt = await this.web3.eth.getTransactionReceipt(txHash); // Tidak perlu timeout
                    if (receipt && receipt.status) {
                        console.log("  âœ… Pendaftaran berhasil.");
                        return txHash;
                    } else {
                        console.log("  âŒ Pendaftaran gagal.");
                        return null;
                    }
                } catch (e) {
                    console.warn(`  âš ï¸ Gagal mendapatkan receipt daftar (mungkin timeout): ${e.message}`);
                    return txHash; // Tetap kembalikan hash, transaksi mungkin masih diproses
                }
            } catch (e) {
                console.warn(`  âš ï¸ Pendaftaran gagal: ${e.message}`);
                return null;
            }
        } catch (e) {
            console.warn(`  âš ï¸ Pendaftaran gagal pada tahap persiapan: ${e.message}`);
            return null;
        }
    }

    async mintUsername(maxAttempts = 5) {
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            const username = PharosMultiMinter.generateUsername();
            const fullUsername = `${username}.phrs`;

            try {
                if (!await this.isUsernameAvailable(fullUsername)) {
                    console.log(`  âŒ [${attempt + 1}/${maxAttempts}] Terpakai: ${fullUsername}`);
                    await new Promise(resolve => setTimeout(resolve, 500)); // Penundaan singkat antar pengecekan
                    continue;
                }
            } catch (e) {
                console.warn(`  âš ï¸ Pemeriksaan ketersediaan gagal: ${e.message}`);
                await new Promise(resolve => setTimeout(resolve, 1000));
                continue;
            }

            console.log(`  âœ… [${attempt + 1}/${maxAttempts}] Tersedia: ${fullUsername}`);

            console.log("  ðŸ” Membuat komitmen...");
            let secret = await this.makeCommitment(fullUsername);
            if (!secret) {
                console.log("  âŒ Komitmen gagal, mencoba nama lain.");
                await new Promise(resolve => setTimeout(resolve, 1000));
                continue;
            }

            const minAge = await this.getMinCommitmentAge();
            const waitTime = Math.max(parseInt(minAge), 60); // Minimum 60 detik, pastikan integer
            console.log(`  â³ Menunggu ${waitTime} detik agar komitmen matang...`);
            await new Promise(resolve => setTimeout(resolve, waitTime * 1000));

            console.log("  ðŸ“ Mendaftarkan nama pengguna...");
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

            await new Promise(resolve => setTimeout(resolve, 1500)); // Penundaan antar percobaan pencetakan
        }

        return { status: 'failed', reason: 'Tidak ada nama yang tersedia setelah beberapa percobaan.' };
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
        throw new Error("Tidak ada akun yang valid dikonfigurasi. Periksa variabel lingkungan PRIVATE_KEY_1.");
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
        console.log(`\nðŸ” Ditemukan ${accounts.length} akun untuk diproses.`);
        
        let totalSuccess = 0;
        let totalFailed = 0;
        let totalPending = 0;

        for (let i = 0; i < accounts.length; i++) {
            const account = accounts[i];
            console.log(`\n${'='.repeat(60)}`);
            console.log(`ðŸ”‘ Memproses Akun ${i + 1}: ${account.name}`);
            console.log(`ðŸ“± User Agent: ${account.userAgent}`);
            console.log(`-${'-'.repeat(58)}`);

            try {
                const minter = new PharosMultiMinter(account.privateKey, account.userAgent);

                const address = minter.account.address;
                try {
                    const balance = await minter.getBalance();
                    const fee = await minter.getMintingFee();
                    const feeEth = minter.web3.utils.fromWei(fee, 'ether');

                    console.log(`ðŸ’¼ Dompet: ${address}`);
                    console.log(`ðŸ’° Saldo: ${balance.toFixed(6)} PHRS`);
                    console.log(`âš¡ Biaya Pencetakan: ${feeEth.toFixed(6)} PHRS`);

                    if (balance < feeEth) {
                        console.log(`âŒ Saldo tidak mencukupi. Dibutuhkan: ${feeEth.toFixed(6)} PHRS`);
                        console.log("Kunjungi faucet testnet jika tersedia.");
                        totalFailed += 1;
                        // Tambahkan 'continue' di sini untuk melewati akun ini jika saldo tidak cukup
                        // Agar tidak mencoba minting dengan saldo 0.
                        continue; 
                    }
                } catch (e) {
                    console.warn(`âš ï¸ Gagal mendapatkan info akun: ${e.message}`);
                    console.log("Lanjutkan dengan percobaan pencetakan...");
                }

                console.log("\nðŸš€ Memulai proses pencetakan dua langkah...");
                const startTime = Date.now() / 1000;
                const result = await minter.mintUsername(7);
                const elapsed = (Date.now() / 1000) - startTime;

                if (result && result.status === 'success') {
                    console.log(`\nðŸŽ‰ Nama Pengguna berhasil dicetak dalam ${elapsed.toFixed(2)} detik!`);
                    console.log(`ðŸ”‘ Nama Pengguna: ${result.username}`);
                    console.log(`ðŸ”— Lihat transaksi: ${result.explorerUrl}`);
                    totalSuccess += 1;
                } else if (result && result.status === 'pending') {
                    console.log(`\nâ±ï¸ Transaksi tertunda setelah ${elapsed.toFixed(2)} detik`);
                    console.log(`ðŸ”— Lacak transaksi: ${result.explorerUrl || 'N/A'}`);
                    totalPending += 1;
                } else {
                    console.log(`\nâŒ Pencetakan gagal setelah ${elapsed.toFixed(2)} detik.`);
                    const reason = result ? result.reason || 'Error tidak diketahui' : 'Tidak ada hasil yang dikembalikan.';
                    console.log(`Alasan: ${reason}`);
                    totalFailed += 1;
                }

                console.log(`\nâ±ï¸ Waktu pemrosesan akun: ${elapsed.toFixed(2)} detik.`);
            } catch (e) {
                console.warn(`\nâš ï¸ Kesalahan kritis dalam pemrosesan akun: ${e.message}`);
                console.error(e.stack);
                console.log("Lewati ke akun berikutnya...");
                totalFailed += 1;
            }

            if (i < accounts.length - 1) {
                const delay = 15;
                console.log(`\nâ³ Menunggu ${delay} detik sebelum akun berikutnya...`);
                await new Promise(resolve => setTimeout(resolve, delay * 1000));
            }
        }

        console.log(`\n${'='.repeat(60)}`);
        console.log("ðŸ“Š Ringkasan Pencetakan:");
        console.log(`   âœ… Berhasil: ${totalSuccess}`);
        console.log(`   â±ï¸ Tertunda: ${totalPending}`);
        console.log(`   âŒ Gagal: ${totalFailed}`);
        console.log(`   ðŸ”¢ Total Akun: ${accounts.length}`);
        console.log(`=${'='.repeat(58)}`);
        console.log("âœ… Semua akun selesai diproses.");
        console.log(`=${'='.repeat(58)}`);
        process.exit(0);
    } catch (e) {
        console.error(`\nðŸ’¥ Kesalahan global tidak terduga: ${e.message}`);
        process.exit(1);
    }
}

process.on('SIGINT', () => {
    console.log('\nðŸš« Operasi dibatalkan oleh pengguna.');
    process.exit(0);
});

main();