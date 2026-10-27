from __future__ import annotations

import unittest

import helpers

helpers.setup_env()

from disk_cleanup.safety import protected_reason


class SafetyTests(unittest.TestCase):
    def assert_allowed(self, path: str):
        self.assertIsNone(protected_reason(path), path)

    def assert_blocked(self, path: str):
        self.assertIsNotNone(protected_reason(path), path)

    def test_system_roots_are_blocked(self):
        for path in (
            "C:/",
            r"C:\Windows",
            r"C:\Windows\System32",
            r"C:\Windows\WinSxS",
            r"C:\Windows\SoftwareDistribution\DataStore",
            r"C:\Windows\Prefetch",
            r"C:\Program Files",
            r"C:\Program Files\App",
            r"C:\ProgramData",
            r"C:\ProgramData\Package Cache",
            r"C:\Recovery",
            r"C:\Boot",
            r"C:\System Volume Information",
            r"C:\$Recycle.Bin",
            r"C:\pagefile.sys",
            r"C:\hiberfil.sys",
        ):
            self.assert_blocked(path)

    def test_windows_allowlist(self):
        for path in (
            r"C:\Windows\Temp",
            r"C:\Windows\SystemTemp",
            r"C:\Windows\SoftwareDistribution\Download",
            r"C:\Windows\Logs",
            r"C:\Windows\Panther",
            r"C:\Windows\LiveKernelReports",
            r"C:\Windows\Minidump",
            r"C:\Windows\System32\LogFiles",
        ):
            self.assert_allowed(path)

    def test_programdata_allowlist(self):
        for path in (
            r"C:\ProgramData\Microsoft\Windows\WER",
            r"C:\ProgramData\Microsoft\Windows\WER\ReportQueue",
            r"C:\ProgramData\Microsoft\Network\Downloader",
            r"C:\ProgramData\NVIDIA Corporation\Downloader",
        ):
            self.assert_allowed(path)

    def test_user_profiles(self):
        self.assert_blocked(r"C:\Users")
        self.assert_blocked(r"C:\Users\alice")
        self.assert_blocked(r"C:\Users\alice\Desktop")
        self.assert_blocked(r"C:\Users\alice\Documents")
        self.assert_blocked(r"C:\Users\alice\OneDrive")
        self.assert_blocked(r"C:\Users\alice\AppData")
        self.assert_blocked(r"C:\Users\alice\AppData\Local")
        self.assert_blocked(r"C:\Users\alice\AppData\Roaming")
        self.assert_blocked(r"C:\Users\alice\AppData\Local\Programs")
        self.assert_blocked(r"C:\Users\alice\AppData\Local\Packages")
        self.assert_blocked(r"C:\Users\alice\AppData\Local\Microsoft\WindowsApps")
        self.assert_blocked(r"C:\Users\alice\.git")
        self.assert_blocked(r"C:\Users\alice\.ssh")

    def test_user_cache_and_downloads_allowed(self):
        for path in (
            r"C:\Users\alice\Downloads",
            r"C:\Users\alice\AppData\Local\Temp",
            r"C:\Users\alice\AppData\Local\pip\Cache",
            r"C:\Users\alice\AppData\Local\Microsoft\Windows\Explorer",
            r"C:\Users\alice\AppData\Local\Packages\App\LocalCache",
            r"C:\Users\alice\AppData\Roaming\Code\Cache",
        ):
            self.assert_allowed(path)

    def test_backup_copy_nested_deeper_is_data(self):
        self.assert_allowed(r"D:\Backup\Windows")
        self.assert_allowed(r"D:\Projects\Program Files")
        self.assert_blocked(r"D:\Windows")
        self.assert_blocked(r"D:\ProgramData")

    def test_drive_specific_recycle_bin(self):
        self.assert_blocked(r"E:\$Recycle.Bin")
        self.assert_blocked(r"E:\System Volume Information")


if __name__ == "__main__":
    unittest.main()
