# Pharos Testnet Auto Bot

Bot otomatis untuk melakukan berbagai transaksi di testnet Pharos Network, termasuk wrapping/unwrapping PHRS, swap token, dan menambahkan likuiditas ke Faroswap.

## Fitur Utama

- 💰 **Wrap/Unwrap PHRS**: Konversi antara PHRS asli dan WPHRS (wrapped)
- 🔄 **Swap Token Otomatis**: Tukar berbagai token secara acak
- 💧 **Tambahkan Likuiditas**: Tambahkan likuiditas ke berbagai pool
- 🤖 **Mode Auto All**: Jalankan semua aktivitas secara berurutan
- 👥 **Multi-Account Support**: Dukung banyak akun sekaligus
- 🌈 **Antarmuka Berwarna**: Tampilan CLI modern dengan warna dan animasi

## Prasyarat

- Python 3.7+
- Dependensi Python:
  ```bash
  pip install web3 eth-account aiohttp fake-useragent colorama
  ```

## Instalasi

1. Clone repositori:
   ```bash
   git clone https://github.com/dicoderin/Faroswap.git
   cd Faroswap
   ```

   ```bash
   pip install -r requirements.txt #or pip3 install -r requirements.txt
   ```
   ```bash
     pip show libary_name
   ```
   ```bash
     pip uninstall libary_name
   ```
   ```bash
     pip install libary_name==version
   ```
   ```bash
   toouch proxy.txt
   ```

2. Buat file `accounts.txt` dan tambahkan private key Anda (satu per baris):
   ```text
   0xYourPrivateKey1
   0xYourPrivateKey2
   ```

3. Jalankan bot:
   ```bash
   python f.py
   ```

   

### Opsi Tersedia

1. **Wrap PHRS**: Konversi PHRS asli ke WPHRS
2. **Unwrap WPHRS**: Konversi WPHRS kembali ke PHRS
3. **Auto All**: Jalankan semua aktivitas secara berurutan:
   - Wrap PHRS
   - Unwrap WPHRS
   - Swap token acak
   - Tambahkan likuiditas ke pool acak
4. **Swap Tokens**: Lakukan swap token secara acak beberapa kali
5. **Exit**: Keluar dari aplikasi

## Struktur Proyek

```
pharos-testnet-bot/
├── f.py      # File utama bot
├── accounts.txt           # File untuk menyimpan private keys
├── README.md          # File dokumentasi ini
```

## Kontribusi

Kontribusi dipersilakan! Ikuti langkah berikut:

1. Fork proyek
2. Buat branch fitur (`git checkout -b fitur-baru`)
3. Commit perubahan (`git commit -am 'Tambahkan fitur baru'`)
4. Push ke branch (`git push origin fitur-baru`)
5. Buat Pull Request

## Penafian

⚠️ **PERHATIAN**: Bot ini hanya untuk keperluan edukasi dan pengujian di testnet. Jangan gunakan dengan mainnet atau dana nyata. Pengembang tidak bertanggung jawab atas kerugian dana.

## Lisensi

Proyek ini dilisensikan di bawah [MIT License](LICENSE).
