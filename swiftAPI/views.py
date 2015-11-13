from django.http import HttpResponse,JsonResponse
from swiftclient import client
import exceptions
import swiftclient.exceptions as swiftException
from django.views.decorators.csrf import csrf_exempt
from .import settings
import json
import Image
import uuid
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
        return HttpResponse(e.message, status=500)
    except exceptions.KeyError as e:
        return HttpResponse('JSON object key error: '+e, status=400)
    except exceptions.ValueError:
        return HttpResponse('No JSON object found', status=400)
    except Exception as e:
        return HttpResponse(e, status=500)


@csrf_exempt
def save(request):
    temp_name = ''
    resp_dict = dict()
    py_dict = {}
    try:
        if request.method == 'POST':
            if not request.session.get('storage_url') and not request.session.get('auth_token'):
                return HttpResponse('Please Contact your administrator', status=401, reason='Unauthorized:'
                                                                                            ' session data not found')
            if not request.FILES:
                return HttpResponse('No file/s found to save', status=400)
            for filename, accepted_file in request.FILES.iteritems():
                try:
                    name = request.FILES[filename].name
                    file_type, file_ext = accepted_file.content_type.split('/')
                    storage_url = request.session.get('storage_url')
                    auth_token = request.session.get('auth_token')
                    with open('temp', 'w+') as file:
                        file.writelines(accepted_file.readlines())
                    if file_type == 'image':
                        temp_name = 'file.thumbnail.'+file_ext
                        try:
                            im = Image.open('temp')
                            size = im.size
                            im_type = im.format
                            unique_id_image = uuid.uuid1()
                            unique_id_thumb = uuid.uuid1()
                            main_header = {'X-Object-Meta-Deleted': False, 'X-Object-Meta-Format': im_type,
                                           'X-Object-Meta-Resolution': size}
                            with open('temp', 'r+') as file:
                                client.put_object(storage_url, auth_token, image_container, str(unique_id_image), file,
                                                  headers=main_header)
                            print resp_dict
                            im.thumbnail(thumbnail_size, Image.ANTIALIAS)
                            thumb_size = im.size
                            im.save(temp_name)
                            thumb_header = {'X-Object-Meta-Deleted': False,
                                            'X-Object-Meta-Format': im_type,
                                            'X-Object-Meta-Resolution': thumb_size,
                                            'X-Object-Meta-Thumbof': unique_id_image}
                            with open(temp_name, 'r') as thumb_file:
                                client.put_object(storage_url, auth_token, image_container, str(unique_id_thumb),
                                                  thumb_file, headers=thumb_header)
                            image_url = str(unique_id_image)
                            thumb_url = str(unique_id_thumb)
                            py_dict[name] = {'image_key': image_url, 'thumb_key': thumb_url}
                        except IOError:
                            py_dict[name] = {'error': 'invalid file'}
                finally:
                    if os.path.exists(temp_name):
                        os.remove(temp_name)
                    if os.path.exists('temp'):
                        os.remove('temp')
            return JsonResponse(py_dict)
        else:
            return HttpResponse('Method Not Allowed', status=405)
    except swiftException.ClientException as e:
        return HttpResponse(e.message, status=401)


def get_obj(request, container, object_name):
    try:
        if request.method == 'GET':
            if not request.session.get('storage_url') and not request.session.get('auth_token'):
                return HttpResponse('Please Contact your administrator', status=401, reason='Unauthorized:'
                                                                                            ' session data not found')
            storage_url = request.session.get('storage_url')
            auth_token = request.session.get('auth_token')
            obj_headers, obj = client.get_object(storage_url, auth_token, container, object_name)
            print object_name
            return HttpResponse(obj)
        else:
            return HttpResponse('Method Not Allowed', status=405)
    except swiftException.ClientException as e:
        return HttpResponse('Please Contact Your Administrator', status=e.http_status, reason=e.http_reason)
    except Exception as e:
        return HttpResponse(e.message, status=500)


@csrf_exempt
def delete_obj(request, container, object_name):
    if request.method == 'DELETE':
        storage_url = request.session.get('storage_url')
        print storage_url
        auth_token = request.session.get('auth_token')
        header = client.head_object(storage_url, auth_token, container, object_name)
        resolution = header['x-object-meta-resolution']
        format = header['x-object-meta-format']
        new_header = {'X-Object-Meta-Deleted': True,
                      'X-Object-Meta-Format': format,
                      'X-Object-Meta-Resolution': resolution}

        if 'x-object-meta-thumbof' in header:
            thumb_of = header['x-object-meta-thumbof']
            new_header['X-Object-Meta-Thumbof'] = thumb_of
        client.post_object(storage_url, auth_token, container, object_name, headers=new_header)
        returned_header = client.head_object(storage_url, auth_token, container, object_name)
        return JsonResponse(returned_header)
    else:
        return HttpResponse('Method Not Allowed', status=405)
