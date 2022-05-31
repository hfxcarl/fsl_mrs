#!/usr/bin/env python

# merge_mrs_reports - merge HTML reports
#
# Author: Saad Jbabdi <saad@fmrib.ox.ac.uk>
#         William Clarke <william.clarke@ndcn.ox.ac.uk>
#
# Copyright (C) 2020 University of Oxford
# SHBASECOPYRIGHT

# Quick imports
import argparse
from bs4 import BeautifulSoup
import copy
import os.path as op
from os import remove


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="FSL Magnetic Resonance Spectroscopy"
                    " - Merge HTML reports based on filename in directory.")

    parser.add_argument('files', type=str, nargs='+', metavar='<str>',
                        help='List of input files')

    required = parser.add_argument_group('required arguments')
    optional = parser.add_argument_group('additional options')

    # REQUIRED ARGUMENTS
    required.add_argument('-d', '--description',
                          required=True, type=str, metavar='<str>',
                          help='Dataset description.')

    # ADDITONAL OPTIONAL ARGUMENTS
    optional.add_argument('-o', '--output',
                          required=False, type=str, metavar='<str>',
                          default='.',
                          help='output folder (default=current directory)')
    optional.add_argument('-f', '--filename', type=str, metavar='<str>',
                          default='mergedReports.html',
                          help='Output filename (default=mergedReports.html).')

    optional.add_argument('--delete', action="store_true",
                          help='Delete files after successful merge.')

    # Parse command-line arguments
    args = parser.parse_args()

    # Sort files by filename
    files = sorted(args.files)

    soups = []
    for f in files:
        with open(f) as fp:
            soups.append(BeautifulSoup(fp, features="html.parser"))

    # Append other body elements to the first.
    # Only use the second element of the bodies.
    # WTC: Not sure why (1st and 3rd are just newlines)
    outsoup = copy.deepcopy(soups[0])
    for ss in soups[1:]:
        toappend = ss.body.contents[1]
        toappend.header.clear()
        outsoup.body.append(toappend)

    description = args.description
    outsoup.body.header.h1.string = f"Combined report for {description}"
    outsoup.body.header.p.string = "Combined using merge_mrs_reports." \
                                   " Part of the FSL-MRS package."

    outfile = op.join(args.output, args.filename)
    with open(outfile, 'w') as fout:
        fout.write(str(outsoup))
    if op.exists(outfile) and op.getsize(outfile) > 0:
        if args.delete:
            for htmlfile in files:
                remove(htmlfile)
    else:
        raise IOError('Merged file not written successfully.')


if __name__ == '__main__':
    main()
