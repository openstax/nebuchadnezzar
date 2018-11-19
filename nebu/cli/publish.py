import os
import sys
import tempfile
import zipfile
from pathlib import Path

import click
import requests
from requests.auth import HTTPBasicAuth
from litezip import (
    parse_collection,
    parse_module,
    Collection,
    Resource,
)

from ._common import common_params, get_base_url, logger, calculate_sha1
from .validate import is_valid

def parse_book_tree(bookdir):
    """Converts filesystem booktree back to a struct"""
    struct = []
    for dirname, subdirs, filenames in os.walk(str(bookdir)):
        if 'collection.xml' in filenames:
            path = Path(dirname)
            struct.append((parse_collection(path), get_sha1s_dict(path)))
        elif 'index.cnxml' in filenames:
            path = Path(dirname)
            struct.append((parse_module(path), get_sha1s_dict(path)))

    return struct


def get_sha1s_dict(path):
    """Returns a dict of sha1-s by filename"""
    try:
        with (path / '.sha1sum').open('r') as sha_file:
            return {line.split('  ')[1].strip(): line.split('  ')[0].strip() for line in sha_file
                    if not line.startswith('#')}
    except FileNotFoundError:
        return {}

def filter_what_changed(contents):
    # NOTE: contents is the output from parse_book_tree
    #       which is a list of tuples (<collection or module>, <sha1-s dict>)
    changed = set()

    # remove the collection model from contents
    # collection_tuple = [contents.remove((model, sha1s_dict)) for model, sha1s_dict in contents if isinstance(model, Collection)][0]
    # for model, sha1s_dict in contents:
    #     if isinstance(model, Collection)
    collection, coll_sha1s_dict = contents.pop(0) # NOTE: requires the first item to be the collection
    # if isinstance(collection, Collection):

    # collection, coll_sha1 = collection_tuple
    for model, sha1s_dict in contents:
        # if isinstance(model, Collection):
            # continue # to next iteration
        # NOTE: model is a Module
        # calculate current sha1 of model.file
        # if calculate_sha1(model.file) != sha1s_dict.get(model.file.name.strip()):
        #     # assume model changed.
        #     changed.add(model)
        changed_module_resources = []
        for resource in model.resources:
            cached_sha1 = sha1s_dict.get(resource.filename.strip())
            # if resource HAS been modified,
            if '.sha1sum' != resource.filename and (cached_sha1 is None or resource.sha1 != cached_sha1):
                # keep it and assume model changed
                # changed.add(model)
                changed_module_resources.append(resource)

        if len(changed_module_resources) > 0 or calculate_sha1(model.file) != sha1s_dict.get(model.file.name.strip()):
            new_model = model._replace(resources = tuple(changed_module_resources))
            changed.add(new_model)

    # now check the Collection and the collection's resources!
    # so, if any of the collection's resource changed, assume collection changed.
    changed_collection_resources = []
    for resource in collection.resources:
        cached_sha1 = coll_sha1s_dict.get(resource.filename.strip())
        # if resource is new or it has changed
        if ('.sha1sum' != resource.filename) and (cached_sha1 is None or resource.sha1 != cached_sha1):
            # then the collection has changed.
            # keep the resource in the collection.
            changed_collection_resources.append(resource)
            # else: # otherwise the collection has not changed, and remove the resource from the collection.
            # v = list(collection.resources)
            # v.remove(resource)
            # collection.resources = tuple(v)

    changed = list(changed)

    new_collection = None
    if len(changed_collection_resources) > 0:
        new_collection = collection._replace(resources = tuple(changed_collection_resources))
        changed.insert(0, new_collection)


    # if any modules (or resources) changed, assume collection changed.
    if len(changed) > 0 or coll_sha1s_dict.get('collection.xml') is None or coll_sha1s_dict.get('collection.xml') != calculate_sha1(collection.file):
        if new_collection is None:
            new_collection = collection._replace(resources = tuple(changed_collection_resources))
            changed.insert(0, new_collection)
        else:
            changed.insert(0, collection)
        return changed
    else: # No changes! :D
        return []


# def find_cached_sha(filepath):
#     # Look for a 'dot' file in the same directory as file in filepath
#     dir_name = os.path.dirname(str(filepath))
#     dot_file_path = Path(dir_name) / '.sha1sum'

#     try:
#         with dot_file_path.open('r') as dotf:
#             # get the sha based on the filename
#             sha1_fname,  = [line.split('  ') for line in dotf][0]
#     # If one is found, get the sha1 for file in filepath
#             if sha1_fname[1] == filepath.name:
#                 return sha1_fname[0]
#             return None # no sha1 found / not listed
#     except FileNotFoundError:
#         # TODO: Should we create a log entry or terminal output?
#         return None


