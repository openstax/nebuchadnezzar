import os
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

import click
from litezip import (
    parse_collection,
    parse_module
)

from ._common import common_params


@click.command()
@common_params
@click.argument('task_file_path',
                type=click.Path(exists=True, dir_okay=False))
@click.argument('content_dir',
                type=click.Path(exists=True, file_okay=False))
@click.argument('task_args', nargs=-1)
@click.pass_context
def content_task(ctx, task_file_path, content_dir, task_args):
    task_spec = spec_from_file_location('content_task', task_file_path)
    task_module = module_from_spec(task_spec)
    task_spec.loader.exec_module(task_module)

    def noop(*args, **kwargs):
        pass

    collection_action = (task_module.with_collection
                         if hasattr(task_module, 'with_collection')
                         else noop)
    module_action = (task_module.with_module
                     if hasattr(task_module, 'with_module')
                     else noop)

    def to_str_dict(collection_or_module):
        return {
            'id': str(collection_or_module.id),
            'file': str(collection_or_module.file),
            'resources': list(map(
                lambda resource: str(resource.data),
                collection_or_module.resources
            ))
        }

    content_dir = Path(content_dir).resolve()
    ex = [lambda filepath: '.sha1sum' in filepath.name]
    for dirname, subdirs, filenames in os.walk(str(content_dir)):
        path = Path(dirname)
        if 'collection.xml' in filenames:
            collection = parse_collection(path, excludes=ex)
            action_params = to_str_dict(collection)
            collection_action(**action_params, args=task_args)
        elif 'index.cnxml' in filenames:
            module = parse_module(path, excludes=ex)
            action_params = to_str_dict(module)
            module_action(**action_params, args=task_args)
