from django.http import HttpResponse, JsonResponse
import swiftclient.exceptions as swiftException
from django.views.decorators.csrf import csrf_exempt
from swiftclient import client
from .import settings
import exceptions
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
        return HttpResponse('JSON object key error: '+str(e), status=400)
    except exceptions.ValueError:
        return HttpResponse('No JSON object found', status=400)
    except Exception as e:
        return HttpResponse(e, status=500)


@csrf_exempt
def save(request):
    temp_name = ''
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
                    original_name = request.FILES[filename].name
                    id = request.POST[filename]
                    print id
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
                            main_header = {'X-Object-Meta-Deleted': False,
                                           'X-Object-Meta-Name': original_name,
                                           'X-Object-Meta-Format': im_type,
                                           'X-Object-Meta-Resolution': size,
                                           'X-Delete-After': 172800,
                                           'X-Object-Meta-Type': 'original',
                                           'X-Object-Meta-Originalof': unique_id_thumb}
                            with open('temp', 'r+') as file:
                                client.put_object(storage_url, auth_token, image_container, str(unique_id_image), file,
                                                  headers=main_header)
                                print client.head_object(storage_url, auth_token, image_container, str(unique_id_image))
                            im.thumbnail(thumbnail_size, Image.ANTIALIAS)
                            im.save(temp_name)
                            thumb_header = {'X-Object-Meta-Deleted': False,
                                            'X-Object-Meta-Format': im_type,
                                            'X-Object-Meta-Name': original_name,
                                            'X-Object-Meta-Resolution': size,
                                            'X-Delete-After': 172800,
                                            'X-Object-Meta-Type': 'thumbnail',
                                            'X-Object-Meta-Thumbof': unique_id_image}
                            with open(temp_name, 'r') as thumb_file:
                                client.put_object(storage_url, auth_token, image_container, str(unique_id_thumb),
                                                  thumb_file, headers=thumb_header)
                            image_url = str(unique_id_image)
                            thumb_url = str(unique_id_thumb)
                            py_dict[id] = {'image_key': image_url, 'thumb_key': thumb_url}
                        except IOError:
                            py_dict[id] = {'error': 'invalid file'}
                finally:
                    if os.path.exists(temp_name):
                        os.remove(temp_name)
                    if os.path.exists('temp'):
                        os.remove('temp')
            return JsonResponse(py_dict)
        else:
            return HttpResponse('Method Not Allowed', status=405)
    except swiftException.ClientException as e:
        message = str(e.message) + ', Please contact your administrator'
        return HttpResponse(message, status=401)
    except Exception as e:
        return HttpResponse(e.message, status=500)


def get_obj(request, container, object_name):
    try:
        if request.method == 'GET':
            if not request.session.get('storage_url') and not request.session.get('auth_token'):
                return HttpResponse('Please Contact your administrator', status=401, reason='Unauthorized:'
                                                                                            ' session data not found')
            storage_url = request.session.get('storage_url')
            auth_token = request.session.get('auth_token')
            obj_headers, obj = client.get_object(storage_url, auth_token, container, object_name)
            return HttpResponse(obj)
        else:
            return HttpResponse('Method Not Allowed', status=405)
    except swiftException.ClientException as e:
        return HttpResponse('Please Contact Your Administrator', status=e.http_status, reason=e.http_reason)
    except Exception as e:
        return HttpResponse(e.message, status=500)


