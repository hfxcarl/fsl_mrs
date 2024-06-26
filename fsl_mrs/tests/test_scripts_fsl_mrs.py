'''FSL-MRS test script

Test the main svs fitting script

Copyright Will Clarke, University of Oxford, 2021'''

# Imports
import subprocess
import os.path as op

# Files
testsPath = op.dirname(__file__)
data = {'metab': op.join(testsPath, 'testdata/fsl_mrs/metab.nii.gz'),
        'water': op.join(testsPath, 'testdata/fsl_mrs/wref.nii.gz'),
        'basis': op.join(testsPath, 'testdata/fsl_mrs/steam_basis'),
        'basis_default': op.join(testsPath, 'testdata/fsl_mrs/steam_basis_default_mm'),
        'seg': op.join(testsPath, 'testdata/fsl_mrs/segmentation.json')}


def test_fsl_mrs(tmp_path):

    subprocess.check_call(['fsl_mrs',
                           '--data', data['metab'],
                           '--basis', data['basis'],
                           '--output', tmp_path,
                           '--h2o', data['water'],
                           '--TE', '11',
                           '--metab_groups', 'Mac',
                           '--tissue_frac', '0.45', '0.45', '0.1',
                           '--overwrite',
                           '--combine', 'Cr', 'PCr'])

    subprocess.check_call(['fsl_mrs',
                           '--data', data['metab'],
                           '--basis', data['basis'],
                           '--output', tmp_path,
                           '--h2o', data['water'],
                           '--TE', '11',
                           '--metab_groups', 'Mac',
                           '--tissue_frac', data['seg'],
                           '--overwrite',
                           '--combine', 'Cr', 'PCr',
                           '--report'])

    assert op.exists(op.join(tmp_path, 'report.html'))
    assert op.exists(op.join(tmp_path, 'summary.csv'))
    assert op.exists(op.join(tmp_path, 'concentrations.csv'))
    assert op.exists(op.join(tmp_path, 'qc.csv'))
    assert op.exists(op.join(tmp_path, 'all_parameters.csv'))
    assert op.exists(op.join(tmp_path, 'options.txt'))
    assert op.exists(op.join(tmp_path, 'data.nii.gz'))
    assert op.exists(op.join(tmp_path, 'basis'))
    assert op.exists(op.join(tmp_path, 'h2o.nii.gz'))


def test_no_fractions(tmp_path):

    subprocess.check_call(['fsl_mrs',
                           '--data', data['metab'],
                           '--basis', data['basis'],
                           '--output', tmp_path,
                           '--h2o', data['water'],
                           '--TE', '11',
                           '--metab_groups', 'Mac',
                           '--overwrite',
                           '--combine', 'Cr', 'PCr',
                           '--report'])

    assert op.exists(op.join(tmp_path, 'report.html'))
    assert op.exists(op.join(tmp_path, 'summary.csv'))
    assert op.exists(op.join(tmp_path, 'concentrations.csv'))
    assert op.exists(op.join(tmp_path, 'qc.csv'))
    assert op.exists(op.join(tmp_path, 'all_parameters.csv'))
    assert op.exists(op.join(tmp_path, 'options.txt'))
    assert op.exists(op.join(tmp_path, 'data.nii.gz'))
    assert op.exists(op.join(tmp_path, 'basis'))
    assert op.exists(op.join(tmp_path, 'h2o.nii.gz'))

    # Check quantification section included
    from bs4 import BeautifulSoup
    with open(op.join(tmp_path, 'report.html')) as fp:
        soup = BeautifulSoup(fp, features="html.parser")
    assert soup.find_all("a", attrs={'name': "quantification"}) is not None


def test_no_ref(tmp_path):
    subprocess.check_call(['fsl_mrs',
                           '--data', data['metab'],
                           '--basis', data['basis'],
                           '--output', tmp_path,
                           '--metab_groups', 'Mac',
                           '--overwrite',
                           '--combine', 'Cr', 'PCr',
                           '--report'])

    assert op.exists(op.join(tmp_path, 'report.html'))


