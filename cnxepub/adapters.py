# -*- coding: utf-8 -*-
# ###
# Copyright (c) 2013, Rice University
# This software is subject to the provisions of the GNU Affero General
# Public License version 3 (AGPLv3).
# See LICENCE.txt for details.
# ###
import os
import io
import mimetypes
from copy import deepcopy

import jinja2
from lxml import etree

from .epub import EPUB, Package, Item
from .models import (
    model_to_tree, flatten_model,
    Binder, TranslucentBinder,
    Document, Resource,
    TRANSLUCENT_BINDER_ID,
    INTERNAL_REFERENCE_TYPE,
    )
from .html_parsers import parse_metadata, parse_navigation_html_to_tree


__all__ = (
    'adapt_package', 'adapt_item',
    'BinderItem',
    'DocumentItem',
    )


def adapt_package(package):
    """Adapts ``.epub.Package`` to a ``BinderItem`` and cascades
    the adaptation downward to ``DocumentItem``
    and ``ResourceItem``.
    The results of this process provide the same interface as
    ``.models.Binder``, ``.models.Document`` and ``.models.Resource``.
    """
    navigation_item = package.navigation
    html = etree.parse(navigation_item.data)
    tree = parse_navigation_html_to_tree(html, navigation_item.name)
    return _node_to_model(tree, package)


def adapt_item(item, package):
    """Adapts ``.epub.Item`` to a ``DocumentItem``.

    """
    if item.media_type == 'application/xhtml+xml':
        model = DocumentItem(item, package)
    else:
        model = Resource(item.name, item.data, item.media_type, item.name)
    return model


def make_epub(binders, file):
    """Creates an EPUB file from a binder(s)."""
    if not isinstance(binders, (list, set, tuple,)):
        binders = [binders]
    epub = EPUB([_make_package(binder) for binder in binders])
    epub.to_file(epub, file)


def make_publication_epub(binders, publisher, publication_message, file):
    """Creates an epub file from a binder(s). Also requires
    publication information, meant to be used in a EPUB publication
    request.
    """
    if not isinstance(binders, (list, set, tuple,)):
        binders = [binders]
    for binder in binders:
        binder = deepcopy(binder)
        binder.metadata.update({'publisher': publisher,
                                'publication_message': publication_message})
        epub = EPUB([_make_package(binder) for binder in binders])
        EPUB.to_file(epub, file)


def _make_package(binder):
    """Makes an ``.epub.Package`` from a  Binder'ish instance."""
    package_id = binder.id
    if package_id is None:
        package_id = hash(binder)

    package_name = "{}.opf".format(package_id)

    extensions = {}
    # Set model identifier file extensions.
    for model in flatten_model(binder):
        if isinstance(model, (Binder, TranslucentBinder,)):
            continue
        ext = mimetypes.guess_extension(model.media_type, strict=False)
        if ext is None:
            raise ValueError("Can't apply an extension to media-type '{}'." \
                             .format(modle.media_type))
        extensions[model.id] = ext

    template = jinja2.Template(HTML_DOCUMENT,
                               trim_blocks=True, lstrip_blocks=True)
    # Build the package item list.
    items = []
    # Build the binder as an item, specifically a navigation item.
    navigation_content =  tree_to_html(model_to_tree(binder))
    navigation_document = template.render(metadata=binder.metadata,
                                          content=navigation_content,
                                          is_translucent=binder.is_translucent)
    navigation_document_name = "{}.xhtml".format(package_id)
    item = Item(str(navigation_document_name),
                io.BytesIO(navigation_document.encode('utf-8')),
                'application/xhtml+xml', is_navigation=True, properties=['nav'])
    items.append(item)
    resources = {}
    # Roll through the model list again, making each one an item.
    for model in flatten_model(binder):
        if isinstance(model, (Binder, TranslucentBinder,)):
            continue
        for resource in model.resources:
            resources[resource.id] = resource
            item = Item(resource.id,
                    resource.data, resource.media_type)
            items.append(item)
        for reference in model.references:
            if reference.remote_type == INTERNAL_REFERENCE_TYPE:
                filename = os.path.basename(reference.uri)
                resource = resources.get(filename)
                if resource:
                    reference.bind(resource, '../resources/{}')

        complete_content = template.render(metadata=model.metadata,
                                           content=model.content)
        item = Item(''.join([model.ident_hash, extensions[model.id]]),
                    io.BytesIO(complete_content.encode('utf-8')),
                    model.media_type)
        items.append(item)

    # Build the package.
    package = Package(package_name, items, binder.metadata)
    return package


