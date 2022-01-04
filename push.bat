@echo off
git add *.cpp *.h *.ino push.bat
git add python\*.py
git commit -m "See history.h"
git push origin main

