pyinstaller --onefile .\p.py

cp dist\lastpass.exe ..\dist\windows\p.exe

git add -f ..\dist\windows\p.exe

git status

#git commit -m "New windows binary"

#git push