def _make_item(model):
    """Makes an ``.epub.Item`` from
    a ``.models.Document`` or ``.models.Resource``
    """
    item = Item(model.id, model.content, model.media_type)


def _node_to_model(tree_or_item, package, parent=None,
                   lucent_id=TRANSLUCENT_BINDER_ID):
    """Given a tree, parse to a set of models"""
    if 'contents' in tree_or_item:
        # It is a binder.
        tree = tree_or_item
        if tree['id'] == lucent_id:
            binder = TranslucentBinder(metadata={'title': tree['title']})
        else:
            package_item = package.grab_by_name(tree['id'])
            binder = BinderItem(package_item, package)
        for item in tree['contents']:
            node = _node_to_model(item, package, parent=binder,
                                  lucent_id=lucent_id)
            if node.metadata['title'] != item['title']:
                binder.set_title_for_node(node, item['title'])
        result = binder
    else:
        # It is a document.
        item = tree_or_item
        package_item = package.grab_by_name(item['id'])
        result = adapt_item(package_item, package)
    if parent is not None:
        parent.append(result)
    return result


def _id_from_metadata(metadata):
    """Given an item's metadata, discover the id."""
    # FIXME Where does the system identifier come from?
    system = 'cnx-archive'
    identifier = "{}-uri".format(system)
    if identifier in metadata:
        id = metadata[identifier]
    else:
        id = None
    return id


class BinderItem(Binder):

    def __init__(self, item, package):
        self._item = item
        self._package = package
        html = etree.parse(self._item.data)
        metadata = parse_metadata(html)
        id = _id_from_metadata(metadata)
        super(BinderItem, self).__init__(id, metadata=metadata)


class DocumentItem(Document):

    def __init__(self, item, package):
        self._item = item
        self._package = package
        self._html = etree.parse(self._item.data)

        metadata = parse_metadata(self._html)
        content_xpath = "//xhtml:body/node()[not(self::node()[@data-type='metadata'])]"
        nsmap = {'xhtml': "http://www.w3.org/1999/xhtml"}

        content = io.BytesIO(
            b''.join([isinstance(n, str) and n.encode('utf-8') or etree.tostring(n)
                      for n in self._html.xpath(content_xpath, namespaces=nsmap)]))
        id = _id_from_metadata(metadata)
        resources = None
        super(DocumentItem, self).__init__(id, content, metadata)

        # Based on the reference list, make a best effort
        # to acquire resources.
        resources = []
        for ref in self.references:
            if ref.remote_type == 'external':
                continue
            elif not ref.uri.find('../resources') >= 0:
                continue
            name = os.path.basename(ref.uri)
            try:
                resource = adapt_item(package.grab_by_name(name), package)
                ref.bind(resource, '../resources/{}')
                resources.append(resource)
            except KeyError:
                # When resources are missing, the problem is pushed off
                # to the rendering process, which will
                # raise a missing reference exception when necessary.
                pass
        self.resources = resources


# XXX Rendering shouldn't happen here.
#     Temporarily place the rendering templates and code here.

