#!/bin/bash

/usr/local/snap/bin/snap --nosplash --nogui --modules --refresh --update-all  2>&1 | while read -r line; do
    echo "$line"
    [ "$line" = "updates=0" ] && sleep 2 && pkill -TERM -f "snap/jre/bin/java"
done