#!/usr/bin/env bash
gunicorn -k gevent -w 4 -b 0.0.0.0:10000 --backlog 512 run:app