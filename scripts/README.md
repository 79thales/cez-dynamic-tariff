# Release installer

`build_release.py` builds `dist/cez_dynamic_tariff.zip` with integration files directly at
the archive root, as required by HACS `zip_release`. It uses `git archive` on the
selected commit's `custom_components/cez_dynamic_tariff` tree, never the working directory.
Uncommitted edits, local credentials, exports, caches and repository metadata are
not included. Keep private data out of Git as well; the repository privacy tests
remain part of validation.

Local verification, without uploading or publishing:

```shell
python -m unittest discover -s tests -v
python scripts/build_release.py --ref HEAD
```

## Preparing a new release

1. Update `manifest.json` and add a matching version section to `CHANGELOG.md`,
   preserving both `### Čeština` and `### English`. Commit the changes and pass
   the **Validate** workflow, including HACS and Hassfest.
2. Push the corresponding `vX.Y.Z` tag. **Prepare release installer** checks out
   that exact tag, runs tests, verifies the manifest version and builds the ZIP.
3. The workflow attaches the ZIP to a **draft** release and copies the matching
   bilingual changelog section into its notes. It does not publish the release.
4. Review the draft's notes and ensure `cez_dynamic_tariff.zip` is attached and the
   workflow succeeded. Only then publish the draft. Do not publish an empty
   release first: HACS expects the configured ZIP to be available immediately.

The workflow can also be run manually with an existing tag that contains these
packaging scripts. It will reuse an identical asset on a draft but will not
overwrite a different asset or modify a published release. Removing/replacing a
GitHub release asset resets its download count; keep published assets intact.

Existing tags are not rewritten. Older releases retain their original `hacs.json`
and source-archive installation path. Default-branch installations are still
supported but do not count as installer downloads.

The README badges filter by the exact asset filename, `cez_dynamic_tariff.zip`, so future
dashboard samples or other attachments do not inflate the installer count. The
latest-release badge and HACS's download indicator cover one release; the total
badge combines installer downloads across releases. Neither metric identifies
unique users or active installations, and no integration telemetry is involved.
