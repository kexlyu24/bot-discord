#!/bin/bash
cd dashboard/frontend && npm run dev &
cd ../.. && python run.py
