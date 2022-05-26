"""Test the FLAMEO wrapper function used for fMRS second level group analysis

Test functions that appear in utils.fmrs_tools.flame module

Copyright Will Clarke, University of Oxford, 2022"""

import numpy as np

from fsl_mrs.utils.fmrs_tools import flame


def test_flameo_wrapper():

    # Test 1 - single group average
    cope = np.ones((10, 1))
    varcope = 1E-5 * np.ones((10, 1))
    z, out_cope, out_varcope = flame.flameo_wrapper(cope, varcope)

    assert np.isclose(z, 10.107995)
    assert np.isclose(out_cope, 1)
    assert np.isclose(out_varcope, 1E-6)

    # Test 2 - multiple values
    cope = np.ones((10, 2))
    varcope = 1E-5 * np.ones((10, 2))
    z, out_cope, out_varcope = flame.flameo_wrapper(cope, varcope)

    assert np.allclose(z, 10.107995)
    assert np.allclose(out_cope, 1)
    assert np.allclose(out_varcope, 1E-6)

    # Test 3 - unpaired group differences (and mean) - matched covariance
    cope = np.concatenate((np.ones((10, 2)), [0, 2] * np.ones((10, 2))))
    varcope = 1E-5 * np.ones((20, 2))
    mats = {'desmat': np.block([[np.ones((10, 1)), np.zeros((10, 1))], [np.zeros((10, 1)), np.ones((10, 1))]]),
            'conmat': np.array([[1, -1], [-1, 1], [1, 0], [0, 1], [0.5, 0.5]]),
            'covmat': np.ones((20, 1))}

    z, out_cope, out_varcope = flame.flameo_wrapper(
        cope,
        varcope,
        design_mat=mats['desmat'],
        contrast_mat=mats['conmat'],
        covariace_mat=mats['covmat'])

    ztrue = np.array([
        [13.486302, -13.486302],
        [-13.486302, 13.486302],
        [13.938844, 13.938844],
        [0.0, 14.802881],
        [13.486302, 14.874]])
    oc_true = np.array([
        [1., -1.],
        [-1., 1.],
        [1., 1.],
        [0., 2.],
        [0.5, 1.5]])

    assert np.allclose(z, ztrue)
    assert np.allclose(out_cope, oc_true)
    assert out_varcope.shape == (5, 2)
