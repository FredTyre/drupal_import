"""This script uses the following Environment Variables to setup a database connection to the
   drupal 6 website we are attempting to export. When setting the envrionment variables, there
   should not be any double quotes ("). They are used here to only to specify to the reader that
   the text in between double quotes can be used. This information is required for the code to be
   able to export the website's data. See the README.TXT for more information."""

import xml.etree.ElementTree as ET
import re
import os
import fnmatch
import MySQLdb
import sshtunnel
import random
import string

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

INPUT_DIRECTORY = 'input'
OUTPUT_DIRECTORY = 'output'
LOGS_DIRECTORY = 'logs'

ENDL = os.linesep

SINGLE_QUOTE = "'"
DOUBLE_QUOTE = '"'

current_website = os.environ.get("D9IT_CURR_SITE_NAME")
current_website_url = os.environ.get("D9IT_CURR_SITE_URL")
db_host = os.environ.get("D9IT_CURR_DB_HOST")
db_port = int(os.environ.get("D9IT_CURR_DB_PORT"))
db_user = os.environ.get("D9IT_CURR_DB_USER")
db_password =  os.environ.get("D9IT_CURR_DB_PASS")
db_database =  os.environ.get("D9IT_CURR_DB_NAME")
automated_username = os.environ.get("D9IT_CURR_AUTO_USER")
automated_password = os.environ.get("D9IT_CURR_AUTO_PASS")

ignore_case_replace_end_lines_1 = re.compile("<br/>", re.IGNORECASE)
ignore_case_replace_end_lines_2 = re.compile("<br />", re.IGNORECASE)
ignore_case_replace_end_lines_3 = re.compile("<br>", re.IGNORECASE)
ignore_case_replace_paragraph_tag_begin = re.compile("<p>", re.IGNORECASE)
ignore_case_replace_paragraph_tag_end = re.compile("</p>", re.IGNORECASE)
ignore_case_replace_space = re.compile("&nbsp;", re.IGNORECASE)
ignore_case_replace_dollar_sign = re.compile("\$", re.IGNORECASE)
ignore_case_replace_comma = re.compile(",", re.IGNORECASE)
ignore_case_replace_left_parenthesis = re.compile("\(", re.IGNORECASE)
ignore_case_replace_right_parenthesis = re.compile("\)", re.IGNORECASE)
ignore_case_replace_negative = re.compile("-", re.IGNORECASE)
ignore_case_replace_forward_slash = re.compile("[/]+", re.IGNORECASE)
ignore_case_replace_letters = re.compile("[a-z]+", re.IGNORECASE)
ignore_case_replace_period = re.compile("[\.]+", re.IGNORECASE)

import_directory = os.path.join(INPUT_DIRECTORY, current_website)
export_directory = os.path.join(OUTPUT_DIRECTORY, current_website)
logs_directory = os.path.join(export_directory, LOGS_DIRECTORY)

def get_random_string(length):
    choices = string.ascii_letters + string.digits + string.punctuation
    random_string = ''.join(random.choice(choices) for i in range(length))
    return random_string
    
def remove_empty_lines(string_to_fix, end_line):
    """Removes any emptyl lines from a string that needs fixing (string_to_fix). 
       end_line is used to find the line endings in the string."""

    return_string = ""

    lines = string_to_fix.split(end_line)
    for line in lines:
        if line is None :
            continue
        
        if len(line.strip()) > 0 :
            return_string += line + end_line

    return return_string

def shrink_width(string_to_shrink, new_width):
    """Change the string (string_to_shrink) so that the words don't go past a 
       certain width(new_width). Does not split words."""

    return_string = ""
    
    current_line_length = 0
    first_word = True
    for current_word in string_to_shrink.split(" "):
        if not first_word and current_line_length > new_width :
            return_string += ENDL
            current_line_length = 0
            first_word = True
            
        return_string += current_word + " "
        current_line_length += len(current_word) + 1
        first_word = False

    return_string = remove_empty_lines(return_string, ENDL)
    
    return return_string.strip()

