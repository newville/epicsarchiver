
Epics PV Archiver Alerts
==========================

Alerts are used to send an email when a PV goes into an 'Alert' condition.
The alert condition is set by the user, and does not need to be related to
Alarm states for Epics Variables.  To set or change an alert, you will be
challenged for the administrator password.  As with all administrative
tasks for the Archiver, this is a security measure so that only trusted
users can set up emails sent from your system.
To set up Alerts, a mail server and "from address" must be configured at
installation time.

Use the main <<Alert Page>> for a list of currently defined alerts.  From
this page you can select a "View/Change" link to modify any of the settings
for a particular alert.

Setting an Alerts
-------------------

Alerts are set for a single PV.  In addition to the PV name, each alert
also has a label which can be used to describe the alert, and so that
multiple alerts can be set on a single PV (one person may want an alert
when a valve closes, while another person may want an alert when it
opens!).

Each alert consists of 3 pieces: a PV's value, a 'test condition' and a
'test trip point'.  When the PV's value meets the test condition, the Alert
is said to be in the 'Alarm' state.     The possible test conditions are:

 not equal to 
 equal to     
 less than or equal to 
 less than
 greater than or equal to
 greater than

Thus, if a PV's value is 1.8, the condition is 'greater than', and the trip
point is 2.0, the Alert will be in the 'OK' state.  If the PV's value changes
to 2.1, the Alert will be in the 'Alarm' state.

 An email notice is sent to the specified addresses when the Alert
changes from 'OK' to 'Alarm'.  Even if the PV's value changes while in the
'Alarm' state or stays in the 'Alarm' state indefinitely,  more emails
will NOT be sent.     In addition, each Alert has a 'Time Out' value. Once
an email has been sent for an alert, no email will be sent for that alert for
this time (in seconds).  This is provided to avoid multiple emails for a value
that may rapidly fluctuate about its trip point.

== Customizing and Formatting an Alert email ==

By default, the content of the sent email will look something like this:

Hello,
   An alarm labeled 'XXX went non-zero'
   was detected for PV = 'XXX.VAL'
   The current value = 1.0. This is
   not equal to the trip point value of 0.0

You can customize this message on the Alerts page, putting in any text you
want.  Since you may want to include some of the the name and value of the
PV, and the alert label, condition, and trip point, you can use the
following simple template format for the mail message to automatically get
these values:

 %PV%  :  PV Name
 %VALUE%:  Current PV Value
 %LABEL%:  Alert Label
 %COMP%:  Alert Condition
 %TRIP%:  Alert Trip Point
 %PV(XXX.VAL)%:  Value of another PV

With the last item, you can get the value for other PVs in the mail message.
For this to work, the other PV must already be added to the Cache and Archive.

Thus, you could customize the message to be:

Hello,
   An alarm labeled %LABEL%
   was detected because %PV% = %VALUE%.

   Other PV Values at the time of this alert were:
        Valve 1 : %PV(Valve1.VAL)%
        Current : %PV(Current.VAL)%

To get a more complete report.

The mail message will always have a Subject line that starts with
[Epics Alert], so you can set up auto-forwarding and mail sorting
rules, and will always include a web link to the PV plot page.

Managing Alerts
-------------------

From the web page for Alerts, each can be set to be inactive and then be
re-activated later.  This can be useful to temporarily suppress messages for
PVs that are not always critical.    Alerts can also be deleted completely.

