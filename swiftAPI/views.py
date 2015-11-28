from django.http import HttpResponse, JsonResponse
import swiftclient.exceptions as swift_exception
from django.views.decorators.csrf import csrf_exempt
from swiftclient import client
from . import settings
import exceptions
import json
import Image
import uuid
import os

account_key = 'account'
username_key = 'user'
pass_key = 'passkey'
storage_URL_key = 'storage_url'
auth_token_key = 'auth_token'

del_after = 172800

image_container = 'Image'
video_container = 'Video'
audio_container = 'Audio'
miscellaneous_container = 'Miscellaneous'

thumbnail_size = (200, 200)


@csrf_exempt
def authenticate(request):
    """ Authenticating Swift user. Sets authentication credentials in cookies
    :param request: accepts JSON object containing account, user, password
    :returns Storage URL, Authentication Token"""

    try:
        if request.method == 'POST':
            request.session.flush()
            auth_data_dict = json.loads(request.body)
            (username, password) = auth_data_dict[account_key] + ':' + auth_data_dict[username_key], auth_data_dict[
                pass_key]
            auth_url = settings.SWIFT_AUTH_URL
            (storage_url, auth_token) = client.get_auth(auth_url, username, password)
            print '======================================================='
            print "storageURL: ", storage_url, "\nauth token: ", auth_token
            print '======================================================='
            Nstorage_url = settings.BASE_URL + storage_url.split(':8080')[1]
            request.session['auth_token'], request.session['storage_url'], request.session['username'] \
                = auth_token, Nstorage_url, username
            return JsonResponse({'username': username, 'auth_token': auth_token, 'storage_url': Nstorage_url})
        else:
            return HttpResponse('Method Not Allowed', status=405)
    except swift_exception.ClientException as e:
        print e
        return HttpResponse(e.message, status=500)
    except exceptions.KeyError as e:
        print e
        return HttpResponse('JSON object key error: ' + str(e), status=400)
    except exceptions.ValueError:
        print 'No JSON FOUND'
        return HttpResponse('No JSON object found', status=400)
    except Exception as e:
        print e
        return HttpResponse(e, status=500)


@csrf_exempt
def upload(request):
    """ Uploads file/s to swift and its thumbnail as seperate object.
        file/s  will be deleted after a specified time
        each file-object is stored against a unique key generated.
        Sets required metadata in object header.
    :param request: multiple/single file object, Unique key value/s
            (file will be recognized by that unique key).
    :return: original image ID, thumbnail image ID of all files uploaded"""

    try:
        if request.method == 'POST':
            if not request.session.get('storage_url') and not request.session.get('auth_token'):
                return HttpResponse('Please Contact your administrator',
                                    status=401, reason='Unauthorized: session data not found')
            if not request.FILES:
                return HttpResponse('No file/s found to save', status=400)
            for filename, accepted_file in request.FILES.iteritems():
                try:
                    temp_name, response_dict, original_name, uid = '', {}, request.FILES[filename].name, request.POST[filename]
                    file_type, file_ext = accepted_file.content_type.split('/')
                    storage_url, auth_token = _get_auth_data(request.session)
                    with open('temp', 'w+') as f:
                        f.writelines(accepted_file.readlines())
                    if file_type == 'image':
                        temp_name = 'file.thumbnail.' + file_ext
                        try:
                            im = Image.open('temp')
                            size, im_type, id_image, id_thumb = im.size, im.format, uuid.uuid1(), uuid.uuid1()
                            main_header = _make_header(False, im_type, original_name, size, 'original', id_thumb)
                            with open('temp', 'r+') as f:
                                client.put_object(storage_url, auth_token, image_container, str(id_image), f,
                                                  headers=main_header)
                            im.thumbnail(thumbnail_size, Image.ANTIALIAS)
                            im.save(temp_name)
                            thumb_header = _make_header(False, im_type, original_name, size, 'thumbnail', id_image)
                            with open(temp_name, 'r') as f:
                                client.put_object(storage_url, auth_token, image_container, str(id_thumb),
                                                  f, headers=thumb_header)
                            response_dict[uid] = {'image_key': str(id_image), 'thumb_key': str(id_thumb)}
                        except IOError:
                            response_dict[uid] = {'error': 'invalid file'}
                finally:
                    if os.path.exists(temp_name):
                        os.remove(temp_name)
                    if os.path.exists('temp'):
                        os.remove('temp')
            return JsonResponse(response_dict)
        else:
            return HttpResponse('Method Not Allowed', status=405)
    except swift_exception.ClientException as e:
        message = str(e.message) + ', Please contact your administrator'
        print e
        return HttpResponse(message, status=401)
    except Exception as e:
        print e
        return HttpResponse(e.message, status=500)


def get_obj(request, container, object_name):
    """Download an object from Swift
    :param container: container of swift where object is stored
    :param object_name: ID of object
    :return: object bytestream
    """
    try:
        if request.method == 'GET':
            if not request.session.get('storage_url') and not request.session.get('auth_token'):
                return HttpResponse('Please Contact your administrator',
                                    status=401, reason='Unauthorized: session data not found')
            storage_url, auth_token = _get_auth_data(request.session)
            obj_headers, obj = client.get_object(storage_url, auth_token, container, object_name)
            return HttpResponse(obj)
        else:
            return HttpResponse('Method Not Allowed', status=405)
    except swift_exception.ClientException as e:
        print e
        return HttpResponse('Please Contact Your Administrator', status=e.http_status)
    except Exception as e:
        print e
        return HttpResponse(e.message, status=500)


