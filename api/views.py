from django.http import HttpResponse
from swiftclient import client
from django.conf import settings

def save(response):
    client.Connection(user=settings.SWIFT_USER,)
    return HttpResponse()

