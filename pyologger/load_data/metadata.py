import os
from notion_client import Client
import pandas as pd
from dotenv import load_dotenv

class Metadata:
    def __init__(self):
        load_dotenv()
        notion_token = os.getenv("notion_token")
        if not notion_token:
            raise ValueError("Notion token not found in environment variables")
        print(f"Loaded Notion secret token.")

        self.notion = Client(auth=notion_token)
        self.databases = {
            "dep_DB": os.getenv("databases.dep_DB"),
            "rec_DB": os.getenv("databases.rec_DB"),
            "logger_DB": os.getenv("databases.logger_DB"),
            "animal_DB": os.getenv("databases.animal_DB"),
        }

        # Check if all database IDs are loaded correctly
        for db_name, db_id in self.databases.items():
            if not db_id:
                raise ValueError(f"Database ID for {db_name} not found in environment variables")
            print(f"Loaded database ID for {db_name}.")

        self.metadata = {}

    def fetch_databases(self, verbose=True):
        for db_name, db_id in self.databases.items():
            try:
                if verbose:
                    print(f"Fetching data for {db_name} with ID {db_id}")
                db = self.notion.databases.query(database_id=db_id)
                rows_list = []
                for page in db["results"]:
                    row_data = {}
                    for prop_name, prop in page["properties"].items():
                        prop_type = prop["type"]
                        if prop_type == "title":
                            row_data[prop_name] = prop[prop_type][0]["text"]["content"] if prop[prop_type] else None
                        elif prop_type == "rich_text":
                            row_data[prop_name] = prop[prop_type][0]["plain_text"] if prop[prop_type] else None
                        elif prop_type == "number":
                            row_data[prop_name] = prop[prop_type]
                        elif prop_type == "select":
                            row_data[prop_name] = prop[prop_type]["name"] if prop[prop_type] else None
                        elif prop_type == "date":
                            row_data[prop_name] = prop[prop_type]["start"] if prop[prop_type] else None
                        # Add more property types as needed
                    rows_list.append(row_data)
                self.metadata[db_name] = pd.DataFrame(rows_list)
                if verbose:
                    print(f"Successfully fetched data for {db_name}.")
            except Exception as e:
                if verbose:
                    print(f"Error fetching data for {db_name}: {e}")

    def get_metadata(self, db_name):
        return self.metadata.get(db_name)

    def print_metadata(self):
        for db_name, df in self.metadata.items():
            print(f"Dataframe: {db_name}")
            print(df)
            print()
