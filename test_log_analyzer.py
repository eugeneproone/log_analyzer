import unittest
import shutil

from pathlib import Path
from log_analyzer import *

class GetMostRecentLogFilenameTestCase(unittest.TestCase):
    def setUp(self):
        self.TEST_LOGS_DIR = './test_logs_dir'
        self.TEST_LOGS_DIR_PATH = Path(self.TEST_LOGS_DIR)
        self.CORRECT_DATE_STR = "2022.04.02"
        self.CORRECT_FILENAME = "nginx-access-ui.log-%s.gzip" % self.CORRECT_DATE_STR
        self.TEST_FILES = ("nginx-access-ui.log-2022.03.02.log",
        "nginx-access-ui.log-2022.03.02.bz",
        "nginx-access-ui.log-2021.03.02.log",
        self.CORRECT_FILENAME)

        if self.TEST_LOGS_DIR_PATH.exists():
            shutil.rmtree(self.TEST_LOGS_DIR_PATH)
        Path.mkdir(self.TEST_LOGS_DIR_PATH, parents=True)
        for test_filename in self.TEST_FILES:
            with open(self.TEST_LOGS_DIR_PATH / test_filename, 'w'):
                pass

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

class ComposeReportDataTestCase(unittest.TestCase):
    def setUp(self):
        self.TEST_LOG_PATH = Path("./test_log")
        self.TEST_EXPECTED_RESULT = ({ "/api/v2/banner/25019354" : [0.390],
        "/api/1/photogenic_banners/list/?server_name=WIN7RB4" : [0.133, 0.135],
        "/api/v2/banner/7763463" : [0.199, 0.181]
        }, 0)
        
        with open(self.TEST_LOG_PATH, 'wt') as test_log_file:
            test_log_file.write(
                """1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /api/v2/banner/25019354 HTTP/1.1" 200 927 "-" "Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5" "-" "1498697422-2190034393-4708-9752759" "dc7161be3" 0.390
                1.99.174.176 3b81f63526fa8  - [29/Jun/2017:03:50:22 +0300] "GET /api/1/photogenic_banners/list/?server_name=WIN7RB4 HTTP/1.1" 200 12 "-" "Python-urllib/2.7" "-" "1498697422-32900793-4708-9752770" "-" 0.133
                1.169.137.128 -  - [29/Jun/2017:03:50:22 +0300] "GET /api/v2/banner/7763463 HTTP/1.1" 200 19415 "-" "Slotovod" "-" "1498697422-2118016444-4708-9752769" "712e90144abee9" 0.199
                1.169.137.128 -  - [29/Jun/2017:03:50:23 +0300] "GET /api/v2/banner/7763463 HTTP/1.1" 200 1018 "-" "Configovod" "-" "1498697422-2118016444-4708-9752774" "712e90144abee9" 0.181
                1.99.174.176 3b81f63526fa8  - [29/Jun/2017:03:50:22 +0300] "GET /api/1/photogenic_banners/list/?server_name=WIN7RB4 HTTP/1.1" 200 12 "-" "Python-urllib/2.7" "-" "1498697422-32900793-4708-9752770" "-" 0.135"""
            )

    def test_compose_report_data(self):
        result = compose_report_data(self.TEST_LOG_PATH)
        self.assertEqual(result, self.TEST_EXPECTED_RESULT)

    def tearDown(self) -> None:
        if self.TEST_LOG_PATH.exists():
            self.TEST_LOG_PATH.unlink()

