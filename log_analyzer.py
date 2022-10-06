#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import re
import logging
import gzip
import json
import statistics
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
}

LogfileInfo = namedtuple('LogFileInfo', ['filename', 'date_str'])

def get_most_recent_log_filename(config: dict):
    LOG_FILE_STARTS_WITH_STR = 'nginx-access-ui.log-'
    DATE_RE = r'\d{8}'
    LOG_FILE_RE = re.compile(LOG_FILE_STARTS_WITH_STR + DATE_RE + r'\.(log|gz)$')

    most_recent_log_fileinfo = None
    log_dir_path = Path(config["LOG_DIR"])
    if log_dir_path.exists() and log_dir_path.is_dir():
        for log_filename in log_dir_path.iterdir():
            file_match = re.match(LOG_FILE_RE, log_filename.name)
            if file_match:
                cur_date_str = file_match[0][len(LOG_FILE_STARTS_WITH_STR) : len(LOG_FILE_STARTS_WITH_STR) + 8]
                cur_date_int = int(cur_date_str)
                if (most_recent_log_fileinfo == None) or (cur_date_int > int(most_recent_log_fileinfo.date_str)):
                    most_recent_log_fileinfo = LogfileInfo(file_match[0], cur_date_str)
    else:
        logging.info("Dir %s does not exist" % log_dir_path)
    return most_recent_log_fileinfo

def compose_report_data(log_path: Path, error_thrsld_qty=0) -> tuple:
    def log_gen(log_path: Path):
        log_file = gzip.open(log_path, mode='rt', encoding='utf8') if str(log_path).endswith('.gz') else open(log_path, 'rt', encoding='utf8')

        while True:
            line = log_file.readline()
            if not line:
                log_file.close()
                break
            yield line
        logging.info("Closing log file")
        log_file.close()

    log_data_dict = {}
    errors_qty = 0
    for line_num, line in enumerate(log_gen(log_path), 0):
        request_url_match = re.search(r'\".*?\"', line)
        request_time_match = re.search(r'\d+\.\d+$', line)
        if request_url_match and request_time_match:
            req_url_arr = request_url_match[0].split(' ')
            if len(req_url_arr) > 1:
                request_url = req_url_arr[1]
                request_time = float(request_time_match[0])
                if request_url in log_data_dict.keys():
                    log_data_dict[request_url].append(request_time)
                else:
                    log_data_dict[request_url] = [request_time]
            else:
                logging.warning("Error in log format. line %u : %s" % (line_num, line))
                errors_qty += 1
        else:
            logging.warning("Error in log format. line %u : %s" % (line_num, line))
            errors_qty += 1
    if (errors_qty >= error_thrsld_qty) and (error_thrsld_qty > 0):
        logging.error("Parsing errors qty reached the threshold qty")
        log_data_dict = None
    return log_data_dict, errors_qty

def render_html_report(prepared_data: list, report_path: Path) -> bool:
    REPORT_TEMPLATE_PATH = Path("./report.html")
    result = True
    if REPORT_TEMPLATE_PATH.exists() and REPORT_TEMPLATE_PATH.is_file():
        with open(REPORT_TEMPLATE_PATH, 'rt', encoding='utf8') as template_file:
            logging.info("Template file opened successfully: %s", REPORT_TEMPLATE_PATH)
            template_report = template_file.read()
        STRING_TO_SUBS = '$table_json'
        write_pos = template_report.find(STRING_TO_SUBS)
        if write_pos < 0:
            logging.error('Template is broken')
            result = False

        with open(Path(report_path), "wt", encoding='utf8') as report_file:
            logging.info("Opening report file: %s", Path(report_path))
            report_file.write(template_report[:write_pos])
            json.dump(prepared_data, report_file)
            report_file.write(template_report[write_pos + len(STRING_TO_SUBS):])
            result = True
    else:
        result = False
    return result

