import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from django.conf import settings
import logging
import time

logger = logging.getLogger(__name__)

def get_exchange_rate(from_currency, to_currency, retries=3, delay=1):
    """Fetch exchange rate from API with fallback."""
    api_key = settings.EXCHANGE_RATE_API_KEY
    if not api_key:
        logger.error("EXCHANGE_RATE_API_KEY is not set")
        return 0
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{from_currency}"
    session = requests.Session()
    retries_config = Retry(total=retries, backoff_factor=delay, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries_config))

    for attempt in range(retries):
        try:
            response = session.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get('result') != 'success':
                logger.error(f"Exchange rate API error: {data.get('error-type', 'Unknown error')}")
                raise ValueError("API returned non-success result")
            rate = data.get('conversion_rates', {}).get(to_currency)
            if not rate:
                logger.error(f"No rate found for {to_currency}")
                raise ValueError(f"No rate for {to_currency}")
            logger.debug(f"Exchange rate {from_currency} to {to_currency}: {rate}")
            return rate
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.warning(f"Exchange rate fetch failed (attempt {attempt + 1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                time.sleep(delay)
            continue

    logger.error(f"Failed to fetch exchange rate after {retries} attempts")
    fallback_rates = {
        ('ETB', 'USD'): 0.007571,
        ('USD', 'ETB'): 132.1
    }
    rate = fallback_rates.get((from_currency, to_currency), 0)
    logger.warning(f"Using fallback rate {from_currency} to {to_currency}: {rate}")
    return rate