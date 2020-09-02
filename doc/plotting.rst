
Using the Epics PV Archiver Plotting and Viewing
-------------------------------------------------

Plotting and Viewing of PV Data is fairly straightforward using the
<<Archive Viewing Page>>.  From this page, you can choose one or two PVs to
plot, and the time range for the data to be plotted.  You can also
explicitly set the range for the y-axis (ordinate), and whether to use
normal or log scale for the y-axis.

 There are two methods for setting the time range (abscissa).  First,
you can select the 'Time From Present' button and the time length from the
drop down menu (ranging from 15 minutes to 1 month).  Second, you can give
an explicit time range and select the 'Data Range' button.  Here, the
format needs to be "YYYY-mm-dd HH:MM:SS" for both dates.  Clicking on the
small buttons will pop-up a calendar than can be used to chose the date and
time for these time ranges.

 The plot should be shown automatically, and labeled well enough to
interpret the data.  In addition, links are provided for:

 data file(s) with the real data for each PV.

 the gnuplot script used to create the plot, in case you'd like to
modify the plot for other purposes.

The data format for these data files is a three column ASCII file with
headers marked by lines starting with #.  The header will include
some information about time range, and for ENUM PVs, the legend for mapping
integer ENUM values to strings.    The data rows (one per time) will be of the form

YYYYMMDD HHMMSS UNIXTS   Value

That is, a 4 digit year, a 2 digit month, a 2 digit day, 1 space, a 2 digit
hour, a 2 digit minute, a 2 digit minute, 1 space, a floating point Unix
timestamp (seconds since epoch), 1 space, and the data value.

 On the server, the data files, gnuplot scripts, and resulting PNG files
will be stored as temporary file in /www/apache/html/cgi-data/pvarch.  These files will be
cleaned out periodically.

