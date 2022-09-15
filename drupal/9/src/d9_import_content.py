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

def get_content_types():
    """Query the database of the drupal 9 site to get all of the existing taxonomy vocabularies."""

    conn = MySQLdb.connect(host=db_host, 
                                user=db_user, 
                                passwd=db_password, 
                                database=db_database, 
                                port=db_port)
    cursor = conn.cursor()
    
    get_sql = "SELECT * FROM config WHERE name LIKE 'node.type.%'"
    
    debug_output_file_handle.write("get_content_types sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    content_types = cursor.fetchall()
    cursor.close()
    conn.close()

    content_type_machine_names = []
    
    for content_type in content_types:
        config_name = content_type[1]
        content_type_machine_name = config_name.split('.')[2]
        if content_type_machine_name is not None:
            content_type_machine_names.append(content_type_machine_name)
        
    return content_type_machine_names

def get_content(content_type_machine_name):
    """Query the database of the drupal 9 site to get all of the existing taxonomy vocabularies."""

    conn = MySQLdb.connect(host=db_host, 
                                user=db_user, 
                                passwd=db_password, 
                                database=db_database, 
                                port=db_port)
    cursor = conn.cursor()
    
    get_sql = "SELECT * FROM config WHERE name LIKE 'node.type." + content_type_machine_name + "%'"
    
    debug_output_file_handle.write("get_content_types sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    content_types = cursor.fetchall()
    cursor.close()
    conn.close()

    content_type_machine_names = []
    
    for content_type in content_types:
        config_name = content_type[1]
        content_type_machine_name = config_name.split('.')[2]
        if content_type_machine_name is not None:
            content_type_machine_names.append(content_type_machine_name)
        
    return content_type_machine_names

def ct_field_exists(ct_machine_name, ct_field_name="body"):
    """Return true if the database has a field (ct_field_name) for content type ct_machine_name"""

    if ct_machine_name is None:
        print("ct_body_field_exists was run for a content type that doesn't exist in the database: " + ct_machine_name)
        return False

    conn = MySQLdb.connect(host=db_host, 
                                user=db_user, 
                                passwd=db_password, 
                                database=db_database, 
                                port=db_port)
    cursor = conn.cursor()
    
    get_sql = "SELECT data FROM config WHERE name LIKE 'field.field.node." + ct_machine_name + ".field_" + ct_field_name + "'"
    
    debug_output_file_handle.write("get_content_types sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    content_type_metadata = cursor.fetchall()
    cursor.close()
    conn.close()

    if content_type_metadata is None or len(content_type_metadata) <=0 :
        return False

    return True

def get_custom_body_label(ct_machine_name):
    """Get the custom body field label from content type (ct_machine_name)."""

    if ct_machine_name is None:
        print("get_custom_body_label was run for a content type that doesn't exist in the database: " + ct_machine_name)
        return None
    
    conn = MySQLdb.connect(host=db_host, 
                                user=db_user, 
                                passwd=db_password, 
                                database=db_database, 
                                port=db_port)
    cursor = conn.cursor()
    
    get_sql = "SELECT data FROM config WHERE name LIKE 'field.field.node." + ct_machine_name + ".body'"
    
    debug_output_file_handle.write("get_content_types sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    content_type_field_body_metadata = cursor.fetchall()
    cursor.close()
    conn.close()

    if content_type_field_body_metadata is None:
        return ""

    custom_body_label = ""

    for ctfbmd_record in content_type_field_body_metadata:
        print(ctfbmd_record)
        custom_body_label = drupal_9_json_get_key(ctfbmd_record[0], "label")

    return custom_body_label


def create_machine_readable_name(non_machine_readable_name):
    """Convert human text into something drupal's "machines" can read."""
    return_string = non_machine_readable_name.lower()
    return_string = return_string.replace(" ", "_")

    return return_string

def add_content_via_selenium(content_type, ct_has_title=True, ct_title=None):
    """Add a new vocabulary to the "current_website" using Selenium (assuming its a drupal 9 site). """
    if ct_has_title and ct_title is None :
        print("Cannot add this without a Title - content type:" + content_type)
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
    
    driver.get(current_website_url + '/admin/structure/types/add')
    assert "Add content type | " + current_website_human_name in driver.title

    elem = driver.find_element_by_id("edit-name")
    elem.clear()
    elem.send_keys(ct_human_name)
    elem.send_keys(Keys.TAB)

    elem = driver.find_element_by_id("edit-type")
    elem.clear()
    elem.send_keys(ct_machine_name)

    if ct_description is not None:
        elem = driver.find_element_by_id("edit-description")
        elem.clear()
        elem.send_keys(ct_description)

    if ct_has_title and ct_title_label != "Title" and ct_title_label is not None:
        elem = driver.find_element_by_id("edit-title-label")
        elem.clear()
        elem.send_keys(ct_title_label)

    if ct_help is not None:
        elem = driver.find_element_by_id("edit-help")
        elem.clear()
        elem.send_keys(ct_help)

    elem = driver.find_element_by_id("edit-save-continue")
    elem.click()
    
    driver.get(current_website_url + "/user/logout")

    driver.close()

def import_content_from_xml_file(current_content_file):
    """Take the content xml filename and automatically create the 
       content in the "current_website"."""
    
    xml_tree = ET.parse(current_content_file)
    xml_root = xml_tree.getroot()
    num_xml_elements = len(list(xml_root))

    db_ct_data_records = get_content()
    num_fields_added = 0
    
    for ct_data_records in xml_root:
        ct_title = None
        
        fields = []
        for ct_data_records in ct_data_records:
            
            if ct_data_records.tag == "title" :
                ct_title = content_type.text

            
                num_records_added += 1

        if num_records_added % 5 == 5 :
            print(str(num_records_added) + " have been added to the content type " + ct_human_name + ".")

def import_content_files():
    """Import all the content files in "import_directory"."""
    files_to_import = os.listdir(import_directory)
    for content_filename in files_to_import:
        if fnmatch.fnmatch(content_filename, 'content_type_data_*.xml'):
            print("Found a content type to import: " + content_filename)
            current_content_file = os.path.join(import_directory, content_filename)
            import_content_from_xml_file(current_content_file)

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

debug_output_file = os.path.join(logs_directory, 'content_debug.log')
debug_output_file_handle = open(debug_output_file, mode='w')

current_website_human_name = get_site_name()
print("Starting Content Import of " + current_website_human_name)

import_content_files()

debug_output_file_handle.close()
