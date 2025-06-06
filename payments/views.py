from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.conf import settings
from django.contrib.auth.decorators import login_required
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

def validate_amount(amount):
    """Validate that the amount is a positive number."""
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
        return Decimal(str(amount)).quantize(Decimal('0.01')), None
    except (ValueError, TypeError):
        return None, "Amount must be a positive number greater than 0."

def initiate_chapa_payment(amount, campaign_id):
    """Initiate a Chapa payment without requiring phone number."""
    amount_val, amount_error = validate_amount(amount)
    if amount_error:
        logger.error(f"Chapa validation error: {amount_error}")
        return {'success': False, 'message': amount_error}

    amount_str = f"{amount_val:.2f}"

    if not settings.SITE_URL.startswith('https://'):
        logger.error(f"Invalid SITE_URL: {settings.SITE_URL}. Must use HTTPS.")
        return {'success': False, 'message': 'Server configuration error: SITE_URL must use HTTPS.'}

    url = "https://api.chapa.co/v1/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.CHAPA_TEST_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": amount_str,
        "currency": "ETB",
        "email": "esa414288@gmail.com",
        "first_name": "Test",
        "last_name": "User",
        "tx_ref": f"CHAPA-{int(time.time())}-{campaign_id}",
        "callback_url": f"{settings.SITE_URL}/api/callback/chapa/",
        "return_url": f"{settings.SITE_URL}/api/callback/chapa/?campaign_id={campaign_id}"
    }
    try:
        logger.debug(f"Sending Chapa request with payload: {payload}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        logger.debug(f"Chapa API response: {data}")
        if data.get('status') == 'success' and data.get('data') and data['data'].get('checkout_url'):
            return {
                'success': True,
                'checkout_url': data['data']['checkout_url'],
                'transaction_id': data['data'].get('tx_ref', payload['tx_ref'])
            }
        logger.error(f"Chapa API returned failure: {data.get('message', 'Unknown error')}")
        return {'success': False, 'message': data.get('message', 'Payment initialization failed')}
    except requests.RequestException as e:
        logger.error(f"Chapa payment initialization failed: {str(e)}")
        if e.response is not None:
            logger.error(f"Chapa error response: {e.response.text}")
        return {'success': False, 'message': f'Failed to connect to Chapa: {str(e)}'}

def verify_chapa_payment(transaction_id):
    """Verify a Chapa payment."""
    url = f"https://api.chapa.co/v1/transaction/verify/{transaction_id}"
    headers = {
        "Authorization": f"Bearer {settings.CHAPA_TEST_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.debug(f"Chapa verification response: {data}")
        if data.get('status') == 'success' and data['data'].get('status') == 'success':
            amount = Decimal(data['data'].get('amount', '0.00'))
            return {'success': True, 'amount': amount, 'message': 'Payment verified'}
        logger.error(f"Chapa verification failed: {data.get('message', 'Payment not successful')}")
        return {'success': False, 'message': data.get('message', 'Payment not successful')}
    except requests.RequestException as e:
        logger.error(f"Chapa payment verification failed: {str(e)}")
        return {'success': False, 'message': f'Failed to verify payment: {str(e)}'}

def simulate_paypal_transfer(amount, recipient_email):
    """Simulate a PayPal transfer."""
    logger.debug(f"Simulated PayPal transfer: {amount} USD to {recipient_email}")
    return {'success': True, 'message': f"Transferred {amount} USD to {recipient_email}"}

def test_page(request):
    """Render the test page with campaign data."""
    campaigns = Campaign.objects.all()
    context = {
        'campaigns': campaigns,
        'campaign_message': request.session.pop('campaign_message', None),
        'campaign_error': request.session.pop('campaign_error', None),
        'chapa_message': request.session.pop('chapa_message', None),
        'chapa_error': request.session.pop('chapa_error', None),
        'paypal_message': request.session.pop('paypal_message', None),
        'paypal_error': request.session.pop('paypal_error', None),
        'withdrawal_message': request.session.pop('withdrawal_message', None),
        'withdrawal_error': request.session.pop('withdrawal_error', None),
    }
    return render(request, 'payments/test.html', context)

class CreateCampaignView(APIView):
    def post(self, request):
        """Create a new campaign."""
        logger.debug(f"CreateCampaignView.post called with data: {request.POST}")
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '')
        goal = request.POST.get('goal', '').strip()

        if not title or len(title) > 200:
            logger.error("Invalid title")
            request.session['campaign_error'] = "Title is required and must not exceed 200 characters."
            return HttpResponseRedirect(reverse('test_page'))

        goal_val, goal_error = validate_amount(goal)
        if goal_error:
            logger.error(f"Invalid goal amount: {goal_error}")
            request.session['campaign_error'] = goal_error
            return HttpResponseRedirect(reverse('test_page'))

        try:
            campaign = Campaign.objects.create(
                title=title,
                description=description,
                goal=goal_val,
                total_usd=Decimal('0.00'),
                total_birr=Decimal('0.00'),
                creator=request.user if request.user.is_authenticated else None
            )
            logger.debug(f"Created campaign: {campaign.id}")
            request.session['campaign_message'] = f"Campaign '{title}' created successfully!"
            return HttpResponseRedirect(reverse('test_page'))
        except Exception as e:
            logger.error(f"Failed to create campaign: {str(e)}")
            request.session['campaign_error'] = f"Error creating campaign: {str(e)}"
            return HttpResponseRedirect(reverse('test_page'))

class CampaignListView(APIView):
    def get(self, request):
        """List all campaigns."""
        campaigns = Campaign.objects.all()
        serializer = CampaignSerializer(campaigns, many=True)
        return Response(serializer.data)

class CampaignDetailView(APIView):
    def get(self, request, pk):
        """Get details of a specific campaign."""
        try:
            campaign = Campaign.objects.get(pk=pk)
            serializer = CampaignSerializer(campaign)
            return Response(serializer.data)
        except Campaign.DoesNotExist:
            logger.error(f"Campaign {pk} not found")
            return Response({"error": "Campaign not found"}, status=status.HTTP_404_NOT_FOUND)

class DonateView(APIView):
    def post(self, request):
        logger.debug(f"DonateView.post called with data: {request.POST}")
        data = request.POST
        campaign_id = data.get('campaign_id', '').strip()
        amount = data.get('amount', '').strip()
        payment_method = data.get('payment_method', '').strip()
        donor_email = data.get('donor_email', '').strip()

        if not campaign_id or not amount or not payment_method:
            logger.error("Missing required fields: campaign_id, amount, or payment_method")
            error_key = 'chapa_error' if payment_method == 'chapa' else 'paypal_error'
            request.session[error_key] = "Please provide campaign ID, amount, and payment method."
            return HttpResponseRedirect(reverse('test_page'))

        amount_val, amount_error = validate_amount(amount)
        if amount_error:
            logger.error(f"Invalid amount: {amount_error}")
            error_key = 'chapa_error' if payment_method == 'chapa' else 'paypal_error'
            request.session[error_key] = amount_error
            return HttpResponseRedirect(reverse('test_page'))

        try:
            campaign = Campaign.objects.get(id=int(campaign_id))
        except (Campaign.DoesNotExist, ValueError):
            logger.error(f"Campaign {campaign_id} not found")
            error_key = 'chapa_error' if payment_method == 'chapa' else 'paypal_error'
            request.session[error_key] = "Hmm, that campaign doesn’t exist."
            return HttpResponseRedirect(reverse('test_page'))

        if payment_method not in ['paypal', 'chapa']:
            logger.error(f"Invalid payment method: {payment_method}")
            error_key = 'chapa_error' if payment_method == 'chapa' else 'paypal_error'
            request.session[error_key] = "Please choose either PayPal or Chapa!"
            return HttpResponseRedirect(reverse('test_page'))

        if payment_method == 'paypal' and not donor_email:
            logger.error("Missing donor email for PayPal")
            request.session['paypal_error'] = "Please provide a donor email for PayPal."
            return HttpResponseRedirect(reverse('test_page'))

        if payment_method == 'paypal':
            return self.initiate_paypal_payment(campaign, amount_val, request, donor_email)
        elif payment_method == 'chapa':
            result = initiate_chapa_payment(amount_val, campaign_id)
            logger.debug(f"Chapa payment initiation result: {result}")
            if result['success']:
                transaction = Transaction.objects.create(
                    campaign=campaign,
                    amount=amount_val,
                    payment_method='chapa',
                    transaction_id=result['transaction_id']
                )
                request.session['chapa_tx_ref'] = result['transaction_id']
                request.session.modified = True
                logger.debug(f"Stored chapa_tx_ref in session: {result['transaction_id']}")
                logger.debug(f"Created Chapa transaction: {transaction.transaction_id} for campaign {campaign_id}")
                return HttpResponseRedirect(result['checkout_url'])
            else:
                request.session['chapa_error'] = result['message']
                return HttpResponseRedirect(reverse('test_page'))

    def initiate_paypal_payment(self, campaign, amount, request, donor_email):
        """Initiate a PayPal payment."""
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
            request.session['paypal_error'] = f"Oh no! PayPal isn’t working right now. Error: {auth_response.text}"
            return HttpResponseRedirect(reverse('test_page'))

        token = auth_response.json().get("access_token")
        if not token:
            logger.error("No PayPal access token received")
            request.session['paypal_error'] = "Sorry, we couldn’t connect to PayPal."
            return HttpResponseRedirect(reverse('test_page'))

        order_url = "https://api-m.sandbox.paypal.com/v2/checkout/orders"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        payload = {
            'intent': 'CAPTURE',
            'purchase_units': [{
                'amount': {'currency_code': 'USD', 'value': f"{amount:.2f}"},
                'custom_id': donor_email
            }],
            'application_context': {
                'return_url': f'{settings.SITE_URL}/api/callback/paypal/',
                'cancel_url': f'{settings.SITE_URL}/cancel/'
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
            return HttpResponseRedirect(redirect_url)
        logger.error(f"PayPal order creation failed: {response.text}")
        request.session['paypal_error'] = f"Oops! Something went wrong with PayPal: {response.text}"
        return HttpResponseRedirect(reverse('test_page'))

class ChapaCallbackView(APIView):
    def post(self, request):
        """Handle Chapa payment callback (POST from Chapa)."""
        logger.debug(f"ChapaCallbackView.post called with data: {request.POST}")
        transaction_id = request.POST.get('tx_ref')
        if not transaction_id:
            logger.error("No transaction ID provided in Chapa callback")
            return Response({"error": "Missing transaction ID"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id)
        except Transaction.DoesNotExist:
            logger.error(f"Transaction {transaction_id} not found")
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

        if transaction.completed:
            logger.debug(f"Transaction {transaction_id} already completed")
            return Response({"message": "Payment already processed"}, status=status.HTTP_200_OK)

        result = verify_chapa_payment(transaction_id)
        if result['success']:
            transaction.completed = True
            transaction.campaign.total_birr += result['amount']
            transaction.campaign.save()
            transaction.save()
            logger.info(f"Chapa payment {transaction_id} completed, updated campaign {transaction.campaign.id} balance: {transaction.campaign.total_birr} ETB")
            request.session['chapa_message'] = f"Successful donation of {result['amount']} ETB via Chapa!"
        else:
            logger.error(f"Chapa verification failed: {result['message']}")
            request.session['chapa_error'] = f"Payment verification failed: {result['message']}"
        return HttpResponseRedirect(reverse('test_page'))

    def get(self, request):
        """Handle redirect back from Chapa (GET after user approval)."""
        logger.debug(f"Chapa callback GET request data: {request.GET}")
        logger.debug(f"Session data: {request.session.items()}")
        transaction_id = request.GET.get('tx_ref') or request.session.get('chapa_tx_ref')
        if not transaction_id:
            campaign_id = request.GET.get('campaign_id')
            if campaign_id:
                try:
                    recent_transaction = Transaction.objects.filter(
                        campaign_id=campaign_id,
                        payment_method='chapa',
                        completed=False
                    ).order_by('-created_at').first()
                    if recent_transaction:
                        transaction_id = recent_transaction.transaction_id
                        logger.debug(f"Fallback: Found recent Chapa transaction {transaction_id} for campaign {campaign_id}")
                except Exception as e:
                    logger.error(f"Error finding recent transaction: {str(e)}")

        if not transaction_id:
            logger.error("No transaction ID provided in Chapa callback GET or session, even after fallback")
            request.session['chapa_error'] = "Missing transaction ID in Chapa callback. Please try again."
            return HttpResponseRedirect(reverse('test_page'))

        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id)
        except Transaction.DoesNotExist:
            logger.error(f"Transaction {transaction_id} not found")
            request.session['chapa_error'] = "Transaction not found."
            return HttpResponseRedirect(reverse('test_page'))

        if transaction.completed:
            logger.debug(f"Transaction {transaction_id} already completed")
            request.session['chapa_message'] = "Payment already processed."
            if 'chapa_tx_ref' in request.session:
                del request.session['chapa_tx_ref']
                request.session.modified = True
            return HttpResponseRedirect(reverse('test_page'))

        result = verify_chapa_payment(transaction_id)
        if result['success']:
            transaction.completed = True
            transaction.campaign.total_birr += result['amount']
            transaction.campaign.save()
            transaction.save()
            logger.info(f"Chapa payment {transaction_id} completed, updated campaign {transaction.campaign.id} balance: {transaction.campaign.total_birr} ETB")
            request.session['chapa_message'] = f"Successful donation of {result['amount']} ETB via Chapa!"
        else:
            logger.error(f"Chapa verification failed in GET: {result['message']}")
            request.session['chapa_error'] = f"Payment verification failed: {result['message']}"
        if 'chapa_tx_ref' in request.session:
            del request.session['chapa_tx_ref']
            request.session.modified = True
        return HttpResponseRedirect(reverse('test_page'))

class PayPalCallbackView(APIView):
    def post(self, request):
        """Handle PayPal payment callback (IPN or webhook)."""
        logger.debug(f"PayPalCallbackView.post called with data: {request.data}")
        transaction_id = request.data.get('transaction_id') or request.data.get('id')
        if not transaction_id:
            logger.error("No transaction ID provided in PayPal callback")
            request.session['paypal_error'] = "Missing transaction ID in PayPal callback."
            return HttpResponseRedirect(reverse('test_page'))

        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id)
        except Transaction.DoesNotExist:
            logger.error(f"Transaction {transaction_id} not found")
            request.session['paypal_error'] = "Transaction not found."
            return HttpResponseRedirect(reverse('test_page'))

        if transaction.completed:
            logger.debug(f"Transaction {transaction_id} already completed")
            request.session['paypal_message'] = "Payment already processed."
            return HttpResponseRedirect(reverse('test_page'))

        return self.verify_paypal_payment(transaction, request)

    def get(self, request):
        """Handle PayPal payment redirect after approval."""
        logger.debug(f"PayPal callback GET request data: {request.GET}")
        token = request.GET.get('token')
        if not token:
            logger.error("No token provided in PayPal callback")
            request.session['paypal_error'] = "Missing token in PayPal callback."
            return HttpResponseRedirect(reverse('test_page'))

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
            request.session['paypal_error'] = f"PayPal auth failed: {auth_response.text}"
            return HttpResponseRedirect(reverse('test_page'))

        access_token = auth_response.json().get("access_token")
        if not access_token:
            logger.error("No PayPal access token received")
            request.session['paypal_error'] = "No PayPal access token received."
            return HttpResponseRedirect(reverse('test_page'))

        order_url = f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{token}"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {access_token}'}
        order_response = requests.get(order_url, headers=headers)
        if order_response.status_code != 200:
            logger.error(f"PayPal order fetch failed: {order_response.text}")
            request.session['paypal_error'] = f"PayPal order fetch failed: {order_response.text}"
            return HttpResponseRedirect(reverse('test_page'))

        order_data = order_response.json()
        transaction_id = order_data.get('id')
        if not transaction_id:
            logger.error("No transaction ID in PayPal order data")
            request.session['paypal_error'] = "No transaction ID in PayPal order data."
            return HttpResponseRedirect(reverse('test_page'))

        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id)
        except Transaction.DoesNotExist:
            logger.error(f"Transaction {transaction_id} not found")
            request.session['paypal_error'] = "Transaction not found."
            return HttpResponseRedirect(reverse('test_page'))

        if transaction.completed:
            logger.debug(f"Transaction {transaction_id} already completed")
            request.session['paypal_message'] = "Payment already processed."
            return HttpResponseRedirect(reverse('test_page'))

        return self.verify_paypal_payment(transaction, request)

    def verify_paypal_payment(self, transaction, request):
        """Verify a PayPal payment."""
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
            request.session['paypal_error'] = f"PayPal auth failed: {auth_response.text}"
            return HttpResponseRedirect(reverse('test_page'))

        token = auth_response.json().get("access_token")
        if not token:
            logger.error("No PayPal access token received")
            request.session['paypal_error'] = "No PayPal access token received."
            return HttpResponseRedirect(reverse('test_page'))

        url = f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{transaction.transaction_id}/capture"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        response = requests.post(url, headers=headers)
        if response.status_code == 201:
            data = response.json()
            transaction.completed = True
            transaction.campaign.total_usd += transaction.amount
            transaction.campaign.save()
            transaction.save()
            logger.info(f"PayPal payment {transaction.transaction_id} completed, updated campaign {transaction.campaign.id} balance: {transaction.campaign.total_usd} USD")
            request.session['paypal_message'] = f"Successful donation via PayPal! Amount: ${transaction.amount:.2f}"
        elif response.status_code == 422:
            logger.error(f"PayPal payment not approved: {response.text}")
            request.session['paypal_error'] = f"PayPal payment not approved: {response.text}"
        else:
            logger.error(f"PayPal capture failed: {response.text}")
            request.session['paypal_error'] = f"PayPal capture failed: {response.text}"
        return HttpResponseRedirect(reverse('test_page'))

@method_decorator(login_required, name='dispatch')
class WithdrawView(APIView):
    def get_exchange_rate(self, from_currency, to_currency):
        """Fetch exchange rate with retries."""
        from .utils.exchange_rate import get_exchange_rate
        api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', None)
        return get_exchange_rate(from_currency, to_currency, api_key=api_key)

    def post(self, request):
        """Handle withdrawal requests."""
        logger.debug(f"WithdrawView.post called with data: {request.POST}")
        data = request.POST
        campaign_id = data.get('campaign_id', '').strip()
        payment_method = data.get('payment_method', '').strip()
        recipient_email = data.get('recipient_email', '').strip()
        recipient_phone = data.get('recipient_phone', '').strip()  # New field for Chapa
        amount = data.get('amount', '').strip()
        convert_to = data.get('convert_to', 'birr').strip().lower()

        try:
            campaign_id = int(campaign_id)
            campaign = Campaign.objects.get(id=campaign_id)
            # Temporarily commented out creator check for testing
            # if campaign.creator != request.user:
            #     logger.error(f"User {request.user} is not the creator of campaign {campaign_id}")
            #     request.session['withdrawal_error'] = "You can only withdraw from campaigns you created."
            #     return HttpResponseRedirect(reverse('test_page'))
        except (ValueError, Campaign.DoesNotExist):
            logger.error(f"Campaign {campaign_id} not found or invalid ID")
            request.session['withdrawal_error'] = "Hmm, that campaign doesn’t exist or the ID is invalid."
            return HttpResponseRedirect(reverse('test_page'))

        if payment_method not in ['paypal', 'chapa']:
            logger.error(f"Invalid payment method: {payment_method}")
            request.session['withdrawal_error'] = "Please choose either PayPal or Chapa!"
            return HttpResponseRedirect(reverse('test_page'))
        if payment_method == 'paypal' and not recipient_email:
            logger.error("Missing recipient email for PayPal")
            request.session['withdrawal_error'] = "Please provide a recipient email for PayPal."
            return HttpResponseRedirect(reverse('test_page'))
        if payment_method == 'chapa' and not recipient_phone:
            logger.error("Missing recipient phone for Chapa")
            request.session['withdrawal_error'] = "Please provide a recipient telephone number for Chapa."
            return HttpResponseRedirect(reverse('test_page'))

        amount_val, amount_error = validate_amount(amount)
        if amount_error:
            logger.error(f"Invalid amount: {amount_error}")
            request.session['withdrawal_error'] = amount_error
            return HttpResponseRedirect(reverse('test_page'))

        # Get the exchange rate
        rate = self.get_exchange_rate('USD', 'ETB')
        if rate == 0:
            rate = 132.1  # Fallback rate
            logger.info(f"Using fallback exchange rate USD to ETB: {rate}")

        # Convert requested amount to Birr for comparison
        if convert_to == 'birr':
            amount_in_birr = amount_val  # Use the amount directly if requesting in Birr
        else:  # convert_to == 'usd'
            amount_in_birr = amount_val * Decimal(str(rate))  # Convert USD to ETB

        # Calculate total available balance in Birr
        total_available = campaign.total_birr + (campaign.total_usd * Decimal(str(rate)))

        if total_available < amount_in_birr:
            logger.error(f"Insufficient funds: requested {amount_in_birr} ETB, available {total_available} ETB")
            request.session['withdrawal_error'] = f"Not enough funds! Requested {amount_in_birr:.2f} ETB, but only {total_available:.2f} ETB available."
            return HttpResponseRedirect(reverse('test_page'))

        try:
            withdrawal = WithdrawalRequest.objects.create(
                campaign=campaign,
                requested_amount=amount_val,
                payment_method=payment_method,
                recipient_email=recipient_email if payment_method == 'paypal' else None,
                recipient_phone=recipient_phone if payment_method == 'chapa' else None,
                convert_to=convert_to
            )
            logger.debug(f"Withdrawal request created: ID {withdrawal.id}, {amount_val} {convert_to.upper()}")
            request.session['withdrawal_message'] = f"Success! Your withdrawal request (ID: {withdrawal.id}) is pending admin approval."
            return HttpResponseRedirect(reverse('test_page'))
        except Exception as e:
            logger.error(f"Failed to create withdrawal request: {str(e)}")
            request.session['withdrawal_error'] = f"Server error: {str(e)}"
            return HttpResponseRedirect(reverse('test_page'))