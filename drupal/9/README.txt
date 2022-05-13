This script uses the following Environment Variables to setup a database connection to the drupal 6 website we are attempting to export. 
When setting the envrionment variables, there should not be any double quotes ("). They are used here to only to specify to the reader that 
the text in between double quotes can be used. This information is required for the code to be able to export the website's data.

Note: D6ET_CURR_SITE_NAME needs to follow the folder naming structure of your current Operating System (OS).

Environment variables can be set through the windows system for long term storage or they can be added to a batch file / script for temporarily setting this information.

In drupal 6, this information should be stored in the settings.php file and look something like ...
   $db_url = 'mysql://username:password@localhost/databasename';

D6ET_CURR_SITE_NAME: 	Environment variable that has a name to use as a reference for the connection credentials. Note: It is not located in settings.php and is just for human reference. This is the name of a folder that will be created in the output folder storing the XML Export.
D6ET_CURR_DB_HOST: 		Environment variable that points to the host of the MySQL database server. "localhost" can be used for databases stored on the current machine.
D6ET_CURR_DB_PORT:		Environment variable that points to the port of the MySQL database server. Default is "3306".
D6ET_CURR_DB_USER:		Environment variable used to store the MySQL database user to login with.
D6ET_CURR_DB_PASS:		Environment variable used to store the MySQL database password to login with.
D6ET_CURR_DB_NAME:		Environment variable used to store the MySQL database name that contains the website data.

An example batch file has been included:
   example_run.bat
Feel free to copy and rename that to something relevant to your specific site. It is possible to have multiple batch files with different site information. However, I don't think that the batch files can be run simultaneously within the d6 area. May need to test that. D6 and D7 environment variables are different, so running one of each drupal version at the same time should be fine.
