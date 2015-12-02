
from rest_framework.decorators import api_view, parser_classes, renderer_classes
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from imageParse import JPEGRenderer
import swiftclient.exceptions as swift_exception
from swiftclient import client
from . import settings
import exceptions
import json
import Image
import uuid
import os
# import pdb

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


@api_view(['POST'])
@parser_classes((JSONParser,))
def authenticate(request):
    """ Authenticating Swift user. Sets authentication credentials in cookies
    :param request: accepts JSON object containing account, user, password
    :returns Storage URL, Authentication Token"""

    try:
        request.session.flush()
        auth_data_dict = request.data
        (username, password) = auth_data_dict[account_key] + ':' + auth_data_dict[username_key], auth_data_dict[
            pass_key]
        auth_url = settings.SWIFT_AUTH_URL
        (storage_url, auth_token) = client.get_auth(auth_url, username, password)
        storage_url = settings.BASE_URL + storage_url.split(':8080')[1]                                      #JUGAAD
        request.session['auth_token'], request.session['storage_url'], request.session['username'] \
            = auth_token, storage_url, username
        return Response({'username': username, 'auth_token': auth_token, 'storage_url': storage_url},
                        status=status.HTTP_200_OK)
    except swift_exception.ClientException as e:
        print e
        return Response(e.message, status=status.HTTP_501_NOT_IMPLEMENTED)
    except exceptions.KeyError as e:
        print e
        return Response('JSON object key error: ' + str(e), status=status.HTTP_400_BAD_REQUEST)
    except exceptions.ValueError:
        print 'No JSON FOUND'
        return Response('No JSON object found', status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print e
        return Response(e, status=status.HTTP_501_NOT_IMPLEMENTED)


# @api_view(['POST'])
# @parser_classes((MultiPartParser, FormParser))
# def upload(request):
#     new_data = dict(request.data.iterlists())
#     print new_data
#     for filename, a_file in new_data.iteritems():
#         print a_file

@api_view(['POST'])
@parser_classes((MultiPartParser, FormParser))
def upload(request):
    """ Uploads file/s to swift and its thumbnail as seperate object.
        file/s  will be deleted after a specified time
        each file-object is stored against a unique key generated.
        Sets required metadata in object header.
    :param request: multiple/single file object, Unique key value/s
            (file will be recognized by that unique key).
    :return: original image ID, thumbnail image ID of all files uploaded"""

    try:
        if not request.FILES:
            return Response('No file/s found to save', status=status.HTTP_400_BAD_REQUEST)
        new_data = dict(request.data.iterlists())
        response_dict = dict()
        for filename, a_file in new_data.iteritems():
            try:
                uid, accepted_file = a_file
                print uid
                original_name = accepted_file.name
                file_type, file_ext = accepted_file.content_type.split('/')
                storage_url, auth_token = _get_auth_data(request.session)
                with open('temp', 'w+') as f:
                    f.writelines(accepted_file.readlines())
                if file_type == 'image':
                    temp_name = 'file.thumbnail.jpeg'
                    try:
                        im = Image.open('temp')
                        size = im.size
                        if size < (200, 200):
                            _small_file_to_swift(im, size, original_name, uid, storage_url, auth_token, response_dict)
                        else:
                            _normal_file_to_swift(im, size, original_name, uid, temp_name, storage_url,
                                                  auth_token, response_dict)
                            print response_dict
                    except IOError:
                        response_dict[uid] = {'error': 'invalid file'}
            finally:
                if os.path.exists(temp_name):
                    os.remove(temp_name)
                if os.path.exists('temp'):
                    os.remove('temp')
        print response_dict
        return Response(response_dict, status=status.HTTP_200_OK)
    except swift_exception.ClientException as e:
        message = str(e.message) + ', Please contact your administrator'
        print e
        return Response(message, status=status.HTTP_501_NOT_IMPLEMENTED)
    except Exception as e:
        print e
        return Response(e.message, status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['GET'])
@renderer_classes((JPEGRenderer,))
def get_obj(request, container, object_name):
    """Download an object from Swift
    :param container: container of swift where object is stored
    :param object_name: ID of object
    :return: object bytestream
    """
    try:
        if not request.session.get('storage_url') and not request.session.get('auth_token'):
            return Response('Please Contact your administrator', status=status.HTTP_401_UNAUTHORIZED)
        storage_url, auth_token = _get_auth_data(request.session)
        obj_headers, obj = client.get_object(storage_url, auth_token, container, object_name)
        return Response(obj)
    except swift_exception.ClientException as e:
        print e
        return Response('Please Contact Your Administrator', status=status.HTTP_501_NOT_IMPLEMENTED)
    except Exception as e:
        print e
        return Response(e.message, status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['GET'])
@parser_classes((JSONParser,))
def get_all(request, container):
    """ Returns List of all Objects present in specified container
    :param container: Name of Swift Container
    :return: meta data and id's of all the objects
    """
    try:
        response_dict = dict()
        storage_url, auth_token = _get_auth_data(request.session)
        data_container = client.get_container(storage_url, auth_token, container)
        for obj in data_container[1]:
            meta_object = client.head_object(storage_url, auth_token, container, obj['name'])
            if not meta_object['x-object-meta-deleted']:
                if meta_object['x-object-meta-type'] in ['thumbnail', 'original-thumbnail']:
                    if meta_object['x-object-meta-format'] not in response_dict:
                        form = meta_object['x-object-meta-format']
                        response_dict[form] = []
                    if meta_object['x-object-meta-format'] in response_dict:
                        new_obj = {'thumbnail_id': obj['name'],
                                   'name': meta_object['x-object-meta-name'],
                                   'type': meta_object['x-object-meta-type'],
                                   'resolution': meta_object['x-object-meta-resolution']}
                        if meta_object['x-object-meta-format'] is 'thumbnail':
                            new_obj['original_id'] = meta_object['x-object-meta-original']
                        response_dict[form].append(new_obj)
        return Response(response_dict)
    except swift_exception.ClientException as e:
        print e
        return Response('Please contact your admininstrator', status=status.HTTP_501_NOT_IMPLEMENTED)
    except Exception as e:
        print e
        return Response('Please contact your admininstrator', status=status.HTTP_501_NOT_IMPLEMENTED)


@api_view(['POST'])
@parser_classes((JSONParser,))
def confirm(request, container):
    """In metaData makes deleted: true and
        Removes "remove-after" field from MetaData.
    :param request: array of ids to be deleted, array of ids to confirm save
    :param container:  Swift Container where object/s is stored
    :return: Success
    """
    try:
        storage_url, auth_token = _get_auth_data(request.session)
        data = json.loads(request.body)
        confirm_delete_list = data['deleted']
        confirm_save_list = data['added']
        response_dict = dict()
        if confirm_delete_list:
            deleted_response = _confirm(confirm_delete_list, container, storage_url, auth_token, deleted=True)
            response_dict["deleted"] = deleted_response
        if confirm_save_list:
            added_response = _confirm(confirm_save_list, container, storage_url, auth_token, deleted=True)
            response_dict["added"] = added_response
        return Response(response_dict)
    except Exception as e:
        print e
        return Response("Please Contact your administrator", status=status.HTTP_501_NOT_IMPLEMENTED)


def _get_auth_data(session):
    if not session.get('storage_url') and not session.get('auth_token'):
        raise ValueError('Unauthorized: session data not found', status=401)
    else:
        return session.get(storage_URL_key), session.get(auth_token_key)


def _small_file_to_swift(im, size, original_name, uid, storage_url, auth_token, response_dict):
    id_image = uuid.uuid1()
    im_type = im.format
    main_header = _make_header(False, im_type, original_name, size, 'original-thumbnail', None)
    with open('temp', 'r+') as f:
        client.put_object(storage_url, auth_token, image_container, str(id_image), f, headers=main_header)
    response_dict[uid] = {'original-thumb-key': id_image}
    return


def _normal_file_to_swift(im, size, original_name, uid, temp_name, storage_url, auth_token, response_dict):
    id_image, id_thumb = uuid.uuid1(), uuid.uuid1()
    im_type = im.format
    main_header = _make_header(False, im_type, original_name, size, 'original', id_thumb)
    with open('temp', 'r+') as f:
        client.put_object(storage_url, auth_token, image_container, str(id_image), f, headers=main_header)
    im.thumbnail(thumbnail_size, Image.ANTIALIAS)
    im.save(temp_name, 'JPEG')
    thumb_header = _make_header(False, im_type, original_name, size, 'thumbnail', id_image)
    with open(temp_name, 'r') as f:
        client.put_object(storage_url, auth_token, image_container, str(id_thumb), f, headers=thumb_header)
    response_dict[uid] = {'image_key': str(id_image), 'thumb_key': str(id_thumb)}



def _make_header(deleted, form, name, res, type_ext, copy_of_id):

    header = {'X-Object-Meta-Deleted': deleted,
              'X-Object-Meta-Format': form,
              'X-Object-Meta-Name': name,
              'X-Object-Meta-Resolution': res,
              'X-Delete-After': del_after,
              'X-Object-Meta-Type': type_ext}
    if type_ext is 'thumbnail':
        header['X-Object-Meta-Original'] = copy_of_id
    if type_ext is 'original':
        header['X-Object-Meta-Thumb'] = copy_of_id
    return header


def _confirm(list_id, container, storage_url, auth_token, deleted):
    try:
        for sid in list_id:
            copy_of = _set_headers(storage_url, auth_token, container, sid, deleted=deleted)
            if copy_of:
                _set_headers(storage_url, auth_token, container, copy_of, deleted=deleted)
        return "SUCCESS"
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
            new_header['X-Object-Meta-Original'] = header['x-object-meta-original']
            copy_of = header['x-object-meta-original']
        if header['x-object-meta-type'] == 'original':
            new_header['X-Object-Meta-Thumb'] = header['x-object-meta-thumb']
            copy_of = header['x-object-meta-thumb']
        client.post_object(storage_url, auth_token, container, object_name, headers=new_header)
        return copy_of
    except swift_exception.ClientException as e:
        raise e
    except Exception as e:
        raise e
