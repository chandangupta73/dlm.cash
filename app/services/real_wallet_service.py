import os
import json
import base64
from decimal import Decimal
from typing import Dict, Optional, Tuple
from cryptography.fernet import Fernet
from eth_account import Account
from web3 import Web3
from web3.exceptions import TransactionNotFound
from django.conf import settings
from django.utils import timezone
from decouple import config

from app.wallet.models import USDTWallet, USDTDepositRequest, SweepLog, WalletTransaction


class RealWalletService:
    """Service for managing real EVM wallets and blockchain operations."""
    
    def __init__(self):
        self.encryption_key = config('WALLET_ENCRYPTION_KEY', default='your_secure_encryption_key_here_32_chars_long')
        self.fernet = Fernet(base64.urlsafe_b64encode(self.encryption_key.encode()[:32].ljust(32, b'0')))
        
        # Web3 connections
        self.eth_w3 = Web3(Web3.HTTPProvider(config('ETHEREUM_RPC_URL', default='https://eth-mainnet.alchemyapi.io/v2/YOUR_ALCHEMY_KEY')))
        self.bsc_w3 = Web3(Web3.HTTPProvider(config('BSC_RPC_URL', default='https://bsc-dataseed.binance.org/')))
        
        # Master wallet addresses
        self.master_wallet_eth = config('MASTER_WALLET_ETH', default='0x742d35Cc6634C0532925a3b8D404d1deBa4Cb61f')
        self.master_wallet_bsc = config('MASTER_WALLET_BSC', default='0x742d35Cc6634C0532925a3b8D404d1deBa4Cb61f')
        
        # USDT token addresses
        self.usdt_eth_address = config('USDT_ETH_ADDRESS', default='0xdAC17F958D2ee523a2206206994597C13D831ec7')
        self.usdt_bsc_address = config('USDT_BSC_ADDRESS', default='0x55d398326f99059fF775485246999027B3197955')
        
        # Gas settings
        try:
            self.auto_sweep_threshold = Decimal(str(config('AUTO_SWEEP_THRESHOLD', default='50.00')))
        except:
            self.auto_sweep_threshold = Decimal('50.00')
        self.gas_limit_erc20 = int(config('GAS_LIMIT_ERC20', default='65000'))
        self.gas_limit_bep20 = int(config('GAS_LIMIT_BEP20', default='65000'))
    
    def generate_real_wallet(self, user, chain_type='erc20') -> Dict:
        """Generate a real EVM wallet for the user."""
        try:
            # Generate new account
            account = Account.create()
            address = account.address
            private_key = account.key.hex()
            
            # Encrypt private key
            encrypted_private_key = self.fernet.encrypt(private_key.encode()).decode()
            
            # Create or update USDT wallet
            usdt_wallet, created = USDTWallet.objects.get_or_create(user=user)
            usdt_wallet.wallet_address = address
            usdt_wallet.private_key_encrypted = encrypted_private_key
            usdt_wallet.chain_type = chain_type
            usdt_wallet.is_real_wallet = True
            usdt_wallet.save()
            
            return {
                'success': True,
                'address': address,
                'chain_type': chain_type,
                'wallet_id': str(usdt_wallet.id)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def decrypt_private_key(self, encrypted_private_key: str) -> str:
        """Decrypt the private key."""
        try:
            decrypted = self.fernet.decrypt(encrypted_private_key.encode())
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt private key: {str(e)}")
    
    def get_web3_connection(self, chain_type: str) -> Web3:
        """Get Web3 connection for the specified chain."""
        if chain_type == 'erc20':
            return self.eth_w3
        elif chain_type == 'bep20':
            return self.bsc_w3
        else:
            raise ValueError(f"Unsupported chain type: {chain_type}")
    
    def get_usdt_contract(self, chain_type: str):
        """Get USDT contract for the specified chain."""
        w3 = self.get_web3_connection(chain_type)
        
        if chain_type == 'erc20':
            contract_address = self.usdt_eth_address
        elif chain_type == 'bep20':
            contract_address = self.usdt_bsc_address
        else:
            raise ValueError(f"Unsupported chain type: {chain_type}")
        
        # USDT ERC20 ABI (minimal for transfer)
        abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "payable": False,
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "payable": False,
                "stateMutability": "view",
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "payable": False,
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        return w3.eth.contract(address=contract_address, abi=abi)
    
    def process_moralis_webhook(self, webhook_data: Dict) -> Dict:
        """Process Moralis webhook for USDT deposits."""
        try:
            # Extract data from Moralis webhook
            to_address = webhook_data.get('to', '').lower()
            from_address = webhook_data.get('from', '').lower()
            value = webhook_data.get('value', '0')
            transaction_hash = webhook_data.get('hash', '')
            chain_type = webhook_data.get('chain', '').lower()
            
            # Map chain to our format
            if chain_type in ['eth', 'ethereum', 'mainnet']:
                chain_type = 'erc20'
            elif chain_type in ['bsc', 'binance', 'bsc-mainnet']:
                chain_type = 'bep20'
            else:
                return {'success': False, 'error': f'Unsupported chain: {chain_type}'}
            
            # Find user by wallet address
            try:
                usdt_wallet = USDTWallet.objects.get(
                    wallet_address__iexact=to_address,
                    chain_type=chain_type,
                    is_real_wallet=True
                )
                user = usdt_wallet.user
            except USDTWallet.DoesNotExist:
                return {'success': False, 'error': f'No wallet found for address: {to_address}'}
            
            # Convert value from Wei to USDT (6 decimals)
            usdt_amount = Decimal(value) / Decimal('1000000')  # USDT has 6 decimals
            
            # Check if deposit already exists
            if USDTDepositRequest.objects.filter(transaction_hash=transaction_hash).exists():
                return {'success': False, 'error': 'Deposit already processed'}
            
            # Create deposit request
            deposit = USDTDepositRequest.objects.create(
                user=user,
                chain_type=chain_type,
                amount=usdt_amount,
                transaction_hash=transaction_hash,
                from_address=from_address,
                to_address=to_address,
                status='confirmed',  # Moralis webhook means it's confirmed
                processed_at=timezone.now()
            )
            
            # Credit user's wallet
            usdt_wallet.add_balance(usdt_amount)
            
            # Create transaction log
            WalletTransaction.objects.create(
                user=user,
                transaction_type='usdt_deposit',
                wallet_type='usdt',
                chain_type=chain_type,
                amount=usdt_amount,
                balance_before=usdt_wallet.balance - usdt_amount,
                balance_after=usdt_wallet.balance,
                status='completed',
                reference_id=transaction_hash,
                description=f"USDT deposit from Moralis webhook - {chain_type.upper()} - TX: {transaction_hash[:10]}...",
                metadata={'chain_type': chain_type, 'from_address': from_address}
            )
            
            # Check if auto-sweep is needed
            if usdt_amount <= self.auto_sweep_threshold:
                self.auto_sweep_deposit(deposit)
            
            return {
                'success': True,
                'deposit_id': str(deposit.id),
                'amount': str(usdt_amount),
                'user_id': str(user.id)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def auto_sweep_deposit(self, deposit: USDTDepositRequest) -> Dict:
        """Automatically sweep deposit to master wallet."""
        try:
            # Get user's wallet
            usdt_wallet = deposit.user.usdt_wallet
            
            # Decrypt private key
            private_key = self.decrypt_private_key(usdt_wallet.private_key_encrypted)
            
            # Perform sweep
            sweep_result = self.sweep_to_master_wallet(
                user=deposit.user,
                amount=deposit.amount,
                chain_type=deposit.chain_type,
                private_key=private_key,
                sweep_type='auto'
            )
            
            if sweep_result['success']:
                deposit.mark_as_swept(sweep_result['tx_hash'], sweep_result.get('gas_fee', 0))
                deposit.sweep_type = 'auto'
                deposit.save()
                
                # Update wallet
                usdt_wallet.last_sweep_at = timezone.now()
                usdt_wallet.save()
            
            return sweep_result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def sweep_to_master_wallet(self, user, amount: Decimal, chain_type: str, 
                              private_key: str, sweep_type: str = 'manual') -> Dict:
        """Sweep USDT from user wallet to master wallet."""
        try:
            w3 = self.get_web3_connection(chain_type)
            usdt_contract = self.get_usdt_contract(chain_type)
            
            # Get account from private key
            account = Account.from_key(private_key)
            
            # Get master wallet address
            master_wallet = self.master_wallet_eth if chain_type == 'erc20' else self.master_wallet_bsc
            
            # Convert amount to Wei (6 decimals for USDT)
            amount_wei = int(amount * 1000000)
            
            # Get nonce
            nonce = w3.eth.get_transaction_count(account.address)
            
            # Get gas price
            gas_price = w3.eth.gas_price
            
            # Gas limit
            gas_limit = self.gas_limit_erc20 if chain_type == 'erc20' else self.gas_limit_bep20
            
            # Build transaction
            transaction = usdt_contract.functions.transfer(
                master_wallet,
                amount_wei
            ).build_transaction({
                'chainId': 1 if chain_type == 'erc20' else 56,  # ETH mainnet: 1, BSC mainnet: 56
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': nonce,
            })
            
            # Sign transaction
            signed_txn = w3.eth.account.sign_transaction(transaction, private_key)
            
            # Send transaction
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            # Calculate gas fee
            gas_fee = Decimal(gas_price * gas_limit) / Decimal('1000000000000000000')  # Convert from Wei to ETH/BNB
            
            # Create sweep log
            sweep_log = SweepLog.objects.create(
                user=user,
                chain_type=chain_type,
                from_address=account.address,
                to_address=master_wallet,
                amount=amount,
                gas_fee=gas_fee,
                transaction_hash=tx_hash_hex,
                sweep_type=sweep_type,
                status='completed',
                initiated_by=user if sweep_type == 'auto' else None
            )
            
            # Create transaction log
            WalletTransaction.objects.create(
                user=user,
                transaction_type='sweep',
                wallet_type='usdt',
                chain_type=chain_type,
                amount=amount,
                balance_before=user.usdt_wallet.balance,
                balance_after=user.usdt_wallet.balance - amount,
                status='completed',
                reference_id=tx_hash_hex,
                description=f"USDT sweep to master wallet - {chain_type.upper()} - TX: {tx_hash_hex[:10]}...",
                metadata={'sweep_type': sweep_type, 'gas_fee': str(gas_fee)}
            )
            
            # Deduct from user's wallet
            user.usdt_wallet.deduct_balance(amount)
            
            return {
                'success': True,
                'tx_hash': tx_hash_hex,
                'gas_fee': str(gas_fee),
                'sweep_log_id': str(sweep_log.id)
            }
            
        except Exception as e:
            # Log failed sweep
            SweepLog.objects.create(
                user=user,
                chain_type=chain_type,
                from_address=account.address if 'account' in locals() else '',
                to_address=master_wallet if 'master_wallet' in locals() else '',
                amount=amount,
                sweep_type=sweep_type,
                status='failed',
                error_message=str(e),
                initiated_by=user if sweep_type == 'auto' else None
            )
            
            return {'success': False, 'error': str(e)}
    
    def get_wallet_balance(self, address: str, chain_type: str) -> Dict:
        """Get USDT balance for a wallet address."""
        try:
            w3 = self.get_web3_connection(chain_type)
            usdt_contract = self.get_usdt_contract(chain_type)
            
            balance_wei = usdt_contract.functions.balanceOf(address).call()
            balance_usdt = Decimal(balance_wei) / Decimal('1000000')  # Convert from Wei
            
            return {
                'success': True,
                'balance': str(balance_usdt),
                'address': address,
                'chain_type': chain_type
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_transaction_status(self, tx_hash: str, chain_type: str) -> Dict:
        """Get transaction status and confirmations."""
        try:
            w3 = self.get_web3_connection(chain_type)
            
            # Get transaction receipt
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            
            if receipt is None:
                return {'success': False, 'error': 'Transaction not found'}
            
            # Get current block number
            current_block = w3.eth.block_number
            
            # Calculate confirmations
            confirmations = current_block - receipt.blockNumber
            
            return {
                'success': True,
                'status': 'success' if receipt.status == 1 else 'failed',
                'confirmations': confirmations,
                'block_number': receipt.blockNumber,
                'gas_used': receipt.gasUsed,
                'effective_gas_price': receipt.effectiveGasPrice
            }
            
        except TransactionNotFound:
            return {'success': False, 'error': 'Transaction not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# Global instance
real_wallet_service = RealWalletService()
