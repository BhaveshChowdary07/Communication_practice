#!/usr/bin/env bash
gunicorn -k gevent -w 4 --backlog 512 -t 60 --graceful-timeout 30 -b 0.0.0.0:10000 run:app