#!/bin/sh

pid=`ps -ef | grep "dcl_pools.py MAINNET" | grep -v grep | /usr/bin/awk '{print $2}'`

cd "/indexer-helper/backends"

# echo ${pid}
date >> backend_dcl_pools.log

if [ ! ${pid} ]; then
        # echo "is null"
        echo "No backend process rubbish to clean." >> backend_dcl_pools.log
else
        # echo "not null"
        kill -s 9 ${pid}
        echo "Warning: clean backend process of last round." >> backend_dcl_pools.log
fi
. ../venv/bin/activate
python dcl_pools.py MAINNET >> backend_dcl_pools.log
echo 'OK'