def convert_html(string_to_convert, end_line):
    """Convert string that has markdown in it(string_to_convert) and remove any empty lines."""

    if string_to_convert is None :
        return ""
    
    return_string = string_to_convert
    return_string = ignore_case_replace_end_lines_1.sub(end_line, return_string)
    return_string = ignore_case_replace_end_lines_2.sub(end_line, return_string)
    return_string = ignore_case_replace_end_lines_3.sub(end_line, return_string)
    return_string = ignore_case_replace_paragraph_tag_begin.sub("", return_string)
    return_string = ignore_case_replace_paragraph_tag_end.sub("", return_string)
    return_string = ignore_case_replace_space.sub(" ", return_string)

    return_string = remove_empty_lines(return_string, end_line)
    #print('================================================\n')
    #print(string2Convert)
    #print('================================================\n')
    #print(returnString)
    #print('================================================\n')
    
    return return_string.strip()

def print_empty_line(file_handle):
    """Print an empty line to a file (file_handle)."""

    file_handle.write(ENDL)

def flush_print_files():
    """Write any data stored in memory to the file(debug_output_file_handle)."""

    debug_output_file_handle.flush()

def drupal_9_json_get_key(json_string, json_key):
    """drupal 9 does JSON differently than python does, apparently. 
       Find the json_key in json_string and return it's value."""

    str_json_string = str(json_string)
    return_string = str_json_string[str_json_string.find(json_key):]
    return_string = return_string.replace(';', ':')
    return_string_array = return_string.split(':')
    return_string = return_string_array[3]
    
    return return_string.strip('"')

def clean_field_name(str_field_name):
    str_field_name = str(str_field_name)
    clean_index = str_field_name.find("field_")
    if clean_index >= 0 :
        return str_field_name[clean_index+6:]
    
    return str_field_name

