#!/bin/bash
cd /home/peter/gpioviz
source venv/bin/activate
git pull
python3 app.py
