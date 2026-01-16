from .base import BaseStrategy

class SimpleStrategy(BaseStrategy):
    def should_enter(self, market_data):
        # Example logic: Enter if price is below a certain threshold defined in config
        current_price = market_data.get('price')
        target_price = self.config.get('target_entry_price', 0.50)
        
        if current_price and current_price < target_price:
            return True
        return False

    def get_order_details(self, market_data):
        return {
            'price': market_data.get('price'), # Limit order at current price
            'size': self.config.get('order_size', 10.0),
            'side': 'BUY',
            'token_id': market_data.get('token_id')
        }
