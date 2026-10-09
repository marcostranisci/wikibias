Download dbpedia-spotlight en.tar.gz from the DBpedia Spotlight model repository (https://databus.dbpedia.org/dbpedia/spotlight/spotlight-model/) and extract its contents into this folder.

After extraction, the folder should contain the following files and directories (paths are relative to this folder):

.
|-- README.txt
|-- compose.yaml
|-- en.tar.gz
`-- models/
	`-- en/
		|-- fsa_dict.mem
		|-- model/
		|   |-- candmap.mem
		|   |-- context.mem
		|   |-- quantized_counts.mem
		|   |-- res.mem
		|   |-- sf.mem
		|   `-- tokens.mem
		|-- model.properties
		|-- spotter_thresholds.txt
		`-- stopwords.list


Run DBpedia Spotlight using Docker to execute 4. perform entity linking with DBpedia Spotlight.py.
