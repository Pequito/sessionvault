import unittest

from app.managers.keepass import KeePassManager


class KeePassManagerTests(unittest.TestCase):
    def test_close_db_keeps_path_known_and_marks_it_locked(self):
        manager = KeePassManager()
        manager._dbs["/tmp/a.kdbx"] = object()
        manager._active_path = "/tmp/a.kdbx"
        manager._known_paths.append("/tmp/a.kdbx")

        manager.close_db("/tmp/a.kdbx")

        self.assertEqual(manager.db_path, "")
        self.assertEqual(manager.open_paths, [])
        self.assertEqual(manager.known_paths, ["/tmp/a.kdbx"])
        self.assertTrue(manager.is_path_locked("/tmp/a.kdbx"))

    def test_close_active_db_switches_to_another_open_database(self):
        manager = KeePassManager()
        manager._dbs["/tmp/a.kdbx"] = object()
        manager._dbs["/tmp/b.kdbx"] = object()
        manager._active_path = "/tmp/a.kdbx"
        manager._known_paths.extend(["/tmp/a.kdbx", "/tmp/b.kdbx"])

        manager.close_db("/tmp/a.kdbx")

        self.assertEqual(manager.db_path, "/tmp/b.kdbx")
        self.assertEqual(manager.open_paths, ["/tmp/b.kdbx"])
        self.assertEqual(manager.known_paths, ["/tmp/a.kdbx", "/tmp/b.kdbx"])
        self.assertTrue(manager.is_path_locked("/tmp/a.kdbx"))
        self.assertFalse(manager.is_path_locked("/tmp/b.kdbx"))


if __name__ == "__main__":
    unittest.main()
