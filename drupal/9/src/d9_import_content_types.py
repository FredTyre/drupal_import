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

def add_content_type_via_selenium(ct_machine_name, ct_human_name, ct_module, ct_description, ct_help, ct_has_title, ct_title_label):
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

def add_text_content_type_field(content_type_machine_name, 
                                    content_type_human_name, 
                                    content_type_field_human_name, 
                                    content_type_field_machine_name, 
                                    required_field,
                                    content_type_field_default,
                                    content_type_field_multiple):

    """Add a text content type field using Selenium. """

    if content_type_machine_name is None :
        print("Cannot add a text field to a content type with no name")
        return
    
    print("Adding content_type_field: ", str(content_type_field_human_name))

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
    
    driver.get(current_website_url + '/admin/structure/types/manage/' + content_type_machine_name + '/fields/add-field')
    assert "Add field | " + current_website_human_name in driver.title

    select = Select(driver.find_element_by_id('edit-new-storage-type'))
    select.select_by_visible_text("Text (formatted, long, with summary)")
    
    elem = driver.find_element_by_id("edit-label")
    elem.clear()
    elem.send_keys(content_type_field_human_name)
    elem.send_keys(Keys.TAB)
    elem.click()

    elem = driver.find_element_by_id("edit-field-name")
    elem.clear()
    elem.send_keys(content_type_field_machine_name)

    elem = driver.find_element_by_id("edit-submit")
    elem.click()

    assert content_type_field_human_name + " | " + current_website_human_name in driver.title

    if content_type_field_multiple :
        select = Select(driver.find_element_by_id('edit-cardinality'))
        select.select_by_visible_text("Unlimited")

    elem = driver.find_element_by_id("edit-submit")
    elem.click()

    assert content_type_field_human_name + " settings for " + content_type_human_name + " | " + current_website_human_name in driver.title

    checkbox = driver.find_element_by_id("edit-required")
    if required_field :
        checkbox.click()

    elem = driver.find_element_by_id("edit-submit")
    elem.click()

    driver.get(current_website_url + "/user/logout")

    driver.close()

def add_integer_content_type_field(content_type_machine_name, 
                                   content_type_human_name, 
                                   content_type_field_human_name, 
                                   content_type_field_machine_name, 
                                   required_field,
                                   content_type_field_default,
                                   content_type_field_multiple):

    """Add a text content type field using Selenium. """

    if content_type_machine_name is None :
        print("Cannot add a text field to a content type with no name")
        return
    
    print("Adding content_type_field: ", str(content_type_field_human_name))

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
    
    driver.get(current_website_url + '/admin/structure/types/manage/' + content_type_machine_name + '/fields/add-field')
    assert "Add field | " + current_website_human_name in driver.title

    select = Select(driver.find_element_by_id('edit-new-storage-type'))
    select.select_by_visible_text("Number (integer)")
    
    elem = driver.find_element_by_id("edit-label")
    elem.clear()
    elem.send_keys(content_type_field_human_name)
    elem.send_keys(Keys.TAB)
    elem.click()

    elem = driver.find_element_by_id("edit-field-name")
    elem.clear()
    elem.send_keys(content_type_field_machine_name)

    elem = driver.find_element_by_id("edit-submit")
    elem.click()

    assert content_type_field_human_name + " | " + current_website_human_name in driver.title

    if content_type_field_multiple :
        select = Select(driver.find_element_by_id('edit-cardinality'))
        select.select_by_visible_text("Unlimited")

    elem = driver.find_element_by_id("edit-submit")
    elem.click()

    assert content_type_field_human_name + " settings for " + content_type_human_name + " | " + current_website_human_name in driver.title

    checkbox = driver.find_element_by_id("edit-required")
    if required_field :
        checkbox.click()

    elem = driver.find_element_by_id("edit-submit")
    elem.click()

    driver.get(current_website_url + "/user/logout")

    driver.close()

def add_file_content_type_field(content_type_machine_name,
                                content_type_human_name,
                                content_type_field_human_name,
                                content_type_field_machine_name,
                                required_field,
                                content_type_field_default,
                                content_type_field_multiple):
    """Add a file content type field using Selenium. """

    if content_type_machine_name is None :
        print("Cannot add a file field to a content type with no name")
        return
    
    print("Adding content_type_field: ", str(content_type_field_human_name))

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
    
    driver.get(current_website_url + '/admin/structure/types/manage/' + content_type_machine_name + '/fields/add-field')
    assert "Add field | " + current_website_human_name in driver.title

    select = Select(driver.find_element_by_id('edit-new-storage-type'))
    select.select_by_visible_text("File")
    
    elem = driver.find_element_by_id("edit-label")
    elem.clear()
    elem.send_keys(content_type_field_human_name)
    elem.send_keys(Keys.TAB)
    elem.click()

    elem = driver.find_element_by_id("edit-field-name")
    elem.clear()
    elem.send_keys(content_type_field_machine_name)

    elem = driver.find_element_by_id("edit-submit")
    elem.click()

    assert content_type_field_human_name + " | " + current_website_human_name in driver.title

    if content_type_field_multiple :
        select = Select(driver.find_element_by_id('edit-cardinality'))
        select.select_by_visible_text("Unlimited")

    elem = driver.find_element_by_id("edit-submit")
    elem.click()

    assert content_type_field_human_name + " settings for " + content_type_human_name + " | " + current_website_human_name in driver.title

    checkbox = driver.find_element_by_id("edit-required")
    if required_field :
        checkbox.click()

    elem = driver.find_element_by_id("edit-submit")
    elem.click()

    driver.get(current_website_url + "/user/logout")

    driver.close()

