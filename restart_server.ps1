# restart_server.ps1 - עצור והפעל מחדש את Flask
taskkill /IM python.exe /F 2>$null
Start-Sleep -Seconds 1
Set-Location "c:\Users\MH\Downloads\45"
& "c:\Users\MH\Downloads\45\.venv\Scripts\python.exe" "app_yemot.py"
