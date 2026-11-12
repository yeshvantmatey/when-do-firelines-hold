# Finalize the shared publication links

The local candidate uses one shared Zenodo record, not separate data/code/archive records.

| Placeholder | Replace with |
|---|---|
| `[ZENODO-DOI]` | DOI for the shared data, results, complete analysis archive and code snapshot |
| https://github.com/yeshvantmatey/when-do-firelines-hold | Confirmed public code repository |
| `[GITHUB-RELEASE-URL]` | Named release URL for the version supporting the paper |
| `[GITHUB-COMMIT-SHA]` | Exact source commit for that release |

After the identifiers exist, update README and citation metadata, the shared Zenodo description, and the manuscript Availability Statement. Add valid DOI/URL fields to CITATION.cff; placeholders remain comments so they are not parsed as real identifiers. Recreate the Zenodo code snapshot from the identified code version and rebuild the current checksum manifests after final edits.

The public code repository is https://github.com/yeshvantmatey/when-do-firelines-hold. The local upload folder has no Git remote or automatic GitHub–Zenodo integration. Do not upload local `_preparation` logs or the full dataset to GitHub. The GitHub code and archived code snapshot should match exactly at the selected release.
