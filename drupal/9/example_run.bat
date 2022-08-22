echo OFF
set D9IT_CURR_SITE_NAME=new_d9_folder
set D9IT_CURR_DB_HOST=localhost
set D9IT_CURR_DB_PORT=3306
set D9IT_CURR_DB_USER=
set D9IT_CURR_DB_PASS=
set D9IT_CURR_DB_NAME=
set D9IT_CURR_AUTO_USER=
set D9IT_CURR_AUTO_PASS=
echo ON

echo importing website %D9IT_CURR_SITE_NAME% to output\%D9IT_CURR_SITE_NAME%
"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --profile-directory="Profile 344" %D9IT_CURR_SITE_URL%
python src\d9_import_active_users.py
"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --profile-directory="Profile 344" %D9IT_CURR_DB_HOST%
python src\d9_import_content_types.py
"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --profile-directory="Profile 344" %D9IT_CURR_DB_HOST%
python src\d9_import_taxonomy.py

pause
