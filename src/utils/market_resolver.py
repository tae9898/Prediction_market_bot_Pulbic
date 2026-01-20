import logging
from py_clob_client.client import ClobClient

logger = logging.getLogger(__name__)

class MarketResolver:
    def __init__(self, host="https://clob.polymarket.com", chain_id=137):
        # Public client for fetching markets
        self.client = ClobClient(host, key=None, chain_id=chain_id)

    def resolve_token_id(self, keyword):
        """
        Find the most relevant Token ID for a given keyword.
        Returns: token_id (str) or None
        """
        logger.info(f"Resolving market for keyword: {keyword}...")
        try:
            # Fetch active markets
            # Note: This fetches a list of markets. We might need to handle pagination 
            # if the desired market isn't in the first page, but for now we fetch default.
            resp = self.client.get_markets()
            
            markets = resp if isinstance(resp, list) else resp.get('data', [])
            
            candidates = []
            for m in markets:
                # Safe attribute access
                def get_attr(obj, key):
                    return getattr(obj, key, None) or (obj.get(key) if isinstance(obj, dict) else None)

                if get_attr(m, 'active') is False or get_attr(m, 'closed') is True:
                    continue
                
                question = get_attr(m, 'question') or ""
                slug = get_attr(m, 'slug') or ""
                
                if keyword.upper() in question.upper() or keyword.upper() in slug.upper():
                    candidates.append(m)
            
            if not candidates:
                logger.warning(f"No active markets found for keyword '{keyword}'")
                return None
            
            # Strategy to pick 'best' market:
            # For now, pick the one with highest liquidity or volume if available.
            # Or simply the first one as a heuristic.
            # TODO: Improve selection logic (e.g. sort by volume)
            
            best_match = candidates[0]
            token_id = getattr(best_match, 'token_id', None) or best_match.get('token_id')
            
            question = getattr(best_match, 'question', None) or best_match.get('question')
            logger.info(f"Resolved '{keyword}' to: {question} (ID: {token_id})")
            
            return token_id

        except Exception as e:
            logger.error(f"Error resolving market for {keyword}: {e}")
            return None
