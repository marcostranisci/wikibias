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

## Transnational classification ablation

Run `.venv/bin/python "18. ablation_test.py"` (or use another Python with
the requirements installed). The script joins `data/authors_links.csv` and
`data/entity_cob_new.csv` by `entity`, and evaluates the gold
`authors_links.transnational` against:

```
T = (FormerColony OR minority) AND (HDI OR passport mobility)
```

HDI is true for `HDI_category` Medium or Low; passport mobility is true for
`passport_bin` Q3 or Q4. These are the specified categorical definitions, not
an average recomputed over authors. In this dataset High HDI values can also
be below 0.8, so the category definition is **not** identical to the numerical
test `HDI_value < 0.8`.

The full formula and four leave-one-out ablations use the same author-level
cohort. Each ablation removes one term from its OR group (sets that term to
false), leaving the other terms and AND unchanged. Accuracy, precision,
recall, F1 and Cohen's kappa compare predictions with gold; delta columns
compare each metric with the full formula. `changed_vs_full` counts prediction
changes, not changes relative to gold. This measures association with the
given gold labels, not causal importance.

Duplicate identical records count once per entity. Authors without a match,
with any missing gold or required criterion, or with conflicting gold labels
or differing values of any of the four criteria across their records, are
excluded. Comparisons use the raw HDI and passport categories, not just the
resulting booleans. Exclusion counts can overlap; `excluded_total` counts
distinct excluded authors. Missing or unknown values are never silently
classified as false. Undefined metrics are left blank in the CSV.

The script writes `cohort_counts.csv`, `author_audit.csv`,
`author_classifications.csv`, and `ablation_summary.csv` under
`data/ablation_formula/`, leaving the older `data/ablation/` results untouched.
The audit includes flags for each exclusion reason and allows mismatches to be
examined per author. Use `--authors`, `--entities`, and `--output-dir` to
override the default paths.

### Explain excluded authors

Run `.venv/bin/python "19. explain_ablation_exclusions.py"` to recompute the
same exclusion rules directly from the input CSVs. The default output directory
is `data/ablation_exclusions/`; `--authors`, `--entities`, and `--output-dir`
override the paths.

`excluded_authors.csv` has one row per excluded entity, with all applicable
reasons, per-field missing/conflicting flags, a Wikidata link, and distinct
values as JSON lists. An empty string inside a list is a missing source value.
For an unmatched author, criterion value cells are empty because no source
record exists; the criterion-level missing flags do not count unmatched
authors. A blank and a non-blank value in separate rows count as both missing
and conflicting, consistent with the ablation script. Binary 0.0/1.0 values are
normalized to 0/1 when comparing values.

Each reason also has its own CSV, so the same author can appear in multiple
files. `exclusion_counts.csv` counts authors by reason and by field;
`reason_combinations.csv` counts mutually exclusive combinations of reasons.
`authors_source_rows.csv` and `entities_source_rows.csv` retain the original
values for all excluded authors, without joining the rows together.
`source_record` is the 1-based data record number in the respective input file,
excluding the header; it is not necessarily a physical line number.

## References

tbd
