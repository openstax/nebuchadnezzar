# -*- coding: utf-8 -*-
# ###
# Copyright (c) 2019, Rice University
# This software is subject to the provisions of the GNU Affero General
# Public License version 3 (AGPLv3).
# See LICENCE.txt for details.
# ###
"""Various standalone utility functions that provide specific outcomes"""
import re
from lxml import etree


__all__ = (
    'squash_xml_to_text',
    'HTML_DOCUMENT_NAMESPACES'
)


HTML_DOCUMENT_NAMESPACES = {
    'xhtml': "http://www.w3.org/1999/xhtml",
    'epub': "http://www.idpf.org/2007/ops",
}


def fix_namespaces(root):
    # Get rid of unused namespaces and put them all in the root tag
    nsmap = {
        None: "http://www.w3.org/1999/xhtml",
        "m": "http://www.w3.org/1998/Math/MathML",
        "epub": "http://www.idpf.org/2007/ops",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "dc": "http://purl.org/dc/elements/1.1/",
        "lrmi": "http://lrmi.net/the-specification",
        "bib": "http://bibtexml.sf.net/",
        "data": "http://www.w3.org/TR/html5/dom.html#custom-data-attribute",
        "qml": "http://cnx.rice.edu/qml/1.0",
        "datadev": "http://dev.w3.org/html5/spec/#custom",
        "mod": "http://cnx.rice.edu/#moduleIds",
        "md": "http://cnx.rice.edu/mdml",
        "c": "http://cnx.rice.edu/cnxml",
    }

    # lxml has a built in function to do this without destroying comments
    etree.cleanup_namespaces(root, top_nsmap=nsmap)

    return etree.tostring(root, pretty_print=True, encoding="utf-8")


def open_xml(p):
    return etree.parse(p, None)


def xpath_html(elem, path):
    return elem.xpath(path, namespaces=HTML_DOCUMENT_NAMESPACES)


def etree_from_str(s, parser=None):
    return etree.fromstring(s, parser)


def squash_xml_to_text(elm, remove_namespaces=False):
    """Squash the given XML element (as `elm`) to a text containing XML.
    The outer most element/tag will be removed, but inner elements will
    remain. If `remove_namespaces` is specified, XML namespace declarations
    will be removed from the text.

    :param elm: XML element
    :type elm: :class:`xml.etree.ElementTree`
    :param remove_namespaces: flag to indicate the removal of XML namespaces
    :type remove_namespaces: bool
    :return: the inner text and elements of the given XML element
    :rtype: str

    """
    leading_text = elm.text and elm.text or ''
    result = [leading_text]

    for child in elm.getchildren():
        # Encoding is set to utf-8 because otherwise `ó` would
        # become `&#243;`
        child_value = etree.tostring(child, encoding='utf-8')
        # Decode to a string for later regexp and whitespace stripping
        child_value = child_value.decode('utf-8')
        result.append(child_value)

    if remove_namespaces:
        # Best way to remove the namespaces without having the parser complain
        # about producing invalid XML.
        result = [re.sub(' xmlns:?[^=]*="[^"]*"', '', v) for v in result]

    # Join the results and strip any surrounding whitespace
    result = u''.join(result).strip()
    return result