HTML_DOCUMENT = """\
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
      xmlns:dc="http://purl.org/dc/elements/1.1/"
      xmlns:lrmi="http://lrmi.net/the-specification"
      >
  <head itemscope="itemscope"
        itemtype="http://schema.org/Book"
        >

    <title>{{ metadata['title'] }}</title>
    <meta itemprop="inLanguage"
          data-type="language"
          content="{{ metadata['language'] }}"
          />

    {# TODO Include this based on the feature being present #}
    <!-- These are for discoverability of accessible content. -->
    <meta itemprop="accessibilityFeature" content="MathML" />
    <meta itemprop="accessibilityFeature" content="LaTeX" />
    <meta itemprop="accessibilityFeature" content="alternativeText" />
    <meta itemprop="accessibilityFeature" content="captions" />
    <meta itemprop="accessibilityFeature" content="structuredNavigation" />

    {# TODO
       <meta refines="#<html-id>" property="display-seq" content="<ord>" />
     #}

    <meta itemprop="dateCreated"
          content="{{ metadata['created'] }}"
          />
    <meta itemprop="dateModified"
          content="{{ metadata['revised'] }}"
          />
  </head>
  <body xmlns:bib="http://bibtexml.sf.net/"
        xmlns:data="http://dev.w3.org/html5/spec/#custom"
        itemscope="itemscope"
        itemtype="http://schema.org/Book"
        >
    <div data-type="metadata">
      <h1 data-type="title" itemprop="name">{{ metadata['title'] }}</h1>
      {% if is_translucent %}
      <span data-type="binding" data-value="translucent" />
      {%- endif %}

      <div class="authors">
        By: 
        {% for author in metadata['authors'] -%}
        <span id="author01"
              itemscope="itemscope"
              itemtype="http://schema.org/Person"
              itemprop="author"
              data-type="author"
              >
          <a href="{{ author['id'] }}"
             itemprop="url"
             data-type="{{ author['type'] }}"
             >{{ author['name'] }}</a>
        </span>{% if not loop.last %}, {% endif %}
        {%- endfor %}

        Edited by: 
        <span itemprop="editor"
              data-type="editor"
              >I. M. Picky</span>

        Illustrated by: 
        <span itemprop="illustrator"
              data-type="illustrator"
              >Francis Hablar</span>

        Translated by: 
        <span itemprop="contributor"
              data-type="translator"
              >Francis Hablar</span>
      </div>

      <div class="publishers">
       {% for publisher in metadata['publishers'] -%}
       Published By: 
        <span itemprop="publisher"
              data-type="publisher"
              >{{ publisher }}</span>
       {%- endfor %}
      </div>

      <div class="derived-from">
        Based on:
        <a href="http://example.org/contents/id@ver"
           itemprop="isBasedOnURL"
           data-type="based-on"
           >Wild Grains and Warted Feet</a>
      </div>

      <div class="permissions">
        {% if metadata['copyright_holders'] %}
        <p class="copyright">
          Copyright:
          {% for holder in metadata['copyright_holders'] -%}
          <span itemprop="copyrightHolder"
                data-type="copyright-holder"
                >{{ holder }}</span>
          {%- endfor %}
        </p>
        {% endif %}
        <p class="license">
          Licensed:
          <a href="{{ metadata['license_url'] }}"
             itemprop="dc:license,lrmi:useRightsURL"
             data-type="license"
             >{{ metadata['license_text'] }}</a>
        </p>
      </div>

      <div class="description"
           itemprop="description"
           data-type="description"
           >
        {{ metadata['summary']|e }}
      </div>

      {% for keyword in metadata['keywords'] -%}
      <div itemprop="keywords" data-type="keyword">{{ keyword }}</div>
      {%- endfor %}
      {% for subject in metadata['subjects'] -%}
      <div itemprop="about" data-type="subject">{{ subject }}</div>
      {%- endfor %}
    </div>

   {{ content }}
  </body>
</html>
"""

# YANK This was pulled from cnx-archive to temporarily provide
#      a way to render the the tree to html. This either needs to
#      move elsewhere or preferably be replaced with a better solution.

def html_listify(tree, root_xl_element, list_type='ol'):
    for node in tree:
        li_elm = etree.SubElement(root_xl_element, 'li')
        if node['id'] == 'subcol':
            span_elm = etree.SubElement(li_elm, 'span')
            span_elm.text = node['title']
        else:
            a_elm = etree.SubElement(li_elm, 'a')
            a_elm.text = node['title']
            a_elm.set('href', '{}.xhtml'.format(node['id']))
        if 'contents' in node:
            elm = etree.SubElement(li_elm, list_type)
            html_listify(node['contents'], elm)


def tree_to_html(tree):
    nav = etree.Element('nav')
    nav.set('id', 'toc')
    ol = etree.SubElement(nav, 'ol')
    html_listify(tree['contents'], ol)
    return etree.tostring(nav)

# /YANK