# def shas_by_filename(root_dir):
#     struct = {}
#     try:
#         with open('{}/**/.sha1sum'.format(root_dir), 'r') as files:
#             for sha_file in files:
#                 for line in sha_file:
#                     # struct = {{r['filename']: r for r in metadata['resources']}}
#                     struct[line.split('  ')[1]]
#         return struct
#     except FileNotFoundError:
#         return {}


def gen_zip_file(base_file_path, struct):
    # TODO Move this block of logic to litezip. Maybe?
    _, zip_file = tempfile.mkstemp()
    zip_file = Path(zip_file)

    with zipfile.ZipFile(str(zip_file), 'w') as zb:
        for model in struct:
            files = []
            # Write the content file into the zip.
            if isinstance(model, Collection):
                file = model.file
                full_path = base_file_path / file.name
                files.append((file, full_path))

                for resource in model.resources:
                    full_path = base_file_path / resource.filename
                    files.append((resource.data, full_path))
            else:  # Module
                file = model.file
                full_path = base_file_path / model.id / file.name
                files.append((file, full_path))

                for resource in model.resources:
                    full_path = base_file_path / model.id / resource.filename
                    files.append((resource.data, full_path))

            for file, full_path in files:
                zb.write(str(file), str(full_path))

    return zip_file


def _publish(base_url, struct, message, username, password):
    auth = HTTPBasicAuth(username, password)

    """Check for good credentials"""
    auth_ping_url = '{}/api/auth-ping'.format(base_url)
    auth_ping_resp = requests.post(auth_ping_url, auth=auth)

    if auth_ping_resp.status_code == 401:
        logger.debug('Temporary raw output...')
        logger.error('Bad credentials: \n{}'.format(auth_ping_resp.content))
        return False

    """Check for permission to publish"""
    publish_ping_url = '{}/api/publish-ping'.format(base_url)
    publish_ping_resp = requests.post(publish_ping_url, auth=auth)

    if publish_ping_resp.status_code == 401:
        logger.debug('Temporary raw output...')
        logger.error('Publishing not allowed: \n{}'.format(
            publish_ping_resp.content))
        return False

    """Publish the struct to a repository"""
    collection_id = struct[0].id
    # Base encapsulating directory within the zipfile
    base_file_path = Path(collection_id)

    # Zip it up!
    zip_file = gen_zip_file(base_file_path, struct)

    url = '{}/api/publish-litezip'.format(base_url)
    headers = {'X-API-Version': '3'}

    # FIXME We don't have nor want explicit setting of the publisher.
    #       The publisher will come through as part of the authentication
    #       information, which will be in a later implementation.
    #       For now, pull it out of a environment variable.
    data = {
        'publisher': os.environ.get('XXX_PUBLISHER', 'OpenStaxCollege'),
        'message': message,
    }
    files = {
        'file': ('contents.zip', zip_file.open('rb'),),
    }
    # Send it!
    resp = requests.post(url, data=data, files=files,
                         auth=auth, headers=headers)

    # Clean up!
    zip_file.unlink()

    # Process any response messages
    if resp.status_code == 200:
        # TODO Nicely format this stuff. Wait for the Bravado client
        #      implementation to work with models to make this work easier.
        logger.debug('Temporary raw output...')
        from pprint import pformat
        logger.info('Publishing response: \n{}'
                    .format(pformat(resp.json())))
    elif resp.status_code == 400:
        # This way be Errors
        # TODO Nicely format this stuff. Wait for the Bravado client
        #      implementation to work with models to make this work easier.
        logger.debug('Temporary raw output...')
        logger.error('ERROR: \n{}'.format(resp.content))
        return False
    else:  # pragma: no cover
        logger.error("unknown response:\n  status: {}\n  contents: {}"
                     .format(resp.status_code, resp.text))
        raise RuntimeError('unknown response, see output above')

    return True


@click.command()
@common_params
@click.argument('env')
@click.argument('content_dir',
                type=click.Path(exists=True, file_okay=False))
@click.option('-m', '--message', type=str,
              prompt='Publication message')
@click.option('-u', '--username', type=str, prompt=True)
@click.option('-p', '--password', type=str, prompt=True, hide_input=True)
@click.option('--skip-validation', is_flag=True)
@click.pass_context
def publish(ctx, env, content_dir, message, username, password,
            skip_validation):
    base_url = get_base_url(ctx, env)

    content_dir = Path(content_dir).resolve()
    struct = parse_book_tree(content_dir)

    struct = filter_what_changed(struct)

    if not skip_validation and not is_valid(struct):
        logger.info("We've got problems... :(")
        sys.exit(1)

    has_published = _publish(base_url, struct, message, username, password)
    if has_published:
        logger.info("Great work!!! =D")
    else:
        logger.info("Stop the Press!!! =()")
        sys.exit(1)