class ComposeReportDataWithErrors(unittest.TestCase):
    def setUp(self):
        self.TEST_LOG_PATH = Path("./test_log_with_errors")
        
        with open(self.TEST_LOG_PATH, 'wt') as test_log_file:
            test_log_file.write(
                """1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GEiT /api/v2/banner/25019354 HTTP/1.1" 200 927 "-" "Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5" "-" "1498697422-2190034393-4708-9752759" "dc7161be3" 0.390 ans
                1.99.174.176 3b81f63526fa8  - [29/Jun/2017:03:50:22 +0300] "GET /api/1/photogenic_banners/list/?server_name=WIN7RB4 HTTP/1.1" 200 12 "-" "Python-urllib/2.7" "-" "1498697422-32900793-4708-9752770" "-" 0.133 asb
                1.169.137.128 -  - [29/Jun/2017:03:50:22 +0300] "GET /api/v2/banner/7763463 HTTP/1.1" 200 19415 "-" "Slotovod" "-" "1498697422-2118016444-4708-9752769" "712e90144abee9"
                1.169.137.128 -  - [29/Jun/2017:03:50:23 +0300] "GET /api/v2/banner/7763463 HTTP/1.1" 200 1018 "-" "Configovod" "-" "1498697422-2118016444-4708-9752774" "712e90144abee9" 0.181
                1.99.174.176 3b81f63526fa8  - [29/Jun/2017:03:50:22 +0300] "GET /api/1/photogenic_banners/list/?server_name=WIN7RB4 HTTP/1.1" 200 12 "-" "Python-urllib/2.7" "-" "1498697422-32900793-4708-9752770" "-" 0.13a5"""
            )

    def test_compose_report_data_should_parse_one_url(self):
        self.TEST_EXPECTED_RESULT = ({
            "/api/v2/banner/7763463" : [0.181]
        }, 4)
        result = compose_report_data(self.TEST_LOG_PATH)
        self.assertEqual(result, self.TEST_EXPECTED_RESULT)

    def test_compose_report_data_should_exit_on_errors(self):
        self.TEST_EXPECTED_RESULT = (None, 2)
        result = compose_report_data(self.TEST_LOG_PATH, 2)
        self.assertEqual(result, self.TEST_EXPECTED_RESULT)

    def tearDown(self) -> None:
        if self.TEST_LOG_PATH.exists():
            self.TEST_LOG_PATH.unlink()

class PrepareDataForJsonTestCase(unittest.TestCase):
    def setUp(self):
        self.REPORT_DATA = ({ "/api/v2/banner/25019354" : [0.390],
            "/api/1/photogenic_banners/list/?server_name=WIN7RB4" : [0.133, 0.135],
            "/api/v2/banner/7763463" : [0.199, 0.181]
        }, 0)
        self.EXPECTED_PREPARED_DATA = [
            { "url" : "/api/v2/banner/25019354",  "count" : 1, "time_avg" : 0.390, "time_max": 0.390, "time_sum" : 0.390, "time_med": 0.390, "time_perc" : 0.390 / 1.038 * 100, "count_perc" : 20 },
            { "url" : "/api/1/photogenic_banners/list/?server_name=WIN7RB4",  "count" : 2, "time_avg" : 0.134, "time_max": 0.135, "time_sum" : 0.268, "time_med": 0.134, "time_perc" : 0.268 / 1.038 * 100, "count_perc" : 2.0 / 5 * 100 },
            { "url" : "/api/v2/banner/7763463",  "count" : 2, "time_avg" : 0.190, "time_max": 0.199, "time_sum" : 0.380, "time_med": 0.190, "time_perc" : 0.380 / 1.038 * 100, "count_perc" : 2.0 / 5 * 100 }]

    def test_prepare_data_for_json(self):
        result = prepare_data_for_json(self.REPORT_DATA[0])
        for row_e in enumerate(result, 0):
            self.assertEqual(len(row_e[1].keys()), len(self.EXPECTED_PREPARED_DATA[0]))
            for col in row_e[1].keys():
                if isinstance(row_e[1][col], str):
                    self.assertEqual(row_e[1][col], self.EXPECTED_PREPARED_DATA[row_e[0]][col])
                else:
                    self.assertAlmostEqual(row_e[1][col], self.EXPECTED_PREPARED_DATA[row_e[0]][col])


    def tearDown(self) -> None:
        pass
        # if self.REPORT_PATH.exists():
        #     self.REPORT_PATH.unlink()
            

if __name__ == '__main__':
    unittest.main()