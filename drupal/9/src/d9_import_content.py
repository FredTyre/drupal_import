"""This script uses the following Environment Variables to setup a database connection to the
   drupal 6 website we are attempting to import. When setting the envrionment variables, there
   should not be any double quotes ("). They are used here to only to specify to the reader that
   the text in between double quotes can be used. This information is required for the code to be
   able to export the website's data. See the README.TXT for more information."""

import xml.etree.ElementTree as ET

import os
import fnmatch
import MySQLdb
import re
import sshtunnel

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

INPUT_DIRECTORY = 'input'
OUTPUT_DIRECTORY = 'output'
LOGS_DIRECTORY = 'logs'

ENDL = "\n"

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
    """Removes any empty lines from a string that needs fixing (string_to_fix). 
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
    # debug_output_file_handle.write('================================================\n')
    # debug_output_file_handle.write(string2Convert)
    # debug_output_file_handle.write('--------------------------------------\n')
    # debug_output_file_handle.write(returnString)
    # debug_output_file_handle.write('================================================\n')
    
    return return_string.strip()

def prep_for_mysql_query(str_data):
    return_string = str_data
    
    return_string = return_string.replace("'", "''")
    
    return return_string

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

    if len(return_string_array) < 4 :
        debug_output_file_handle.write("Could not find json_key " + json_key)
        debug_output_file_handle.write()
        debug_output_file_handle.write(json_string)
        debug_output_file_handle.write()

        return ""

    return_string = return_string_array[3]
    
    return return_string.strip('"')

def clean_field_name(str_field_name):
    str_field_name = str(str_field_name)
    clean_index = str_field_name.find("field_")
    if clean_index >= 0 :
        return str_field_name[clean_index+6:]
    
    return str_field_name

def ct_filename_to_ct(directory, filename):
    return_content_type = filename
    
    return_content_type = return_content_type.replace(directory, "")
    return_content_type = return_content_type.replace("ct_data_", "")
    return_content_type = return_content_type.replace(".xml", "")
    return_content_type = re.sub("\\\\", "", return_content_type)
    
    return return_content_type

def execute_and_commit_sql(sql_to_execute):

    conn = MySQLdb.connect(host=db_host, 
                           user=db_user, 
                           passwd=db_password, 
                           database=db_database, 
                           port=db_port)
    
    cursor = conn.cursor()

    debug_output_file_handle.write("execute_and_commit_sql sql statement: " + str(sql_to_execute) + ENDL)
    
    cursor.execute(sql_to_execute)
    cursor.close()
    conn.commit()
    conn.close()
    
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

def uploadListingPhotos(outputDirectory, newNodeId, newNodeTitle, oldPhotoList):
    if(oldPhotoList is None):
        return

    driver = webdriver.Chrome()

    driver.get(newSiteURL + "/user")

    assert "Login | " + siteHumanName in driver.title
    
    username = driver.find_element_by_id("edit-name")
    username.clear()
    username.send_keys(seleniumUsername)

    password = driver.find_element_by_id("edit-pass")
    password.clear()
    password.send_keys(seleniumPassword)

    driver.find_element_by_id("edit-submit").click()
    
    driver.get(newSiteURL + '/node/' + str(newNodeId) + '/edit')
    assert "Edit Aircraft Listing " + str(newNodeTitle) + " | " + siteHumanName in driver.title

    driver.find_element_by_css_selector(".group-aircraft-media").click()

    uploadFilesLocation = imagesFolder
    uploadFileList = oldPhotoList.replace("/", uploadFilesLocation)
    
    oldPhotos = uploadFileList.split(', ')
    counter = 0
    for oldPhoto in oldPhotos:
        
        if(oldPhoto is None or oldPhoto == uploadFilesLocation):
            continue
        
        if(not path.exists(oldPhoto) and oldPhoto.find("/") == -1):
            oldPhoto = "/" + oldPhoto
            oldPhoto = oldPhoto.replace("/", uploadFilesLocation)
        
        if(not path.exists(oldPhoto)):
            debug_output_file_handle.write("photo does not exist:", oldPhoto)
            continue
        
        elem = driver.find_element_by_id("edit-field-listing-image-und-" + str(counter) + "-upload")
        elem.send_keys(oldPhoto)

        driver.find_element_by_id("edit-field-listing-image-und-" + str(counter) + "-upload-button").click()
        time.sleep(10)
        
        counter += 1
        
    elem = driver.find_element_by_id("edit-submit")
    elem.click()
    
    driver.get(newSiteURL + "/user/logout")

    driver.close()

    changeNodeUsersToAnonymous(newDBInfoAlias)

def mysql_gen_select_statement(column_names, from_tables, where_clause = None, order_by = None, groupby = None):
    return_sql = "SELECT "
    for column_name in column_names:
        return_sql += str(column_name) + ", "
    return_sql = return_sql.strip(", ")
    
    return_sql += " FROM "
    for table_name in from_tables:
        return_sql += str(table_name) + ", "
    return_sql = return_sql.strip(", ")
    
    if where_clause is not None:
        return_sql += " WHERE " + where_clause
        
    if order_by is not None:
        return_sql += " ORDER BY " + order_by
        
    if groupby is not None:
        return_sql += " GROUP BY " + groupby

    return return_sql
        
def d9_mysql_add_left_join_on(content_type, left_table_name, right_table_name):
    return "LEFT JOIN " + right_table_name + " ON " + left_table_name + ".nid = " + right_table_name + ".entity_id AND " + right_table_name + ".bundle = '" + content_type + "' AND " + right_table_name + ".deleted = 0 AND " + right_table_name + ".langcode = 'en' "

def get_content_types(content_types_to_exclude):
    """Query the database of the drupal 9 site to get all of the existing content types."""

    conn = MySQLdb.connect(host=db_host, 
                                user=db_user, 
                                passwd=db_password, 
                                database=db_database, 
                                port=db_port)
    cursor = conn.cursor()
    
    get_sql = "SELECT data FROM config WHERE name LIKE 'node.type.%'"
    
    debug_output_file_handle.write("get_content_types sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    content_types = cursor.fetchall()
    cursor.close()
    conn.close()

    content_type_machine_names = []
    
    for content_type in content_types:
        content_type_machine_name = drupal_9_json_get_key(content_type[0], "type")

        if content_type_machine_name is None :
            continue

        if content_types_to_exclude is not None and content_type_machine_name in content_types_to_exclude:
            continue

        content_type_machine_names.append(content_type_machine_name)
        
    return content_type_machine_names

def get_ct_field_names(content_type_machine_name):
    """Query the database of the drupal 9 site to get all of the field names for the specified content type."""

    conn = MySQLdb.connect(host=db_host, 
                                user=db_user, 
                                passwd=db_password, 
                                database=db_database, 
                                port=db_port)
    cursor = conn.cursor()
    
    get_sql = "SELECT data FROM config WHERE name LIKE 'field.field.node." + content_type_machine_name + ".%'"
    
    debug_output_file_handle.write("get_ct_field_names sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    field_data = cursor.fetchall()
    cursor.close()
    conn.close()

    field_names = []
    
    for field_record in field_data:
        data_field = field_record[0]
        
        field_name = drupal_9_json_get_key(data_field, "field_name")
        field_type = drupal_9_json_get_key(data_field, "field_type")
        
        if field_name is not None:
            field_names.append((field_name, field_type))
        
    return field_names

def get_field_type(curr_content_type, curr_fieldname):
    custom_field_names = get_ct_field_names(curr_content_type)
    for field_data in custom_field_names:
        (field_name, field_type) = field_data
        if field_name == curr_fieldname:
            return field_type
        
    return None

def get_content(curr_content_type, ct_title=None):
    """Query the database of the drupal 9 site to get all of the existing taxonomy vocabularies."""

    conn = MySQLdb.connect(host=db_host, 
                                user=db_user, 
                                passwd=db_password, 
                                database=db_database, 
                                port=db_port)
    cursor = conn.cursor()

    custom_field_names = get_ct_field_names(curr_content_type)

    get_sql = "SELECT node.nid, node.vid, node.type, node.uuid "
    get_sql += ", node_field_data.title, node_field_data.created, node_field_data.changed, node_field_data.promote, node_field_data.sticky"

    # need to know the field type to pick column names correctly in the sql
    for field_data in custom_field_names:
        (field_name, field_type) = field_data
        
        if field_name == "" or field_name is None:
            continue

        if field_name == "body":
            right_table_name = "node__body"
            get_sql += ", " + right_table_name + ".body_format, " + right_table_name + ".body_summary, " + right_table_name + ".body_value "
        elif field_name == "comment":
            right_table_name = "node__comment"
            get_sql += ", " + right_table_name + ".comment_status "
        else:
            right_table_name = "node__" + field_name
            
            if field_type == "taxonomy_term_reference":
                get_sql += ", " + right_table_name + "." + field_name + "_tid "
            elif field_type == "image":
                get_sql += ", " + right_table_name + "." + field_name + "_target_id "
                # Need to look in config table to determine these fields.
                #get_sql += ", " + right_table_name + "." + field_name + "_description "
                #get_sql += ", " + right_table_name + "." + field_name + "_display "
            elif field_type == "file":
                get_sql += ", " + right_table_name + "." + field_name + "_target_id "
                # Need to look in config table to determine these fields.
                #get_sql += ", " + right_table_name + "." + field_name + "_description "
                #get_sql += ", " + right_table_name + "." + field_name + "_display "
            elif field_type == "entity_reference":
                get_sql += ", " + right_table_name + "." + field_name + "_target_id "
            elif field_type == "addressfield":
                get_sql += ", " + right_table_name + "." + field_name + "_organisation_name "
                get_sql += ", " + right_table_name + "." + field_name + "_first_name "
                get_sql += ", " + right_table_name + "." + field_name + "_last_name "
                get_sql += ", " + right_table_name + "." + field_name + "_thoroughfare " + curr_field_name + "_address_1 "
                get_sql += ", " + right_table_name + "." + field_name + "_locality " + curr_field_name + "_city "
                get_sql += ", " + right_table_name + "." + field_name + "_administrative_area " + curr_field_name + "_state "
                get_sql += ", " + right_table_name + "." + field_name + "_country "
                get_sql += ", " + right_table_name + "." + field_name + "_postal_code "
            elif field_type == "link":
                get_sql += ", " + right_table_name + "." + field_name + "_uri "
                get_sql += ", " + right_table_name + "." + field_name + "_title "
            elif field_type == "email":
                get_sql += ", " + right_table_name + "." + field_name + "_email "
            elif field_type == "text_with_summary" :
                get_sql += ", " + right_table_name + "." + field_name + "_value "
                get_sql += ", " + right_table_name + "." + field_name + "_summary "
                get_sql += ", " + right_table_name + "." + field_name + "_format "
            elif field_type == "yoast_seo" :
                get_sql += ", " + right_table_name + "." + field_name + "_status "
                get_sql += ", " + right_table_name + "." + field_name + "_focus_keyword "
            else:
                get_sql += ", " + right_table_name + "." + field_name + "_value "
        
    get_sql += "FROM node "
    get_sql += "LEFT JOIN node_field_data ON node.nid = node_field_data.nid AND node_field_data.type = '" + curr_content_type + "' AND node_field_data.langcode = 'en' "
    
    for field_data in custom_field_names:
        (field_name, field_type) = field_data
        
        if field_name == "" or field_name is None:
            continue
        
        if field_name == "body":
            right_table_name = "node__body"
        elif field_name == "comment":
            right_table_name = "node__comment"
        else:
            right_table_name = "node__" + field_name

        get_sql += d9_mysql_add_left_join_on(curr_content_type, "node", right_table_name)
        
    get_sql += "WHERE node.type = '" + curr_content_type + "' "
    get_sql += "AND node.langcode = 'en' "

    if ct_title is not None and ct_title != "":
        get_sql += "AND node_field_data.title = '" + prep_for_mysql_query(ct_title) + "'"
    
    debug_output_file_handle.write("get_content_types sql statement: " + str(get_sql) + ENDL)
    debug_output_file_handle.flush()
    cursor.execute(get_sql)
    ct_data_records = cursor.fetchall()
    cursor.close()
    conn.close()

    field_names = [curr_index[0] for curr_index in cursor.description]
    
    return (field_names, ct_data_records)

def ct_field_exists(ct_machine_name, ct_field_name="body"):
    """Return true if the database has a field (ct_field_name) for content type ct_machine_name"""

    if ct_machine_name is None:
        debug_output_file_handle.write("ct_body_field_exists was run for a content type that doesn't exist in the database: " + ct_machine_name)
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
        debug_output_file_handle.write("get_custom_body_label was run for a content type that doesn't exist in the database: " + ct_machine_name)
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
        debug_output_file_handle.write(ctfbmd_record)
        custom_body_label = drupal_9_json_get_key(ctfbmd_record[0], "label")

    return custom_body_label


def create_machine_readable_name(non_machine_readable_name):
    """Convert human text into something drupal's "machines" can read."""
    return_string = non_machine_readable_name.lower()
    return_string = return_string.replace(" ", "_")

    return return_string

