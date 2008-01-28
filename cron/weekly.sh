#!/bin/bash
## Weekly
##  Conditionally execute a command if it is issued
##  during a given week of the month.
##  weeks are numbered 1 through 5
## Example:
##   weekly 2 ls -l  # run ls -l if this is the second week of the month!
[ $# -ge 2 ] || {
  echo "$0 requires least two args: week number and command" 1>&2
  exit 1
  }

[ "$(( $1 + 0 ))" == "$1"  ] &> /dev/null || {
  echo "$0: first argument must be a week number" 1>&2
  exit 1
  }

[ "$[ $(date +%e) / 7 + 1 ]" == "$1" ] || exit 0
shift
eval $@
