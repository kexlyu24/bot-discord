@echo off
echo Starting Eq's Music Bot Dashboard...
start cmd /k "cd dashboard/frontend && npm run dev"
python run.py
