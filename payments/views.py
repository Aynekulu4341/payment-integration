from django.http import HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Campaign, Transaction, WithdrawalRequest
from .serializers import CampaignSerializer
import requests
import time
from decimal import Decimal
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging

logger = logging.getLogger(__name__)

FAKE_TELEBIRR_ACCOUNTS = [
    {"phone": "251912345678", "name": "Abebe Kebede", "balance": Decimal('1000.00')},
    {"phone": "251989941044", "name": "Marta Tesfaye", "balance": Decimal('50.00')},
    {"phone": "251923456789", "name": "Yared Alemayehu", "balance": Decimal('750.00')},
]

def simulate_telebirr_payment(amount, donor_phone):
    amount = Decimal(str(amount)).quantize(Decimal('0.01'))
    donor = next((acc for acc in FAKE_TELEBIRR_ACCOUNTS if acc["phone"] == donor_phone), None)
    if not donor:
        return {'success': False, 'message': f"Telebirr account {donor_phone} not found!"}
    if donor["balance"] < amount:
        return {'success': False, 'message': f"Insufficient balance in {donor_phone}! Only {donor['balance']} ETB available."}
    transaction_id = f"TEL-{int(time.time())}"
    donor["balance"] -= amount
    logger.debug(f"Updated Telebirr accounts: {FAKE_TELEBIRR_ACCOUNTS}")
    return {
        'success': True,
        'transaction_id': transaction_id,
        'redirect_url': "http://localhost:8000/success",
        'source': f"Telebirr account {donor_phone} ({donor['name']})"
    }

def simulate_telebirr_verify(transaction_id):
    logger.debug(f"Verifying Telebirr transaction: {transaction_id}")
    return {'success': True, 'message': "Verified payment from Telebirr account"}

def simulate_telebirr_transfer(amount, recipient_phone):
    recipient = next((acc for acc in FAKE_TELEBIRR_ACCOUNTS if acc["phone"] == recipient_phone), None)
    if recipient:
        recipient["balance"] += amount
        logger.debug(f"Simulated Telebirr transfer: {amount} ETB to {recipient_phone}. New balance: {recipient['balance']}")
        print(f"Telebirr account {recipient_phone} balance: {recipient['balance']} ETB")  # For debugging
        return {'success': True, 'message': f"Transferred {amount} ETB to {recipient_phone}"}
    return {'success': False, 'message': f"Recipient {recipient_phone} not found!"}

def simulate_paypal_transfer(amount, recipient_email):
    logger.debug(f"Simulated PayPal transfer: {amount} USD to {recipient_email}")
    return {'success': True, 'message': f"Transferred {amount} USD to {recipient_email}"}

class CampaignListView(APIView):
    def get(self, request):
        """List all campaigns with their progress in Birr."""
        campaigns = Campaign.objects.all()
        serializer = CampaignSerializer(campaigns, many=True)
        return Response(serializer.data)

