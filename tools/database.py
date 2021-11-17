#!/usr/bin/python
import sqlite3
from sqlite3.dbapi2 import Error
from configuration.settings import DATABASE
# To initialize Database
# python -c "from tools.database import init_database; init_database()"
db_file = DATABASE

def create_connection():
    """ create a database connection to the SQLite database
        specified by the db_file
    :param db_file: database file
    :return: Connection object or None
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)

    return conn

def init_database():
    con = create_connection()
    with con:
        cur = con.cursor()
        cur.execute("DROP TABLE IF EXISTS variations")
        cur.execute("CREATE TABLE variations(case_id INT, scenario INT, case_variation_id INT, activity TEXT, variant INT, function_name TEXT, gui_element TEXT)")
    con.commit()

def select_all_variations(conn):
    """
    Query all rows in the variations table
    :param conn: the Connection object
    :return: Collections of fetched objects
    """
    cur = conn.cursor()
    cur.execute("SELECT * FROM variations")

    return cur.fetchall()

def select_variations_by(conn, case, scenario, activity, case_variation_id, variant):
    """
    Query variations by Id_case and Activity
    :param conn: the Connection object
    :param case:
    :param activity:
    :return: Collections of fetched objects
    """
    if not conn:
        conn = create_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM variations WHERE scenario=? AND case_id=? AND activity=? AND case_variation_id=? AND variant=?", (scenario,case,activity,case_variation_id,variant))

    return cur.fetchall()

def create_variation(conn, case, scenario, case_variation_id, activity, variant, function, image_element):
    if not conn:
        conn = create_connection()
    cur = conn.cursor()
    v = [case, scenario, case_variation_id, activity, variant, function, image_element]
    cur.execute("INSERT INTO variations(case_id, scenario, case_variation_id, activity, variant, function_name, gui_element) VALUES (?,?,?,?,?,?,?)", v)
    res = cur.lastrowid
    conn.commit()
    return res