def test_alt_ref(tmp_path):

    subprocess.check_call(['fsl_mrs',
                           '--data', data['metab'],
                           '--basis', data['basis'],
                           '--output', tmp_path,
                           '--h2o', data['water'],
                           '--TE', '11',
                           '--metab_groups', 'Mac',
                           '--tissue_frac', '0.45', '0.45', '0.1',
                           '--overwrite',
                           '--combine', 'Cr', 'PCr',
                           '--combine', 'NAA', 'NAAG',
                           '--internal_ref', 'NAA', 'NAAG',
                           '--wref_metabolite', 'PCh',
                           '--ref_protons', '3',
                           '--ref_int_limits', '3.0', '3.4',
                           '--report'])

    assert op.exists(op.join(tmp_path, 'report.html'))
    assert op.exists(op.join(tmp_path, 'summary.csv'))
    assert op.exists(op.join(tmp_path, 'concentrations.csv'))
    assert op.exists(op.join(tmp_path, 'qc.csv'))
    assert op.exists(op.join(tmp_path, 'all_parameters.csv'))
    assert op.exists(op.join(tmp_path, 'options.txt'))


def test_alt_multiple_ref(tmp_path):

    subprocess.check_call(['fsl_mrs',
                           '--data', data['metab'],
                           '--basis', data['basis'],
                           '--output', tmp_path,
                           '--h2o', data['water'],
                           '--TE', '11',
                           '--metab_groups', 'Mac',
                           '--tissue_frac', '0.45', '0.45', '0.1',
                           '--overwrite',
                           '--combine', 'Cr', 'PCr',
                           '--combine', 'NAA', 'NAAG',
                           '--internal_ref', 'NAA', 'NAAG',
                           '--wref_metabolite', 'PCh', 'GPC',
                           '--ref_protons', '3',
                           '--ref_int_limits', '3.0', '3.4',
                           '--report'])

    assert op.exists(op.join(tmp_path, 'report.html'))
    assert op.exists(op.join(tmp_path, 'summary.csv'))
    assert op.exists(op.join(tmp_path, 'concentrations.csv'))
    assert op.exists(op.join(tmp_path, 'qc.csv'))
    assert op.exists(op.join(tmp_path, 'all_parameters.csv'))
    assert op.exists(op.join(tmp_path, 'options.txt'))


def test_fsl_mrs_default_mm(tmp_path, capfd):

    subprocess.check_call(['fsl_mrs',
                           '--data', data['metab'],
                           '--basis', data['basis_default'],
                           '--output', tmp_path,
                           '--h2o', data['water'],
                           '--TE', '11',
                           '--tissue_frac', '0.45', '0.45', '0.1',
                           '--report',
                           '--overwrite',
                           '--combine', 'Cr', 'PCr'])
    out, _ = capfd.readouterr()
    assert out == (
        'Default macromolecules (MM09, MM12, MM14, MM17, MM21) are present in the '
        'basis set.\n'
        'However they are not all listed in the --metab_groups.\n'
        'It is recommended that all default MM are assigned their own group.\n'
        'E.g. Use --metab_groups MM09 MM12 MM14 MM17 MM21\n')

    subprocess.check_call(['fsl_mrs',
                           '--data', data['metab'],
                           '--basis', data['basis_default'],
                           '--output', tmp_path,
                           '--h2o', data['water'],
                           '--TE', '11',
                           '--metab_groups', 'MM09', 'MM12', 'MM14', 'MM17', 'MM21',
                           '--tissue_frac', '0.45', '0.45', '0.1',
                           '--report',
                           '--overwrite',
                           '--combine', 'Cr', 'PCr'])

    assert op.exists(op.join(tmp_path, 'report.html'))
    assert op.exists(op.join(tmp_path, 'summary.csv'))
    assert op.exists(op.join(tmp_path, 'concentrations.csv'))
    assert op.exists(op.join(tmp_path, 'qc.csv'))
    assert op.exists(op.join(tmp_path, 'all_parameters.csv'))
    assert op.exists(op.join(tmp_path, 'options.txt'))
    assert op.exists(op.join(tmp_path, 'data.nii.gz'))
    assert op.exists(op.join(tmp_path, 'basis'))
    assert op.exists(op.join(tmp_path, 'h2o.nii.gz'))
