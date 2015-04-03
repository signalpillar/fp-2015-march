# encoding: utf-8
"""Collected data processing tool.

Usage:
    bugs import <dat-dir>
    bugs alter <csv-file> <dat-file>
    bugs count <csv-file> <frequencies-file>
    bugs analyze <csv-file> --count-cofficients-file=<count-coef-file>
                            --countries-file=<countries-file>
    bugs -h | --help
    bugs --version

Options:
    -h --help      Show this screen.
    --version      Show version.
    <dat-dir>      Path to the folder with dat-files
"""

# std
from __future__ import print_function
import collections
import codecs
import csv
import itertools as it
import os
import re
import string
import sys

# 3rd-party
import docopt

from six import StringIO
from six.moves import reduce


__version__ = "0.1"

DATA_FILE_EXT = '.dat'

DEFAULT_CSV_DELIMITER = ";"

REGION_CELL_NAME = "Регион"


def main(args):
    """Entry point function that should take care of parsing parameters and control the flow."""

    if args.get('import'):
        print(render_to_csv(import_data(data_dir=args.get('<dat-dir>'))))
    elif args.get('alter'):
        print(render_to_csv(alter_csv(csv_file=args.get('<csv-file>'),
                                      data_file=args.get('<dat-file>'))))
    elif args.get('count'):
        print(dict_to_str(count_bugs(csv_file=args.get('<csv-file>'),
                                     freq_file=args.get('<frequencies-file>'))))
    elif args.get('analyze'):
        print(dict_to_str(analyze_bugs(csv_file=args.get('<csv-file>'),
                                       coeff_file=args.get('<count-coef-file>'),
                                       regions_file=args.get('<countries-file>'))))


def import_data(data_dir):
    """str -> dict[str, dict[str, str]]"""

    root_dir = os.path.join(os.getcwd(), data_dir)
    data_files = list_files(root_dir, DATA_FILE_EXT)
    bug_info_by_name = dict(map(read_bug_info, data_files))
    return bug_info_by_name


def alter_csv(csv_file, data_file):
    """str -> str -> dict[str, dict[str, str]]"""

    bug_info_by_name = read_csv(csv_file)
    name, number_by_country = read_bug_info(data_file)
    bug_info_by_name[name] = number_by_country
    return bug_info_by_name


def count_bugs(csv_file, freq_file):
    """Return mapping of bugs per region

    str -> str -> dict[str, int]
    """

    number_to_freq = read_mapping_files(freq_file)
    bug_info_by_name = read_csv(csv_file)
    print(number_to_freq)

    def count(accumulator, bug_info):
        bug_name, region, number = bug_info
        if number not in number_to_freq:
            print("'{}' '{}' {!r}".format(bug_name, region, number))
        accumulator[region] += number_to_freq.get(number)
        return accumulator

    return reducer(count, bug_info_by_name)


def analyze_bugs(csv_file, coeff_file, regions_file):
    """str -> str -> str -> dict[str, int]"""

    number_to_freq = read_mapping_files(coeff_file)
    care_rate_per_region = read_mapping_files(regions_file)

    def calculate_risk(tripplet, accumulator):
        bug_name, region, number = tripplet
        accumulator[bug_name] += care_rate_per_region.get(region, 0) * number_to_freq.get(number)
        return accumulator

    return reducer(calculate_risk, read_csv(csv_file))


def list_files(root_dir, ext):
    """str -> str -> list[str]"""

    return (
        os.path.join(root_dir, file_)
        for file_ in os.listdir(root_dir)
        if os.path.isfile(os.path.join(root_dir, file_)) and file_.endswith(ext)
    )


def dict_to_str(dict_, pair_format="{key}: {value}", pairs_separator='\n'):
    return pairs_separator.join(
        pair_format.format(key=key_, value=value)
        for key_, value in dict_.items()
    )


DEFAULT_ENCODING = 'utf-8'


def read_bug_info(dat_file_path, encoding=DEFAULT_ENCODING):
    """str -> str -> tuple[str, dict[str, str]]"""

    def parse_bug_number_per_country(line):
        """str -> list[str, str]"""
        number, countries = line.split(':', 1)
        return zip(it.imap(string.strip, countries.split(',')), it.repeat(number.strip()))

    with codecs.open(dat_file_path, "r", encoding=encoding) as fd:
        lines = it.dropwhile(lambda line: not line.strip(), fd)
        bug_name = next(lines).strip()

        number_by_country = dict(it.chain.from_iterable(
            parse_bug_number_per_country(line)
            for line in lines
            if line.strip()
        ))
        return bug_name, number_by_country


def render_to_csv(bug_info_by_name, csv_delimiter=DEFAULT_CSV_DELIMITER):
    """dict[str, dict[str, str]] -> str -> str"""

    buffer_ = StringIO.StringIO()
    writer = csv.writer(buffer_, delimiter=csv_delimiter)
    bug_names = []

    rows_by_country = collections.defaultdict(lambda: ['-'] * len(bug_info_by_name))

    all_countries = set(it.chain.from_iterable(
        number_by_country
        for number_by_country in bug_info_by_name.viewvalues()
    ))

    for idx, (bug_name, number_by_country) in enumerate(bug_info_by_name.viewitems()):
        bug_names.append(bug_name)
        for country in all_countries:
            if country in number_by_country:
                rows_by_country[country][idx] = number_by_country.get(country)

    writer.writerow([REGION_CELL_NAME] + bug_names)
    for country in sorted(rows_by_country):
        writer.writerow([country] + rows_by_country.get(country))
    return buffer_.getvalue()


def read_csv(csv_file, delimiter=DEFAULT_CSV_DELIMITER, encoding=DEFAULT_ENCODING):
    """str -> str -> str -> dict[str, dict[str, str]]"""
    with codecs.open(csv_file, "r", encoding=encoding) as fd:
        reader = csv.reader(fd, delimiter=delimiter)
        header = next(reader)

        bug_names = header[1:]

        bug_info_by_name = collections.defaultdict(dict)

        for row in it.ifilter(bool, reader):
            region_name = row[0]
            for bug_name, number in it.izip(bug_names, row[1:]):
                if number is not '-':
                    bug_info_by_name[bug_name][region_name] = number
        return bug_info_by_name


def read_mapping_files(path, encoding=DEFAULT_ENCODING):
    """Read special mapping file and represent content as a dict.
    Every line of the file has the following format::

        N description

    Return mapping of description to N

    str -> str -> dict[str, int]
    """
    line_re = re.compile("(\d+)\s+?(.*)")

    def parse_line(line):
        n, description = line_re.match(line).groups()
        return description.strip(), int(n)

    with codecs.open(path, "r+", encoding=DEFAULT_ENCODING) as fd:
        return dict(
            parse_line(line)
            for line in fd
            if line
        )


def walk_tree(tree):
    """dict[N, dict[K, V]] -> Generator[tuple[N, K, V]]"""
    for n, sub_tree in tree.items():
        for k, v in sub_tree.items():
            yield n, k, v


def reducer(accumulator_fn, bug_info_by_name):
    """(tuple -> dict[str, int] -> dict[str, int]) -> dict[str, dict[str, str]] -> dict[str, int]"""
  return reduce(
        accumulator_fn,
        walk_tree(bug_info_by_name),
        collections.defaultdict(int))


if __name__ == '__main__':
    try:
        main(docopt.docopt(__doc__, version=__version__))
    except KeyboardInterrupt:
        print('Interrupted from keyboard')
        sys.exit(1)