def remove_ct_body_field_via_selenium(content_type_machine_name):
    """Remove the body field from content type ct_machine_name """

    if content_type_machine_name is None :
        print("Cannot remove the body field for a content type with no name")
        return
    
    print("Removing this content type's body field: ", str(content_type_machine_name))

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
    
    driver.get(current_website_url + '/admin/structure/types/manage/' + content_type_machine_name + '/fields/node.' + content_type_machine_name + '.body/delete')
    assert "Are you sure you want to delete the field Body? | " + current_website_human_name in driver.title

    elem = driver.find_element_by_id("edit-submit")
    elem.click()
    
    driver.get(current_website_url + "/user/logout")

    driver.close()

def rename_ct_body_field_via_selenium(content_type_machine_name, content_type_human_name, db_body_label, ct_body_label):
    """Use selenium to rename the body field for content type content_type_machine_name from db_body_label to the label ct_body_label."""

    if content_type_machine_name is None :
        print("Cannot rename the body label for a content type with no name")
        return

    if db_body_label is None :
        print("database has an empty body label for content type: " + content_type_machine_name + " with an empty label: " + db_body_label)
        return

    if ct_body_label is None :
        print("Cannot rename the body label for content type: " + content_type_machine_name + " with an empty label: " + ct_body_label)
        return
    
    print("Renaming this content type's body field: ", str(content_type_machine_name), " from ", db_body_label, " to ", ct_body_label)

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
    
    driver.get(current_website_url + '/admin/structure/types/manage/' + content_type_machine_name + '/fields/node.' + content_type_machine_name + '.body')
    assert db_body_label + " settings for " + content_type_human_name + " | " + current_website_human_name in driver.title

    elem = driver.find_element_by_id("edit-label")
    elem.clear()
    elem.send_keys(ct_body_label)

    elem = driver.find_element_by_id("edit-submit")
    elem.click()
    
    driver.get(current_website_url + "/user/logout")

    driver.close()

