#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import re
import os
import logging
import gzip
import json
from collections import namedtuple

from pathlib import Path


# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

default_config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
    "LOGGING_LOG_FILENAME": None,
    "ERRORS_THRSLD_QTY": 0
}

LogfileInfo = namedtuple('LogFileInfo', ['filename', 'date_str'])

def get_most_recent_log_filename(config: dict) -> LogfileInfo:
    LOG_FILE_STARTS_WITH_STR = 'nginx-access-ui.log-'
    DATE_RE = r'\d{4}\.\d{2}\.\d{2}'
    LOG_FILE_RE = re.compile(LOG_FILE_STARTS_WITH_STR + DATE_RE + r'\.(log|gzip)$')

    most_recent_log_fileinfo = None
    for log_filename in os.listdir(config["LOG_DIR"]):
        file_match = re.match(LOG_FILE_RE, log_filename)
        if file_match:
            cur_date_str = file_match[0][len(LOG_FILE_STARTS_WITH_STR) : len(LOG_FILE_STARTS_WITH_STR) + 10]
            cur_date_int = int(cur_date_str.replace(".", ""))
            if (most_recent_log_fileinfo == None) or (cur_date_int > int(most_recent_log_fileinfo.date_str.replace(".", ""))):
                most_recent_log_fileinfo = LogfileInfo(file_match[0], cur_date_str)
    return most_recent_log_fileinfo

def compose_report_data(log_path: Path, error_thrsld_qty=0) -> tuple:
    def log_gen(log_path: Path):
        log_file = gzip.open(log_path, mode='rt') if str(log_path).endswith('.gz') else open(log_path, 'rt')

        while True:
            line = log_file.readline()
            if not line:
                log_file.close()
                break
            yield line

    log_data_dict = {}
    errors_qty = 0
    for line in log_gen(log_path):
        request_url_match = re.search(r'GET\s+\S+', line)
        request_time_match = re.search(r'\d+\.\d+$', line)
        if request_url_match and request_time_match:
            request_url = request_url_match[0].replace('GET', '').strip()
            request_time = float(request_time_match[0])
            if request_url in log_data_dict.keys():
                log_data_dict[request_url].append(request_time)
            else:
                log_data_dict[request_url] = [request_time]
        else:
            errors_qty += 1
        if (errors_qty >= error_thrsld_qty) and (error_thrsld_qty > 0):
            logging.exception("Parsing errors qty reached the threshold qty")
            log_data_dict = None
            break
    return log_data_dict, errors_qty

def render_html_report(prepared_data: list, report_path: Path):
    REPORT_TEMPLATE_PATH = Path("./report.html")
    with open(REPORT_TEMPLATE_PATH, 'rt') as template_file:
        template_report = template_file.read()
    STRING_TO_SUBS = '$table_json'
    write_pos = template_report.find(STRING_TO_SUBS)
    if write_pos < 0:
        logging.error('Template is broken')
        return False

    with open(Path(report_path), "wt") as report_file:
        report_file.write(template_report[:write_pos])
        json.dump(prepared_data, report_file)
        report_file.write(template_report[write_pos + len(STRING_TO_SUBS):])

def prepare_data_for_json(log_data_dict: dict) -> list:
    out_list = []
    
    total_time = 0.0
    total_count = 0
    for url in log_data_dict.keys():
        elem = log_data_dict[url]
        cur_count = len(sorted(elem))
        cur_middle_idx = cur_count // 2 - 1
        cur_median = (elem[cur_middle_idx] + elem[cur_middle_idx + 1]) / 2.0 if (cur_count % 2 == 0) else elem[cur_middle_idx + 1]
        cur_sum, cur_max, cur_min, cur_avg = elem[0], elem[0], elem[0], elem[0]
        for i in elem[1:]:
            if i > cur_max:
                cur_max = i
            if i < cur_min:
                cur_min = i
            cur_sum += i
        cur_avg = cur_sum / cur_count
        out_list.append(dict(url=url, count=cur_count, time_avg=cur_avg, time_max=cur_max, time_sum=cur_sum, time_med=cur_median))
        total_count += cur_count
        total_time += cur_sum

    for elem in out_list:
        elem["time_perc"] = elem["time_sum"] / total_time * 100
        elem["count_perc"] = elem["count"] / total_count * 100
    
    return out_list

def main():
    arg_parser = argparse.ArgumentParser(description="Script for nginx logs parsing and for html-reports generation")
    arg_parser.add_argument('--config', nargs=1, help="Path to config file", dest='config_path', required=False)
    args = arg_parser.parse_args()

    used_config = default_config

    if args.config_path:
        with open(args.config_path, 'r') as config_file:
            try:
                config_json_data = json.load(config_file)
            except json.JSONDecodeError:
                logging.error("Could not parse json file. Probably it is broken or has incorrect format")
                exit(1)
            expected_fields = default_config.keys()
            for field in config_json_data:
                if field in expected_fields:
                    used_config[field] = config_json_data[field]
                else:
                    logging.error('Unknown key in json config file: %s' % field)
                    exit(1)
    used_config["ERRORS_THRSLD_QTY"] = int(used_config["ERRORS_THRSLD_QTY"])
    logging.basicConfig(filename=used_config["LOGGING_LOG_FILENAME"], format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d%H:%M:%S')
    logging.info("Used config:") #todo
    logfile_info = get_most_recent_log_filename(used_config)

    if logfile_info is None:
        logging.warning("No logs found")
        exit(0)

    logging.info("Most recent log path: %s" % logfile_info.filename)

    out_report_filename = "report-%s.html" % logfile_info.date_str

    if out_report_filename in os.listdir(used_config["REPORT_DIR"]):
        logging.warning("Report already exists. Exiting...")
        exit(0)

    report_data, errors_qty = compose_report_data(Path(used_config["LOG_DIR"]) / logfile_info.filename, used_config["ERRORS_THRSLD_QTY"])
    if report_data:
        logging.info("Report data successfully composed. Errors qty: %u" % errors_qty)
        render_html_report(report_data, Path(used_config["REPORT_DIR"] / out_report_filename))
    else:
        logging.error("Report data is not composed because of too many errors: %u. Exiting" % errors_qty)
        exit(1)

    
if __name__ == "__main__":
    main()
