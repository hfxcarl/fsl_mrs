#!/usr/bin/env python

# fsl_mrs_proc - script for individual MRS preprocessing stages
#
# Author:   Will Clarke <william.clarke@ndcn.ox.ac.uk>
#           Saad Jbabdi <saad@fmrib.ox.ac.uk>
#
# Copyright (C) 2020 University of Oxford
# SHBASECOPYRIGHT

# Imports
from fsl_mrs.auxiliary import configargparse
from fsl_mrs import __version__
from fsl_mrs.utils.splash import splash
from os import makedirs
from shutil import rmtree
import os.path as op
from fsl_mrs.utils.preproc import nifti_mrs_proc as preproc
from fsl_mrs.core import NIFTI_MRS, is_nifti_mrs
from dataclasses import dataclass


class InappropriateDataError(Exception):
    pass


class ArgumentError(Exception):
    pass


@dataclass
class datacontainer:
    '''Class for keeping track of data and reference data together.'''
    data: NIFTI_MRS
    datafilename: str
    reference: NIFTI_MRS = None
    reffilename: str = None


def main():
    # Parse command-line arguments
    p = configargparse.ArgParser(
        add_config_file_help=False,
        description="FSL Magnetic Resonance Spectroscopy - Preprocessing")

    p.add_argument('-v', '--version', action='version', version=__version__)
    p.add('--config',
          required=False,
          is_config_file=True,
          help='configuration file')

    sp = p.add_subparsers(title='subcommands',
                          description='Preprocessing subcommands',
                          required=True,
                          dest='subcommand')

    # Coil combination subcommand
    ccparser = sp.add_parser('coilcombine',
                             help='Combine coils.',
                             add_help=False)
    cc_group = ccparser.add_argument_group('coilcombine arguments')
    cc_group.add_argument('--file', type=str, required=True,
                          help='Uncombined coil data file(s)')
    cc_group.add_argument('--reference', type=str, required=False,
                          help='Water unsuppressed reference data')
    cc_group.add_argument('--no_prewhiten', action="store_false",
                          help="Don't prewhiten data before coil combination")
    ccparser.set_defaults(func=coilcombine)
    add_common_args(ccparser)

    # Average subcommand
    avgparser = sp.add_parser('average', help='Average FIDs.', add_help=False)
    avg_group = avgparser.add_argument_group('average arguments')
    avg_group.add_argument('--file', type=str, required=True,
                           help='MRS file(s)')
    avg_group.add_argument('--dim', type=str,
                           help='Select dimension to average across')
    avgparser.set_defaults(func=average)
    add_common_args(avgparser)

    # Align subcommand - frequency/phase alignment
    alignparser = sp.add_parser('align', help='Align FIDs.', add_help=False)
    align_group = alignparser.add_argument_group('Align arguments')
    align_group.add_argument('--file', type=str, required=True,
                             help='List of files to align')
    align_group.add_argument('--dim', type=str, default='DIM_DYN',
                             help='NIFTI-MRS dimension tag to align across.'
                                  'Or "all" to align over all spectra in higer dimensions.'
                                  'Default = DIM_DYN')
    align_group.add_argument('--ppm', type=float, nargs=2,
                             metavar=('<lower-limit>', '<upper-limit>'),
                             default=(0.2, 4.2),
                             help='ppm limits of alignment window'
                                  ' (default=0.2->4.2)')
    align_group.add_argument('--reference', type=str, required=False,
                             help='Align to this reference data.')
    align_group.add_argument('--apod', type=float, default=10,
                             help='Apodise data to reduce noise (Hz).')
    alignparser.set_defaults(func=align)
    add_common_args(alignparser)

    # Align difference spectra subcommand - frequency/phase alignment
    alignDparser = sp.add_parser('align-diff', add_help=False,
                                 help='Align subspectra for differencing.')
    alignD_group = alignDparser.add_argument_group('Align subspec arguments')
    alignD_group.add_argument('--file', type=str, required=True,
                              help='Subspectra 1 - List of files to align')
    alignD_group.add_argument('--dim', type=str, default='DIM_DYN',
                              help='NIFTI-MRS dimension tag to align across')
    alignD_group.add_argument('--dim_diff', type=str, default='DIM_EDIT',
                              help='NIFTI-MRS dimension tag to difference across')
    alignD_group.add_argument('--ppm', type=float, nargs=2,
                              metavar='<lower-limit upper-limit>',
                              default=(0.2, 4.2),
                              help='ppm limits of alignment window'
                                   ' (default=0.2->4.2)')
    alignD_group.add_argument('--diff_type', type=str, required=False,
                              default='add',
                              help='add (default) or subtract.')
    alignDparser.set_defaults(func=aligndiff)
    add_common_args(alignDparser)

    # ECC subcommand - eddy current correction
    eccparser = sp.add_parser('ecc', add_help=False,
                              help='Eddy current correction')
    ecc_group = eccparser.add_argument_group('ECC arguments')
    ecc_group.add_argument('--file', type=str, required=True,
                           help='Uncombined coil data file(s)')
    ecc_group.add_argument('--reference', type=str, required=True,
                           help='Phase reference data file(s)')
    eccparser.set_defaults(func=ecc)
    add_common_args(eccparser)

    # remove subcommand - remove peak using HLSVD
    hlsvdparser = sp.add_parser('remove', add_help=False,
                                help='Remove peak (default water) with HLSVD.')
    hlsvd_group = hlsvdparser.add_argument_group('HLSVD arguments')
    hlsvd_group.add_argument('--file', type=str, required=True,
                             help='Data file(s)')
    hlsvd_group.add_argument('--ppm', type=float, nargs=2,
                             metavar='<lower-limit upper-limit>',
                             default=[4.5, 4.8],
                             help='ppm limits of removal window.'
                                  ' Defaults to 4.5 to 4.8 ppm.'
                                  ' Includes (4.65 ppm) shift to TMS reference.')
    hlsvdparser.set_defaults(func=remove)
    add_common_args(hlsvdparser)

    # model subcommand - model peaks using HLSVD
    modelparser = sp.add_parser('model', add_help=False,
                                help='Model peaks with HLSVD.')
    model_group = modelparser.add_argument_group('HLSVD modelling arguments')
    model_group.add_argument('--file', type=str, required=True,
                             help='Data file(s)')
    model_group.add_argument('--ppm', type=float, nargs=2,
                             metavar='<lower-limit upper-limit>',
                             default=[4.5, 4.8],
                             help='ppm limits of removal window')
    model_group.add_argument('--components', type=int,
                             default=5,
                             help='Number of components to model.')
    modelparser.set_defaults(func=model)
    add_common_args(modelparser)

    # tshift subcommand - shift/resample in timedomain
    tshiftparser = sp.add_parser('tshift', add_help=False,
                                 help='shift/resample in timedomain.')
    tshift_group = tshiftparser.add_argument_group('Time shift arguments')
    tshift_group.add_argument('--file', type=str, required=True,
                              help='Data file(s) to shift')
    tshift_group.add_argument('--tshiftStart', type=float, default=0.0,
                              help='Time shift at start (ms),'
                                   ' negative pads with zeros,'
                                   ' positive truncates')
    tshift_group.add_argument('--tshiftEnd', type=float, default=0.0,
                              help='Time shift at end (ms),'
                                   ' negative truncates,'
                                   ' positive pads with zeros')
    tshift_group.add_argument('--samples', type=int,
                              help='Resample to N points in FID.')
    tshiftparser.set_defaults(func=tshift)
    add_common_args(tshiftparser)

    # truncate
    truncateparser = sp.add_parser('truncate', add_help=False,
                                   help='truncate or pad by integer'
                                        ' points in timedomain.')
    truncate_group = truncateparser.add_argument_group(
        'Truncate/pad arguments')
    truncate_group.add_argument('--file', type=str, required=True,
                                help='Data file(s) to shift')
    truncate_group.add_argument('--points', type=int, default=0,
                                help='Points to add/remove (+/-)')
    truncate_group.add_argument('--pos', type=str, default='last',
                                help="'first' or 'last' (default)")
    truncateparser.set_defaults(func=truncate)
    add_common_args(truncateparser)

    # apodize
    apodparser = sp.add_parser('apodize', help='Apodize FID.', add_help=False)
    apod_group = apodparser.add_argument_group('Apodize arguments')
    apod_group.add_argument('--file', type=str, required=True,
                            help='Data file(s) to shift')
    apod_group.add_argument('--filter', type=str, default='exp',
                            help="Filter choice."
                                 "Either 'exp' (default) or 'l2g'.")
    apod_group.add_argument('--amount', type=float, nargs='+',
                            help='Amount of broadening.'
                                 ' In Hz for exp mode.'
                                 ' Use space separated list for l2g.')
    apodparser.set_defaults(func=apodize)
    add_common_args(apodparser)

    # fshift subcommand - shift in frequency domain
    fshiftparser = sp.add_parser('fshift', add_help=False,
                                 help='shift in frequency domain.')
    fshift_group = fshiftparser.add_argument_group('Frequency shift arguments')
    fshift_group.add_argument('--file', type=str, required=True,
                              help='Data file(s) to shift')
    fshift_group.add_argument('--shiftppm', type=float,
                              help='Apply fixed shift (ppm scale)')
    fshift_group.add_argument('--shifthz', type=float,
                              help='Apply fixed shift (Hz scale)')
    fshift_group.add_argument('--shiftRef', action="store_true",
                              help='Shift to reference (default = Cr)')
    fshift_group.add_argument('--ppm', type=float, nargs=2,
                              metavar='<lower-limit upper-limit>',
                              default=(2.8, 3.2),
                              help='Shift maximum point in this range'
                                   ' to target (must specify --target).')
    fshift_group.add_argument('--target', type=float, default=3.027,
                              help='Target position (must be used with ppm).'
                                   ' Default = 3.027')
    fshiftparser.set_defaults(func=fshift)
    add_common_args(fshiftparser)

    # unlike subcomand - find FIDs that are unlike
    unlikeparser = sp.add_parser('unlike', add_help=False,
                                 help='Identify unlike FIDs.')
    unlike_group = unlikeparser.add_argument_group('unlike arguments')
    unlike_group.add_argument('--file', type=str, required=True,
                              help='Data file(s) to shift')
    unlike_group.add_argument('--sd', type=float, default=1.96,
                              help='Exclusion limit'
                                   ' (# of SD from mean,default=1.96)')
    unlike_group.add_argument('--iter', type=int, default=2,
                              help='Iterations of algorithm.')
    unlike_group.add_argument('--ppm', type=float, nargs=2,
                              metavar='<lower-limit upper-limit>',
                              default=None,
                              help='ppm limits of alignment window')
    unlike_group.add_argument('--outputbad', action="store_true",
                              help='Output failed FIDs')
    unlikeparser.set_defaults(func=unlike)
    add_common_args(unlikeparser)

    # Phasing - based on maximum point in range
    phaseparser = sp.add_parser('phase', add_help=False,
                                help='Phase spectrum based on'
                                     ' maximum point in range')
    phase_group = phaseparser.add_argument_group('Phase arguments')
    phase_group.add_argument('--file', type=str, required=True,
                             help='Data file(s) to shift')
    phase_group.add_argument('--ppm', type=float, nargs=2,
                             metavar='<lower-limit upper-limit>',
                             default=(2.8, 3.2),
                             help='ppm limits of alignment window')
    phase_group.add_argument('--hlsvd', action="store_true",
                             help='Remove peaks outside the search area')
    phaseparser.set_defaults(func=phase)
    add_common_args(phaseparser)

    fixphaseparser = sp.add_parser('fixed_phase', add_help=False,
                                   help='Apply fixed phase to spectrum')
    fphase_group = fixphaseparser.add_argument_group('Phase arguments')
    fphase_group.add_argument('--file', type=str, required=True,
                              help='Data file(s) to shift')
    fphase_group.add_argument('--p0', type=float,
                              metavar='<degrees>',
                              help='Zero order phase (degrees)')
    fphase_group.add_argument('--p1', type=float,
                              default=0.0,
                              metavar='<seconds>',
                              help='First order phase (seconds)')
    fixphaseparser.set_defaults(func=fixed_phase)
    add_common_args(fixphaseparser)

    # subtraction - subtraction of FIDs
    subtractparser = sp.add_parser('subtract', add_help=False,
                                   help='Subtract two FID files or across a dimension')
    subtract_group = subtractparser.add_argument_group('Subtraction arguments')
    subtract_group.add_argument('--file', type=str, required=True,
                                help='File to subtract from')
    subtract_group.add_argument('--reference', type=str,
                                help='File to subtract from --file'
                                     '(output is file - reference)')
    subtract_group.add_argument('--dim', type=str,
                                help='NIFTI-MRS dimension tag to subtract across')
    subtractparser.set_defaults(func=subtract)
    add_common_args(subtractparser)

    # add - addition of FIDs
    addparser = sp.add_parser('add', add_help=False, help='Add two FIDs or across a dimension')
    add_group = addparser.add_argument_group('Addition arguments')
    add_group.add_argument('--file', type=str, required=True,
                           help='File to add to.')
    add_group.add_argument('--reference', type=str,
                           help='File to add to --file')
    add_group.add_argument('--dim', type=str,
                           help='NIFTI-MRS dimension tag to add across')
    addparser.set_defaults(func=add)
    add_common_args(addparser)

    # conj - conjugation
    conjparser = sp.add_parser('conj', add_help=False, help='Conjugate fids')
    conj_group = conjparser.add_argument_group('Conjugation arguments')
    conj_group.add_argument('--file', type=str, required=True,
                            help='Data file(s) to conjugate')
    conj_group.set_defaults(func=conj)
    add_common_args(conj_group)

    # Parse command-line arguments
    args = p.parse_args()

    # Output kickass splash screen
    if args.verbose:
        splash(logo='mrs')

    # Parse file arguments
    datafiles, reffiles = parsefilearguments(args)

    # Handle data loading
    dataList = loadData(datafiles,
                        refdatafile=reffiles)

    # Create output folder if required
    if not op.isdir(args.output):
        makedirs(args.output)
    elif op.isdir(args.output) and args.overwrite:
        rmtree(args.output)
        makedirs(args.output)

    # Handle report generation output location.
    # Bit of a hack, but I messed up the type expected by the
    # nifti mrs proc functions.
    if args.generateReports:
        args.generateReports = args.output
    else:
        args.generateReports = None

    # Call function - pass dict like view of args
    #  for compatibility with other modules
    dataout = args.func(dataList, vars(args))
    if isinstance(dataout, tuple):
        additionalOutputs = dataout[1:]
        dataout = dataout[0]
    else:
        additionalOutputs = None

    # Write data
    writeData(dataout, args)

    # Output any additional arguments
    if additionalOutputs is not None:
        print(additionalOutputs)


