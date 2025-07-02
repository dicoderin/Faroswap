#!/usr/bin/env node
'use strict';

const dotenv = require('dotenv');
dotenv.config();

const Web3 = require('web3');
const { randomFillSync } = require('crypto');
const { v4: uuidv4 } = require('uuid');

// =============================================
// CONTRACT ABI
// =============================================
const CONTRACT_ABI = [
  {
    inputs: [
      { internalType: 'bytes32', name: 'commitment', type: 'bytes32' }
    ],
    name: 'commit',
    outputs: [],
    stateMutability: 'nonpayable',
    type: 'function'
  },
  {
    inputs: [
      { internalType: 'string', name: 'name', type: 'string' },
      { internalType: 'address', name: 'owner', type: 'address' },
      { internalType: 'bytes32', name: 'secret', type: 'bytes32' }
    ],
    name: 'register',
    outputs: [],
    stateMutability: 'payable',
    type: 'function'
  },
  {
    inputs: [
      { internalType: 'string', name: 'name', type: 'string' }
    ],
    name: 'available',
    outputs: [
      { internalType: 'bool', name: '', type: 'bool' }
    ],
    stateMutability: 'view',
    type: 'function'
  },
  {
    inputs: [],
    name: 'minCommitmentAge',
    outputs: [
      { internalType: 'uint256', name: '', type: 'uint256' }
    ],
    stateMutability: 'view',
    type: 'function'
  },
  {
    inputs: [],
    name: 'mintingFee',
    outputs: [
      { internalType: 'uint256', name: '', type: 'uint256' }
    ],
    stateMutability: 'view',
    type: 'function'
  }
];

// =============================================
// UTILITIES
// =============================================

/**
 * Untuk chain PoA via HTTP provider:  
 * alihkan send → sendAsync jika perlu.
 */
function injectPoaMiddleware(web3) {
  const prov = web3.currentProvider;
  if (prov && typeof prov.sendAsync === 'function') {
    prov.send = prov.sendAsync.bind(prov);
    console.log('✓ POA middleware injected (send → sendAsync)');
  }
}

/** Banner sederhana */
function printBanner() {
  console.log('===============================================');
  console.log('   Pharos Username Minter v7.2 – Commit/Register');
  console.log('===============================================');
  console.log(`Network: ${process.env.CHAIN_ID || '688688'} (Pharos Testnet)`);
  console.log('===============================================');
}

class PharosMultiMinter {
  constructor(privateKey, userAgent = null) {
    if (!privateKey || /^0x0+$/.test(privateKey)) {
      throw new Error('Invalid private key');
    }

    // HTTP headers custom untuk RPC
    const headers = {
      'User-Agent': userAgent || PharosMultiMinter.generateRandomUserAgent(),
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'X-Request-ID': uuidv4()
    };

    const rpcUrl = process.env.RPC_URL || 'https://testnet.dplabs-internal.com';
    console.log(`→ Connecting to RPC: ${rpcUrl}`);

    this.web3 = new Web3(
      new Web3.providers.HttpProvider(rpcUrl, { headers, timeout: 120_000 })
    );
    injectPoaMiddleware(this.web3);

    // NOTE: tidak bisa cek di constructor, pindahkan ke init()
    this.account = this.web3.eth.accounts.privateKeyToAccount(privateKey);
    this.contractAddress = this.web3.utils.toChecksumAddress(
      process.env.CONTRACT_ADDRESS || '0x51be1ef20a1fd5179419738fc71d95a8b6f8a175'
    );
    this.contract = new this.web3.eth.Contract(CONTRACT_ABI, this.contractAddress);

    this.chainId = parseInt(process.env.CHAIN_ID || '688688', 10);
  }

  /** Harus dipanggil sekali sebelum mulai minting */
  async init() {
    const listening = await this.web3.eth.net.isListening();
    if (!listening) {
      throw new Error('✗ Failed to connect to RPC endpoint');
    }
    console.log('✓ Connected to blockchain');
    console.log(`→ Contract @ ${this.contractAddress}`);
  }

  static generateRandomUserAgent() {
    const ios = ['16_0','16_1','16_2','16_3','16_4','16_5','16_6','17_0','17_1'];
    const safari = ['604.1','605.1.15','606.1.36','607.1.40'];
    const v1 = ios[Math.floor(Math.random()*ios.length)];
    const v2 = safari[Math.floor(Math.random()*safari.length)];
    return `Mozilla/5.0 (iPhone; CPU iPhone OS ${v1} like Mac OS X) `
         + `AppleWebKit/${v2} (KHTML, like Gecko) Version/${v1.replace('_','.')}`
         + ` Mobile/15E148 Safari/${v2}`;
  }

