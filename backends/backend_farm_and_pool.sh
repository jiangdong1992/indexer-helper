#!/bin/sh

pid=`ps -ef | grep "farm_and_pool.py MAINNET" | grep -v grep | /usr/bin/awk '{print $2}'`

cd "/indexer-helper/backends"

# echo ${pid}
date >> backend_farm_and_pool.log

if [ ! ${pid} ]; then
        # echo "is null"
        echo "No backend process rubbish to clean." >> backend_farm_and_pool.log
else
        # echo "not null"
        kill -s 9 ${pid}
        echo "Warning: clean backend process of last round." >> backend_farm_and_pool.log
fi
python farm_and_pool.py MAINNET >> backend_farm_and_pool.log
echo 'OK'