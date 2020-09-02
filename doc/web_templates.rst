##== Templates ==##

Epics PV Archiver Templates and Web Page Layout

The web status pages are automatically generated from the template 
files in the 'web template directory', which in this installation
are in the directory:  /usr/local/share/pvarch/templates/ 

Each template file can list many PVs, typically grouped logically, 
and will be shown as a separate 'Notebook Tab' in the status page, 
with the pages title. The template format for each of these template 
files is detailed below.

== Ordering of Pages / Overall Structure ==

The master file FileList in the template directory contains the 
list of Title, Template File pairs: 

Storage Ring | storage_ring.txt
Vacuum System | vacuum.txt

and so on, with Title and File name separated by '|'.  This will 
be used to make the 'Notebook Tabs' in the status page.  For this 
example, there will be two tabs; 'Storage Ring' and 'Vacuum System'.

To add or change the Tab titles or template files, alter FileList 
and run 'make'.  This will generate pages.py which will be loaded 
by the web scripts.

You do NOT need to run 'make; when you change a template file -- 
these are read on the fly.

== Template Formatting: ==

The status pages contain an HTML table, with each row corresponding to one
or more Epics PVs.  The general idea is to list the PV(s) to be shown.
A simple example would be:

 S:SRCurrentAI.VAL

This will generally get mapped to a table row that has

   Description               Current_Value_with_Link_to_Archive

The description shown can be found automatically from the PVs own 
description field, if available.  If it is not available, the PV
name will be used.  In either case, it can be set explicitly set 
by separating with a '|':

 S:SRCurrentAI.VAL | Ring Current

In addition, the formatting can be explicitly set as well:

 S:SRCurrentAI.VAL | Ring Current | %.2f

For ENUM PVs, the ENUM string will be shown as the Current_Value, 
but it's not uncommon for integer PVs to hold a 'status' field with 
values '0' and '1' (for example, the 'Stations Searched' PVs at the 
APS!)  For these, there a special 'yes/no' format can be used to
map 0 to No, 1 to Yes, and any other value to Unknown.

To specify the formatting but use the default description, use
  

 S:SRCurrentAI.VAL | | %.2f

You can put multiple PVs on a single line, separated by commas:
  

XXX:m1.VAL, XXX:m2.VAL

Which will list many PVs on a single line.  You'll probably want to 
set the description explicitly:
  

XXX:m1.VAL, XXX:m2.VAL | Sample Motors (chi, theta)

Other formatting options: a section heading line in red can be
given with [Title], a horizontal rule with ----,
and an empty row with <>
 
Several examples are provided in the files 'GSE_pageN.txt'

And, again, the template files can be edited 'on-the-fly'.
------------------------------------------------------------

