import os
import json
from dotenv import load_dotenv

load_dotenv()

class ConfigLoader:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self):
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def get_trading_config(self):
        return self._config.get("trading", {})
    
    def get_risk_config(self):
        return self._config.get("risk_management", {})
    
    def get_redeem_config(self):
        return self._config.get("redeem", {})

    def get_polymarket_config(self):
        return self._config.get("polymarket", {})

    @staticmethod
    def get_env_var(key, default=None):
        return os.getenv(key, default)
