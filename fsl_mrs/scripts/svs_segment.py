#!/usr/bin/env python

# svs_segment - use fsl to make a mask from a svs voxel and T1 nifti,
# then produce tissue segmentation file.
#
# Author: Saad Jbabdi <saad@fmrib.ox.ac.uk>
#         William Clarke <william.clarke@ndcn.ox.ac.uk>
#
# Copyright (C) 2020 University of Oxford
# SHBASECOPYRIGHT

# Quick imports
import argparse
import os.path as op
from os import remove
import nibabel as nib
import numpy as np
from fsl.wrappers import flirt, fslstats, fsl_anat, fslmaths
import json
import warnings


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="FSL Magnetic Resonance Spectroscopy"
                    " - Construct mask in T1 space of an SVS voxel"
                    " and generate a tissue segmentation file.")

    parser.add_argument('svs', type=str, metavar='SVS',
                        help='SVS nifti file')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-t', '--t1', type=str, metavar='T1',
                       help='T1 nifti file')
    group.add_argument('-a', '--anat', type=str,
                       help='fsl_anat output directory.')
    parser.add_argument('-o', '--output', type=str,
                        help='Output directory', default='.')
    parser.add_argument('-f', '--filename', type=str,
                        help='file name stem. _mask.nii.gz'
                             ' or _segmentation.json will be added.',
                        default=None)
    parser.add_argument('-m', '--mask_only', action="store_true",
                        help='Only perform masking stage,'
                             ' do not run fsl_anat if only T1 passed.')
    parser.add_argument('--no_clean', action="store_false",
                        help="Don't clean intermediate output.", dest='clean')
    args = parser.parse_args()

    # If not prevented run fsl_anat for fast segmentation
    if (args.anat is None) and (not args.mask_only):
        anat = op.join(args.output, 'fsl_anat')
        fsl_anat(args.t1, out=anat, nosubcortseg=True)
        anat += '.anat'
    else:
        anat = args.anat

    data_hdr = nib.load(args.svs)

    # Create 3D mock data
    mockData = np.zeros((2, 2, 2))
    mockData[0, 0, 0] = 1.0
    img = nib.Nifti1Image(mockData, affine=data_hdr.affine)

    flirt_in = op.join(args.output, 'tmp_mask.nii')
    nib.save(img, flirt_in)

    # Run flirt
    if anat is not None:
        flirt_ref = op.join(anat, 'T1_biascorr.nii.gz')
    else:
        flirt_ref = args.t1

    if args.filename is None:
        mask_name = 'mask.nii.gz'
    else:
        mask_name = args.filename + '_mask.nii.gz'
    flirt_out = op.join(args.output, mask_name)

    flirt(flirt_in,
          flirt_ref,
          out=flirt_out,
          usesqform=True,
          applyxfm=True,
          noresampblur=True,
          interp='nearestneighbour',
          setbackground=0,
          paddingsize=1)

    # Clean up
    if args.clean:
        remove(flirt_in)

    # Provide tissue segmentation if anat is available
    if anat is not None:
        # Check that the svs mask intersects with brain, issue warning if not.
        fslmaths(flirt_out).add(
            op.join(anat, 'T1_biascorr_brain_mask.nii.gz')) \
            .mas(flirt_out).run(op.join(args.output, 'tmp.nii.gz'))

        meanInVox = fslstats(op.join(args.output, 'tmp.nii.gz')).M.run()
        if meanInVox < 2.0:
            warnings.warn('The mask does not fully intersect'
                          ' with the brain mask. Check manually.')

        if args.clean:
            remove(op.join(args.output, 'tmp.nii.gz'))

        # Count up segmentation values in mask.
        seg_csf = op.join(anat, 'T1_fast_pve_0.nii.gz')
        seg_gm = op.join(anat, 'T1_fast_pve_1.nii.gz')
        seg_wm = op.join(anat, 'T1_fast_pve_2.nii.gz')

        # fslstats -t /fast_output/fast_output_pve_0 -k SVS_mask.nii –m
        CSF = fslstats(seg_csf).k(flirt_out).m.run()
        GM = fslstats(seg_gm).k(flirt_out).m.run()
        WM = fslstats(seg_wm).k(flirt_out).m.run()
        print(f'CSF: {CSF:0.2f}, GM: {GM:0.2f}, WM: {WM:0.2f}.')
        segresults = {'CSF': CSF, 'GM': GM, 'WM': WM}

        if args.filename is None:
            seg_name = 'segmentation.json'
        else:
            seg_name = args.filename + '_segmentation.json'

        with open(op.join(args.output, seg_name), 'w', encoding='utf-8') as f:
            json.dump(segresults, f, ensure_ascii=False, indent='\t')


if __name__ == '__main__':
    main()