class CampaignDetailView(APIView):
    def get(self, request, pk):
        """Get detailed view of a campaign with total_birr and total_usd."""
        try:
            campaign = Campaign.objects.get(pk=pk)
        except Campaign.DoesNotExist:
            logger.error(f"Campaign {pk} not found")
            return Response({"error": "Campaign not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CampaignSerializer(campaign)
        return Response(serializer.data)

class DonateView(APIView):
    def post(self, request):
        logger.debug(f"DonateView.post called with data: {request.data}")
        data = request.data
        campaign_id = data.get('campaign_id')
        amount = data.get('amount')
        payment_method = data.get('payment_method')
        donor_phone = data.get('donor_phone')
        donor_email = data.get('donor_email')

        missing = []
        if not campaign_id:
            missing.append('campaign_id')
        if not amount:
            missing.append('amount')
        if not payment_method:
            missing.append('payment_method')
        if payment_method == 'telebirr' and not donor_phone:
            missing.append('donor_phone')
        if missing:
            logger.error(f"Missing required fields: {', '.join(missing)}")
            return HttpResponse(f"Oops! Please provide {', '.join(missing)}.", status=400)

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            logger.error("Invalid amount provided")
            return HttpResponse("Sorry, the amount must be a positive number!", status=400)

        try:
            campaign = Campaign.objects.get(id=campaign_id)
        except Campaign.DoesNotExist:
            logger.error(f"Campaign {campaign_id} not found")
            return HttpResponse("Hmm, that campaign doesn’t exist.", status=404)

        if payment_method not in ['paypal', 'telebirr']:
            logger.error(f"Invalid payment method: {payment_method}")
            return HttpResponse("Please choose either PayPal or Telebirr!", status=400)

        if payment_method == 'paypal':
            return self.initiate_paypal_payment(campaign, amount, request, donor_email)
        elif payment_method == 'telebirr':
            result = simulate_telebirr_payment(amount, donor_phone)
            if result['success']:
                transaction = Transaction.objects.create(
                    campaign=campaign,
                    amount=amount,
                    payment_method='telebirr',
                    transaction_id=result['transaction_id'],
                    donor_phone=donor_phone
                )
                logger.debug(f"Created Telebirr transaction: {transaction.transaction_id} for campaign {campaign_id}")
                return HttpResponse(
                    f"Great! Your payment ID is {result['transaction_id']}. "
                    f"Paid from {result['source']}. Go to {result['redirect_url']} to finish!",
                    status=200
                )
            logger.error(f"Telebirr payment failed: {result['message']}")
            return HttpResponse(f"Sorry, Telebirr payment failed: {result['message']}", status=400)

    def initiate_paypal_payment(self, campaign, amount, request, donor_email=None):
        logger.debug(f"Initiating PayPal payment for campaign {campaign.id}, amount {amount}")
        auth_url = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
        auth_headers = {"Accept": "application/json", "Accept-Language": "en_US"}
        auth_data = {"grant_type": "client_credentials"}
        auth_response = requests.post(
            auth_url,
            auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
            headers=auth_headers,
            data=auth_data
        )
        if auth_response.status_code != 200:
            logger.error(f"PayPal auth failed: {auth_response.text}")
            return HttpResponse(f"Oh no! PayPal isn’t working right now. Error: {auth_response.text}", status=auth_response.status_code)

        token = auth_response.json().get("access_token")
        if not token:
            logger.error("No PayPal access token received")
            return HttpResponse("Sorry, we couldn’t connect to PayPal.", status=500)

        order_url = "https://api-m.sandbox.paypal.com/v2/checkout/orders"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        payload = {
            'intent': 'CAPTURE',
            'purchase_units': [{
                'amount': {'currency_code': 'USD', 'value': f"{amount:.2f}"},
                'custom_id': donor_email or 'anonymous'
            }],
            'application_context': {
                'return_url': f'{request.scheme}://{request.get_host()}/api/callback/paypal',
                'cancel_url': f'{request.scheme}://{request.get_host()}/cancel'
            }
        }
        response = requests.post(order_url, headers=headers, json=payload)
        if response.status_code == 201:
            data = response.json()
            transaction = Transaction.objects.create(
                campaign=campaign,
                amount=amount,
                payment_method='paypal',
                transaction_id=data['id'],
                donor_email=donor_email
            )
            logger.debug(f"Created PayPal transaction: {transaction.transaction_id} for campaign {campaign.id}")
            redirect_url = next(link['href'] for link in data['links'] if link['rel'] == 'approve')
            return HttpResponse(f"Great! Your payment ID is {data['id']}. Go to {redirect_url} to finish!", status=200)
        logger.error(f"PayPal order creation failed: {response.text}")
        return HttpResponse(f"Oops! Something went wrong with PayPal: {response.text}", status=response.status_code)

class PaymentCallbackView(APIView):
    @csrf_exempt
    def get(self, request):
        logger.debug(f"PaymentCallbackView.get called with query params: {request.GET}")
        transaction_id = request.GET.get('token')
        if not transaction_id:
            logger.error("No token provided in PayPal callback")
            return HttpResponse("Please provide a transaction ID!", status=400)

        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id)
        except Transaction.DoesNotExist:
            logger.error(f"Transaction {transaction_id} not found")
            return HttpResponse("We couldn’t find that transaction.", status=404)

        if transaction.completed:
            logger.debug(f"Transaction {transaction_id} already completed")
            return HttpResponse("This payment is already done!", status=200)

        if transaction.payment_method == 'paypal':
            return self.verify_paypal_payment(transaction, request)
        logger.error("Invalid payment method for GET request")
        return HttpResponse("Invalid payment method for GET request.", status=400)

    @csrf_exempt
    def post(self, request):
        logger.debug(f"PaymentCallbackView.post called with data: {request.data}")
        transaction_id = request.data.get('transaction_id')
        if not transaction_id:
            logger.error("No transaction ID provided in callback")
            return HttpResponse("Please tell us the transaction ID!", status=400)

        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id)
        except Transaction.DoesNotExist:
            logger.error(f"Transaction {transaction_id} not found")
            return HttpResponse("We couldn’t find that transaction.", status=404)

        if transaction.completed:
            logger.debug(f"Transaction {transaction_id} already completed")
            return HttpResponse("This payment is already done!", status=200)

        if transaction.payment_method == 'paypal':
            return self.verify_paypal_payment(transaction, request)
        elif transaction.payment_method == 'telebirr':
            result = simulate_telebirr_verify(transaction_id)
            if result['success']:
                transaction.completed = True
                transaction.campaign.total_birr += transaction.amount
                transaction.campaign.save()
                transaction.save()
                logger.info(f"Telebirr payment {transaction_id} completed, updated campaign {transaction.campaign.id} balance: {transaction.campaign.total_birr} ETB")
                return HttpResponse(
                    f"Hooray! Your Telebirr payment is complete! {result['message']}",
                    status=200
                )
            logger.error(f"Telebirr verification failed: {result['message']}")
            return HttpResponse(f"Telebirr didn’t confirm: {result['message']}", status=400)

    def verify_paypal_payment(self, transaction, request):
        logger.debug(f"Verifying PayPal payment for transaction {transaction.transaction_id}")
        auth_url = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
        auth_headers = {"Accept": "application/json", "Accept-Language": "en_US"}
        auth_data = {"grant_type": "client_credentials"}
        auth_response = requests.post(
            auth_url,
            auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
            headers=auth_headers,
            data=auth_data
        )
        if auth_response.status_code != 200:
            logger.error(f"PayPal auth failed: {auth_response.text}")
            return HttpResponse(f"PayPal isn’t responding right now. Error: {auth_response.text}", status=auth_response.status_code)

        token = auth_response.json().get("access_token")
        if not token:
            logger.error("No PayPal access token received")
            return HttpResponse("We couldn’t talk to PayPal.", status=500)

        url = f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{transaction.transaction_id}/capture"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        response = requests.post(url, headers=headers)
        if response.status_code == 201:
            transaction.completed = True
            transaction.campaign.total_usd += transaction.amount
            transaction.campaign.save()
            transaction.save()
            logger.info(f"PayPal payment {transaction.transaction_id} completed, updated campaign {transaction.campaign.id} balance: {transaction.campaign.total_usd} USD")
            return HttpResponse("Hooray! Your PayPal payment is complete!", status=200)
        elif response.status_code == 422:
            logger.error(f"PayPal payment not approved: {response.text}")
            return HttpResponse(f"Sorry, PayPal says this payment wasn’t approved: {response.text}", status=422)
        logger.error(f"PayPal capture failed: {response.text}")
        return HttpResponse(f"Something went wrong with PayPal: {response.text}", status=400)

