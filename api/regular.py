from django.http import HttpResponse
import swiftclient
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def index(request, account, container, object, authtoken):
        authurl, username, password = ('http://192.168.134.77:8080/auth/v1.0', 'asset:master', 'master')
        conn = swiftclient.Connection(authurl=authurl, user=username, key=password)
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
        print(">>>>>>>>>>>>>>>Requst Incoming ")
        authurl, username, password = ('http://192.168.134.77:8080/auth/v1.0', 'asset:master', 'master')
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