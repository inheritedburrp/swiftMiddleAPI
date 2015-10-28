from django.http import HttpResponse,JsonResponse
import swiftclient
from swiftclient import client
from django.views.decorators.csrf import csrf_exempt
from .import settings
from django.contrib import messages


@csrf_exempt
def authenticate(request):
    request.session.flush()
    (username, password) = request.body.split('&')
    try:
        authurl = settings.SWIFT_AUTH_URL
        (storage_url, auth_token) = client.get_auth(authurl, username, password)
        request.session['auth_token'], request.session['storage_url'], request.session['username'] \
            = auth_token, storage_url, username
        return JsonResponse({'username': username, 'auth_token': auth_token, 'storage_url': storage_url})

    except client.ClientException:
        return HttpResponse(dir(client.ClientException))

@csrf_exempt
def index(request, account, container, object, authtoken):
        conn = swiftclient.Connection(authurl=settings.SWIFT_AUTH_URL, user=settings.SWIFT_USER, key=settings.SECRET_KEY)
        acct_headers, containers = conn.get_account()
        cont_headers, objs = conn.get_container('ContentImages')
        obj_headers, obj = conn.get_object('ContentImages', 'IMG_22102015_144509.png')
        print("Container Header : ", acct_headers)
        print("Container Objects : ", objs)
        return HttpResponse(obj)



@csrf_exempt
def save(request):
    print("Save Reqtest")
    if request.method == 'POST':
        authurl, username, password = (settings.SWIFT_AUTH_URL, settings.SWIFT_USER, settings.SWIFT_KEY)
        conn = swiftclient.Connection(authurl=authurl, user=username, key=password)
        acct_headers, containers = conn.get_account()
        print(">>>>>>>>>>>>>>>Swift Auth done ")
        #cont_headers, objs = conn.get_container('ContentImages')
        #print("Object Saved hash : ", hash)
        for filename, file in request.FILES.iteritems():
                name = request.FILES[filename].name
                byte = file.read()
                hash = conn.put_object('ContentImages',name,byte);
                print("File Saved with hash : ",hash)
    return HttpResponse('Upload file to save.!!!!!!!!!')