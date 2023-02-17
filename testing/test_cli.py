import unittest

from cli import cli
import os

from translator import utils


class TestCli(unittest.TestCase):
    os.chdir(utils.get_project_root_path())

    def test_cli(self):
        cli.main(
            ["--template-file", "examples/small_nfv_example.yaml", "--validate-only"]
        )

    def test_cli_change_wd(self):
        os.chdir("examples")
        try:
            cli.main(["--template-file", "small_nfv_example.yaml", "--validate-only"])
        finally:
            os.chdir(utils.get_project_root_path())


if __name__ == "__main__":
    unittest.main()