def add_content_via_selenium(content_type, ct_has_title=True, ct_title=None, ct_username=None):
    """Add a new vocabulary to the "current_website" using Selenium (assuming its a drupal 9 site). """
    if ct_has_title and (ct_title == "" or ct_title is None):
        debug_output_file_handle.write("Cannot add this without a Title - content type:" + content_type)
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
    
    driver.get(current_website_url + '/node/add/' + content_type)
    # assert "Add content type | " + current_website_human_name in driver.title

    if ct_has_title and ct_title != "" and ct_title is not None:
        debug_output_file_handle.write("entering title: " + ct_title)
        elem = driver.find_element_by_id("edit-title-0-value")
        elem.clear()
        elem.send_keys(ct_title)

    if ct_username != "" and ct_username is not None:
        debug_output_file_handle.write("entering author info: " + ct_username)
        
        driver.find_element_by_id("edit-author").click()
        time.sleep(10)
    
        elem = driver.find_element_by_id("edit-uid-0-target-id")
        elem.send_keys(ct_username)
        
    elem = driver.find_element_by_id("edit-submit")
    elem.click()

    driver.get(current_website_url + "/user/logout")

    driver.close()
    
def add_field_data_to_site(content_type, curr_nid, curr_vid, db_field_name, field_type, xml_ct_data_field):
    debug_output_file_handle.write("Could not find " + str(db_field_name) + "(type:" + str(field_type) + ") in the new site, so adding it..." + ENDL)
    
    if db_field_name == "created" or db_field_name == "changed" or db_field_name == "sticky":
        update_field_data_in_site(content_type, curr_nid, curr_vid, db_field_name, field_type, xml_ct_data_field, None)
        return
    
    # Field does not exist in this database so not adding the data
    if field_type is None:
        debug_output_file_handle.write("The field " + str(db_field_name) + " does not exist in this website so we cannot add the data (" + str(xml_ct_data_field) + ")..." + ENDL)
        return
    
    if field_type == "image":
        debug_output_file_handle.write("The field " + str(db_field_name) + " requires an image upload function to be built (" + str(xml_ct_data_field) + ")..." + ENDL)
        return

    if field_type == "file":
        debug_output_file_handle.write("The field " + str(db_field_name) + " requires a file upload function to be built (" + str(xml_ct_data_field) + ")..." + ENDL)
        return

    if field_type == "taxonomy_term_reference":
        debug_output_file_handle.write("The field " + str(db_field_name) + " requires a taxonomy term reference function to be built (" + str(xml_ct_data_field) + ")..." + ENDL)
        return

    if field_type == "entity_reference":
        debug_output_file_handle.write("The field " + str(db_field_name) + " requires an entity reference function to be built (" + str(xml_ct_data_field) + ")..." + ENDL)
        return

    if field_type == "addressfield":
        debug_output_file_handle.write("The field " + str(db_field_name) + " requires an entity reference function to be built (" + str(xml_ct_data_field) + ")..." + ENDL)
        return

    if field_type == "link":
        debug_output_file_handle.write("The field " + str(db_field_name) + " requires an entity reference function to be built (" + str(xml_ct_data_field) + ")..." + ENDL)
        return

    if field_type == "email":
        table_name = "node__" + db_field_name
        executeSQL = "INSERT INTO " + table_name + " (bundle, deleted, entity_id, revision_id, langcode, delta, " + table_name + "." + db_field_name + "_email "
        executeSQL += ") VALUES ('" + content_type + "', 0, " + str(curr_nid) + ", " + str(curr_vid) + ", 'en', 0, '"
        executeSQL += xml_ct_data_field
        executeSQL += "')"

        if("None" not in executeSQL):
            execute_and_commit_sql(executeSQL)
        
        return
    
    if field_type == "text_with_summary" :
        debug_output_file_handle.write("The field " + str(db_field_name) + " requires a text with summary function to be built (" + str(xml_ct_data_field) + ")..." + ENDL)
        return

    if field_type == "yoast_seo" :
        debug_output_file_handle.write("The field " + str(db_field_name) + " requires a yoast seo function to be built (" + str(xml_ct_data_field) + ")..." + ENDL)
        return
        
    table_name = "node__" + db_field_name
    executeSQL = "INSERT INTO " + table_name + " (bundle, deleted, entity_id, revision_id, langcode, delta, " + table_name + "." + db_field_name + "_value "
    executeSQL += ") VALUES ('" + content_type + "', 0, " + str(curr_nid) + ", " + str(curr_vid) + ", 'en', 0, '"
    executeSQL += xml_ct_data_field
    executeSQL += "')"

    if("None" not in executeSQL):
        execute_and_commit_sql(executeSQL)
    
