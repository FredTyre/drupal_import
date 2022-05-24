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

def flush_print_files(debug_output_file_handle):
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

def get_vocabularies(debug_output_file_handle):
    """Query the database of the drupal 9 site to get all of the existing taxonomy vocabularies."""
    conn = MySQLdb.connect(host=db_host, 
                                user=db_user, 
                                passwd=db_password, 
                                database=db_database, 
                                port=db_port)
    cursor = conn.cursor()
    
    get_sql = "SELECT data FROM config WHERE name LIKE 'taxonomy.vocabulary.%' ORDER BY name"
    
    debug_output_file_handle.write("get_vocabularies sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    vocabularies = cursor.fetchall()
    cursor.close()
    conn.close()

    vocabulary_names = []
    
    for vocabulary in vocabularies:
        vocabulary_name = drupal_9_json_get_key(str(vocabulary), "name")
        vocabulary_names.append(vocabulary_name)
        
    return vocabulary_names

def get_vocabulary_machine_name(debug_output_file_handle, vocabulary_name_to_find):    
    """Get drupal's machine readable name of the vocabulary passed in(vocabulary_name_to_find)."""
    conn = MySQLdb.connect(host=db_host, user=db_user, passwd=db_password, database=db_database, port=db_port)
    cursor = conn.cursor()
    
    get_sql = "SELECT data FROM config WHERE name LIKE 'taxonomy.vocabulary.%' ORDER BY name"
    
    debug_output_file_handle.write("get_vocabularies sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    vocabularies = cursor.fetchall()
    cursor.close()
    conn.close()
    
    for vocabulary in vocabularies:
        vocabulary_name = drupal_9_json_get_key(str(vocabulary), "name")
        
        if vocabulary_name == vocabulary_name_to_find :
            return drupal_9_json_get_key(str(vocabulary), "vid")
        
    return None

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

def get_taxonomy_terms(debug_output_file_handle, vocabulary_machine_name):
    """Query the database of the drupal 9 site to get all of the existing taxonomy terms."""
    conn = MySQLdb.connect(host=db_host, user=db_user, passwd=db_password, database=db_database, port=db_port)
    cursor = conn.cursor()
    
    get_sql = "SELECT tid, name, parent_target_id, "
    get_sql = get_sql + "(SELECT name FROM taxonomy_term_field_data "
    get_sql = get_sql + "WHERE vid = taxonomy_term__parent.bundle "
    get_sql = get_sql + "AND tid = taxonomy_term__parent.parent_target_id) "
    get_sql = get_sql + "FROM taxonomy_term_field_data "
    get_sql = get_sql + "LEFT JOIN taxonomy_term__parent "
    get_sql = get_sql + "ON (taxonomy_term_field_data.vid = taxonomy_term__parent.bundle "
    get_sql = get_sql + "AND taxonomy_term_field_data.tid = taxonomy_term__parent.entity_id) "    
    get_sql = get_sql + "WHERE vid = '" + str(vocabulary_machine_name) + "' "
    get_sql = get_sql + "ORDER BY name, weight, taxonomy_term_field_data.tid"
    
    debug_output_file_handle.write("get_taxonomy_terms sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    taxonomy_terms = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return taxonomy_terms

def get_parent_id_and_term_name(taxonomies_in_this_vocabulary, term_name):
    """Pass in the vocabulary and term name and get back the parent id and the term name."""
    for term in taxonomies_in_this_vocabulary:
        if term[1] == term_name :
            return (term[2], term[3])

    return (0, None)

def get_depth_of_term(taxonomies_in_this_vocabulary, term_name):
    """Pass in the vocabulary and term name and get back how deep it is in the taxonomy tree."""
    if term_name is None :
        return 0

    term_name = term_name.strip()
    (parent_id, parent_term) = get_parent_id_and_term_name(taxonomies_in_this_vocabulary, term_name)
    if parent_term is not None :
        parent_term = parent_term.strip()
    
    if parent_id == 0 :
        return 0

    return 1+get_depth_of_term(taxonomies_in_this_vocabulary, parent_term)

def change_node_users_to_anonymous():
    """Change the nodes in drupal that we (or siteadmin) created to being created by Anonymous"""
    print("Change content created by " + automated_username + " and siteadmin to be marked as created by anonymous ...")
    
    conn = MySQLdb.connect(host=db_host, user=db_user, passwd=db_password, database=db_database, port=db_port)
    cursor = conn.cursor()
    
    update_sql = "UPDATE node SET uid = 0 WHERE uid IN (1, 2)"
        
    debug_output_file_handle.write("change_node_users_to_anonymous sql statement: " + str(update_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(update_sql)
    cursor.close()
    conn.close()

def create_machine_readable_name(non_machine_readable_name):
    """Convert human text into something drupal's "machines" can read."""
    return_string = non_machine_readable_name.lower()
    return_string = return_string.replace(" ", "_")

    return return_string

def add_vocabulary_via_selenium_ide(vocabulary_name):
    """Add a new vocabulary to the "current_website" using Selenium (assuming its a drupal 9 site). """
    if vocabulary_name is None :
        print("Cannot add a vocabulary with no name")
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
    
    driver.get(current_website_url + '/admin/structure/taxonomy/add')
    assert "Add vocabulary | " + current_website_human_name in driver.title

    elem = driver.find_element_by_id("edit-name")
    elem.clear()
    elem.send_keys(vocabulary_name)
    elem.send_keys(Keys.TAB)

    elem = driver.find_element_by_id("edit-vid")
    elem.clear()
    elem.send_keys(create_machine_readable_name(vocabulary_name))

    elem = driver.find_element_by_id("edit-submit")
    elem.click()
    
    driver.get(current_website_url + "/user/logout")

    driver.close()

def add_taxonomy_term(vocabulary_machine_name, term_name, parent_id, parent_name=None, parent_depth=0):
    """Add a taxonomy term to the vocabulary using Selenium. 
       If the parent_name and parent_depth are passed in, it will place the taxonomy in the correct hierarchy."""
    if vocabulary_machine_name is None :
        print("Cannot add a term to a vocabulary with no name")
        return
    
    print("Adding term_name: ", str(term_name), " with parent_term of : ", str(parent_name), "(" + str(parent_id) + ")", " and a parent_depth of: ", str(parent_depth))

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
    
    driver.get(current_website_url + '/admin/structure/taxonomy/manage/' + vocabulary_machine_name + '/add')
    assert "Add term | " + current_website_human_name in driver.title

    elem = driver.find_element_by_id("edit-name-0-value")
    elem.clear()
    elem.send_keys(term_name)

    if parent_name is not None and parent_name != 'None' :
        parent_name = parent_name.strip()
        elem = driver.find_element_by_id("edit-relations")
        elem.click()

        select = Select(driver.find_element_by_id('edit-parent'))
        select.deselect_all()
        select.select_by_visible_text('-'*parent_depth + str(parent_name))

    elem = driver.find_element_by_id("edit-submit")
    elem.click()
    
    driver.get(current_website_url + "/user/logout")

    driver.close()

def import_taxonomy_from_xml_file(current_vocabulary_file):
    """Take the vocabulary xml filename and automatically create the 
       vocabulary and all it's terms in the "current_website"."""
    xml_tree = ET.parse(current_vocabulary_file)
    xml_root = xml_tree.getroot()
    num_xml_elements = len(list(xml_root))

    print(str(num_xml_elements) + " taxonomy terms in this XML File")

    db_vocabularies = get_vocabularies(debug_output_file_handle)
    num_terms_added = 0

    for term in xml_root:
        vocabulary_id = None
        vocabulary_name = None
        term_id = None
        term_name = None
        parent_id = None
        parent_name = None
            
        for term_data in term:
            
            if term_data.tag == "vocabulary_id" :
                vocabulary_id = term_data.text
            if term_data.tag == "vocabulary_name" :
                vocabulary_name = term_data.text
            if term_data.tag == "term_id" :
                term_id = term_data.text
            if term_data.tag == "term_name" :
                term_name = term_data.text
            if term_data.tag == "term_parent_id" :
                parent_id = term_data.text
            if term_data.tag == "term_parent_name" :
                parent_name = term_data.text
            
        if vocabulary_name not in db_vocabularies :
            add_vocabulary_via_selenium_ide(vocabulary_name)
            db_vocabularies = get_vocabularies(debug_output_file_handle)

        vocabulary_machine_name = get_vocabulary_machine_name(debug_output_file_handle, vocabulary_name)

        taxonomies_in_this_vocabulary = get_taxonomy_terms(debug_output_file_handle, vocabulary_machine_name)
        
        if term_not_in_this_vocabulary(taxonomies_in_this_vocabulary, term_name, parent_name) :
            parent_depth = get_depth_of_term(taxonomies_in_this_vocabulary, parent_name)
            add_taxonomy_term(vocabulary_machine_name, term_name, parent_id, parent_name, parent_depth)
            num_terms_added += 1
        
        if num_terms_added % 5 == 5 :
            print(str(num_terms_added) + " have been added to the site.")

def import_taxonomy_files():
    """Import all the vocabulary files in "import_directory"."""
    files_to_import = os.listdir(import_directory)
    for taxonomy_filename in files_to_import:
        if fnmatch.fnmatch(taxonomy_filename, '*_taxonomy.xml'):
            print("Found a vocabulary to import: " + taxonomy_filename)
            current_vocabulary_file = os.path.join(import_directory, taxonomy_filename)
            import_taxonomy_from_xml_file(current_vocabulary_file)

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
print("Starting Taxonomy Import of " + current_website_human_name)

import_taxonomy_files()

debug_output_file_handle.close()
