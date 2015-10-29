from django.http import HttpResponse,JsonResponse,HttpResponseNotAllowed
import swiftclient
from swiftclient import client
from django.views.decorators.csrf import csrf_exempt
from .import settings
import json

account_key = 'account'
username_key = 'user'
pass_key = 'passkey'

@csrf_exempt
def authenticate(request):
    if request.method == 'POST':
        request.session.flush()
        auth_data_dict = json.loads(request.body)
        (username, password) = auth_data_dict[account_key]+':'+auth_data_dict[username_key], auth_data_dict[pass_key]
        try:
            authurl = settings.SWIFT_AUTH_URL
            (storage_url, auth_token) = client.get_auth(authurl, username, password)
            request.session['auth_token'], request.session['storage_url'], request.session['username'] \
                = auth_token, storage_url, username
            return JsonResponse({'username': username, 'auth_token': auth_token, 'storage_url': storage_url})
        except client.ClientException:
            return HttpResponse(dir(client.ClientException))


def get_obj(request, account, container, object_name):
    if request.method == 'GET':
        storage_url = request.session.get('storage_url')
        auth_token = request.session.get('auth_token')
        obj_headers, obj = client.get_object(storage_url, auth_token, container, object_name)
        return HttpResponse(obj)


@csrf_exempt
def save(request):
    if request.method == 'POST':
        authurl, username, password = (settings.SWIFT_AUTH_URL, settings.SWIFT_USER, settings.SWIFT_KEY)
        conn = swiftclient.Connection(authurl=authurl, user=username, key=password)

        print(">>>>>>>>>>>>>>>Swift Auth done ")

        for filename, file in request.FILES.iteritems():
            name = request.FILES[filename].name
            byte = file.read()
            hash = conn.put_object('ContentImages', name, byte)
        return HttpResponse("File Saved with hash : ")