def update_field_data_in_site(content_type, curr_nid, curr_vid, db_field_name, field_type, xml_ct_data_field, db_data_field):        
    debug_output_file_handle.write("XML Data for field_name: " + str(db_field_name) + " (" + str(xml_ct_data_field) + ") does not match (" + str(db_data_field) + ") in the new site, so updating it..." + ENDL)
    
    if db_field_name == "created" or db_field_name == "changed" or db_field_name == "sticky":
        executeSQL = "UPDATE node_field_data SET " + db_field_name + " = " + xml_ct_data_field
        executeSQL += " WHERE nid = " + str(curr_nid) + " AND vid = " + str(curr_vid)
        executeSQL += " AND type = '" + str(content_type) + "' AND langcode = 'en' AND status = 1 "
        
        if("None" not in executeSQL):
            execute_and_commit_sql(executeSQL)
        
        return
        
    # Field does not exist in this database so not updating the data
    if field_type is None:
        debug_output_file_handle.write("The field " + str(db_field_name) + " does not exist in this website so we cannot update the data (" + str(xml_ct_data_field) + ")..." + ENDL)
        return
    
def compare_xml_to_db_data_and_fix(content_type, dict_ct_data_record_in_xml, dict_ct_data_records_in_db):
    curr_nid = None
    curr_vid = None
    for field_name in dict_ct_data_record_in_xml:
        add_new_data = False
        update_data = False
        # If node ids don't match that is normal and we don't need to fix it.
        if field_name == "nid":
            # We do need to know what the new site nid is, though.
            if "nid" in dict_ct_data_records_in_db.keys():
                curr_nid = dict_ct_data_records_in_db["nid"]
            continue
    
        # If vids don't match that is normal and we don't need to fix it.
        if field_name == "vid":
            # We do need to know what the new site vid is, though.
            if "vid" in dict_ct_data_records_in_db.keys():
                curr_vid = dict_ct_data_records_in_db["vid"]
            continue
    
        # If uids don't match that is normal and we don't need to fix it.
        if field_name == "uid":
            continue

        field_type = get_field_type(content_type, field_name)
        
        if field_name not in dict_ct_data_records_in_db.keys():
            add_new_data = True
        elif str(dict_ct_data_record_in_xml[field_name]) != str(dict_ct_data_records_in_db[field_name]):
            update_data = True

        if add_new_data and len(field_name) > 4 and field_name[-4:] == "_url":
            db_field_name = field_name[:-4] + "_uri"
            if db_field_name not in dict_ct_data_records_in_db.keys():
                add_field_data_to_site(content_type, curr_nid, curr_vid, db_field_name, field_type, dict_ct_data_record_in_xml)
                continue
            
            elif dict_ct_data_record_in_xml[field_name] != dict_ct_data_records_in_db[db_field_name]:
                update_field_data_in_site(content_type, curr_nid, curr_vid, db_field_name, field_type, dict_ct_data_record_in_xml[field_name], dict_ct_data_records_in_db[db_field_name])
                continue
        
        if add_new_data:
            add_field_data_to_site(content_type, curr_nid, curr_vid, field_name, field_type, dict_ct_data_record_in_xml[field_name])
            continue

        if update_data:
            update_field_data_in_site(content_type, curr_nid, curr_vid, field_name, field_type, dict_ct_data_record_in_xml[field_name], dict_ct_data_records_in_db[field_name])
            continue
    