def add_common_args(p):
    """Add any arguments which are common between the sub commands."""
    # This is so the arguments can appear after the subcommand.

    # Arguments not associated with subcommands
    required = p.add_argument_group('required arguments')
    optional = p.add_argument_group('additional options')

    # REQUIRED ARGUMENTS
    required.add_argument('--output',
                          required=True, type=str, metavar='<str>',
                          help='output folder')

    # ADDITIONAL OPTIONAL ARGUMENTS
    optional.add_argument('--overwrite', action="store_true",
                          help='overwrite existing output folder')
    optional.add_argument('-r', '--generateReports', action="store_true",
                          help='Generate HTML reports.')
    # optional.add_argument('-i', '--reportIndicies',
    #                       type=int,
    #                       nargs='+',
    #                       default=[0],
    #                       help='Generate reports for selected inputs where'
    #                            ' multiple input files exist.'
    #                            ' Defaults to first (0).'
    #                            ' Specify as indices counting from 0.')
    optional.add_argument('--allreports', action="store_true",
                          help='Generate reports for all inputs.')
    # optional.add_argument('--conjugate', action="store_true",
    #                       help='apply conjugate to FID')
    optional.add_argument('--filename', type=str, metavar='<str>',
                          help='Override output file name.')
    optional.add_argument('--verbose', action="store_true",
                          help='spit out verbose info')
    optional.add_argument('-h', '--help', action='help',
                          help='show this help message and exit')


