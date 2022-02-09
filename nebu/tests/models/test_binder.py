from cnxepub.models import (
    flatten_to_documents,
    model_to_tree,
)

from nebu.models.binder import Binder


class TestBinder(object):

    def test_from_collection_xml(self, neb_collection_data):
        filepath = neb_collection_data / 'collection.xml'

        # Hit the target
        binder = Binder.from_collection_xml(filepath)

        # Verify the tree structure
        expected_tree = {
            'contents': [
                {'id': 'm47830@1.17',
                 'shortId': None,
                 'title': 'Preface'},
                {'contents': [{'id': 'd93df8ff-6e4a-4a5e-befc-ba5a144f309c@14',
                               'shortId': None,
                               'title': 'Introduction'},
                              {'id': 'cb418599-f69b-46c1-b0ef-60d9e36e677f@12',
                               'shortId': None,
                               'title': 'Definitions of '
                               'Statistics, Probability, '
                               'and Key Terms'},
                              {'id': 'm46885@1.21',
                               'shortId': None,
                               'title': 'Data, Sampling, and '
                               'Variation in Data and '
                               'Sampling'},
                              {'id': '3fb20c92-9515-420b-ab5e-6de221b89e99@17',
                               'shortId': None,
                               'title': 'Frequency, Frequency '
                               'Tables, and Levels of '
                               'Measurement'},
                              {'id': 'm46919@1.13',
                               'shortId': None,
                               'title': 'Experimental Design and '
                               'Ethics'}],
                 'id': 'subcol',
                 'shortId': None,
                 'title': 'Sampling and Data'},
                {'contents': [{'id': 'm46925@1.7',
                               'shortId': None,
                               'title': 'Introduction'},
                              {'id': 'm46934@1.10',
                               'shortId': None,
                               'title': 'Stem-and-Leaf Graphs '
                               '(Stemplots), Line Graphs, '
                               'and Bar Graphs'}],
                 'id': 'subcol',
                 'shortId': None,
                 'title': 'Descriptive Statistics'},
                {'id': 'm47864@1.17',
                 'shortId': None,
                 'title': 'Review Exercises (Ch 3-13)'},
                {'id': 'm47865@1.16',
                 'shortId': None,
                 'title': 'Practice Tests (1-4) and Final Exams'},
                {'id': 'm47873@1.9',
                 'shortId': None,
                 'title': 'Data Sets'}],
            'id': '30189442-6998-4686-ac05-ed152b91b9de@23.41',
            'shortId': None,
            'title': 'Introductory Statistics',
        }
        assert model_to_tree(binder) == expected_tree

        # Verify the metadata
        expected_metadata = {
            'authors': [{'id': 'OpenStaxCollege',
                         'name': 'OpenStaxCollege',
                         'type': 'cnx-id'}],
            'cnx-archive-shortid': None,
            'cnx-archive-uri': '30189442-6998-4686-ac05-ed152b91b9de@23.41',
            'copyright_holders': [{'id': 'OpenStaxCollege',
                                   'name': 'OpenStaxCollege',
                                   'type': 'cnx-id'}],
            'created': '2013-07-18T19:30:26-05:00',
            'derived_from_title': 'Principles of Economics',
            'derived_from_uri': 'https://legacy.cnx.org/content/col11613/1.2',
            'editors': [],
            'illustrators': [],
            'keywords': (),
            'language': 'en',
            'license_text': 'Creative Commons Attribution License',
            'license_url': 'http://creativecommons.org/licenses/by/4.0/',
            'print_style': 'statistics',
            'publishers': [{'id': 'OpenStaxCollege',
                            'name': 'OpenStaxCollege',
                            'type': 'cnx-id'},
                           {'id': 'cnxstats',
                            'name': 'cnxstats',
                            'type': 'cnx-id'}],
            'revised': '2019-02-22T14:15:14.840187-06:00',
            # FIXME: Subject from derived-from is duplicated here
            # This is a problem with the cnxml library, not neb
            # Same problem will exist with keywords and potentially roles
            'subjects': ('Mathematics and Statistics',
                         'Mathematics and Statistics'),
            'summary': None,
            'title': 'Introductory Statistics',
            'translators': [],
            'version': '23.41',
            'uuid': None,
            'canonical_book_uuid': None,
            'slug': None,
        }
        assert binder.metadata == expected_metadata

        # Verify documents have been created
        expected = [
            'd93df8ff-6e4a-4a5e-befc-ba5a144f309c',
            'cb418599-f69b-46c1-b0ef-60d9e36e677f',
            '3fb20c92-9515-420b-ab5e-6de221b89e99'
        ]
        assert [x.id for x in flatten_to_documents(binder)] == expected

        # Verify the collection title overrides
        custom_title_doc = [
            doc
            for doc in flatten_to_documents(binder)
            if doc.id == 'd93df8ff-6e4a-4a5e-befc-ba5a144f309c'
        ][0]
        # the page believes its title is...
        title = 'Introduction to Statistics'
        assert custom_title_doc.metadata['title'] == title
        # ...and the book believes the title is...
        title = 'Introduction'
        assert binder[1].get_title_for_node(custom_title_doc) == title

        # Verify the DocumentPointer objects have a title set on the object
        doc_pt = binder[0]
        title = 'Preface'
        assert doc_pt.metadata['title'] == title

        # Verify cnx-archive-uri is set in modules with metadata
        expected = {
            '3fb20c92-9515-420b-ab5e-6de221b89e99':
                '3fb20c92-9515-420b-ab5e-6de221b89e99@17',
            'cb418599-f69b-46c1-b0ef-60d9e36e677f':
                'cb418599-f69b-46c1-b0ef-60d9e36e677f@12',
            'd93df8ff-6e4a-4a5e-befc-ba5a144f309c':
                'd93df8ff-6e4a-4a5e-befc-ba5a144f309c@14'
        }
        for doc in flatten_to_documents(binder):
            assert expected.get(doc.id)
            assert expected[doc.id] == doc.metadata['cnx-archive-uri']

        # Verify reference uris are updated based upon metadata
        expected = {
            'd93df8ff-6e4a-4a5e-befc-ba5a144f309c': [
                'd93df8ff-6e4a-4a5e-befc-ba5a144f309c/CNX_Stats_C01_COs.jpg'
            ],
            'cb418599-f69b-46c1-b0ef-60d9e36e677f': [
                'cb418599-f69b-46c1-b0ef-60d9e36e677f/fig-ch01_02_01n.png',
                'cb418599-f69b-46c1-b0ef-60d9e36e677f'
                '/m16020_DotPlot_description.html',
                'cb418599-f69b-46c1-b0ef-60d9e36e677f'
                '/m16020_DotPlot_description.html'
            ],
            '3fb20c92-9515-420b-ab5e-6de221b89e99': [
                '/contents/m10275@2.1',
                'http://en.wikibooks.org/',
                '3fb20c92-9515-420b-ab5e-6de221b89e99'
                '/CNX_Stats_C01_M10_003.jpg',
                'foobar.png',
                '/contents/cb418599-f69b-46c1-b0ef-60d9e36e677f',
                '/contents/d93df8ff-6e4a-4a5e-befc-ba5a144f309c#pagelocation'
            ]
        }

        for doc in flatten_to_documents(binder):
            assert expected.get(doc.id)
            for reference in doc.references:
                assert reference.uri in expected[doc.id]

    def test_from_git_collection_xml(self, git_collection_data):
        filepath = git_collection_data / 'collection.xml'

        # Hit the target
        binder = Binder.from_collection_xml(filepath)

        # Verify the tree structure
        expected_tree = {
            'contents': [
                {'id': 'm47830@1.17',
                 'shortId': None,
                 'title': 'Preface'},
                {'contents': [{'id': 'd93df8ff-6e4a-4a5e-befc-ba5a144f309c@',
                               'shortId': None,
                               'title': 'Introduction'},
                              {'id': 'cb418599-f69b-46c1-b0ef-60d9e36e677f@',
                               'shortId': None,
                               'title': 'Definitions of '
                               'Statistics, Probability, '
                               'and Key Terms'},
                              {'id': 'm46885@1.21',
                               'shortId': None,
                               'title': 'Data, Sampling, and '
                               'Variation in Data and '
                               'Sampling'},
                              {'id': '3fb20c92-9515-420b-ab5e-6de221b89e99@',
                               'shortId': None,
                               'title': 'Frequency, Frequency '
                               'Tables, and Levels of '
                               'Measurement'},
                              {'id': 'm46919@1.13',
                               'shortId': None,
                               'title': 'Experimental Design and '
                               'Ethics'}],
                 'id': 'subcol',
                 'shortId': None,
                 'title': 'Sampling and Data'},
                {'contents': [{'id': 'm46925@1.7',
                               'shortId': None,
                               'title': 'Introduction'},
                              {'id': 'm46934@1.10',
                               'shortId': None,
                               'title': 'Stem-and-Leaf Graphs '
                               '(Stemplots), Line Graphs, '
                               'and Bar Graphs'}],
                 'id': 'subcol',
                 'shortId': None,
                 'title': 'Descriptive Statistics'},
                {'id': 'm47864@1.17',
                 'shortId': None,
                 'title': 'Review Exercises (Ch 3-13)'},
                {'id': 'm47865@1.16',
                 'shortId': None,
                 'title': 'Practice Tests (1-4) and Final Exams'},
                {'id': 'm47873@1.9',
                 'shortId': None,
                 'title': 'Data Sets'}],
            'id': '30189442-6998-4686-ac05-ed152b91b9de@af89d35',
            'shortId': None,
            'title': 'Introductory Statistics',
        }
        assert model_to_tree(binder) == expected_tree

        # Verify the metadata
        expected_metadata = {
            'authors': [],
            'cnx-archive-shortid': None,
            'cnx-archive-uri': '30189442-6998-4686-ac05-ed152b91b9de@af89d35',
            'copyright_holders': [],
            'created': None,
            'derived_from_title': None,
            'derived_from_uri': None,
            'editors': [],
            'illustrators': [],
            'keywords': (),
            'language': None,
            'license_text': 'Creative Commons Attribution License',
            'license_url': 'http://creativecommons.org/licenses/by/4.0/',
            'print_style': 'statistics',
            'publishers': [],
            'revised': '2019-02-22T14:15:14.840187-06:00',
            'subjects': (),
            'summary': None,
            'title': 'Introductory Statistics',
            'translators': [],
            'version': 'af89d35',
            'uuid': '30189442-6998-4686-ac05-ed152b91b9de',
            'canonical_book_uuid': None,
            'slug': 'introductory-statistics',
        }
        assert binder.metadata == expected_metadata

        # Verify documents have been created
        expected = [
            'd93df8ff-6e4a-4a5e-befc-ba5a144f309c',
            'cb418599-f69b-46c1-b0ef-60d9e36e677f',
            '3fb20c92-9515-420b-ab5e-6de221b89e99'
        ]
        assert [x.id for x in flatten_to_documents(binder)] == expected

        # Verify the collection title overrides
        custom_title_doc = [
            doc
            for doc in flatten_to_documents(binder)
            if doc.id == 'd93df8ff-6e4a-4a5e-befc-ba5a144f309c'
        ][0]
        # the page believes its title is...
        title = 'Introduction to Statistics'
        assert custom_title_doc.metadata['title'] == title
        # ...and the book believes the title is...
        title = 'Introduction'
        assert binder[1].get_title_for_node(custom_title_doc) == title

        # Verify the DocumentPointer objects have a title set on the object
        doc_pt = binder[0]
        title = 'Preface'
        assert doc_pt.metadata['title'] == title

        # Verify cnx-archive-uri is set in modules with metadata
        expected = {
            '3fb20c92-9515-420b-ab5e-6de221b89e99':
                '3fb20c92-9515-420b-ab5e-6de221b89e99@',
            'cb418599-f69b-46c1-b0ef-60d9e36e677f':
                'cb418599-f69b-46c1-b0ef-60d9e36e677f@',
            'd93df8ff-6e4a-4a5e-befc-ba5a144f309c':
                'd93df8ff-6e4a-4a5e-befc-ba5a144f309c@'
        }
        for doc in flatten_to_documents(binder):
            assert expected.get(doc.id)
            assert expected[doc.id] == doc.metadata['cnx-archive-uri']
