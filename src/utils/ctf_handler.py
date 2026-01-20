import time
import logging
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account

logger = logging.getLogger(__name__)

# Minimal ABIs
CTF_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "conditionId", "type": "bytes32"},
            {"name": "index", "type": "uint256"}
        ],
        "name": "payoutNumerators",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSets", "type": "uint256[]"}
        ],
        "name": "redeemPositions",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

GNOSIS_SAFE_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"},
            {"name": "operation", "type": "uint8"},
            {"name": "safeTxGas", "type": "uint256"},
            {"name": "baseGas", "type": "uint256"},
            {"name": "gasPrice", "type": "uint256"},
            {"name": "gasToken", "type": "address"},
            {"name": "refundReceiver", "type": "address"},
            {"name": "signatures", "type": "bytes"}
        ],
        "name": "execTransaction",
        "outputs": [{"name": "success", "type": "bool"}],
        "payable": True,
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "nonce",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }
]

class CTFHandler:
    def __init__(self, private_key, proxy_address=None, rpc_url="https://polygon-rpc.com"):
        self.private_key = private_key
        self.proxy_address = proxy_address
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.account = self.w3.eth.account.from_key(private_key)
        
        # Mainnet Addresses
        self.ctf_address = "0x4D97DCd97eC945f40cF65F87097ACE5EA0476045"
        self.collateral = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        
        self.ctf_contract = self.w3.eth.contract(address=self.ctf_address, abi=CTF_ABI)

    def is_redeemable(self, condition_id):
        """Check if market is resolved on-chain."""
        try:
            p0 = self.ctf_contract.functions.payoutNumerators(condition_id, 0).call()
            p1 = self.ctf_contract.functions.payoutNumerators(condition_id, 1).call()
            return p0 > 0 or p1 > 0
        except Exception as e:
            logger.error(f"Error checking payout status: {e}")
            return False

    def merge_positions(self, condition_id, amount):
        """Merge YES and NO positions into USDC (Supports EOA and Proxy)."""
        if self.proxy_address and self.proxy_address != self.account.address:
            return self._merge_proxy(condition_id, amount)
        else:
            return self._merge_eoa(condition_id, amount)

    def _merge_eoa(self, condition_id, amount):
        try:
            amount_wei = int(amount * 1_000_000) # USDC 6 decimals
            func = self.ctf_contract.functions.mergePositions(
                self.collateral,
                "0x" + "0" * 64,
                condition_id,
                [1, 2],
                amount_wei
            )
            gas_estimate = func.estimate_gas({'from': self.account.address})
            tx = func.build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': int(gas_estimate * 1.2),
                'gasPrice': self.w3.eth.gas_price
            })
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            logger.info(f"Merge TX sent (EOA): {self.w3.to_hex(tx_hash)}")
            return True
        except Exception as e:
            logger.error(f"Merge EOA failed: {e}")
            return False

    def _merge_proxy(self, condition_id, amount):
        try:
            amount_wei = int(amount * 1_000_000)
            inner_func = self.ctf_contract.functions.mergePositions(
                self.collateral,
                "0x" + "0" * 64,
                condition_id,
                [1, 2],
                amount_wei
            )
            inner_data = inner_func.build_transaction({'gas': 0})['data']
            
            safe_contract = self.w3.eth.contract(address=self.proxy_address, abi=GNOSIS_SAFE_ABI)
            nonce = safe_contract.functions.nonce().call()
            
            to = self.ctf_address
            data_bytes = bytes.fromhex(inner_data[2:]) if inner_data.startswith('0x') else inner_data
            
            eip712_data = {
                "types": {
                    "EIP712Domain": [{"name": "chainId", "type": "uint256"}, {"name": "verifyingContract", "type": "address"}],
                    "SafeTx": [
                        {"name": "to", "type": "address"}, {"name": "value", "type": "uint256"},
                        {"name": "data", "type": "bytes"}, {"name": "operation", "type": "uint8"},
                        {"name": "safeTxGas", "type": "uint256"}, {"name": "baseGas", "type": "uint256"},
                        {"name": "gasPrice", "type": "uint256"}, {"name": "gasToken", "type": "address"},
                        {"name": "refundReceiver", "type": "address"}, {"name": "nonce", "type": "uint256"}
                    ]
                },
                "primaryType": "SafeTx",
                "domain": {"chainId": 137, "verifyingContract": self.proxy_address},
                "message": {
                    "to": to, "value": 0, "data": data_bytes, "operation": 0,
                    "safeTxGas": 0, "baseGas": 0, "gasPrice": 0,
                    "gasToken": "0x0000000000000000000000000000000000000000",
                    "refundReceiver": "0x0000000000000000000000000000000000000000",
                    "nonce": nonce
                }
            }
            signed = Account.sign_typed_data(self.private_key, full_message=eip712_data)
            
            exec_func = safe_contract.functions.execTransaction(
                to, 0, data_bytes, 0, 0, 0, 0,
                "0x0000000000000000000000000000000000000000",
                "0x0000000000000000000000000000000000000000",
                signed.signature
            )
            
            gas_estimate = exec_func.estimate_gas({'from': self.account.address})
            tx = exec_func.build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': int(gas_estimate * 1.2),
                'gasPrice': self.w3.eth.gas_price
            })
            
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            logger.info(f"Merge TX sent (Proxy): {self.w3.to_hex(tx_hash)}")
            return True
        except Exception as e:
            logger.error(f"Merge Proxy failed: {e}")
            return False

    def redeem_positions(self, condition_id):
        """Execute redeem transaction (Supports EOA and Proxy)."""
        if self.proxy_address and self.proxy_address != self.account.address:
            return self._redeem_proxy(condition_id)
        else:
            return self._redeem_eoa(condition_id)

    def _redeem_eoa(self, condition_id):
        try:
            func = self.ctf_contract.functions.redeemPositions(
                self.collateral,
                "0x" + "0" * 64,
                condition_id,
                [1, 2]
            )
            gas_estimate = func.estimate_gas({'from': self.account.address})
            tx = func.build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': int(gas_estimate * 1.2),
                'gasPrice': self.w3.eth.gas_price
            })
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            logger.info(f"Redeem TX sent (EOA): {self.w3.to_hex(tx_hash)}")
            return True
        except Exception as e:
            logger.error(f"Redeem EOA failed: {e}")
            return False

    def _redeem_proxy(self, condition_id):
        try:
            # 1. Prepare Inner Transaction Data
            inner_func = self.ctf_contract.functions.redeemPositions(
                self.collateral,
                "0x" + "0" * 64,
                condition_id,
                [1, 2]
            )
            inner_data = inner_func.build_transaction({'gas': 0})['data']
            
            # 2. Prepare Safe Transaction
            safe_contract = self.w3.eth.contract(address=self.proxy_address, abi=GNOSIS_SAFE_ABI)
            nonce = safe_contract.functions.nonce().call()
            
            to = self.ctf_address
            value = 0
            data_bytes = bytes.fromhex(inner_data[2:]) if inner_data.startswith('0x') else inner_data
            
            # 3. Sign (EIP-712)
            eip712_data = {
                "types": {
                    "EIP712Domain": [{"name": "chainId", "type": "uint256"}, {"name": "verifyingContract", "type": "address"}],
                    "SafeTx": [
                        {"name": "to", "type": "address"}, {"name": "value", "type": "uint256"},
                        {"name": "data", "type": "bytes"}, {"name": "operation", "type": "uint8"},
                        {"name": "safeTxGas", "type": "uint256"}, {"name": "baseGas", "type": "uint256"},
                        {"name": "gasPrice", "type": "uint256"}, {"name": "gasToken", "type": "address"},
                        {"name": "refundReceiver", "type": "address"}, {"name": "nonce", "type": "uint256"}
                    ]
                },
                "primaryType": "SafeTx",
                "domain": {"chainId": 137, "verifyingContract": self.proxy_address},
                "message": {
                    "to": to, "value": value, "data": data_bytes, "operation": 0,
                    "safeTxGas": 0, "baseGas": 0, "gasPrice": 0,
                    "gasToken": "0x0000000000000000000000000000000000000000",
                    "refundReceiver": "0x0000000000000000000000000000000000000000",
                    "nonce": nonce
                }
            }
            
            signed = Account.sign_typed_data(self.private_key, full_message=eip712_data)
            
            # 4. Execute
            exec_func = safe_contract.functions.execTransaction(
                to, value, data_bytes, 0, 0, 0, 0,
                "0x0000000000000000000000000000000000000000",
                "0x0000000000000000000000000000000000000000",
                signed.signature
            )
            
            gas_estimate = exec_func.estimate_gas({'from': self.account.address})
            tx = exec_func.build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': int(gas_estimate * 1.2),
                'gasPrice': self.w3.eth.gas_price
            })
            
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            logger.info(f"Redeem TX sent (Proxy): {self.w3.to_hex(tx_hash)}")
            return True

        except Exception as e:
            logger.error(f"Redeem Proxy failed: {e}")
            return False
