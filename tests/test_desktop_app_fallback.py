"""Tests for desktop_app.py fallback behaviour (T014).

Verifies the PySide6-missing fallback message includes the correct
install command.

No external API, no LLM, no Vivado.
"""

from __future__ import annotations

import unittest
from io import StringIO
from unittest.mock import patch

from fpga_devmind.desktop_app import main


class TestDesktopAppFallback(unittest.TestCase):

    def test_pyside6_missing_message_contains_install_command(self) -> None:
        """When PySide6 is missing, the fallback message mentions .[desktop]."""
        # Force ImportError for PySide6 by patching the import inside main().
        # Since PySide6 may or may not be installed in the test environment,
        # we patch the import mechanism to simulate a missing PySide6.
        import builtins
        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):  # type: ignore[no-untyped-def]
            if name == "PySide6":
                raise ImportError("No module named 'PySide6'")
            return real_import(name, *args, **kwargs)

        buf = StringIO()
        with (
            patch("builtins.__import__", side_effect=_fake_import),
            patch("sys.stdout", buf),
        ):
            exit_code = main(["--artifact-dir", "/tmp/nonexistent"])

        output = buf.getvalue()
        # The fallback message should mention the desktop extras install
        self.assertIn(".[desktop]", output)
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
