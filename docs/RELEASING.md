# Release assets

[Release assets](../.github/workflows/release.yml) attaches a wheel, source
distribution, and `SHA256SUMS` to an existing GitHub release. It runs automatically
when a release is published and supports manual backfills of older tags.

## Backfill v0.1.0

After the workflow PR merges:

1. Open **Actions → Release assets → Run workflow**.
2. Select the `master` workflow branch, so the new workflow is available.
3. Enter `v0.1.0` for **tag**, then run it.
4. Open the `v0.1.0` release to download `nox_tach-0.1.0-py3-none-any.whl`,
   `nox_tach-0.1.0.tar.gz`, and `SHA256SUMS`.

The workflow resolves the tag to an exact commit and builds that revision, including
for manual runs launched from `master`. It rejects a tag that differs from
`v` plus the checked-out package version and runs that revision's `make ci` before
building. It also checks that the release and tag have not changed before uploading.

## Future releases and retries

Update the package version, pass CI, merge, and publish a matching `v<version>`
GitHub release. Its tagged commit must contain the release workflow for automatic
publishing. Older releases can use the manual backfill above. Draft releases can
also receive assets through a manual run before publication.

The job uses the repository's built-in `GITHUB_TOKEN` with Contents write permission;
no PyPI account, registry publishing, or additional release secret is needed. Files
remain private with the repository. COMO and other private consumers still need
their own read credentials to download them.

Retries skip assets whose GitHub SHA256 digest matches the new build. Different,
incomplete, or unverifiable existing assets stop the job before any uploads; the
workflow never deletes or replaces assets. Immutable published releases cannot
receive additional assets; attach assets to a draft before publishing those releases.
