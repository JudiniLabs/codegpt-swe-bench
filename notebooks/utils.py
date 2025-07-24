from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import pandas as pd
import psycopg

load_dotenv()

# Get current graphs for the swe-bench user 
username = os.environ['DATABASE_USERNAME']
password = os.environ['DATABASE_PASSWORD']
host = os.environ['DATABASE_HOST']
port = os.environ['DATABASE_PORT']
database = os.environ['DATABASE_NAME']
conn_string = f"postgresql://{username}:{password}@{host}:{port}/{database}"

def extract_html_content_bs(html_string: str, tag: str) -> list:
    soup = BeautifulSoup(html_string, 'html.parser')
    # decode_contents returns the inner HTML of the tag
    # formatter=None tells BeautifulSoup not to replace characters like '<' with '&lt;'
    return [element.decode_contents(formatter=None) for element in soup.find_all(tag)]

def get_sql_query(query, col_names=[]):
    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    if col_names:
        db_info = pd.DataFrame(rows, columns=col_names)
        return db_info
    else:
        return rows
