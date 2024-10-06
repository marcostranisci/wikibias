# reducing-underrepresentation
experiments related to the reduction of underrepresentation

## Prepare the repo

* Copy the file [authors_links.csv](https://drive.google.com/file/d/1EsZmlv4yTUll5E7E-EJpKJzYKCKUNQ99/view?usp=drive_link) in the folder data/
* Copy the file [all_people.parquet](https://drive.google.com/file/d/1JDN7ygIEju50ozvFTC7c52Gh27NDrOg4/view?usp=drive_link) in the folder data/
* Copy the [biographical event detection model](https://drive.google.com/file/d/1KWGphIp7HV39RWmGxp7_KuMxNhX-TSTi/view?usp=drive_link) in the root directory


## Experiment

if you run python main.py, you will start an experiment that works as follows:

1. it takes a sample of 50 Transnational writers and 50 Western writers;
2. it counts how many relations with other people these authors have on Wikidata;
3. it gets the English Wikipedia page of each writer and extracts all the relations with others people from raw text through an Open Information Extraction approach;
4. it counts how many relations with other people these authors have **after the extraction**

## Results

I will put a beautiful table and some images here

## References

```
@inproceedings{stranisci2023wikibio,
  title={WikiBio: a Semantic Resource for the Intersectional Analysis of Biographical Events},
  author={Stranisci, Marco Antonio and Damiano, Rossana and Mensa, Enrico and Patti, Viviana and Radicioni, Daniele and Caselli, Tommaso},
  booktitle={Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)},
  pages={12370--12384},
  year={2023}
}
```
