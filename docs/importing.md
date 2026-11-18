# Importing and uploading media

Use `import-from-url` for a page, gallery or feed, `import-from-booru` for a
tag search on another booru, and `upload-media` for a local directory. The
[browser extensions](browser-extensions.md) send page URLs to the same importer.

## Import from a URL

`import-from-url` uses gallery-dl to download media and reads the source's
metadata for tags, rating and source URLs where available. Pass URLs as
separate quoted arguments or use a text file with one URL per line.

```sh
szuru-toolkit import-from-url "https://danbooru.donmai.us/posts?tags=foo"
szuru-toolkit import-from-url --input-file urls.txt
szuru-toolkit import-from-url --cookies "/path/to/cookies.txt" --range "1-10" "https://x.com/USERNAME/likes"
```

Use a Netscape-format cookie file for authenticated downloads. The file must
be readable by the machine or container that runs the toolkit. Set
`[import_from_url].cookies` to reuse a path, or supply `--cookies` for a single
run. `--range "1-10"` selects the first ten media files. A post with multiple
images can take up multiple positions. `--verbose` shows gallery-dl output
to help diagnose authentication or extractor problems.

If a cookie file is mounted read-only and gallery-dl reports that it cannot
save cookies, set `cookies-update = false` for that extractor in the
gallery-dl configuration.

- Use `--add-tags "tag_one,tag_two"` to add your own tags.
- Use `--update-tags-if-exists` to add metadata tags to existing duplicates.
  The default skips byte-identical files before tagging.
- Use `--use-twitter-artist` to allow an X account name as an artist tag
  when the toolkit cannot resolve a canonical artist tag.
- Enable `--wd-tagger`, `--md5-search` or `--saucenao` to enrich imports.
  See [automatic tagging](tagging.md#automatic-tagging).

Gallery-dl determines which URLs can be downloaded. The toolkit has additional
metadata handling for sources including Boorus, X, Pixiv and E-Hentai.
E-Hentai and ExHentai imports use the gallery URL as the source and can apply
the gallery's `artist:` tag. Other namespaced E-Hentai tags are skipped.

## Recurring imports from one feed

Set `queue_path` in the job's `config.toml` to a writable directory that persists
between runs. The value must be a quoted path string. TOML booleans such as
`true` are invalid here. Relative paths are resolved from the working directory.

```toml
[import_from_url]
queue_path = "./state/x-likes"
```

With this option enabled, the toolkit passes two paths to gallery-dl.

- `archive.sqlite3` records downloaded media IDs. When gallery-dl scans the feed
  again, it skips archived media before downloading the files.
- `pending/` holds downloaded media and their JSON metadata until the toolkit
  confirms an upload or recognizes an existing duplicate in the booru. If an
  upload fails, the next run retries the local file even if the item has moved
  out of the feed's current scan window.

The first run starts with an empty archive and can download existing media for
the toolkit to check against the booru. Later runs still fetch the feed
metadata. The `--range` option limits the media inspected in the feed, so choose
a window large enough to include new media added between runs.

```sh
szuru-toolkit import-from-url --cookies "/path/to/cookies.txt" --range "1-50" "https://x.com/USERNAME/likes"
```

Use a dedicated configuration and queue directory for each feed. The queue
accepts one URL per invocation and excludes `--input-file`. For a scheduled job,
prevent overlapping runs on the same directory, for example with `flock`.
Keep `queue_path` unset in configurations shared with `import-from-booru` or the
browser-extension webserver.

When `queue_path` is omitted, imports use a temporary download directory and
the toolkit supplies no download archive. Any archive configured directly in
gallery-dl can still apply.

## Import by booru tag query

```sh
szuru-toolkit import-from-booru --booru danbooru --limit 25 "tag_one tag_two"
```

`--booru` accepts `danbooru`, `gelbooru`, `konachan`, `sankaku`, `yandere`
and `all`. The query is sent to the source booru. The limit is applied per
source when using `all`. This command imports tags from the source and supports
optional WD tagging via `--wd-tagger` or `[import_from_booru].wd_tagger`.
Its tagging workflow skips MD5 and SauceNAO lookups. For authenticated
sources, see [credentials](setup.md#optional-service-credentials).

## Upload a local directory

```sh
szuru-toolkit upload-media --tags "tagme,inbox" "/path/to/inbox"
szuru-toolkit upload-media --read-sidecar-tags --auto-tag "/path/to/gallery"
```

The command scans the directory and its visible subdirectories for JPG,
JPEG, PNG, WebP, GIF, MP4, WebM and SWF files. If you omit the directory,
the toolkit uses `[upload_media].src_path`. The default tags for local
files are configured in `[upload_media].tags`.

With `--read-sidecar-tags`, a file named `abc.jpg` uses `abc.jpg.txt` or
`abc.txt`, in that order. Put one tag on each line. If there are no sidecar
tags, the configured default tags apply. Use `--update-tags-if-exists` to
append sidecar tags to an existing duplicate. Use `--auto-tag` to apply
the methods configured in `[auto_tagger]` to newly uploaded posts.

`--cleanup` removes processed source files, including recognized duplicates
and any consumed tag sidecars. Use it for an upload inbox whose files are safe
to remove.

## Duplicates and upload settings

Imports check for exact or sufficiently similar posts before creating a new
post. `max_similarity` controls how close a reverse-search match must be
to count as a duplicate. To review visual duplicates already on your board,
see [find duplicate images](maintenance.md#find-duplicate-images).

The import and upload commands share the following options. You can set
these on the command line or in the configuration for your workflow.

| Option | Effect |
| --- | --- |
| `--max-similarity` | Similarity cutoff used by upload duplicate detection. |
| `--convert-to-jpg`, `--convert-threshold` | Convert PNGs above the size threshold to JPEG. Use a size such as `3MB`. |
| `convert_quality` (TOML) | JPEG quality for conversion, up to 95. |
| `--shrink`, `--shrink-threshold`, `--shrink-dimensions` | Resize large images. The threshold counts pixels and dimensions use a value such as `2500x2500`. |
| `--default-safety` | Safety fallback when an imported post has no detected rating. Choose `safe`, `sketchy` or `unsafe`. |

See `szuru-toolkit COMMAND --help` for all flags. For recurring jobs,
start with a small range or a small inbox and check the output before
increasing the number of files or workers.
