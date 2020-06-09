extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
]

templates_path = ['.templates']

source_suffix = '.rst'

master_doc = 'index'

project = 'SCPI Middlelayer Device Base'
copyright = '2020, Martin Teichmann'
author = 'Martin Teichmann'

# The short X.Y version.
version = '1.0'
# The full version, including alpha/beta/rc tags.
release = '1.0'

language = None

exclude_patterns = ['.build', 'Thumbs.db', '.DS_Store']

pygments_style = 'sphinx'

todo_include_todos = False


html_theme = 'alabaster'

html_static_path = ['.static']

htmlhelp_basename = 'SCPIMiddlelayerDeviceBasedoc'

latex_elements = {}

latex_documents = [
    (master_doc, 'SCPIMiddlelayerDeviceBase.tex', 'SCPI Middlelayer Device Base Documentation',
     'Martin Teichmann', 'manual'),
]

man_pages = [
    (master_doc, 'scpimiddlelayerdevicebase', 'SCPI Middlelayer Device Base Documentation',
     [author], 1)
]

texinfo_documents = [
    (master_doc, 'SCPIMiddlelayerDeviceBase', 'SCPI Middlelayer Device Base Documentation',
     author, 'SCPIMiddlelayerDeviceBase', 'One line description of project.',
     'Miscellaneous'),
]
