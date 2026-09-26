# 2.1.0 — release preparation

Status: unreleased. This document covers changes since 2.0.2.

## New features

- Automatically categorize new tags during auto-tagging and booru/URL imports
  ([#91](https://github.com/reluce/szurubooru-toolkit/issues/91)). Source categories
  and WD model categories are mapped to the existing categories in your instance.
  Existing tags and aliases retain their categories. Optional batched Danbooru
  lookups fill gaps where sources provide no category information.
- Add `fix-sankaku-sources` to rewrite outdated Sankaku source URLs, including
  resolving chan MD5 and www alphanumeric post identifiers.

## Fixes and documentation

- Document NVIDIA GPU device reservations, the Compose 2.30.0 requirement for
  `gpus: all`, and GPU verification steps
  ([#92](https://github.com/reluce/szurubooru-toolkit/issues/92)).
- Preserve progress-bar output and show progress while posts are still being fetched.
- Exit on a single Ctrl+C without waiting for worker completion.
- Announce the daily SauceNAO limit only once across workers.
- Accept oxibooru's `tag-category` and `pool-category` search tokens.
- Suppress broken-pipe tracebacks when browser extensions disconnect.

## Upgrade from 2.0.2

Tag categorization is disabled by default. Existing configurations continue to
work. To enable it, add this section to the config used by the running toolkit
(for Docker, the mounted `config.toml`):

```toml
[tag_categories]
enabled = true
lookup_danbooru = false
category_map = { general = "default", artist = "artist", character = "character", copyright = "series", meta = "meta" }
```

Adapt the target names to your instance and create those categories beforehand.
The toolkit account needs permission to create tags. Existing tags are not
recategorized, including tags already in the default category. There is no data
migration. Unknown categories retain the server's default behavior.

Legacy `remap_categories` and `category_map` under `[auto_tagger]` are supported;
explicit `[tag_categories]` settings take precedence. Import category extraction
can add network requests. `lookup_danbooru = true` additionally enables batched
lookups for missing tags whose categories are unknown.

After publication, update the Python package to `szurubooru-toolkit==2.1.0`, keeping
your installed extras. Docker users should select `:2.1.0` or the appropriate
`:2.1.0-wd-tagger`, `:2.1.0-wd-tagger-cuda`, `:2.1.0-pixiv`, or `:2.1.0-all` tag.
The current Docker publishing workflow targets linux/amd64; ARM64 users still
need a local build. GPU configuration does not add ARM64 image support.

## Local validation

- All 248 tests passed; flake8 and diff whitespace checks passed.
- Default Compose configuration and the enabled NVIDIA device reservation both
  passed `docker compose config --quiet` (Compose 5.2.0).
- Wheel and source distribution built successfully. Package metadata and lockfile
  agree on 2.1.0; both artifacts include `tag_categories.py`.
- Live-instance and NVIDIA inference checks have not been performed locally.

## Maintainer checklist before publishing

- Run the full test suite, lint checks and package build; inspect the wheel for
  the new tag categorization module and matching 2.1.0 package metadata.
- On a test instance, import a post with new categorized tags, repeat the import,
  and check that existing categories and aliases remain unchanged. Run an
  auto-tagger dry run and confirm that no tags or posts are written.
- On an NVIDIA host, validate Compose, run the documented `nvidia-smi` check,
  and confirm the WD tagger selects CUDA during actual inference.
- Confirm the version in `pyproject.toml`, `uv.lock`, and the intended `2.1.0`
  release tag agree. Both publishing workflows run on tag pushes: publish only
  when these checks are complete and release publication is authorized.
- Verify PyPI and the five Docker image variants after publishing, then update
  issues #91 and #92 with the released version and request user confirmation.