  static generateUsername(len = 5) {
    const chars = 'abcdefghijklmnopqrstuvwxyz';
    let s = '';
    while (s.length < len) {
      s += chars[Math.floor(Math.random()*chars.length)];
    }
    return s;
  }

  static generateSecret() {
    const buf = Buffer.alloc(32);
    randomFillSync(buf);
    return buf;
  }

  generateCommitment(name, secret) {
    const nameHash = this.web3.utils.soliditySha3({ t:'string', v:name });
    return this.web3.utils.soliditySha3(
      { t:'bytes32', v:nameHash },
      { t:'bytes32', v:secret }
    );
  }

  async getMinCommitmentAge() {
    try {
      return await this.contract.methods.minCommitmentAge().call();
    } catch {
      console.warn('⚠️ Failed to fetch minCommitmentAge, fallback=60s');
      return 60;
    }
  }

  async getMintingFee() {
    try {
      return await this.contract.methods.mintingFee().call();
    } catch {
      console.warn('⚠️ Failed to fetch mintingFee, fallback=0.01 ETH');
      return this.web3.utils.toWei('0.01','ether');
    }
  }

  async getBalance() {
    try {
      const bal = await this.web3.eth.getBalance(this.account.address);
      return parseFloat(this.web3.utils.fromWei(bal,'ether'));
    } catch {
      console.warn('⚠️ Failed to fetch balance');
      return 0;
    }
  }

  async isUsernameAvailable(name) {
    try {
      return await this.contract.methods.available(name).call();
    } catch {
      console.warn('⚠️ available() check failed');
      return false;
    }
  }

  async getGasPrice() {
    try {
      const gp = await this.web3.eth.getGasPrice();
      console.log(`💡 Gas price oracle: ${this.web3.utils.fromWei(gp,'gwei')} gwei`);
      return gp;
    } catch {
      console.warn('⚠️ getGasPrice() failed, fallback=20 gwei');
      return this.web3.utils.toWei('20','gwei');
    }
  }

  async estimateCommitGas(commitment) {
    try {
      const est = await this.contract.methods.commit(commitment)
        .estimateGas({ from:this.account.address });
      const lim = Math.floor(est * 1.3);
      console.log(`💡 Commit gas est: ${est}, using ${lim}`);
      return lim;
    } catch {
      console.warn('⚠️ Commit gas estimate failed, fallback=150k');
      return 150_000;
    }
  }

  async estimateRegisterGas(name, owner, secret, fee) {
    try {
      const est = await this.contract.methods.register(name,owner,secret)
        .estimateGas({ from:this.account.address, value:fee });
      const lim = Math.floor(est * 1.5);
      console.log(`💡 Register gas est: ${est}, using ${lim}`);
      return lim;
    } catch {
      console.warn('⚠️ Register gas estimate failed, fallback=450k');
      return 450_000;
    }
  }

  /**
   * Sign & kirim tx, tunggu transactionHash & receipt.
   * @returns {Promise<string|null>} txHash atau null jika gagal
   */
  async signAndSendTransaction(tx) {
    try {
      const { rawTransaction } = await this.account.signTransaction(tx);
      return new Promise((resolve, reject) => {
        this.web3.eth.sendSignedTransaction(rawTransaction)
          .once('transactionHash', hash => {
            console.log(`→ Tx sent: ${hash}`);
            resolve(hash);
          })
          .once('receipt', receipt => {
            if (receipt.status) {
              console.log('✓ Tx confirmed');
            } else {
              console.warn('✗ Tx reverted');
            }
          })
          .on('error', err => {
            console.error(`✗ Tx error: ${err.message}`);
            reject(null);
          });
      });
    } catch (err) {
      console.error(`✗ Signing/sending failed: ${err.message}`);
      return null;
    }
  }

  /** Langkah 1: commit */
  async makeCommitment(fullName) {
    const secret = PharosMultiMinter.generateSecret();
    const commitment = this.generateCommitment(fullName, secret);
    const nonce = await this.web3.eth.getTransactionCount(this.account.address);
    const gasPrice = await this.getGasPrice();
    const gasLimit = await this.estimateCommitGas(commitment);
    const tx = {
      chainId: this.chainId,
      from: this.account.address,
      nonce,
      gasPrice,
      gas: gasLimit,
      data: this.contract.methods.commit(commitment).encodeABI()
    };
    const hash = await this.signAndSendTransaction(tx);
    return hash ? secret : null;
  }

  /** Langkah 2: register (setelah delay) */
  async registerUsername(fullName, secret) {
    const fee = await this.getMintingFee();
    const nonce = await this.web3.eth.getTransactionCount(this.account.address);
    const gasPrice = await this.getGasPrice();
    const gasLimit = await this.estimateRegisterGas(fullName, this.account.address, secret, fee);
    const tx = {
      chainId: this.chainId,
      from: this.account.address,
      nonce,
      value: fee,
      gasPrice,
      gas: gasLimit,
      data: this.contract.methods.register(fullName, this.account.address, secret).encodeABI()
    };
    return this.signAndSendTransaction(tx);
  }