def get_all(request, container):
    """ Returns List of all Objects present in specified container
    :param container: Name of Swift Container
    :return: meta data and id's of all the objects
    """
    try:
        if request.method == 'GET':
            if not request.session.get('storage_url') and not request.session.get('auth_token'):
                return HttpResponse('Please Contact your administrator',
                                    status=401, reason='Unauthorized: session data not found')
            response_dict = dict()
            storage_url, auth_token = _get_auth_data(request.session)
            data_container = client.get_container(storage_url, auth_token, container)
            for object in data_container[1]:
                if 'name' in object:
                    meta_object = client.head_object(storage_url, auth_token, container, object['name'])
                    if not meta_object['x-object-meta-deleted']:
                        if meta_object['x-object-meta-type'] == 'thumbnail':
                            if meta_object['x-object-meta-format'] not in response_dict:
                                format = meta_object['x-object-meta-format']
                                response_dict[format] = []
                            if meta_object['x-object-meta-format'] in response_dict:
                                format = meta_object['x-object-meta-format']
                                id = object['name']
                                type = meta_object['x-object-meta-type']
                                resolution = meta_object['x-object-meta-resolution']
                                original = meta_object['x-object-meta-thumbof']
                                name = meta_object['x-object-meta-name']
                                new_obj = {'thumbnail_id': id, 'name': name, 'type': type, 'resolution': resolution,
                                           'original_id': original}
                                response_dict[format].append(new_obj)
                        else:
                            pass
            print response_dict
            return JsonResponse(response_dict)
        else:
            return HttpResponse('Method Not allowed', status=405)
    except exceptions.Exception as e:
        print e
        return HttpResponse('Please contact your admininstrator', status=e.http_status)
    except Exception as e:
        print e
        return HttpResponse('Please contact your admininstrator', status=500)


@csrf_exempt
def confirm(request, container):
    """In metaData makes deleted: true and
        Removes "remove-after" field from MetaData.
    :param request: array of ids to be deleted, array of ids to confirm save
    :param container:  Swift Container where object/s is stored
    :return: Success
    """
    try:
        print request.body
        if request.method == 'POST':
            if not request.session.get('storage_url') and not request.session.get('auth_token'):
                return HttpResponse('Please Contact your administrator', status=401,
                                    reason='Unauthorized: session data not found')
            storage_url, auth_token = _get_auth_data(request.session)
            data = json.loads(request.body)
            confirm_delete_list = data['deleted']
            confirm_save_list = data['added']
            response_dict = dict()
            if confirm_delete_list:
                deleted_response = _confirm_delete(confirm_delete_list, container, storage_url, auth_token)
                response_dict["deleted"] = deleted_response
            if confirm_save_list:
                added_response = _confirm_save(confirm_save_list, container, storage_url, auth_token)
                response_dict["added"] = added_response
            return JsonResponse(response_dict)
        else:
            return HttpResponse('Method Not Allowed', status=405)
    except Exception as e:
        print e
        return HttpResponse("Please Contact your administrator", status=e.http_status)


def _get_auth_data(session):
    return session.get(storage_URL_key), session.get(auth_token_key)


def _make_header(deleted, form, name, res, type, copy_of_id):

    header = {'X-Object-Meta-Deleted': deleted,
              'X-Object-Meta-Format': form,
              'X-Object-Meta-Name': name,
              'X-Object-Meta-Resolution': res,
              'X-Delete-After': del_after,
              'X-Object-Meta-Type': type}
    if type is 'thumbnail':
        header['X-Object-Meta-Thumbof'] = copy_of_id
    if type is 'original':
        header['X-Object-Meta-Originalof'] = copy_of_id
    return header


def _confirm_save(list_id, container, storage_url, auth_token):
    try:
        saved_list = []
        for sid in list_id:
            copy_of = _set_headers(storage_url, auth_token, container, sid, deleted=False)
            saved_list.append(sid)
            _set_headers(storage_url, auth_token, container, copy_of, deleted=False)
            saved_list.append(copy_of)
        return saved_list
    except Exception as e:
        raise e


def _confirm_delete(list_id, container, storage_url, auth_token):
    try:
        deleted_list = []
        for sid in list_id:
            copy_of = _set_headers(storage_url, auth_token, container, sid, deleted=True)
            deleted_list.append(sid)
            _set_headers(storage_url, auth_token, container, copy_of, deleted=True)
            deleted_list.append(copy_of)
        return deleted_list
    except Exception as e:
        raise e


def _set_headers(storage_url, auth_token, container, object_name, deleted):
    try:
        header = client.head_object(storage_url, auth_token, container, object_name)
        new_header = {'X-Object-Meta-Deleted': deleted,
                      'X-Object-Meta-Format': header['x-object-meta-format'],
                      'X-Object-Meta-Resolution': header['x-object-meta-resolution'],
                      'X-Object-Meta-Name': header['x-object-meta-name'],
                      'X-Object-Meta-Type': header['x-object-meta-type']
                      }
        copy_of = None
        if header['x-object-meta-type'] == 'thumbnail':
            new_header['X-Object-Meta-Thumbof'] = header['x-object-meta-thumbof']
            copy_of = header['x-object-meta-thumbof']
        if header['x-object-meta-type'] == 'original':
            new_header['X-Object-Meta-Originalof'] = header['x-object-meta-originalof']
            copy_of = header['x-object-meta-originalof']
        client.post_object(storage_url, auth_token, container, object_name, headers=new_header)
        return copy_of
    except swift_exception.ClientException as e:
        raise e
    except Exception as e:
        raise e