def parsefilearguments(args):
    # print(args.file)
    datafiles = args.file
    if 'reference' in args:
        # print(args.reference)
        reffiles = args.reference
    else:
        reffiles = None

    return datafiles, reffiles


# Data I/O functions
def loadData(datafile, refdatafile=None):
    """ Load data from path.

    The data must be of NIFTI MRS format.
    Optionaly loads a reference file.
    """

    # Do a check on the data file passed. The data must be of nifti type.
    if not is_nifti_mrs(datafile):
        raise ValueError('Preprocessing routines only handle NIFTI MRS'
                         ' format data. Please convert your data using'
                         ' spec2nii.')

    if refdatafile and not is_nifti_mrs(refdatafile):
        raise ValueError('Preprocessing routines only handle NIFTI MRS'
                         ' format data. Please convert your data using'
                         ' spec2nii.')

    if refdatafile:
        loaded_data = datacontainer(NIFTI_MRS(datafile),
                                    op.basename(datafile),
                                    NIFTI_MRS(refdatafile),
                                    op.basename(datafile))
    else:
        loaded_data = datacontainer(NIFTI_MRS(datafile),
                                    op.basename(datafile))

    return loaded_data


def writeData(dataobj, args):

    if args.filename is None:
        fileout = op.join(args.output, dataobj.datafilename)
    else:
        fileout = op.join(args.output, args.filename + '.nii.gz')

    dataobj.data.save(fileout)


