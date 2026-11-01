"""Network construction and analysis.

* ``wikidata_relations`` - person-to-person relations stored on Wikidata
* ``build``              - base / extended / joint networks with node attributes
* ``analysis``           - attribute distributions, centrality, group density,
                           events on shortest paths
* ``sampling``           - sample event sentences for manual annotation
"""

from .wikidata_relations import Relation, WikidataRelations

__all__ = ["Relation", "WikidataRelations"]
