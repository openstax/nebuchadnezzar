import os
from pathlib import Path
from collections import namedtuple

import cnxepub
from lxml import etree
from cnxepub.models import Binder, TranslucentBinder, Document
from cnxepub.formatters import SingleHTMLFormatter
from litezip.main import COLLECTION_NSMAP

from .logger import logger


__all__ = (
    'assemble',
)

Module = namedtuple('Module', 'id, path')


"""`Document`s require that modules contain a body tag, but this assembler
allows for building a single/collection HTML with empty modules, therefore
we must use this variable in place of data when building `Document` models.
When updating this also update the tests.
"""
DATA_WHEN_MODULE_NOT_FOUND = "<body style='color: red;'>Module with id {} "\
                             "goes here.</body>"


def assemble(source_dir='.'):
    """Assembles module HTML files into one HTML file using a collxml file
    to define their order.
    """
    collxml_path = find_collxml(source_dir)
    OUT_DIR = collxml_path.parent
    binder = collxml_to_binder(collxml_path.open('rb'))
    documents = list(cnxepub.flatten_to_documents(binder))

    modules_struct = find_modules(source_dir)

    # Update the documents' content
    update_content(documents, source_dir, modules_struct)
    # Rewrite the documents' URIs to point to where they're stored locally
    fix_uri(documents, OUT_DIR, modules_struct)

    with (OUT_DIR / 'collection.xhtml').open('w') as f:
        f.write(str(SingleHTMLFormatter(binder)))

###############################################################################
# internal functions
###############################################################################


def collxml_to_binder(collxml):
    tags = [
        '{http://cnx.rice.edu/collxml}subcollection',
        '{http://cnx.rice.edu/collxml}collection',
        '{http://cnx.rice.edu/collxml}module',
        '{http://cnx.rice.edu/mdml}title',
    ]

    events = etree.iterparse(collxml, events=('start', 'end'),
                             tag=tags, remove_blank_text=True)

    adapters_tree = build_adapters_tree(events)

    binder = adapters_tree.to_model()
    return binder


def find_collxml(source_dir):
    for root, dirs, files in os.walk(str(source_dir)):
        if 'collection.xml' in files:
            return Path(root) / 'collection.xml'


def find_modules(source_dir):
    struct = dict()
    for directory, subdirs, filenames in os.walk(str(source_dir)):
        if 'index.cnxml.html' in filenames:
            module_id = parse_module_id(Path(directory) / 'index.cnxml')
            path = Path(directory) / 'index.cnxml.html'
            module = Module(module_id, path)

            struct[module_id] = module
    return struct


class AdapterNode(object):
    def __init__(self, tag, attrib, title=''):
        self.tag = tag
        self.attrib = dict(attrib).copy()
        self.title = title
        self.parent = self
        self.children = []

    def insert(self, child):
        child.parent = self
        self.children.append(child)
        return self

    def to_model(self):
        ch_models = [child.to_model() for child in self.children]
        meta = {'title': self.title}

        if self.tag == 'collection':
            return Binder(self.title, nodes=ch_models, metadata=meta)
        elif self.tag == 'subcollection':
            return TranslucentBinder(nodes=ch_models, metadata=meta)
        elif self.tag == 'module':
            module_id = self.attrib.get('document')
            meta['license_url'] = None  # required by `Document`
            data = ''  # document content is populated in later steps
            return Document(module_id, data, metadata=meta)
        else:
            raise Exception('unrecognized tag: {}'.format(self.tag))


def build_adapters_tree(events):
    """Build adapters because Binders require bottom-up construction
    (sub-binders are passed into the constructor), so we'll (1) parse
    the element tree top-down and store the needed information in adapter
    nodes and then (2) use post-order traversal on the adapters tree to
    construct Binders from their sub-binders.
    """
    node = None  # the node currently being parsed

    for event, element in events:
        tag = element.tag.split('}')[-1]  # tag without namespace

        if tag == 'title':
            assert node  # adapter w/ 'collection' tag should already exist
            node.title = element.text

        elif event == 'start':
            new_ = AdapterNode(tag, element.attrib)
            if node:
                node.insert(new_)
            node = new_

        elif event == 'end':
            node = node.parent

    # After the last `end` event is processed, `node` is the root node
    root_node = node
    return root_node


def parse_module_id(index_cnxml_path):
    """Given a cnxml file (aka. "a module"), parse its ID from the metadata.
    """
    with index_cnxml_path.open('rb') as f:
        cnxml = etree.parse(f)
    content_id = cnxml.xpath('//md:content-id', namespaces=COLLECTION_NSMAP)
    if not content_id:
        raise Exception('module id not found in {}'.format(index_cnxml_path))
    return content_id[0].text


def update_content(documents, source_dir, modules_struct):
    for document in documents:
        module = get_module_by_id(document.id, modules_struct)

        if module:
            with module.path.open('rb') as f:
                document.content = f.read()
        else:
            document.content = DATA_WHEN_MODULE_NOT_FOUND.format(document.id)
            # TODO: raise an exception or track how many found?


def fix_uri(documents, out_dir, modules_struct):
    """ Rewrite references for internal resources to point to the correct
    path in different module directories.
    """
    for document in documents:
        for ref in document.references:
            if ref.remote_type == cnxepub.INTERNAL_REFERENCE_TYPE and \
                    not ref.uri.startswith('#'):
                r_name = Path(ref.uri).name
                module = get_module_by_id(document.id, modules_struct)
                if list(module.path.parent.glob(r_name)):
                    # only rewrite the uri if the file is found in the module
                    # directory
                    ref.uri = str((module.path.parent / r_name)
                                  .relative_to(out_dir))


def get_module_by_id(id, modules_struct):
    try:
        module = modules_struct[id]
    except KeyError:
        module = None
        logger.warning('WARNING: Module {} not found'.format(id))
    return module
