import os
import sys

path = '/home/beko41/community_funding'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'community_funding.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()