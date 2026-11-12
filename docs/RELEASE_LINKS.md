# Shared publication links

One shared Zenodo record contains the dataset, saved results, complete analysis archive, and a snapshot of the paper's code.

| Resource | Identifier |
|---|---|
| Shared record DOI (reserved) | https://doi.org/10.5281/zenodo.24148495 |
| Public code repository | https://github.com/yeshvantmatey/when-do-firelines-hold |
| Paper code version | 1.0.0; Git tag `v1.0.0` |
| Code release URL | https://github.com/yeshvantmatey/when-do-firelines-hold/releases/tag/v1.0.0 |

The Zenodo DOI is reserved. The DOI and release links become available when the corresponding records are published. Preparing these files does not publish either record.

The final code snapshot must be copied from the commit identified by tag `v1.0.0`. Record the final commit hash in the external Zenodo `code_snapshot_manifest.json`, after the metadata update is committed and the release tag is created. Do not insert a predecessor commit hash into the tracked metadata as though it identified the updated files. A Git commit cannot contain its own final hash. In a checkout containing the release tag, `git rev-parse "v1.0.0^{commit}"` reports the commit.

Before archiving, compare every code-snapshot file with the tagged GitHub version. Update the shared Zenodo metadata and manuscript Availability Statement with the DOI, repository URL, and code version. Rebuild the archive manifests after all metadata edits. The DOI identifies the combined record, rather than a separate software-only record.

The local upload folder has no Git remote or automatic GitHub–Zenodo integration. Local `_preparation` logs and the full dataset are excluded from GitHub. The GitHub release and archived code snapshot must match exactly at the selected version.
