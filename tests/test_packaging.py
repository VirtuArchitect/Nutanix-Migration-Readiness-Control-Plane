import tomllib
import unittest
from pathlib import Path


class PackagingTests(unittest.TestCase):
    def test_pyproject_exposes_nmrcp_console_script(self):
        pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(pyproject["project"]["scripts"]["nmrcp"], "nmrcp.cli:main")
        self.assertEqual(pyproject["tool"]["setuptools"]["package-dir"][""], "src")

    def test_gitignore_excludes_python_build_metadata(self):
        gitignore = Path(".gitignore").read_text(encoding="utf-8").splitlines()

        for expected in ("*.egg-info/", "build/", "dist/"):
            self.assertIn(expected, gitignore)


if __name__ == "__main__":
    unittest.main()