@csrf_exempt
def delete_obj(request, container):
    data = json.loads(request.body)
    delete_ids = data['deleted']
    added_array = data['added']
    py_dict = dict()
    if request.method == 'DELETE':
        if not request.session.get('storage_url') and not request.session.get('auth_token'):
                return HttpResponse('Please Contact your administrator', status=401, reason='Unauthorized:'
                                                                                            ' session data not found')
        try:
            storage_url = request.session.get('storage_url')
            auth_token = request.session.get('auth_token')
            saved = _save_confirm(added_array, storage_url, auth_token)
            py_dict['confirm_saved'] = saved
            if delete_ids:
                delete_dict = dict()
                for object_name in delete_ids:
                    header = client.head_object(storage_url, auth_token, container, object_name)
                    if header['x-object-meta-type'] == 'thumbnail':
                        belongs_to = header['x-object-meta-thumbof']
                        _set_headers(storage_url, auth_token, container, belongs_to, deleted=True)
                        _set_headers(storage_url, auth_token, container, object_name, deleted=True)
                        delete_dict[object_name] = {'thumbnail': object_name, 'original': belongs_to}
                    if header['x-object-meta-type'] == 'original':
                        belongs_to = header['x-object-meta-originalof']
                        _set_headers(storage_url, auth_token, container, belongs_to, deleted=True)
                        _set_headers(storage_url, auth_token, container, object_name, deleted=True)
                        delete_dict[object_name] = {'thumbnail': belongs_to, 'original': object_name}
                py_dict['deleted'] = delete_dict
            return JsonResponse(py_dict)
        except swiftException.ClientException as e:
            return HttpResponse('Please Contact Your Administrator', status=e.http_status, reason=e.http_reason)
    else:
        return HttpResponse('Method Not Allowed', status=405)


def _set_headers(storage_url, auth_token, container, object_name, deleted):
    copy = None
    header = client.head_object(storage_url, auth_token, container, object_name)
    new_header = {'X-Object-Meta-Deleted': deleted,
                  'X-Object-Meta-Format': header['x-object-meta-format'],
                  'X-Object-Meta-Resolution': header['x-object-meta-resolution'],
                  'X-Object-Meta-Name': header['x-object-meta-name'],
                  'X-Object-Meta-Type': header['x-object-meta-type']
                  }
    if header['x-object-meta-type'] == 'thumbnail':
        new_header['X-Object-Meta-Thumbof'] = header['x-object-meta-thumbof']
        copy = header['x-object-meta-thumbof']
    if header['x-object-meta-type'] == 'original':
        new_header['X-Object-Meta-Originalof'] = header['x-object-meta-originalof']
        copy = header['x-object-meta-originalof']
    client.post_object(storage_url, auth_token, container, object_name, headers=new_header)
    return copy


def _save_confirm(ids_array, storage_url, auth_token):
    confirm = []
    print ids_array
    for object_name in ids_array:
        copy_of = _set_headers(storage_url, auth_token, image_container, object_name, deleted=False)
        confirm.append(object_name)
        _set_headers(storage_url, auth_token, image_container, copy_of, deleted=False)
        confirm.append(copy_of)
    return confirm


def get_all(request, container):
    if request.method == 'GET':
        if not request.session.get('storage_url') and not request.session.get('auth_token'):
                return HttpResponse('Please Contact your administrator', status=401, reason='Unauthorized:'
                                                                                            ' session data not found')
        resp_dict = dict()
        storage_url = request.session.get('storage_url')
        auth_token = request.session.get('auth_token')
        data_container = client.get_container(storage_url, auth_token, container)
        for object in data_container[1]:
            if 'name' in object:
                meta_object = client.head_object(storage_url, auth_token, container, object['name'])
                if not meta_object['x-object-meta-deleted']:
                    if meta_object['x-object-meta-type'] == 'thumbnail':
                        if meta_object['x-object-meta-format'] not in resp_dict:
                            format = meta_object['x-object-meta-format']
                            resp_dict[format] = []
                        if meta_object['x-object-meta-format'] in resp_dict:
                            format = meta_object['x-object-meta-format']
                            id = object['name']
                            type= meta_object['x-object-meta-type']
                            resolution = meta_object['x-object-meta-resolution']
                            original = meta_object['x-object-meta-thumbof']
                            name = meta_object['x-object-meta-name']
                            new_obj = {'thumbnail_id': id,
                                       'name': name,
                                       'type': type,
                                       'resolution': resolution,
                                       'original_id': original}
                            resp_dict[format].append(new_obj)
                    else:
                        pass
        print resp_dict
        return JsonResponse(resp_dict)
    else:
        return HttpResponse('Method Not allowed', status=405)
