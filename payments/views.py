import requests
from django.http import HttpResponse
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Campaign, Transaction, WithdrawalRequest
import hashlib
import time

# Simple homepage
def home(request):
    return HttpResponse("Welcome to Community Funding System")

# Donation endpoint
class DonateView(APIView):
    def post(self, request):
        data = request.data
        campaign_id = data.get('campaign_id')
        amount = data.get('amount')
        payment_method = data.get('payment_method')

        # Validate required fields
        missing = []
        if not campaign_id:
            missing.append('campaign_id')
        if not amount:
            missing.append('amount')
        if not payment_method:
            missing.append('payment_method')
        if missing:
            return Response({'error': f'Missing required fields: {", ".join(missing)}'}, 
                           status=status.HTTP_400_BAD_REQUEST)

        # Validate amount
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return Response({'error': 'Invalid amount: must be a positive number'}, 
                           status=status.HTTP_400_BAD_REQUEST)

        # Check campaign
        try:
            campaign = Campaign.objects.get(id=campaign_id)
        except Campaign.DoesNotExist:
            return Response({'error': 'Campaign not found'}, status=status.HTTP_404_NOT_FOUND)

        # Validate payment method
        if payment_method not in ['paypal', 'telebirr']:
            return Response({'error': 'Invalid payment method: must be "paypal" or "telebirr"'}, 
                           status=status.HTTP_400_BAD_REQUEST)

        if payment_method == 'paypal':
            return self.initiate_paypal_payment(campaign, amount)
        elif payment_method == 'telebirr':
            return self.initiate_telebirr_payment(campaign, amount)

    def initiate_paypal_payment(self, campaign, amount):
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
            return Response({
                'error': 'PayPal authentication failed',
                'details': auth_response.text
            }, status=auth_response.status_code)

        token = auth_response.json().get("access_token")
        if not token:
            return Response({'error': 'Failed to obtain PayPal access token'}, 
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        order_url = "https://api-m.sandbox.paypal.com/v2/checkout/orders"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        payload = {
            'intent': 'CAPTURE',
            'purchase_units': [{
                'amount': {
                    'currency_code': 'USD',
                    'value': f"{amount:.2f}"
                }
            }],
           'application_context': {
    'return_url': 'https://6061-34-78-109-88.ngrok-free.app/api/callback/paypal',
    'cancel_url': 'https://6061-34-78-109-88.ngrok-free.app/cancel'
}
        }
        response = requests.post(order_url, headers=headers, json=payload)
        if response.status_code == 201:
            data = response.json()
            transaction = Transaction.objects.create(
                campaign=campaign,
                amount=amount,
                payment_method='paypal',
                transaction_id=data['id']
            )
            return Response({
                'transaction_id': data['id'],
                'redirect_url': next(link['href'] for link in data['links'] if link['rel'] == 'approve')
            }, status=status.HTTP_200_OK)
        return Response({
            'error': 'PayPal order creation failed',
            'details': response.json()
        }, status=response.status_code)

    def initiate_telebirr_payment(self, campaign, amount):
        url = "https://api.sandbox.ethiotelecom.et/v1/payments"
        timestamp = str(int(time.time() * 1000))
        nonce = hashlib.sha256(timestamp.encode()).hexdigest()
        payload = {
            'appId': settings.TELEBIRR_APP_ID,
            'timestamp': timestamp,
            'nonce': nonce,
            'amount': f"{amount:.2f}",
            'outTradeNo': f"TR{int(time.time())}",
            'notifyUrl': 'http://localhost:8080/api/callback/telebirr',
            'returnUrl': 'http://localhost:8080/success',
            'subject': f"Donation to {campaign.title}",
            'body': campaign.description[:100]
        }
        signature = hashlib.sha256(
            f"{payload['appId']}{payload['timestamp']}{payload['nonce']}{settings.TELEBIRR_APP_KEY}".encode()
        ).hexdigest()
        payload['sign'] = signature

        response = requests.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            transaction = Transaction.objects.create(
                campaign=campaign,
                amount=amount,
                payment_method='telebirr',
                transaction_id=data.get('outTradeNo', payload['outTradeNo'])
            )
            return Response({
                'transaction_id': transaction.transaction_id,
                'redirect_url': data.get('payUrl', 'http://localhost:8080/success')
            }, status=status.HTTP_200_OK)
        return Response({
            'error': 'Telebirr payment initiation failed',
            'details': response.text
        }, status=response.status_code)

# Payment callback endpoint
class PaymentCallbackView(APIView):
    def post(self, request):
        transaction_id = request.data.get('transaction_id')
        if not transaction_id:
            return Response({'error': 'Missing transaction_id'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id)
        except Transaction.DoesNotExist:
            return Response({'error': 'Transaction not found'}, status=status.HTTP_404_NOT_FOUND)

        if transaction.completed:
            return Response({'message': 'Transaction already completed'}, status=status.HTTP_200_OK)

        if transaction.payment_method == 'paypal':
            return self.verify_paypal_payment(transaction)
        elif transaction.payment_method == 'telebirr':
            return self.verify_telebirr_payment(transaction)
        return Response({'error': 'Unsupported payment method'}, status=status.HTTP_400_BAD_REQUEST)

    def verify_paypal_payment(self, transaction):
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
            return Response({
                'error': 'PayPal authentication failed',
                'details': auth_response.text
            }, status=auth_response.status_code)

        token = auth_response.json().get("access_token")
        if not token:
            return Response({'error': 'Failed to obtain PayPal access token'}, 
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        url = f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{transaction.transaction_id}/capture"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        response = requests.post(url, headers=headers)
        if response.status_code == 201:
            transaction.completed = True
            transaction.campaign.total_usd += transaction.amount
            transaction.campaign.save()
            transaction.save()
            return Response({'message': 'PayPal payment completed'}, status=status.HTTP_200_OK)
        elif response.status_code == 422:
            return Response({
                'error': 'PayPal payment not approved',
                'details': response.json()
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response({
            'error': 'PayPal payment verification failed',
            'details': response.json()
        }, status=status.HTTP_400_BAD_REQUEST)

    def verify_telebirr_payment(self, transaction):
        url = "https://api.sandbox.ethiotelecom.et/v1/payment/verify"
        payload = {
            'appId': settings.TELEBIRR_APP_ID,
            'outTradeNo': transaction.transaction_id,
            'appKey': settings.TELEBIRR_APP_KEY
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200 and response.json().get('status') == 'success':
            transaction.completed = True
            transaction.campaign.total_birr += transaction.amount
            transaction.campaign.save()
            transaction.save()
            return Response({'message': 'Telebirr payment completed'}, status=status.HTTP_200_OK)
        return Response({
            'error': 'Telebirr payment verification failed',
            'details': response.text
        }, status=response.status_code if response.status_code in [400, 404] else status.HTTP_400_BAD_REQUEST)

# Withdrawal endpoint
class WithdrawalView(APIView):
    def post(self, request):
        data = request.data
        campaign_id = data.get('campaign_id')
        amount = data.get('amount')
        payment_method = data.get('payment_method')

        # Validate required fields
        missing = []
        if not campaign_id:
            missing.append('campaign_id')
        if not amount:
            missing.append('amount')
        if not payment_method:
            missing.append('payment_method')
        if missing:
            return Response({'error': f'Missing required fields: {", ".join(missing)}'}, 
                           status=status.HTTP_400_BAD_REQUEST)

        # Validate amount
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return Response({'error': 'Invalid amount: must be a positive number'}, 
                           status=status.HTTP_400_BAD_REQUEST)

        # Check campaign
        try:
            campaign = Campaign.objects.get(id=campaign_id)
        except Campaign.DoesNotExist:
            return Response({'error': 'Campaign not found'}, status=status.HTTP_404_NOT_FOUND)

        # Validate payment method and balance
        if payment_method not in ['paypal', 'telebirr']:
            return Response({'error': 'Invalid payment method: must be "paypal" or "telebirr"'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        if payment_method == 'paypal' and campaign.total_usd < amount:
            return Response({'error': 'Insufficient USD balance'}, status=status.HTTP_400_BAD_REQUEST)
        if payment_method == 'telebirr' and campaign.total_birr < amount:
            return Response({'error': 'Insufficient ETB balance'}, status=status.HTTP_400_BAD_REQUEST)

        withdrawal = WithdrawalRequest.objects.create(
            campaign=campaign,
            amount_usd=amount if payment_method == 'paypal' else 0,
            amount_birr=amount if payment_method == 'telebirr' else 0,
            payment_method=payment_method
        )
        return Response({
            'message': 'Withdrawal request created',
            'withdrawal_id': withdrawal.id
        }, status=status.HTTP_201_CREATED)