from pathlib import Path
import tempfile
from unittest import mock

import pytest

from nebu.cli.pdf import INPUT_FILE, OUTPUT_FILE, IMAGE_TAG, MOUNT_POINT


@pytest.fixture
def pdf_cleanup(request, datadir):
    def _pdf_cleanup(filenames=()):
        def cleanup():
            for filename in (INPUT_FILE, OUTPUT_FILE) + filenames:
                if (datadir / filename).is_file():
                    (datadir / filename).unlink()

        cleanup()
        request.addfinalizer(cleanup)
    return _pdf_cleanup


def create_collection_baked_xhtml(datadir, filename=INPUT_FILE):
    with (datadir / filename).open('w') as out:
        out.write('<html></html>')


def create_pdf(datadir):
    def inner(*args, **kwargs):
        with (datadir / OUTPUT_FILE).open('w') as out:
            out.write('pdf')
        return b''
    return inner


@pytest.fixture
def pdf_docker_client(datadir):
    patcher = mock.patch('nebu.cli.pdf.docker')
    mock_docker = patcher.start()
    client = mock_docker.from_env()
    client.images.pull.return_value = ['<princexml image>']
    client.containers.run.side_effect = create_pdf(datadir)
    yield client
    patcher.stop()


class TestPdfCmd:
    def test_w_collection_baked_xhtml(self, datadir, invoker, pdf_cleanup,
                                      pdf_docker_client):
        docker = pdf_docker_client
        pdf_cleanup()
        create_collection_baked_xhtml(datadir)

        from nebu.cli.main import cli
        args = ['pdf', str(datadir)]
        result = invoker(cli, args)

        assert docker.images.pull.called
        assert not docker.images.build.called
        assert docker.containers.run.called
        (image_tag,), kwargs = docker.containers.run.call_args
        assert image_tag == IMAGE_TAG
        assert 'prince ' in kwargs['command']
        assert '--style' not in kwargs['command']

        assert result.exit_code == 0
        assert (datadir / OUTPUT_FILE).is_file()

    def test_wo_collection_baked_xhtml(self, datadir, invoker, pdf_cleanup,
                                       pdf_docker_client):
        docker = pdf_docker_client
        pdf_cleanup()

        from nebu.cli.main import cli
        args = ['pdf', str(datadir)]
        result = invoker(cli, args)

        assert result.exit_code == 1
        assert str(result.exception) == \
            'Input file {} not found or is not a file.'.format(
                datadir / INPUT_FILE)
        assert not docker.containers.run.called

    def test_input_file_directory(self, datadir, invoker, pdf_cleanup):
        pdf_cleanup()

        from nebu.cli.main import cli
        args = ['pdf', '-i', str(datadir), str(datadir)]
        result = invoker(cli, args)

        assert result.exit_code == 1
        assert str(result.exception) == \
            'Input file {} not found or is not a file.'.format(datadir)

    def test_input_file(self, datadir, invoker, pdf_cleanup,
                        pdf_docker_client):
        docker = pdf_docker_client
        pdf_cleanup()
        create_collection_baked_xhtml(datadir, 'my_input.xhtml')

        from nebu.cli.main import cli
        args = ['pdf', '-i', str(datadir / 'my_input.xhtml'), str(datadir)]
        result = invoker(cli, args)

        assert docker.containers.run.called
        kwargs = docker.containers.run.call_args[1]
        assert 'my_input.xhtml' in kwargs['command']

        assert result.exit_code == 0
        assert (datadir / OUTPUT_FILE).is_file()

    def test_w_style(self, datadir, invoker, pdf_cleanup, pdf_docker_client):
        docker = pdf_docker_client

        from nebu.cli.main import cli
        with tempfile.NamedTemporaryFile(suffix='.css') as f:
            style_name = Path(f.name).name
            pdf_cleanup((str(datadir / style_name),))
            create_collection_baked_xhtml(datadir)
            f.file.write(b'.hidden { display: none; }\n')
            f.file.close()
            args = ['pdf', '-s', f.name, str(datadir)]
            result = invoker(cli, args)

        # the css file is copied to the collection directory so the file is
        # mounted in the container
        with (datadir / style_name).open('r') as f:
            assert f.read() == '.hidden { display: none; }\n'
        args, kwargs = docker.containers.run.call_args
        assert '--style="{}"'.format(Path(MOUNT_POINT) / style_name) in \
            kwargs['command']
        assert result.exit_code == 0
        assert (datadir / OUTPUT_FILE).is_file()

    def test_image_not_found(self, datadir, invoker, pdf_cleanup,
                             pdf_docker_client):
        docker = pdf_docker_client
        pdf_cleanup()
        create_collection_baked_xhtml(datadir)
        docker.images.list.return_value = []
        docker.images.build.side_effect = lambda *args, **kwargs: \
            ('<image>', [{'stream': 'build log'}])

        from nebu.cli.main import cli
        args = ['pdf', str(datadir)]
        result = invoker(cli, args, catch_exceptions=False)
        assert result.exit_code == 0

        assert docker.images.build.called
        args, kwargs = docker.images.build.call_args
        assert sorted(kwargs.keys()) == ['fileobj', 'rm', 'tag']
        assert b'princexml.com' in kwargs['fileobj'].read()
        assert kwargs['rm'] is True
        assert kwargs['tag'] == IMAGE_TAG
        assert (datadir / OUTPUT_FILE).is_file()

    def test_build_flag(self, datadir, invoker, pdf_cleanup,
                        pdf_docker_client):
        docker = pdf_docker_client
        pdf_cleanup()
        create_collection_baked_xhtml(datadir)
        docker.images.build.side_effect = lambda *args, **kwargs: \
            ('<image>', [])

        from nebu.cli.main import cli
        args = ['pdf', '--build', str(datadir)]
        result = invoker(cli, args)
        assert result.exit_code == 0

        assert docker.images.build.called
        assert (datadir / OUTPUT_FILE).is_file()
