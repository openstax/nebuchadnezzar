class TestAssembleCmd:
    def test_assemble_command(self, invoker, datadir):
        from nebu.cli.main import cli

        source_dir = datadir / 'col11562_1.23_complete'

        args = ['assemble', str(source_dir)]
        result = invoker(cli, args)

        if result.exception:
            raise result.exception

        assert result.exit_code == 0  # command succeeded, zero errors.

        # TARGET: it generates the collection.xhtml file
        expected_fpath = source_dir / 'collection.xhtml'

        with expected_fpath.open('rb') as expected:
            # this file was generated, we can read it.
            assert expected.read()
