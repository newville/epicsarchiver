#!/usr/bin/env python

import os

f = open('FileList','r')
lines = f.readlines()
f.close()
outlist = []
for l in lines:
    l = l[:-1].strip()
    if not (l.startswith('#') or len(l)< 2):
        title,fname = [i.strip() for i in l.split('|')]
        
        outlist.append((title,fname))
        
fout = open('pages.py','w')

fout.write("#!/usr/bin/env python\n")

fout.write("# Warning: edit by hand with care: use make_pages.py!\n\n")

fout.write("pagelist = (\n")
for title,fname in outlist:
    fout.write("        '%s',\n" % title)
fout.write(")\n\n")

fout.write("filemap = {\n")
for title,fname in outlist:
    fout.write("        '%s':'%s',\n" % (title,os.path.abspath(fname)))
fout.write("}\n\n")

fout.close()
