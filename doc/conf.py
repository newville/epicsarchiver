# -*- coding: utf-8 -*-
#

import os, sys, sphinx_rtd_theme

project = 'epicsarchiver'
copyright = 'Matthew Newville, The University of Chicago'
version = release = '2.1'


extensions = ['sphinx.ext.todo', 'sphinx.ext.autodoc',
              'sphinx.ext.mathjax', 'sphinx.ext.extlinks',
              'sphinxcontrib.napoleon', 'sphinxcontrib.bibtex' ]

intersphinx_mapping = {'py': ('https://docs.python.org/3/', None)}

templates_path = ['_templates']
source_suffix = '.rst'
source_encoding = 'utf-8'

master_doc = 'index'

exclude_trees = ['_build']

add_function_parentheses = True
add_module_names = False
todo_include_todos = True

today_fmt = '%Y-%B-%d'

pygments_style = 'sphinx'
html_theme = 'pyramid'

html_title = 'Epics PV Archiver'
html_short_title = 'Epics PV Archiver'
htmlhelp_basename = 'epics_pvarchiver'

html_static_path = ['_static']
html_last_updated_fmt = '%Y-%B-%d'
html_show_sourcelink = True
html_favicon = '_static/gse_logo.ico'

html_sidebars = {'index': ['indexsidebar.html','searchbox.html']}
html_show_sourcelink = True
