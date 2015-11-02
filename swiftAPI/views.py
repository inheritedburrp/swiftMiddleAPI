from django.http import HttpResponse,JsonResponse
from swiftclient import client
from django.views.decorators.csrf import csrf_exempt
from .import settings
import json
import Image
import uuid
from cStringIO import StringIO
import os

account_key = 'account'
username_key = 'user'
pass_key = 'passkey'

image_container = 'Image'
video_container = 'Video'
audio_container = 'Audio'
miscellaneous_container = 'Miscellaneous'

thumbnail_size = (200, 200)


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


@csrf_exempt
def save(request):
    if request.method == 'POST':
        try:
            for filename, accepted_file in request.FILES.iteritems():
                file_type, file_ext = accepted_file.content_type.split('/')
                storage_url = request.session.get('storage_url')
                auth_token = request.session.get('auth_token')
                with open('temp', 'w+') as file:
                    file.writelines(accepted_file.readlines())
                if file_type == 'image':
                    temp_name = 'file.thumbnail.'+file_ext
                    unique_id_image = uuid.uuid1()
                    unique_id_thumb = uuid.uuid1()
                    with open('temp', 'r+') as file:
                        client.put_object(storage_url, auth_token, image_container, str(unique_id_image), file)
                    im = Image.open('temp')
                    im.thumbnail(thumbnail_size, Image.ANTIALIAS)
                    im.save(temp_name)
                    with open(temp_name, 'r') as thumb_file:
                        client.put_object(storage_url, auth_token, image_container, str(unique_id_thumb), thumb_file)
                    image_url = '/'+image_container+'/'+str(unique_id_image)+'/'
                    thumb_url = '/'+image_container+'/'+str(unique_id_thumb)+'/'
                    return JsonResponse({'image url': image_url,
                                         'thumb url': thumb_url})
        finally:
            os.remove(temp_name)
            os.remove('temp')


def get_obj(request, container, object_name):
    if request.method == 'GET':
        storage_url = request.session.get('storage_url')
        auth_token = request.session.get('auth_token')

        obj_headers, obj = client.get_object(storage_url, auth_token, container, object_name)

        return HttpResponse(obj)


@csrf_exempt
def delete_obj(request, container, object_name):
    if request.method == 'DELETE':
        storage_url = request.session.get('storage_url')
        auth_token = request.session.get('auth_token')
        client.delete_object(storage_url, auth_token, container, object_name)
        return HttpResponse(object_name)


# @csrf_exempt
# def save(request):
#     if request.method == 'POST':
#         for filename, accepted_file in request.FILES.iteritems():
#             name = request.FILES[filename].name
#             storage_url = request.session.get('storage_url')
#             auth_token = request.session.get('auth_token')
#             image = Image.open(StringIO(accepted_file.read()))
#             print image.size
#             print type(image)
#             image.thumbnail(thumbnail_size, Image.ANTIALIAS)
#             print name
#             print image
#             print type(image)
#             print dir(image)
#             print image.size
#             image.save('file.JPEG')
#             f = open('file.JPEG', 'r')
#             client.put_object(storage_url, auth_token, image_container, name, f)
#             f.close()
#             os.remove('file.JPEG')
#             return HttpResponse("saved!!!")
