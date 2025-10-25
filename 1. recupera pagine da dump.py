import bz2
import gzip

import mwxml

# Definisci il percorso completo del file di dump sull'hard disk esterno
dump_path = "data/enwiki-20241101-pages-articles-multistream.xml.bz2"


import os
import csv
from wiki_dump_reader import Cleaner, iterate
import hashlib
from xml.etree import ElementTree
import bz2
from utils import string_to_hash


def iterate(file_path): #Override wiki_dump_reader.iterate
    with bz2.open(file_path, 'rb') as reader:
        #dump = mwxml.Dump.from_file(file)
        #reader=dump.pages
        #with codecs.open(file_path, 'r', 'utf8') as reader:
        content = None
        for line in reader:
            line=line.decode("utf-8")
            line = line.strip()
            if line == '<page>':
                content = [line]
            elif line == '</page>':
                content.append(line)
                content = '\n'.join(content)
                tree = ElementTree.fromstring(content)
                content = None
                ns_elem = tree.find('ns')
                if ns_elem is None:
                    continue
                if ns_elem.text.strip() != '0':
                    continue
                title_elem = tree.find('title')
                if title_elem is None:
                    continue
                title = title_elem.text
                text_elem = tree.find('revision/text')
                if text_elem is None:
                    continue
                text = text_elem.text
                if text is None:
                    continue
                yield title, text
            else:
                if type(content) is list:
                    content.append(line)



# Lista dei titoli di cui vogliamo estrarre il contenuto
titles = []
file=open("data/authors_links.csv")
reader=csv.DictReader(file,delimiter=",",quotechar="\"")
for row in reader:
    titles.append(row["sitelink"])


output_folder = "output"
os.makedirs(output_folder, exist_ok=True)
cleaner = Cleaner()
i=0
j=0
for page_title, text in iterate(dump_path):
    #print(title)
    i+=1
    if i % 10000 == 0:
        print(i,j)

    if page_title in titles:
        j+=1
        text = cleaner.clean_text(text)
        cleaned_text, links = cleaner.build_links(text)
        file_name = string_to_hash(page_title)
        file_path = os.path.join(output_folder, f"{file_name}.txt.gz")
        with gzip.open(file_path, 'wt', encoding='utf-8') as f:
            f.write(page_title + "\n")
            f.write(text)