def import_content_from_xml_file(import_directory, current_content_file):
    """Take the content xml filename and automatically create the 
       content in the "current_website"."""
    
    xml_tree = ET.parse(current_content_file)
    xml_root = xml_tree.getroot()
    num_xml_elements = len(list(xml_root))

    content_type_name = ct_filename_to_ct(import_directory, current_content_file)
    
    (field_names_in_db, db_ct_data_records) = get_content(content_type_name)
    num_records_added = 0
    
    for ct_data_records in xml_root:
        ct_has_title = False
        ct_title = None
        ct_user_name = None
        
        fields = []
        field_names_in_xml = []
        curr_ct_data_record_in_xml = {}
        for ct_data_record in ct_data_records:
            
            if ct_data_record.tag == "title" :
                ct_title = ct_data_record.text
                if ct_title is None or ct_title == "":
                    ct_has_title = False
                else:
                    ct_has_title = True
                
            if ct_data_record.tag == "user_name" :
                ct_user_name = ct_data_record.text

            field_names_in_xml.append(ct_data_record.tag)
            curr_ct_data_record_in_xml[ct_data_record.tag] = ct_data_record.text

        debug_output_file_handle.write("content_type_name: " + str(content_type_name))
        debug_output_file_handle.write("ct_has_title: " + str(ct_has_title))
        debug_output_file_handle.write("ct_title: " + str(ct_title))
        debug_output_file_handle.write("ct_user_name: " + str(ct_user_name))

        (curr_field_names_in_db, curr_ct_data_record_in_db) = get_content(content_type_name, ct_title=ct_title)

        if curr_ct_data_record_in_db is None or len(curr_ct_data_record_in_db) <= 0:
            add_content_via_selenium(content_type_name, ct_has_title, ct_title, ct_user_name)

        # convert curr_ct_data_record_in_db information to a dictionary (should have done that originally?)
        
        dict_ct_data_records = {}
        for this_curr_ct_data_record_in_db in curr_ct_data_record_in_db:
            curr_field_index = 0
            for curr_field_data in this_curr_ct_data_record_in_db:
                if curr_field_index < len(curr_field_names_in_db):
                    dict_ct_data_records[curr_field_names_in_db[curr_field_index]] = curr_field_data
                    curr_field_index +=1

        #debug_output_file_handle.write("xml data in dictionary form: " + str(curr_ct_data_record_in_xml))
        #debug_output_file_handle.write("db data in dictionary form: " + str(dict_ct_data_records))
        
        compare_xml_to_db_data_and_fix(content_type_name, curr_ct_data_record_in_xml, dict_ct_data_records)
        
        num_records_added += 1

        if num_records_added % 5 == 5 :
            debug_output_file_handle.write(str(num_records_added) + " have been added to the content type " + ct_human_name + ".")

def import_content_files():
    """Import all the content files in "import_directory"."""
    files_to_import = os.listdir(import_directory)
    for content_filename in files_to_import:
        if fnmatch.fnmatch(content_filename, 'ct_data_*.xml'):
            debug_output_file_handle.write("Found a content type to import: " + content_filename)
            current_content_file = os.path.join(import_directory, content_filename)
            import_content_from_xml_file(import_directory, current_content_file)

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
debug_output_file_handle.write("Starting Content Import of " + current_website_human_name + ENDL)

import_content_files()

debug_output_file_handle.close()
