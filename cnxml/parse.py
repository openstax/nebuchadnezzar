import re
from functools import partial

from lxml import etree


__all__ = (
    'NSMAP',
    'make_cnx_xpath',
    'parse_metadata',
)


# XML namespace mapping used by lxml.etree for parsing and element lookup
NSMAP = {
    "bib": "http://bibtexml.sf.net/",
    "c": "http://cnx.rice.edu/cnxml",
    "cnxorg": "http://cnx.rice.edu/system-info",
    "col": "http://cnx.rice.edu/collxml",
    "data": "http://www.w3.org/TR/html5/dom.html#custom-data-attribute",
    "datadev": "http://dev.w3.org/html5/spec/#custom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "epub": "http://www.idpf.org/2007/ops",
    "lrmi": "http://lrmi.net/the-specification",
    "m": "http://www.w3.org/1998/Math/MathML",
    "md": "http://cnx.rice.edu/mdml",
    "mod": "http://cnx.rice.edu/#moduleIds",
    "qml": "http://cnx.rice.edu/qml/1.0",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
}


def _maybe(l):
    """Grab the first value if it exists."""
    try:
        return l[0]
    except IndexError:
        return None


def make_cnx_xpath(elm_tree):
    """Makes an xpath function that includes the CNX namespaces.

    :param elm_tree: the xml element to begin the xpath from
    :type elm_tree: an element-like object from :mod:`lxml.etree`

    """
    return partial(elm_tree.xpath, namespaces=NSMAP)


def _squash_to_text(elm, remove_namespaces=False):
    if elm is None:
        return None
    value = [elm.text or '']
    for child in elm.getchildren():
        value.append(etree.tostring(child).decode('utf-8').strip())
    if remove_namespaces:
        value = [re.sub(' xmlns:?[^=]*="[^"]*"', '', v) for v in value]
    value = ''.join(value)
    return value


def parse_metadata(elm_tree):
    """Given an element-like object (:mod:`lxml.etree`)
    lookup the metadata and return the found elements

    :param elm_tree: the root xml element
    :type elm_tree: an element-like object from :mod:`lxml.etree`
    :returns: common metadata properties
    :rtype: dict

    """
    xpath = make_cnx_xpath(elm_tree)
    role_xpath = lambda xp: tuple(xpath(xp)[0].split())  # noqa: E731

    props = {
        'id': _maybe(xpath('//md:content-id/text()')),
        'version': xpath('//md:version/text()')[0],
        'created': xpath('//md:created/text()')[0],
        'revised': xpath('//md:revised/text()')[0],
        'title': xpath('//md:title/text()')[0],
        'license_url': xpath('//md:license/@url')[0],
        'language': xpath('//md:language/text()')[0],
        'authors': role_xpath('//md:role[@type="author"]/text()'),
        'maintainers': role_xpath('//md:role[@type="maintainer"]/text()'),
        'licensors': role_xpath('//md:role[@type="licensor"]/text()'),
        'keywords': tuple(xpath('//md:keywordlist/md:keyword/text()')),
        'subjects': tuple(xpath('//md:subjectlist/md:subject/text()')),
        'abstract': _squash_to_text(
            _maybe(xpath('//md:abstract')),
            remove_namespaces=True,
        ),
        'print_style': _maybe(
            xpath('//col:param[@name="print-style"]/@value'),
        ),
    }
    return props
