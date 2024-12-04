import os.path
import wikipediaapi
import pandas as pd
from utils import string_to_hash
import gzip
import time
authors = pd.read_csv('data/authors_links.csv')

for index,author in authors.iterrows():
    filename=string_to_hash(author["sitelink"])
    file_name = f"output/{filename}.txt.gz"

    if not os.path.isfile(file_name):
        print(author["sitelink"])
        user_agent = "MyApp/1.0 (https://example.com; mirko.lai@unito.it)"  # Sostituisci con i tuoi dettagli
        wiki_wiki = wikipediaapi.Wikipedia(
            language='en',
            user_agent=user_agent
        )
        page = wiki_wiki.page(author["sitelink"])
        if page.exists():
            print("\ttext", page.text[0:20])

            with gzip.open(file_name, 'wt', encoding='utf-8') as f:
                f.write(author["sitelink"] + "\n")
                f.write(page.text)
            f.close()
            print("Recuperato da API", author["sitelink"])
        else:
            print("Pagina non esiste", author["sitelink"])
        time.sleep(2)
