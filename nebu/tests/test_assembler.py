from os import scandir
from pathlib import Path

from lxml import etree

from nebu.assembler import assembler

TITLES_XPATH = '//*[@data-type="document-title"]/text()'


class TestAssembler(object):
    def test_assembler_main(self, datadir, clear_files):
        """assert that `expected` etree contains certain elements in the
        expected xpath position, containing the expected text.
        """
        source_dir = datadir / 'col11562_1.23_complete'

        assembler(source_dir)

        """Parse the titles in source modules (expected)"""
        mod_fname = '/index.cnxml.html'
        modules = [Path((m.path + mod_fname)) for m in scandir(str(source_dir))
                   if m.name.startswith('m')]
        mod_trees = [etree.parse(m.open('rb')) for m in modules]
        expected_titles = list([t.xpath(TITLES_XPATH)[0] for t in mod_trees])

        """Parse the titles in assembler output (actual)"""
        out_path = source_dir / 'collection.xhtml'
        actual_titles = etree.parse(out_path.open('rb')).xpath(TITLES_XPATH)

        for expected in expected_titles:
            assert expected in actual_titles

        clear_files(source_dir, 'collection.xhtml')

        # NOTE: When a module's index.cnxml.html file cannot be found in the
        # source dir, we currently replace it with DATA_WHEN_MODULE_NOT_FOUND
        # in the assembled single html output.

    def test_w_book_tree_structure(self, datadir, clear_files):
        """It should be able to locate all necessary files to produce/assemble
        the single HTML file
        """
        source_dir = datadir / 'col11562_1.23_complete_book_tree'
        assembler(source_dir)

        book_name = 'Introductory Statistics'
        out_path = source_dir / book_name / 'collection.xhtml'

        """Parse the titles in source modules (expected)"""
        mod_fname = '/index.cnxml.html'
        modules = [f for f in scandir(str(out_path.parent))
                   if f.is_dir()]

        mod_trees = [etree.parse(Path(m.path + mod_fname).open('rb'))
                     for m in modules]
        expected_titles = list([t.xpath(TITLES_XPATH)[0] for t in mod_trees])

        """Parse the titles in assembler output (actual)"""
        # Expectation - collection.xhtml is created in `book_name` folder
        actual_titles = etree.parse(out_path.open('rb')).xpath(TITLES_XPATH)

        for expected in expected_titles:
            assert expected in actual_titles

        clear_files((source_dir / book_name), 'collection.xhtml')

    def test_image_links(self, datadir, clear_files):
        """Test that images' `src` attribute points to the locally stored files
        so that they display from local source.
        """
        source_dir = datadir / 'col11562_1.23_complete'

        assembler(source_dir)

        def parse_imgs_uri(path):
            from cnxepub.models import _parse_references
            from lxml import etree

            with path.open('rb') as f:
                refs = _parse_references(etree.XML(f.read()))

            uris = [r.uri for r in refs
                    if r.uri.endswith('.png') or r.uri.endswith('.jpg')]
            return uris

        expected_img_links = ['m46913/CNX_Stats_C01_COs.jpg',
                              'm46909/fig-ch01_02_01n.png',
                              'm46882/CNX_Stats_C01_M10_003.jpg']

        """Parse img links in assembler output (actual)"""
        out_path = source_dir / 'collection.xhtml'
        actual = parse_imgs_uri(out_path)

        for expected in expected_img_links:
            assert expected in actual

        clear_files(source_dir, 'collection.xhtml')