def import_content_type_from_xml_file(current_content_type_file):
    """Take the content type xml filename and automatically create the 
       vocabulary and all it's terms in the "current_website"."""
    
    # Need to handle profile content type differently (at least initially)
    #   /admin/config/people/profile-types
    # Need to handle panels content type differently (at least initially)

    xml_tree = ET.parse(current_content_type_file)
    xml_root = xml_tree.getroot()
    num_xml_elements = len(list(xml_root))

    db_content_types = get_content_types()
    num_fields_added = 0
    
    for content_types in xml_root:
        ct_machine_name = None
        ct_human_name = None
        ct_module = None
        ct_description = None
        ct_help = None
        ct_has_title = None
        ct_title_label = None
        ct_has_body = None
        ct_body_label = None
        
        fields = []
        for content_type in content_types:
            
            if content_type.tag == "ct_machine_name" :
                ct_machine_name = content_type.text
            if content_type.tag == "ct_human_name" :
                ct_human_name = content_type.text
            if content_type.tag == "ct_module" :
                ct_module = content_type.text
            if content_type.tag == "ct_description" :
                ct_description = content_type.text
            if content_type.tag == "ct_help" :
                ct_help = content_type.text
            if content_type.tag == "ct_has_title" :
                if content_type.text == "1" :
                    ct_has_title = True
                else :
                    ct_has_title = False
            if content_type.tag == "ct_title_label" :
                ct_title_label = content_type.text
            if content_type.tag == "ct_has_body" :
                if content_type.text == "1" :
                    ct_has_body = True
                else :
                    ct_has_body = False
            if content_type.tag == "ct_body_label" :
                ct_body_label = content_type.text
            
            if content_type.tag == "content_type_field" :
                ct_field_type = None
                ct_field_global_settings = None
                ct_field_required = None
                ct_field_name = None
                ct_field_multiple = None
                ct_field_db_storage = None
                ct_field_module = None
                ct_field_db_columns = None
                ct_field_active = None
                ct_field_weight = None
                ct_field_label = None
                ct_field_widget_type = None
                ct_field_widget_settings = None
                ct_field_display_settings = None
                ct_field_description = None
                ct_field_widget_module = None
                ct_field_widget_active = None

                for field_properties in content_type:
                    if field_properties.tag == "ct_field_name" :
                        ct_field_name = clean_field_name(field_properties.text)
                    if field_properties.tag == "ct_field_type" :
                        ct_field_type = field_properties.text
                    if field_properties.tag == "ct_field_required" :
                        if field_properties.text == "YES" :
                            ct_field_required = True
                        else :
                            ct_field_required = False
                    if field_properties.tag == "ct_field_key" :
                        ct_field_key = field_properties.text
                    if field_properties.tag == "ct_field_default" :
                        ct_field_default = field_properties.text
                    if field_properties.tag == "ct_field_extra" :
                        ct_field_extra = field_properties.text
                    if field_properties.tag == "ct_field_global_settings" :
                        ct_field_global_settings = field_properties.text
                    if field_properties.tag == "ct_field_multiple" :
                        if field_properties.text == "YES" :
                            ct_field_multiple = True
                        else :
                            ct_field_multiple = False
                    if field_properties.tag == "ct_field_db_storage" :
                        ct_field_db_storage = field_properties.text
                    if field_properties.tag == "ct_field_active" :
                        ct_field_active = field_properties.text
                    if field_properties.tag == "ct_field_weight" :
                        ct_field_weight = field_properties.text
                    if field_properties.tag == "ct_field_label" :
                        ct_field_label = field_properties.text
                    if field_properties.tag == "ct_field_widget_type" :
                        ct_field_widget_type = field_properties.text
                    if field_properties.tag == "ct_field_widget_settings" :
                        ct_field_widget_settings = field_properties.text
                    if field_properties.tag == "ct_field_display_settings" :
                        ct_field_display_settings = field_properties.text
                    if field_properties.tag == "ct_field_description" :
                        ct_field_description = field_properties.text
                    if field_properties.tag == "ct_field_widget_module" :
                        ct_field_widget_module = field_properties.text
                    if field_properties.tag == "ct_field_widget_active" :
                        ct_field_widget_active = field_properties.text

                fields.append((ct_field_name, 
                               ct_field_type, 
                               ct_field_required,
                               ct_field_global_settings,
                               ct_field_multiple,
                               ct_field_db_storage,
                               ct_field_module,
                               ct_field_db_columns,
                               ct_field_active,
                               ct_field_weight,
                               ct_field_label,
                               ct_field_widget_type,
                               ct_field_widget_settings,
                               ct_field_display_settings,
                               ct_field_description,
                               ct_field_widget_module,
                               ct_field_widget_active))
            
        if ct_machine_name not in db_content_types :
            add_content_type_via_selenium(ct_machine_name, ct_human_name, ct_module, ct_description, ct_help, ct_has_title, ct_title_label)
            num_fields_added += 2
            db_content_types = get_content_types()

        if not ct_has_body and ct_field_exists(ct_machine_name):
            remove_ct_body_field_via_selenium(ct_machine_name)
            num_fields_added -= 1

        if ct_has_body and ct_body_label != "Body" :
            if ct_field_exists(ct_machine_name) :
                db_custom_body_label = get_custom_body_label(ct_machine_name)
                if db_custom_body_label != ct_body_label :
                    rename_ct_body_field_via_selenium(ct_machine_name, ct_human_name, db_custom_body_label, ct_body_label)


        for field in fields:
            curr_ct_field_name = field[0]
            curr_ct_field_type = field[1]
            curr_ct_field_required = field[2]
            curr_ct_field_global_settings = field[3]
            curr_ct_field_multiple = field[4]
            curr_ct_field_db_storage = field[5]
            curr_ct_field_module = field[6]
            curr_ct_field_db_columns = field[7]
            curr_ct_field_active = field[8]
            curr_ct_field_weight = field[9]
            curr_ct_field_label = field[10]
            curr_ct_field_widget_type = field[11]
            curr_ct_field_widget_settings = field[12]
            curr_ct_field_display_settings = field[13]
            curr_ct_field_description = field[14]
            curr_ct_field_widget_module = field[15]
            curr_ct_field_widget_active = field[16]

            if not ct_field_exists(ct_machine_name, curr_ct_field_name) :
                # Need to add fields here...

                # integer
                if curr_ct_field_type == "number_integer":
                    add_integer_content_type_field(ct_machine_name, ct_human_name, curr_ct_field_label, curr_ct_field_name, curr_ct_field_required, "", curr_ct_field_multiple)
                
                # Text (formatted, long)
                if curr_ct_field_type == "text":
                    add_text_content_type_field(ct_machine_name, ct_human_name, curr_ct_field_label, curr_ct_field_name, curr_ct_field_required, "", curr_ct_field_multiple)
                
                if curr_ct_field_type == "filefield":
                    add_file_content_type_field(ct_machine_name, ct_human_name, curr_ct_field_label, curr_ct_field_name, curr_ct_field_required, "", curr_ct_field_multiple)
                
                num_fields_added += 1

        if num_fields_added % 5 == 5 :
            print(str(num_fields_added) + " have been added to the content type " + ct_human_name + ".")

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
