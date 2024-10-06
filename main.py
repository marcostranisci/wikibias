from src import retrieve_knowledge,wd_knowledge
import pandas as pd
import random, requests
import numpy as np
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from tqdm import tqdm
import logging as log

log.basicConfig(
    encoding='utf-8', 
    level=log.INFO,
    format='%(asctime)s %(message)s', 
    datefmt='%m/%d/%Y %I:%M:%S %p'
)

random.seed(30081993)

class Experiment:
    def __init__(self) -> None:
        self.authors = pd.read_csv('./data/authors_links.csv')
        self.wdknow = wd_knowledge.Knowledge()
        self.retriever = retrieve_knowledge.RetrieveSources()
        self.extractor = retrieve_knowledge.OpenInformationExtraction()

    
    def launch_experiment(self,group,seed,size=50):
        sample,rels,counted = self._create_sample(group,seed,size=size)
        all_expanded = list()
        for au,row in tqdm(sample.iterrows(),total=len(sample)):
            try:
                expanded = self._expand_kb(row.entity,row.sitelink)
                all_expanded.extend(expanded)
            except Exception as e:
                log.info(e)
        
        return all_expanded,rels,counted

    def _create_sample(self,group:str,seed:int,size:int):

        sample = self.authors[self.authors.transnational==group].sample(n=size,random_state=seed)
        rels,counted = self.wdknow.find_claims(sample.entity.to_list())

        return sample,rels,counted
    

    def _expand_kb(self,entity,link):

        linked_people = list()
        req = requests.get('https://en.wikipedia.org/wiki/{}'.format(link))
        soup = BeautifulSoup(req.text,'html.parser')
        page = '\n'.join([x.text for x in soup.find_all('p')])
        sentences = self.extractor.tokenize_sentences(page)
         
        for i,sent in enumerate(sentences):
            mentions = list()
            events = self.extractor.event_detection(sent)
            try:
                if len(events)>0:
                    people = self.extractor.entity_linking(sent)
                    for person in people:
                        wd = self.extractor.find_candidates_wiki(person)
                        if wd is not None and wd !=entity:
                            mentions.append(wd)
                if len(mentions)>0:
                    output = {'author':entity,'sentence':i,'events':events,'mentions':mentions,'n_mentions':len(set(mentions))}
                    linked_people.append(output)
            except:continue

        return linked_people


       

exp = Experiment()

l = list()
for i in [42,883,1914,1985,2020,2005,99,900,300,61]:
    for j in [0,1]:
        expanded,rels,counted = exp.launch_experiment(j,seed=i,size=50)
        
        avg_exp = sum([x['n_mentions'] for x in expanded])/50  

        l.append({'group':j,'before':np.mean(counted),'after':avg_exp})


pd.DataFrame(l).to_csv('data/results.csv',index=False)





