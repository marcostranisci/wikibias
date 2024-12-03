import requests,json
import pandas as pd
from tqdm import tqdm
from collections import Counter


class Knowledge():
	
    def __init__(self,path='data/people-and-media_cleaned.csv') -> None:
        df = pd.read_csv(path)
        self.relations = [(x.prop,x.o) for i,x in df.iterrows()]



    def find_claim(self,a_list,claim:str,dtype='wikibase-item'):
            wikidata = 'https://www.wikidata.org/w/api.php'
            wd_params =  {'format':'json','action':'wbgetentities','ids':'{}'.format('|'.join(a_list)),'props':'claims','languages':'en'}
            req = requests.get(wikidata,params=wd_params)
            titles = list()
        
            if dtype == 'wikibase-item':
                for item in req.json()['entities']:
                    try:
                        titles.append({'entity':item,claim:req.json()['entities'][item]['claims'][claim][0]['mainsnak']['datavalue']['value']['id']})
                    except Exception as e:continue
            elif dtype == 'external-id':
                for item in req.json()['entities']:
                    try:
                        titles.append({'entity':item,claim:req.json()['entities'][item]['claims'][claim][0]['mainsnak']['datavalue']['value']})
                    except Exception as e:continue
            
            elif dtype == 'time':
                for item in req.json()['entities']:
                    try:
                        titles.append({'entity':item,claim:req.json()['entities'][item]['claims'][claim][0]['mainsnak']['datavalue']['value']['time']})
                    except Exception as e:continue
                
            return titles
    
    def find_claims(self,a_list):
            wikidata = 'https://www.wikidata.org/w/api.php'
            wd_params =  {'format':'json','action':'wbgetentities','ids':'{}'.format('|'.join(a_list)),'props':'claims','languages':'en'}
            req = requests.get(wikidata,params=wd_params)
            counted_rels = list()
            all_rels = list()
            data = req.json()['entities']
            for person in req.json()['entities']:
                person_rels = list()
                triples = list()
                for rel in self.relations:
                    try:
                        if rel[0] in data[person]['claims'].keys():
                            for claim in data[person]['claims'][rel[0]]:
                                if 'id' in claim['mainsnak']['datavalue']['value']:
                                    triples.append((person,rel[0],claim['mainsnak']['datavalue']['value']['id']))
                                    person_rels.append(rel[1])
                                elif 'time' in claim['mainsnak']['datavalue']['value']:
                                    person_rels.append(rel[1])
                                    triples.extend((person,rel[0],claim['mainsnak']['datavalue']['value']['time']))
                                else: 
                                    person_rels.append(rel[1])
                    except:continue
                
                counted_rels.append(len(person_rels))
                all_rels.extend(triples)
                                                
            return all_rels,counted_rels
    
    def find_sitelinks(self,a_list,dtype='wikibase-item'):
            wikidata = 'https://www.wikidata.org/w/api.php'
            wd_params =  {'format':'json','action':'wbgetentities','ids':'{}'.format('|'.join(a_list)),'props':'sitelinks','languages':'en'}
            req = requests.get(wikidata,params=wd_params)
            data = req.json()['entities']
            all_links = list()
            for entity in data:
                try:
                    if 'enwiki' in data[entity]['sitelinks']:
                        all_links.append({'entity':entity,'sitelink':data[entity]['sitelinks']['enwiki']['title']})
                except: continue
            return all_links
    
    def gather_relations(self,a_json,a_list):
        claims = list()
        for item in a_list:
            tmp = list()
            if item in a_list:
                if item in a_json['claims'].keys():
                    tmp = [{'property':item,'object':x['mainsnak']['datavalue']['value']} for x in a_json['claims'][item]]
            claims.extend(tmp)




