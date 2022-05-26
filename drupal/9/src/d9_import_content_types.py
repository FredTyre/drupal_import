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
    return_string = json_string[json_string.find(json_key):]
    return_string = return_string.replace(';', ':')
    return_string_array = return_string.split(':')
    return_string = return_string_array[3]
    
    return return_string.strip('"')

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

    return_string = drupal_9_json_get_key(str(site_information_json[0][0]), "name")
    
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

def term_not_in_this_vocabulary(taxonomies_in_this_vocabulary, term_name, parent_name):
    """Check to see if the term(term_name) is already in the current website. 
       It uses local memory to speed up the check.
       We gain a performance boost if any of the terms are already in the database."""
    term_name = term_name.strip()
    for term in taxonomies_in_this_vocabulary:
        if term[1] == term_name :
            if parent_name is None :
                return False
            parent_name = parent_name.strip()
            if term[3] == parent_name :
                return False
            
    # print("Could not find this term: (" + '"' + str(term_name) + '", ' + '"' + str(parent_name) + '")')
    
    return True

def create_machine_readable_name(non_machine_readable_name):
    """Convert human text into something drupal's "machines" can read."""
    return_string = non_machine_readable_name.lower()
    return_string = return_string.replace(" ", "_")

    return return_string

def add_content_type_via_selenium_ide(ct_machine_name, ct_human_name, ct_module, ct_description, ct_help, ct_has_title, ct_title_label, ct_has_body, ct_body_label):
    """Add a new vocabulary to the "current_website" using Selenium (assuming its a drupal 9 site). """
    if ct_human_name is None :
        print("Cannot add a content type with no name")
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

    if ct_help is not None:
        elem = driver.find_element_by_id("edit-help")
        elem.clear()
        elem.send_keys(ct_help)

    elem = driver.find_element_by_id("edit-save-continue")
    elem.click()
    
    driver.get(current_website_url + "/user/logout")

    driver.close()

def add_content_type_field(content_type_machine_name, content_type_field):
    """Add a taxonomy term to the vocabulary using Selenium. 
       If the parent_name and parent_depth are passed in, it will place the taxonomy in the correct hierarchy."""
    if content_type_machine_name is None :
        print("Cannot add a term to a vocabulary with no name")
        return
    
    print("Adding content_type_field: ", str(content_type_field))

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
    
    driver.get(current_website_url + '/admin/structure/taxonomy/manage/' + content_type_machine_name + '/add')
    assert "Add term | " + current_website_human_name in driver.title

    elem = driver.find_element_by_id("edit-name-0-value")
    elem.clear()
    elem.send_keys(content_type_field)

    elem = driver.find_element_by_id("edit-submit")
    elem.click()
    
    driver.get(current_website_url + "/user/logout")

    driver.close()

def import_content_type_from_xml_file(current_content_type_file):
    """Take the content type xml filename and automatically create the 
       vocabulary and all it's terms in the "current_website"."""
    xml_tree = ET.parse(current_content_type_file)
    xml_root = xml_tree.getroot()
    num_xml_elements = len(list(xml_root))

    print(str(num_xml_elements) + " content type fields in this XML File")

    db_content_types = get_content_types()
    num_terms_added = 0

    print(xml_root)
    
    for content_type in xml_root:
        ct_machine_name = None
        ct_human_name = None
        ct_module = None
        ct_description = None
        ct_help = None
        ct_has_title = None
        ct_title_label = None
        ct_has_body = None
        ct_body_label = None
            
        for content_type in content_type:
            
            if content_type.tag == "ct_machine_name" :
                ct_machine_name = content_type.text
                print(ct_machine_name)
            if content_type.tag == "ct_human_name" :
                ct_human_name = content_type.text
                print(ct_human_name)
            if content_type.tag == "ct_module" :
                ct_module = content_type.text
                print(ct_module)
            if content_type.tag == "ct_description" :
                ct_description = content_type.text
                print(ct_description)
            if content_type.tag == "ct_help" :
                ct_help = content_type.text
                print(ct_help)
            if content_type.tag == "ct_has_title" :
                ct_has_title = content_type.text
                print(ct_has_title)
            if content_type.tag == "ct_title_label" :
                ct_title_label = content_type.text
                print(ct_title_label)
            if content_type.tag == "ct_has_body" :
                ct_has_body = content_type.text
                print(ct_has_body)
            if content_type.tag == "ct_body_label" :
                ct_body_label = content_type.text
                print(ct_body_label)
            
        if ct_machine_name not in db_content_types :
            add_content_type_via_selenium_ide(ct_machine_name, ct_human_name, ct_module, ct_description, ct_help, ct_has_title, ct_title_label, ct_has_body, ct_body_label)
            db_content_types = get_content_types()

#        vocabulary_machine_name = get_vocabulary_machine_name(vocabulary_name)
#
#        taxonomies_in_this_vocabulary = get_taxonomy_terms(vocabulary_machine_name)
#        
#        if term_not_in_this_vocabulary(taxonomies_in_this_vocabulary, term_name, parent_name) :
#            add_content_type_field(vocabulary_machine_name, term_name, parent_id, parent_name, parent_depth)
#            num_terms_added += 1
#
        if num_terms_added % 5 == 5 :
            print(str(num_terms_added) + " have been added to the site.")

def import_content_type_files():
    """Import all the content type files in "import_directory"."""
    files_to_import = os.listdir(import_directory)
    for content_type_filename in files_to_import:
        if fnmatch.fnmatch(content_type_filename, 'content_type_*.xml'):
            print("Found a content type to import: " + content_type_filename)
            current_content_type_file = os.path.join(import_directory, content_type_filename)
            import_content_type_from_xml_file(current_content_type_file)

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

debug_output_file = os.path.join(logs_directory, 'debug.log')
debug_output_file_handle = open(debug_output_file, mode='w')

current_website_human_name = get_site_name()
print("Starting Content Type Import of " + current_website_human_name)

import_content_type_files()

debug_output_file_handle.close()
