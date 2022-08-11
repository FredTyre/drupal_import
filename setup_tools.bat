c:
cd C:\Users\fred\Documents\GitHub\drupalXMLImport
PATH=C:\Users\fred\AppData\Local\Programs\Python\Python36;C:\Users\fred\AppData\Local\Programs\Python\Python36\Scripts;%PATH%
python -m pip install --upgrade pip
pip install -U MySQL
pip install -U wget
pip install -U selenium
pip install -U urllib3
pip install -U webdriver-manager
pip install -U --only-binary :all: mysqlclient
xcopy /Y "drivers\chromedriver_win32" "C:\Users\Public\Documents\Python Scripts\BrowserDrivers\chromedriver_win32"
pause