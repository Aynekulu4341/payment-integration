import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging

logger = logging.getLogger(__name__)

def get_exchange_rate(from_currency, to_currency, api_key=None):
    """Fetch exchange rate with retries."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)

    if not api_key:
        logger.warning("No API key provided, using fallback rate")
        return 132.1 if to_currency == 'ETB' else 0.007571

    url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{from_currency}/{to_currency}"
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('result') == 'success':
            rate = data.get('conversion_rate')
            logger.debug(f"Exchange rate {from_currency} to {to_currency}: {rate}")
            return rate
        logger.error(f"Exchange rate API failed: {data.get('error-type')}")
        return 132.1 if to_currency == 'ETB' else 0.007571
    except requests.RequestException as e:
        logger.error(f"Exchange rate API request failed: {str(e)}")
        return 132.1 if to_currency == 'ETB' else 0.007571