  /** Proses minting dua langkah */
  async mintUsername(maxAttempts = 5) {
    for (let i = 0; i < maxAttempts; i++) {
      const name = PharosMultiMinter.generateUsername();
      const fullName = `${name}.phrs`;
      if (!await this.isUsernameAvailable(fullName)) {
        console.log(`✗ [${i+1}/${maxAttempts}] Taken: ${fullName}`);
        await new Promise(r => setTimeout(r, 500));
        continue;
      }
      console.log(`✓ [${i+1}/${maxAttempts}] Available: ${fullName}`);

      // Commit
      console.log('→ Making commitment…');
      const secret = await this.makeCommitment(fullName);
      if (!secret) {
        console.log('✗ Commitment gagal, coba nama lain');
        continue;
      }

      // Tunggu minCommitmentAge
      const minAge = await this.getMinCommitmentAge();
      const waitSec = Math.max(minAge, 60);
      console.log(`⏳ Waiting ${waitSec}s for commitment to mature…`);
      await new Promise(r => setTimeout(r, waitSec * 1_000));

      // Register
      console.log('→ Registering username…');
      const txHash = await this.registerUsername(fullName, secret);
      if (txHash) {
        const explorer = (process.env.EXPLORER_BASE_URL || 'https://testnet.pharosscan.xyz/tx/') + txHash;
        return { status:'success', username:fullName, txHash, explorer };
      }
      console.log('✗ Registration gagal, ulangi');
      await new Promise(r => setTimeout(r, 1_500));
    }
    return { status:'failed', reason:'No available names found' };
  }
}

// ======================
// LOADING ACCOUNTS
// ======================
function loadAccounts() {
  const accs = [];
  [['PRIVATE_KEY_1','USER_AGENT_1','Account 1'],
   ['PRIVATE_KEY_2','USER_AGENT_2','Account 2']]
    .forEach(([pkEnv, uaEnv, label]) => {
      const pk = process.env[pkEnv];
      if (pk && !/^0x0+$/.test(pk)) {
        accs.push({
          name: label,
          privateKey: pk,
          userAgent: process.env[uaEnv] || null
        });
      }
    });
  if (!accs.length) {
    throw new Error('No valid accounts. Set PRIVATE_KEY_1 or PRIVATE_KEY_2.');
  }
  return accs;
}

// ======================
// MAIN
// ======================
(async () => {
  printBanner();
  try {
    const accounts = loadAccounts();
    console.log(`\nFound ${accounts.length} account(s) to process\n`);

    let success=0, failed=0, pending=0;
    for (let i=0; i<accounts.length; i++) {
      const { name, privateKey, userAgent } = accounts[i];
      console.log(`\n===== Account ${i+1}: ${name} =====`);
      const minter = new PharosMultiMinter(privateKey, userAgent);
      await minter.init();

      // Cek saldo & fee
      const balance = await minter.getBalance();
      const feeWei = await minter.getMintingFee();
      const feeEth = parseFloat(minter.web3.utils.fromWei(feeWei,'ether'));
      console.log(`Wallet: ${minter.account.address}`);
      console.log(`Balance: ${balance.toFixed(6)} PHRS`);
      console.log(`Fee: ${feeEth.toFixed(6)} PHRS`);
      if (balance < feeEth) {
        console.log('✗ Insufficient balance');
        failed++;
        continue;
      }

      console.log('\n🚀 Starting two‑step minting\n');
      const start = Date.now();
      const result = await minter.mintUsername(7);
      const elapsed = ((Date.now()-start)/1000).toFixed(2);

      if (result.status==='success') {
        console.log(`\n🎉 Minted in ${elapsed}s! Username: ${result.username}`);
        console.log(`🔗 Explorer: ${result.explorer}`);
        success++;
      } else {
        console.log(`\n✗ Failed after ${elapsed}s. Reason: ${result.reason||'unknown'}`);
        failed++;
      }

      if (i<accounts.length-1) {
        console.log('\n⏳ Waiting 15s before next account…');
        await new Promise(r => setTimeout(r, 15_000));
      }
    }

    console.log('\n===============================================');
    console.log('Minting Summary:');
    console.log(` ✓ Success : ${success}`);
    console.log(` ✗ Failed  : ${failed}`);
    console.log('===============================================');
    process.exit(0);

  } catch (err) {
    console.error(`\n🔥 Fatal error: ${err.message}`);
    process.exit(1);
  }
})();