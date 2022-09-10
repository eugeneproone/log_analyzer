import unittest
import shutil

from pathlib import Path
from log_analyzer import *

class GetMostRecentLogFilenameTestCase(unittest.TestCase):
    TEST_LOGS_DIR = './test_logs_dir'
    TEST_LOGS_DIR_PATH = Path(TEST_LOGS_DIR)
    CORRECT_DATE_STR = "2022.04.02"
    CORRECT_FILENAME = "nginx-access-ui.log-%s.gzip" % CORRECT_DATE_STR
    TEST_FILES = ("nginx-access-ui.log-2022.03.02.log",
    "nginx-access-ui.log-2022.03.02.bz",
    "nginx-access-ui.log-2021.03.02.log",
    CORRECT_FILENAME)

    def setUp(self):
        if self.TEST_LOGS_DIR_PATH.exists():
            shutil.rmtree(self.TEST_LOGS_DIR_PATH)
        Path.mkdir(self.TEST_LOGS_DIR_PATH, parents=True)
        for test_filename in self.TEST_FILES:
            with open(self.TEST_LOGS_DIR_PATH / test_filename, 'w'):
                pass
                # file.write("Hello")

    def test_get_most_recent_log_filename(self):
        log_fileinfo = get_most_recent_log_filename({
            "REPORT_SIZE": 1000,
            "REPORT_DIR": "./reports",
            "LOG_DIR": self.TEST_LOGS_DIR,
            "LOGGING_LOG_FILENAME": None
        })
        self.assertIsNotNone(log_fileinfo)
        self.assertEqual(log_fileinfo.filename, self.CORRECT_FILENAME)
        self.assertEqual(log_fileinfo.date_str, self.CORRECT_DATE_STR)

    def tearDown(self) -> None:
        if self.TEST_LOGS_DIR_PATH.exists():
            shutil.rmtree(self.TEST_LOGS_DIR_PATH)

if __name__ == '__main__':
    unittest.main()