class WithdrawView(APIView):
    def post(self, request):
        logger.debug(f"WithdrawView.post called with data: {request.data}")
        data = request.data
        campaign_id = data.get('campaign_id')
        payment_method = data.get('payment_method')
        recipient_phone = data.get('recipient_phone')
        recipient_email = data.get('recipient_email')
        withdraw_all = data.get('withdraw_all', False)
        convert_to = data.get('convert_to', 'birr').lower()

        missing = []
        if not campaign_id:
            missing.append('campaign_id')
        if not payment_method:
            missing.append('payment_method')
        if payment_method == 'telebirr' and not recipient_phone:
            missing.append('recipient_phone')
        if payment_method == 'paypal' and not recipient_email:
            missing.append('recipient_email')
        if missing:
            logger.error(f"Missing required fields: {', '.join(missing)}")
            return HttpResponse(f"Please include {', '.join(missing)}!", status=400)

        try:
            campaign = Campaign.objects.get(id=campaign_id)
        except Campaign.DoesNotExist:
            logger.error(f"Campaign {campaign_id} not found")
            return HttpResponse("That campaign isn’t here!", status=404)

        if payment_method not in ['paypal', 'telebirr']:
            logger.error(f"Invalid payment method: {payment_method}")
            return HttpResponse("Use PayPal or Telebirr, please!", status=400)

        if convert_to not in ['usd', 'birr']:
            logger.error(f"Invalid conversion currency: {convert_to}")
            return HttpResponse("Convert to USD or birr, please!", status=400)

        available_usd = campaign.total_usd
        available_birr = campaign.total_birr
        if available_usd <= 0 and available_birr <= 0:
            logger.error(f"No funds available for campaign {campaign_id}: {available_usd} USD, {available_birr} ETB")
            return HttpResponse("Not enough funds for that!", status=400)

        if convert_to == 'usd':
            rate = self.get_exchange_rate('ETB', 'USD')
            if rate == 0:
                rate = 0.007571
                logger.info("Using fallback exchange rate ETB to USD: 0.007571")
            total_available_usd = available_usd + (available_birr * Decimal(str(rate)))
            total_available_usd = total_available_usd.quantize(Decimal('0.01'))
            if total_available_usd <= 0:
                logger.error(f"No funds available after conversion to USD for campaign {campaign_id}: {total_available_usd} USD")
                return HttpResponse("Not enough funds after conversion to USD!", status=400)
        else:
            rate = self.get_exchange_rate('USD', 'ETB')
            if rate == 0:
                rate = 132.1
                logger.info("Using fallback exchange rate USD to ETB: 132.1")
            total_available_birr = available_birr + (available_usd * Decimal(str(rate)))
            total_available_birr = total_available_birr.quantize(Decimal('0.01'))
            if total_available_birr <= 0:
                logger.error(f"No funds available after conversion to birr for campaign {campaign_id}: {total_available_birr} ETB")
                return HttpResponse("Not enough funds after conversion to birr!", status=400)

        amount_usd = Decimal('0.00')
        amount_birr = Decimal('0.00')

        if withdraw_all:
            if convert_to == 'usd':
                amount_usd = total_available_usd
            else:
                amount_birr = total_available_birr
        else:
            amount = data.get('amount')
            try:
                amount = float(amount)
                if amount <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                logger.error("Invalid amount provided")
                return HttpResponse("The amount needs to be a positive number!", status=400)

            if convert_to == 'usd':
                amount_usd = Decimal(str(amount)).quantize(Decimal('0.01'))
                if amount_usd > total_available_usd:
                    logger.error(f"Insufficient funds: requested {amount_usd} USD, available {total_available_usd} USD")
                    return HttpResponse(f"Not enough funds! Requested {amount_usd} USD, but only {total_available_usd} USD available.", status=400)
            else:
                amount_birr = Decimal(str(amount)).quantize(Decimal('0.01'))
                if amount_birr > total_available_birr:
                    logger.error(f"Insufficient funds: requested {amount_birr} ETB, available {total_available_birr} ETB")
                    return HttpResponse(f"Not enough funds! Requested {amount_birr} ETB, but only {total_available_birr} ETB available.", status=400)

        if amount_usd == 0 and amount_birr == 0:
            logger.error("Calculated withdrawal amount is zero")
            return HttpResponse("Withdrawal amount cannot be zero!", status=400)

        try:
            withdrawal = WithdrawalRequest.objects.create(
                campaign=campaign,
                amount_usd=amount_usd,
                amount_birr=amount_birr,
                payment_method=payment_method,
                recipient_phone=recipient_phone,
                recipient_email=recipient_email,
                convert_to=convert_to
            )
            logger.debug(f"Withdrawal request created: ID {withdrawal.id}, {amount_usd} USD, {amount_birr} ETB")
            return HttpResponse(
                f"Success! Your withdrawal request (ID: {withdrawal.id}) is pending admin approval.",
                status=201
            )
        except Exception as e:
            logger.error(f"Failed to create withdrawal request: {str(e)}")
            return HttpResponse(f"Server error: {str(e)}", status=500)

    def get_exchange_rate(self, from_currency, to_currency, retries=3, delay=1):
        logger.debug(f"Fetching exchange rate from {from_currency} to {to_currency}")
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
                logger.debug(f"Exchange rate API response: {data}")

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
        rate = fallback_rates.get((from_currency, to_currency))
        if rate:
            logger.info(f"Using fallback rate {from_currency} to {to_currency}: {rate}")
            return rate
        logger.error("No fallback rate available")
        return 0