# Option functions
# Functions below here should be associated with a
# subcommand method specified above.
# They should call a method in nifti_mrs_proc.py.

# Preprocessing functions
def coilcombine(dataobj, args):

    if 'DIM_COIL' not in dataobj.data.dim_tags:
        raise InappropriateDataError(f'Data ({dataobj.datafilename}) has no coil dimension.'
                                     f' Dimensions are is {dataobj.data.dim_tags}.')

    combined = preproc.coilcombine(dataobj.data,
                                   reference=dataobj.reference,
                                   no_prewhiten=args['no_prewhiten'],
                                   report=args['generateReports'],
                                   report_all=args['allreports'])

    return datacontainer(combined, dataobj.datafilename)


def average(dataobj, args):
    if args['dim'] not in dataobj.data.dim_tags:
        raise InappropriateDataError(f'Data ({dataobj.datafilename}) has no {args["dim"]} dimension.'
                                     f' Dimensions are is {dataobj.data.dim_tags}.')

    averaged = preproc.average(dataobj.data,
                               args["dim"],
                               report=args['generateReports'],
                               report_all=args['allreports'])

    return datacontainer(averaged, dataobj.datafilename)


def align(dataobj, args):
    if args['dim'].lower() == 'all':
        pass
    elif args['dim'] not in dataobj.data.dim_tags:
        raise InappropriateDataError(f'Data ({dataobj.datafilename}) has no {args["dim"]} dimension.'
                                     f' Dimensions are is {dataobj.data.dim_tags}.')

    aligned = preproc.align(dataobj.data,
                            args['dim'],
                            ppmlim=args['ppm'],
                            apodize=args['apod'],
                            report=args['generateReports'],
                            report_all=args['allreports'])

    return datacontainer(aligned, dataobj.datafilename)


