from duckduckgo_search import DDGS
from newsplease import NewsPlease
from transformers import AutoModelForTokenClassification,AutoTokenizer
import regex as re
import torch
import spacy,requests
from tqdm import tqdm
import pandas as pd
from src.model import Bert4EventExtraction
from difflib import SequenceMatcher




class RetrieveSources:
    def __init__(self) -> None:
        pass

    def search_pages(self,label,max_res=5):

        domains = set()
        urls = list()
        results = DDGS().text("{} -wiki".format(label),max_results=max_res)

        for res in results:
            domain = re.search('(http|https)://.+?/',res['href']).group()
            domains.add(domain)
            urls.append(res['href'])
        
        output = {
            'domains':domains,
            'urls':urls
        }

        return output
    
    def get_page_text(self,url):
        scraped = NewsPlease.from_url(url)
        try:
            page_text = scraped.maintext
        except Exception as e:print(e,url)

        return page_text

class OpenInformationExtraction:

    def __init__(self,sent_tokenizer = 'en_core_web_sm',ev_model='distilbert-base-uncased') -> None:
        self.nlp = spacy.load(sent_tokenizer)
        self.ev_model = Bert4EventExtraction(ev_model,2)
        self.ev_model.load_state_dict(torch.load('./event_detection_model.pth'))
        self.tokenizer = AutoTokenizer.from_pretrained(ev_model)
        self.people = pd.read_parquet('./data/all_people.parquet')

    
    def tokenize_sentences(self,page_text):
        tokenized = self.nlp(page_text)

        sents = [x.text for x in tokenized.sents]
        sents = [[x.text for x in self.nlp(sent)] for sent in sents]

        return sents
    
    def event_detection(self,sentence):
        tokenized = self.tokenizer.encode_plus(sentence,is_split_into_words=True,return_tensors="pt")
        tokens = self.tokenizer.convert_ids_to_tokens(tokenized['input_ids'][0])
        tokenized['tokens'] = tokens
        
        prediction = self.ev_model(tokenized['input_ids'],tokenized['attention_mask'])
        
        labels = [torch.argmax(x).item() for x in prediction[0]]

        events = self.__cleanoutput(tokens,labels)
        
        return events
    
    def entity_linking(self,sentence):
        sentence = self.nlp(' '.join(sentence))

        people = [x.text for x in sentence.ents if x.label_ =='PERSON']
        

        return people
    
    def find_candidates_wiki(self,mention,limit=1,language='en'):
        kb = self.people.o.to_list()
        mention = mention.strip()
        if mention in kb:
            return self.people[self.people.o==mention].s.values[0]
        else:return None



    
    def get_wikidata_id_from_wikipedia(self,page_title):

          names = list()
          url = f"https://en.wikipedia.org/w/api.php"

          # Parameters to request the Wikidata ID from a Wikipedia page
          params = {
               "action": "query",
               "titles": page_title,
               "prop": "pageprops",
               "format": "json"
          }

          # Send request to the Wikipedia API
          response = requests.get(url, params=params)
          data = response.json()

          # Extract page information
          pages = data["query"]["pages"]
          
          for page_id, page_info in pages.items():
               
               if "pageprops" in page_info and "wikibase_item" in page_info["pageprops"]:
                    names.append(({'candidate':page_info['title'],'wd_id':page_info["pageprops"]["wikibase_item"]}))
          
          return names
    
    
    def __cleanoutput(self,tokens,labels,label_type=1):
        events = list()
        for i,label in enumerate(labels):
            if label == label_type:
                if tokens[i].startswith('#'):
                    a = re.sub('##','',tokens[i-1])
                    b = re.sub('##','',tokens[i])
                    event = a+b
                else:
                    event = tokens[i]
                events.append(event)

        return events


