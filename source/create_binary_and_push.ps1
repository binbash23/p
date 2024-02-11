pyinstaller .\p.py --onefile --bootloader-ignore-signals --log-level=WARN

cp dist\p.exe ..\dist\windows\p.exe

#git add -f ..\dist\windows\p.exe

#git status

#git commit -m "New windows binary"

#git push

