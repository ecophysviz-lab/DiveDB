# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

import os
import sys

# Allow autodoc to find the DiveDB package
sys.path.insert(0, os.path.abspath('../../'))
sys.path.insert(0, os.path.abspath('../../DiveDB/'))


# -- Project information -----------------------------------------------------

project = 'DiveDB'
copyright = '2024, Jessica Kendall-Bar'
author = 'Jessica Kendall-Bar'

# The full version, including alpha/beta/rc tags
release = '0.1.0'


# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.mathjax',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = []

# Suppress nitpicky warnings about missing cross-references
nitpicky = False

# Mock heavy dependencies that won't be installed in CI
autodoc_mock_imports = [
    'duckdb',
    'pyiceberg',
    'pyarrow',
    'xarray',
    'netCDF4',
    'dash',
    'plotly',
    'mne',
    'google',
    'google.cloud',
    'boto3',
    's3fs',
    'edfio',
    'notion_client',
    'pyEDFlib',
    'tqdm',
    'requests',
    'dask',
    'pydantic',
    'bs4',
    'dash_bootstrap_components',
    'dash_extensions',
    'numpy',
    'pandas',
    'psycopg2',
    'keystoneclient',
    'swiftclient',
]

# Show both class docstring and __init__ docstring
autoclass_content = 'both'

# Document members in source order
autodoc_member_order = 'bysource'


# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (style sheets, etc.) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
