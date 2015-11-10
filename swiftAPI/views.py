from django.http import HttpResponse,JsonResponse
from swiftclient import client
import exceptions
import swiftclient.exceptions as swiftException
from django.views.decorators.csrf import csrf_exempt
from .import settings
import json
import Image
import uuid
import traceback
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
    try:
        if request.method == 'POST':
            request.session.flush()
            auth_data_dict = json.loads(request.body)
            (username, password) = auth_data_dict[account_key]+':'+auth_data_dict[username_key], auth_data_dict[pass_key]
            authurl = settings.SWIFT_AUTH_URL
            (storage_url, auth_token) = client.get_auth(authurl, username, password)
            request.session['auth_token'], request.session['storage_url'], request.session['username'] \
                = auth_token, storage_url, username
            return JsonResponse({'username': username, 'auth_token': auth_token, 'storage_url': storage_url})
        else:
            return HttpResponse('Method Not Allowed', status=405)
    except swiftException.ClientException as e:
        return HttpResponse(e.message, status=e.http_status)
    except exceptions.KeyError as e:
        return HttpResponse('JSON object key error: '+e, status=400)
    except exceptions.ValueError:
        return HttpResponse('No JSON object found', status=400)
    except Exception as e:
        return HttpResponse(e, status=500)


@csrf_exempt
def save(request):
    temp_name = ''
    try:
        if request.method == 'POST':
            py_dict = {}
            if not request.FILES:
                return HttpResponse('No file/s found to save', status=400)
            for filename, accepted_file in request.FILES.iteritems():
                print filename
                print request.FILES
                print type(request.FILES)
                name = request.FILES[filename].name
                file_type, file_ext = accepted_file.content_type.split('/')
                storage_url = request.session.get('storage_url')
                auth_token = request.session.get('auth_token')
                with open('temp', 'w+') as file:
                    file.writelines(accepted_file.readlines())
                if file_type == 'image':
                    print file_type
                    temp_name = 'file.thumbnail.'+file_ext
                    im = Image.open('temp')
                    unique_id_image = uuid.uuid1()
                    unique_id_thumb = uuid.uuid1()
                    with open('temp', 'r+') as file:
                        client.put_object(storage_url, auth_token, image_container, str(unique_id_image), file)
                    im.thumbnail(thumbnail_size, Image.ANTIALIAS)
                    im.save(temp_name)
                    with open(temp_name, 'r') as thumb_file:
                        client.put_object(storage_url, auth_token, image_container, str(unique_id_thumb), thumb_file)
                    image_url = str(unique_id_image)
                    print image_url
                    thumb_url = str(unique_id_thumb)
                    py_dict[name] = {'image_key': image_url, 'thumb_key': thumb_url}
            print py_dict
            return JsonResponse(py_dict)
        else:
            return HttpResponse('Method Not Allowed', status=405)
    except swiftException.ClientException as e:
        return HttpResponse(e.message, status=401)
    except Exception as e:
        if e.message == 'cannot identify image file':
            return HttpResponse('Image file corrupt or not a valid image file', status=400)
    finally:
        if os.path.exists(temp_name):
            os.remove(temp_name)
        if os.path.exists('temp'):
            os.remove('temp')


def get_obj(request, container, object_name):
    if request.method == 'GET':
        storage_url = request.session.get('storage_url')
        print storage_url
        auth_token = request.session.get('auth_token')
        print auth_token
        obj_headers, obj = client.get_object(storage_url, auth_token, container, object_name)

        return HttpResponse(obj)


@csrf_exempt
def delete_obj(request, container, object_name):
    if request.method == 'DELETE':
        storage_url = request.session.get('storage_url')
        auth_token = request.session.get('auth_token')
        client.delete_object(storage_url, auth_token, container, object_name)
        return HttpResponse(object_name)
