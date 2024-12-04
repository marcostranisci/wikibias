import gzip
import re
import time
from utils import string_to_hash

import wikipediaapi
import os
import glob
i=0
j=0
for file_name in glob.glob("output/*"):
    j+=1
    f=gzip.open(file_name,"rt")

    # Leggi e salva la prima riga (il titolo)
    page_title = f.readline().strip()
    #print("page_title",page_title)
    # Se è un redirect ci interessa solo la prima riga
    first_line = f.readline().strip()

    f.close()

    """
    Provo a cercare la pagina con le API se c'è redirect 
    """
    if len(first_line.strip().lower())==0:
        i += 1
        print(j,i, page_title, "EMPTY")
        print("\tfirst_line",first_line)
        #print(file_name)

        user_agent = "MyApp/1.0 (https://example.com; mirko.lai@unito.it)"  # Sostituisci con i tuoi dettagli
        wiki_wiki = wikipediaapi.Wikipedia(
            language='en',
            user_agent=user_agent
        )
        page = wiki_wiki.page(page_title)

        if page.exists():
            print("\ttext",page.text[0:20])


            with gzip.open(file_name, 'wt', encoding='utf-8') as f:
                f.write(page_title + "\n")
                f.write(page.text)
            f.close()
            print("Recuperato da API", page_title)
        else:
            print("Pagina non esiste", page_title)
        time.sleep(2)
    elif "redirect [" in first_line.lower() or "redirect[" in first_line.lower():
        pattern = r'\[\[(.*?)\]\]'

        # Trova tutte le corrispondenze
        redirect = re.findall(pattern, first_line)[0]
        i += 1
        print(j,i, page_title, "REDIRECT",redirect)
        print("\tfirst_line",first_line)
        print("\t",redirect)
        #print(file_name)

        user_agent = "MyApp/1.0 (https://example.com; mirko.lai@unito.it)"  # Sostituisci con i tuoi dettagli
        wiki_wiki = wikipediaapi.Wikipedia(
            language='en',
            user_agent=user_agent
        )
        page = wiki_wiki.page(redirect)

        if page.exists():
            print("\ttext",page.text[0:20])


            with gzip.open(file_name, 'wt', encoding='utf-8') as f:
                f.write(page_title + "\n")
                f.write(page.text)
            f.close()
            print("Recuperato da API", page_title)
        else:
            print("Pagina non esiste", page_title)
        time.sleep(2)



#406
print(i)