def get_site_name():
    """Look up the human readable name of the website in the drupal database.
       Used to verify we are at the correct website when adding new content via Selenium."""

    conn = MySQLdb.connect(host=db_host, 
                           user=db_user, 
                           passwd=db_password, 
                           database=db_database, 
                           port=db_port)
    cursor = conn.cursor()
    
    get_sql = "SELECT data FROM config WHERE name = 'system.site'"
    
    debug_output_file_handle.write("get_site_name sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    site_information_json = cursor.fetchall()
    cursor.close()
    conn.close()

    if site_information_json is None:
        return ""

    return_string = drupal_9_json_get_key(site_information_json[0][0], "name")
    
    return return_string

def create_machine_readable_name(non_machine_readable_name):
    """Convert human text into something drupal's "machines" can read."""
    return_string = non_machine_readable_name.lower()
    return_string = return_string.replace(" ", "_")

    return return_string

def add_user(user_name, user_email, user_theme, user_signature, user_sig_format, user_created, user_access, user_login, user_status, user_timezone, user_language, user_init, user_data, user_changed):
    if not user_status:
        print("We only add active users!")
        return
    
    add_user_via_selenium(user_name, user_email, user_timezone)

def add_user_via_selenium(user_name, user_email, user_timezone):
    """Add a new user to the "current_website" using Selenium (assuming its a drupal 9 site). """

    if user_name is None :
        print("Cannot add a user without a username.")
        return
    
    driver = webdriver.Chrome()

    driver.get(current_website_url + "/user")

    assert "Log in | " + current_website_human_name in driver.title
    
    username = driver.find_element_by_id("edit-name")
    username.clear()
    username.send_keys(automated_username)

    password = driver.find_element_by_id("edit-pass")
    password.clear()
    password.send_keys(automated_password)

    driver.find_element_by_id("edit-submit").click()
    
    driver.get(current_website_url + '/admin/people/create')
    assert "Add user | " + current_website_human_name in driver.title
    
    if user_email is not None:
        elem = driver.find_element_by_id("edit-mail")
        elem.clear()
        elem.send_keys(user_email)

    elem = driver.find_element_by_id("edit-name")
    elem.clear()
    elem.send_keys(user_name)

    # Have the user reset their password via the Reset Password tab at /user/password 
    user_pass = get_random_string(15)
    
    elem = driver.find_element_by_id("edit-pass-pass1")
    elem.clear()
    elem.send_keys(user_pass)
    elem = driver.find_element_by_id("edit-pass-pass2")
    elem.clear()
    elem.send_keys(user_pass)

    select = Select(driver.find_element_by_id('edit-timezone--2'))
    if user_timezone is None or user_timezone == "None":
        select.select_by_visible_text("- None selected -")
    else:
        select.select_by_visible_text(user_timezone)
        
    elem = driver.find_element_by_id("edit-submit")
    elem.click()
    
    driver.get(current_website_url + "/user/logout")

    driver.close()

def get_active_usernames():
    conn = MySQLdb.connect(host=db_host, user=db_user, passwd=db_password, database=db_database, port=db_port)
    cursor = conn.cursor()

    user_records = []
    get_sql = "SELECT name "
    get_sql += "FROM users_field_data "
    get_sql += "WHERE status = 1 "
    get_sql += "ORDER BY uid"
    debug_output_file_handle.write("get_active_usernames sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    user_records = cursor.fetchall()
    cursor.close()
    conn.close()

    users = []
    for user_record in user_records:
        users.append(user_record[0])
    
    return users

def get_active_users():
    conn = MySQLdb.connect(host=db_host, user=db_user, passwd=db_password, database=db_database, port=db_port)
    cursor = conn.cursor()

    user_records = []
    get_sql = "SELECT name, mail, created, access, login, status, timezone, init, changed "
    get_sql += "FROM users_field_data "
    get_sql += "WHERE status = 1 "
    get_sql += "ORDER BY uid"
    debug_output_file_handle.write("get_active_users sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    user_records = cursor.fetchall()
    cursor.close()
    conn.close()

    users = []
    for user_record in user_records:
        users.append(user_record)
    
    return users

def import_active_users_from_xml_file():
    """Take the content type xml filename and automatically create the 
       vocabulary and all it's terms in the "current_website"."""

    current_active_user_file = os.path.join(import_directory, "active_users.xml")
    xml_tree = ET.parse(current_active_user_file)
    xml_root = xml_tree.getroot()
    num_xml_elements = len(list(xml_root))    
    print(str(num_xml_elements) + " active users in this XML File")

    db_active_usernames = get_active_usernames()    
    print(str(len(db_active_usernames)) + " active users in the destination website")
    
    num_users_added = 0
    
    for active_users in xml_root:
        user_name = None
        user_email = None
        user_theme = None
        user_signature = None
        user_sig_format = None
        user_created = None
        user_access = None
        user_login = None
        user_status = None
        user_timezone = None
        user_language = None
        user_init = None
        user_data = None
        user_changed = None
        
        for active_user in active_users:
            
            if active_user.tag == "name" :
                user_name = active_user.text
            if active_user.tag == "mail" :
                user_email = active_user.text
            if active_user.tag == "theme" :
                user_theme = active_user.text
            if active_user.tag == "signature" :
                user_signature = active_user.text
            if active_user.tag == "signature_format" :
                user_sig_format = active_user.text
            if active_user.tag == "created" :
                user_created = active_user.text
            if active_user.tag == "access" :
                user_access = active_user.text
            if active_user.tag == "login" :
                user_login = active_user.text
            if active_user.tag == "status" :
                if active_user.text == "1" :
                    user_status = True
                else :
                    user_status = False
            if active_user.tag == "timezone" :
                user_timezone = active_user.text
            if active_user.tag == "language" :
                user_language = active_user.text
            if active_user.tag == "init" :
                user_init = active_user.text
            if active_user.tag == "data" :
                user_data = active_user.text
            if active_user.tag == "changed" :
                user_changed = active_user.text

        if user_name not in db_active_usernames:
            add_user(user_name, user_email, user_theme, user_signature, user_sig_format, user_created, user_access, user_login, user_status, user_timezone, user_language, user_init, user_data, user_changed)
            num_users_added += 1

        if num_users_added % 5 == 0:
            print(str(num_users_added) + " new users imported.")
            

def prep_file_structure():
    """Ensures that all of the necessary file folders exist."""
    if not os.path.isdir(INPUT_DIRECTORY) :
        os.mkdir(INPUT_DIRECTORY)

    if not os.path.isdir(import_directory) :
        os.mkdir(import_directory)

    if not os.path.isdir(OUTPUT_DIRECTORY) :
        os.mkdir(OUTPUT_DIRECTORY)

    if not os.path.isdir(export_directory) :
        os.mkdir(export_directory)

    if not os.path.isdir(logs_directory) :
        os.mkdir(logs_directory)

prep_file_structure()

debug_output_file = os.path.join(logs_directory, 'active_users_debug.log')
debug_output_file_handle = open(debug_output_file, mode='w')

current_website_human_name = get_site_name()
print("Starting Active Users Import")

import_active_users_from_xml_file()

debug_output_file_handle.close()
