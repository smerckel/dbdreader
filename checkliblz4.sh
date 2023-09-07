#!/bin/bash

MAJOR=1
MINOR=7
MINORMINOR=5

libfile=$( ldconfig -p | grep "liblz4" | awk '{if (NR==1){
                                                   print $(NF);
					       }                                                                                  }
					      END{if (NR==0){
                                                   print "Not found"
                                                 }
                                              }
                                              ' )

if [ -L $libfile ]; then
    versioned_libfile=$( ls -l $libfile | awk '{print $(NF)}' )
    major=$( echo $versioned_libfile |cut -d "." -f 3 )
    minor=$( echo $versioned_libfile |cut -d "." -f 4 )
    minorminor=$( echo $versioned_libfile |cut -d "." -f 5 )
    if [ $major -gt $MAJOR ]; then
	r=0;
    else
	if [ $major -eq $MAJOR -a $minor -gt $MINOR ]; then
	    r=0
	else
	    if [ $minor -eq $MINOR -a $minorminor -ge $MINORMINOR ]; then
		r=0
	    else
		r=1
	    fi
	fi
    fi
else
    r=1
fi

exit $r


