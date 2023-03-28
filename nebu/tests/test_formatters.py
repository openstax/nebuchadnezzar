from nebu.formatters import _doc_to_html, _col_to_html, assemble_collection


# Raw means no exercises, no id updates, unresolved links
def test_doc_to_html_raw(snapshot, parts_tuple):
    _, docs_by_id, _ = parts_tuple

    for doc_id, document in docs_by_id.items():
        snapshot.assert_match(_doc_to_html(document), doc_id + ".xhtml")


def test_col_to_html_raw(snapshot, parts_tuple):
    from nebu.models.book_part import PartType

    collection, _, _ = parts_tuple
    snapshot.assert_match(_col_to_html(collection), "collection.xhtml")
    for i, subcol in enumerate(collection.get_parts_by_type(PartType.SUBCOL)):
        snapshot.assert_match(_col_to_html(subcol), f"subcol-{i}.xhtml")


def test_assemble_collection_raw(snapshot, parts_tuple):
    from lxml import etree

    collection, _, _ = parts_tuple
    assembled_collection = assemble_collection(collection)
    snapshot.assert_match(
        etree.tostring(
            assembled_collection, pretty_print=True, encoding="utf-8"
        ),
        "collection.assembled.xhtml",
    )
