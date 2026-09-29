import unittest

from domain.calver import is_calver


class CalVerTests(unittest.TestCase):
    def test_accepts_date_and_optional_revision(self):
        self.assertTrue(is_calver("2026.09.29"))
        self.assertTrue(is_calver("2026.09.29.0"))
        self.assertTrue(is_calver("2026.09.29.2"))

    def test_rejects_semver_invalid_dates_and_padded_revisions(self):
        self.assertFalse(is_calver("0.1.0"))
        self.assertFalse(is_calver("2026.02.30"))
        self.assertFalse(is_calver("2026.09.29.01"))


if __name__ == "__main__":
    unittest.main()
