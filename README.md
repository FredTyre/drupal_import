# drupal_import
Tools for automating migration between versions of drupal. Implemented using Python.

Requires database access to the websites where data is being exported.
Requires the version of ChromeDriver that matches the person running drupalXMLImport's Chrome Browser version.
	At this time, there are drivers for Windows, Linux, and Mac OS available for download at...
	https://sites.google.com/chromium.org/driver/
	
	The provided setup_tools.bat assumes the driver has been exported into the following folder...
		drivers\chromedriver_win32
   
It also installs the latest versions of pip, wget, selenium, urllib3, and webdriver-manager with ...
	python -m pip install --upgrade pip
	pip install -U wget
	pip install -U selenium
	pip install -U urllib3
	pip install -U webdriver-manager