def prepare_data_for_json(log_data_dict: dict, report_size_urls=0) -> list:
    PRECISION = 3
    out_list = []
    
    total_time = 0.0
    total_count = 0

    urls_tpl = tuple(log_data_dict.keys()) if (report_size_urls == 0) else tuple(log_data_dict.keys())[0:report_size_urls]

    logging.info("Used URLs limit: %u. So only %u urls will be rendered to report", report_size_urls, len(urls_tpl))

    for url in urls_tpl:
        log_data_dict[url].sort()
        elem = log_data_dict[url]
        cur_count = len(elem)
        cur_sum_time = round(sum(elem), PRECISION)
        out_list.append(dict(url=url, count=len(elem), time_avg=round(statistics.fmean(elem), PRECISION),
            time_max=round(max(elem), PRECISION), time_sum=cur_sum_time, time_med=round(statistics.median(elem), PRECISION)))
        total_count += cur_count
        total_time += cur_sum_time

    for elem in out_list:
        elem["time_perc"] = round(elem["time_sum"] / total_time * 100, PRECISION)
        elem["count_perc"] = round(elem["count"] / total_count * 100, PRECISION)
    return out_list

def main():
    arg_parser = argparse.ArgumentParser(description="Script for nginx logs parsing and for html-reports generation")
    arg_parser.add_argument('--config', nargs=1, help="Path to config file", dest='config_path')
    arg_parser.add_argument('--log', nargs=1, help="Logging level", dest='logging_level', default=['WARNING'])
    arg_parser.add_argument('--log-file', nargs=1, help="Logging filename", dest='logging_filename', default=None)
    arg_parser.add_argument('--errors-thrshld', nargs=1, help="Parsing errors threshold value", dest='errors_thrshld', default=['0'])
    args = arg_parser.parse_args()

    log_filename = None if args.logging_filename is None else Path(args.logging_filename[0].strip())

    logging_level = getattr(logging, args.logging_level[0].strip().upper())
    logging.basicConfig(level=logging_level, filename=log_filename, format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d%H:%M:%S')

    used_config = default_config
    config_path = Path(args.config_path[0].strip()) if args.config_path else None
    if config_path != None:
        logging.info("Using given config file: %s", config_path)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf8') as config_file:
                try:
                    config_json_data = json.load(config_file)
                except json.JSONDecodeError:
                    logging.error("Could not parse json file. Probably it is broken or has incorrect format")
                    exit(1)
                expected_fields = default_config.keys()
                for field in config_json_data:
                    if field in expected_fields:
                        used_config[field] = config_json_data[field]
                        logging.info("Using '%s'='%s' param from user cfg", field, config_json_data[field])
                    else:
                        logging.error('Unknown key in json config file: %s', field)
                        exit(1)
        else:
            logging.error("Config file %s does not exist", config_path)
            exit(1)
    try:
        errors_thrshld_qty = int(args.errors_thrshld[0].strip())
    except:
        logging.error("Incorrect errors-thrshld argument value")
        exit(1)
    logging.info("Used params:\r\n%s\r\nErrors threshold qty: %u\r\n Logging level: %s", used_config, errors_thrshld_qty, logging_level)
    logfile_info = get_most_recent_log_filename(used_config)

    if logfile_info is None:
        logging.warning("No logs found")
        exit(0)

    logging.info("Most recent log path: %s" % logfile_info.filename)
    out_report_filename = "report-%s.html" % logfile_info.date_str
    report_dir_path = Path(used_config["REPORT_DIR"])

    if report_dir_path.exists(): 
        if out_report_filename in report_dir_path.iterdir():
            logging.warning("Report already exists. Exiting...")
            exit(0)
    else:
        report_dir_path.mkdir(parents=True)
    report_data, errors_qty = compose_report_data(Path(used_config["LOG_DIR"]) / logfile_info.filename, errors_thrshld_qty)
    if report_data:
        logging.info("Report data successfully composed. Errors qty: %u" % errors_qty)
        exit (0 if render_html_report(prepare_data_for_json(report_data, used_config['REPORT_SIZE']), report_dir_path / out_report_filename) else 1)
    else:
        logging.error("Report data is not composed because of too many errors: %u. Exiting" % errors_qty)
        exit(1)

    
if __name__ == "__main__":
    main()