def aligndiff(dataobj, args):
    if args['dim'] not in dataobj.data.dim_tags:
        raise InappropriateDataError(f'Data ({dataobj.datafilename}) has no {args["dim"]} dimension.'
                                     f' Dimensions are is {dataobj.data.dim_tags}.')

    aligned = preproc.aligndiff(dataobj.data,
                                args['dim'],
                                args['dim_diff'],
                                args['diff_type'],
                                ppmlim=args['ppm'],
                                report=args['generateReports'],
                                report_all=args['allreports'])

    return datacontainer(aligned, dataobj.datafilename)


def ecc(dataobj, args):
    corrected = preproc.ecc(dataobj.data,
                            dataobj.reference,
                            report=args['generateReports'],
                            report_all=args['allreports'])

    return datacontainer(corrected, dataobj.datafilename)


def remove(dataobj, args):
    corrected = preproc.remove_peaks(dataobj.data,
                                     limits=args['ppm'],
                                     report=args['generateReports'],
                                     report_all=args['allreports'])

    return datacontainer(corrected, dataobj.datafilename)


def model(dataobj, args):
    modelled = preproc.hlsvd_model_peaks(dataobj.data,
                                         limits=args['ppm'],
                                         components=args['components'],
                                         report=args['generateReports'],
                                         report_all=args['allreports'])

    return datacontainer(modelled, dataobj.datafilename)


