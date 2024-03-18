

git pull

pyinstaller p.py --onefile --bootloader-ignore-signals --log-level=WARN

cp dist/p.exe ../dist/windows/p.exe
dist/p.exe -V > ../dist/windows/version

git add -f ../dist/windows/p.exe
git add -f ../dist/windows/version

git status

read-host "Press enter to git commit..."

git commit -m "New windows binary"

read-host "Press enter to git push..."

git push

