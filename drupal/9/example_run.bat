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
python src\d9ImportTaxonomy.py

pause