def tshift(dataobj, args):
    shifted = preproc.tshift(dataobj.data,
                             tshiftStart=args['tshiftStart'],
                             tshiftEnd=args['tshiftEnd'],
                             samples=args['samples'],
                             report=args['generateReports'],
                             report_all=args['allreports'])

    return datacontainer(shifted, dataobj.datafilename)


def truncate(dataobj, args):
    truncated = preproc.truncate_or_pad(dataobj.data,
                                        args['points'],
                                        args['pos'],
                                        report=args['generateReports'],
                                        report_all=args['allreports'])

    return datacontainer(truncated, dataobj.datafilename)


def apodize(dataobj, args):
    apodized = preproc.truncate_or_pad(dataobj.data,
                                       args['amount'],
                                       filter=args['filter'],
                                       report=args['generateReports'],
                                       report_all=args['allreports'])

    return datacontainer(apodized, dataobj.datafilename)


def fshift(dataobj, args):
    if args['shiftppm'] is not None:
        shift = args['shiftppm'] * dataobj.data.spectrometer_frequency[0]
        callMode = 'fixed'
    elif args['shifthz'] is not None:
        shift = args['shifthz']
        callMode = 'fixed'
    elif args['shiftRef']:
        callMode = 'ref'
    else:
        raise ArgumentError('Specify --shiftppm or --shifthz.')

    if callMode == 'fixed':
        shifted = preproc.fshift(dataobj.data,
                                 shift,
                                 report=args['generateReports'],
                                 report_all=args['allreports'])

    elif callMode == 'ref':
        shifted = preproc.shift_to_reference(dataobj.data,
                                             args['target'],
                                             args['ppm'],
                                             report=args['generateReports'],
                                             report_all=args['allreports'])

    return datacontainer(shifted, dataobj.datafilename)


def unlike(dataobj, args):
    if dataobj.data.shape[:3] != (1, 1, 1):
        raise InappropriateDataError('unlike subcommand only works on single voxel data.'
                                     ' It is unclear what should happen with MRSI data.')

    good, bad = preproc.shift_to_reference(dataobj.data,
                                           ppmlim=args['ppm'],
                                           sdlimit=args['sd'],
                                           iterations=args['iter'],
                                           report=args['generateReports'])

    if args['outputbad']:
        # Save bad results here - bit of a hack!
        bad.save(op.join(args.output, dataobj.datafilename + '_FAIL'))

    return datacontainer(good, dataobj.datafilename)


def phase(dataobj, args):
    phased = preproc.phase_correct(dataobj.data,
                                   args['ppm'],
                                   hlsvd=args['hlsvd'],
                                   report=args['generateReports'],
                                   report_all=args['allreports'])

    return datacontainer(phased, dataobj.datafilename)


def fixed_phase(dataobj, args):
    phased = preproc.apply_fixed_phase(dataobj.data,
                                       args['p0'],
                                       p1=args['p1'],
                                       report=args['generateReports'],
                                       report_all=args['allreports'])

    return datacontainer(phased, dataobj.datafilename)


def subtract(dataobj, args):
    if dataobj.reference is not None:
        subtracted = preproc.subtract(dataobj.data,
                                      data1=dataobj.reference,
                                      report=args['generateReports'],
                                      report_all=args['allreports'])
    elif args['dim'] is not None:
        subtracted = preproc.subtract(dataobj.data,
                                      dim=args['dim'],
                                      report=args['generateReports'],
                                      report_all=args['allreports'])
    else:
        raise ArgumentError('Specify --reference or --dim.')

    return datacontainer(subtracted, dataobj.datafilename)


def add(dataobj, args):
    if dataobj.reference is not None:
        added = preproc.add(dataobj.data,
                            data1=dataobj.reference,
                            report=args['generateReports'],
                            report_all=args['allreports'])
    elif args['dim'] is not None:
        added = preproc.add(dataobj.data,
                            dim=args['dim'],
                            report=args['generateReports'],
                            report_all=args['allreports'])
    else:
        raise ArgumentError('Specify --reference or --dim.')

    return datacontainer(added, dataobj.datafilename)


def conj(dataobj, args):
    conjugated = preproc.conjugate(dataobj.data,
                                   report=args['generateReports'],
                                   report_all=args['allreports'])

    return datacontainer(conjugated, dataobj.datafilename)


if __name__ == '__main__':
    main()
