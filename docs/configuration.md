# Configuration reference

This page explains every option in [config_sample.toml](../config_sample.toml),
including the commented examples. Values in the sample illustrate one setup.
The toolkit can use different built-in defaults when a key is omitted. For
file locations and CLI overrides, see [configuration lookup](setup.md#configuration-lookup).

## `[globals]`

| Setting | What it controls |
| --- | --- |
| `url` | Base URL of the destination board, including `https://` or `http://`. Use the board's address without an `/api` suffix. |
| `username` | Account on the destination board. Its permissions determine which operations the toolkit can perform. |
| `api_token` | API token issued for that account in the board's settings. Keep it private. |
| `public` | Set to `true` if SauceNAO can fetch post URLs from your board. For private boards, use `false` so the toolkit can submit image data for the search. |
| `hide_progress` | Set to `true` to suppress progress bars for commands that use this global setting. If set, its value takes precedence over the command's setting where supported. Omit it to use per-command settings. `find-duplicates` reads its own setting. |

## `[credentials]`

Set up credentials in the subsections for the services you use. Treat
`"None"` in the sample as placeholder text. Omit the service subsection
if you have no credentials for it.

### `[credentials.pixiv]`

| Setting | What it controls |
| --- | --- |
| `token` | Pixiv refresh token used to fetch artwork metadata. Install the `pixiv` extra to enable these lookups. |

### `[credentials.sankaku]`

| Setting | What it controls |
| --- | --- |
| `username` | Sankaku login name for the toolkit's API searches, including MD5 lookups. |
| `password` | Password for that Sankaku account. Set both credentials together. For authenticated page downloads, use a gallery-dl cookie file where required. |

### `[credentials.gelbooru]`

| Setting | What it controls |
| --- | --- |
| `user_id` | Gelbooru account ID to send with API requests. Enable this subsection to configure Gelbooru searches and imports. |
| `api_key` | API key for the same Gelbooru account. Set it together with `user_id`. |

## `[logging]`

| Setting | What it controls |
| --- | --- |
| `log_enabled` | Write a log file in addition to the terminal output. |
| `log_file` | Path for the file log. A relative path starts from the working directory. |
| `log_level` | Minimum level for the file log. Use `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`. |
| `log_colorized` | Include terminal color codes in the file log. Set to `false` for plain-text logs. |

## `[tag_categories]`

| Setting | What it controls |
| --- | --- |
| `enabled` | Assign categories to newly created tags from automatic tagging and imports when category metadata is available. Existing tags retain their categories. |
| `lookup_danbooru` | Ask Danbooru for categories when the source did not supply them. This makes extra network requests. |
| `category_map` | Map the source categories `general`, `artist`, `character`, `copyright` and `meta` to your board's category names. The target names are case-sensitive and must already exist. Omitted entries use the built-in mapping shown in the sample. |

See [automatic tag categories](tagging.md#automatic-tag-categories) for the
lookup order and an example with custom category names.

## `[auto_tagger]`

These settings control [automatic tagging](tagging.md#automatic-tagging) and
the tagger invoked by imports or uploads.

| Setting | What it controls |
| --- | --- |
| `saucenao_api_token` | Optional API key for SauceNAO. Request limits depend on the account. Omit the key to use unauthenticated search. |
| `saucenao` | Enable SauceNAO reverse image search to find source metadata. |
| `md5_search` | Search supported boorus for a file with the same MD5 checksum. |
| `wd_tagger` | Enable local WD inference for `auto-tagger`. Turn on the corresponding import's `wd_tagger` setting separately for imports. |
| `wd_tagger_model` | Hugging Face model ID or path to a directory containing `model.onnx` and `selected_tags.csv`. The toolkit caches downloads from Hugging Face. |
| `wd_tagger_providers` | Ordered list of ONNX Runtime execution providers. An empty list uses CPU inference. The CPU remains available as a fallback when you request acceleration. |
| `wd_tagger_threshold` | Confidence cutoff for general tags, on a scale from 0 to 1. Scores must exceed this value to be accepted. |
| `wd_tagger_character_threshold` | Separate confidence cutoff for character tags. Raising it makes character tagging more selective. |
| `wd_tagger_forced` | Run WD inference even when source lookups already supplied useful tags. Requires WD tagging to be enabled. |
| `wd_tagger_set_tag` | Add the marker tag `wd_tagger` when inference accepts at least one general or character tag. |
| `wd_tagger_videos` | Run WD inference on sampled video frames and average the scores. Requires ffmpeg. |
| `wd_tagger_review` | Add `needs_review` when a character prediction falls in the review range. |
| `wd_tagger_review_threshold` | Lower cutoff for the review range. A score above this value and at or below `wd_tagger_character_threshold` triggers review when enabled. |
| `default_safety` | Fallback when WD cannot produce a recognized rating. Use `safe`, `sketchy` or `unsafe`. Uploads have a separate fallback in their workflow section. |
| `safety_overrides` | Map a minimum rating of `sketchy` or `unsafe` to a list of trigger tags. A matching tag can raise the rating. If both levels match, `unsafe` wins. |
| `use_pixiv_artist` | Use a normalized Pixiv artist name as a fallback when the toolkit cannot match it to a Danbooru artist. |
| `use_pixiv_tags` | Allow raw Pixiv tags as a fallback when booru matches and translated Pixiv tags yielded none. Requires the Pixiv extra and refresh token. |
| `update_relations` | Apply existing tag implications when WD supplies tags and MD5 and SauceNAO supply none. For example, a character tag can imply its series. |
| `hide_progress` | Hide the automatic-tagging progress bar. |
| `limit` | Maximum number of matching posts to process per run. Use `0` for no limit. |
| `workers` | Number of posts to process concurrently. Use `1` for sequential processing. |

The sample enables `wd_tagger_set_tag` and `update_relations`. Both are off
by default when the corresponding keys are omitted.

## `[create_relations]`

| Setting | What it controls |
| --- | --- |
| `threshold` | Minimum number of posts that must contain both the character and the series or parody before the toolkit creates the implication and suggestion. |
| `hide_progress` | Hide progress while scanning posts for tag relationships. |
| `workers` | Number of posts to process concurrently. |

## `[fix_relations]`

| Setting | What it controls |
| --- | --- |
| `hide_progress` | Hide progress while completing existing groups of related posts. |

## `[create_tags]`

| Setting | What it controls |
| --- | --- |
| `limit` | Maximum number of tags to fetch from a Danbooru query. The results start with the most recent tags. |
| `min_post_count` | Minimum number of Danbooru posts using a tag for it to be selected by the query. |
| `query` | Danbooru tag-name search pattern. Use `"*"` to match any tag name, or a pattern such as `"genshin*"`. |
| `overwrite` | Allow a tag in the selection to change the category of an existing tag on your board. |
| `import_implications` | Also import active Danbooru tag implications for tags selected by a query. Tag files and single-tag commands can specify their own implications. |
| `hide_progress` | Hide progress while creating tags. |
| `workers` | Number of tags to process concurrently. |

## `[delete_posts]`

| Setting | What it controls |
| --- | --- |
| `hide_progress` | Hide progress while deleting matched posts. |
| `workers` | Number of delete operations to run concurrently. |

## `[find_duplicates]`

| Setting | What it controls |
| --- | --- |
| `threshold` | Maximum Hamming distance between perceptual hashes. Increasing it allows looser matches. |
| `set_relations` | Link posts in each duplicate group. With `false`, the command only reports the groups. |
| `workers` | Number of posts to download and hash concurrently. |
| `hide_progress` | Hide duplicate scanning progress. This command uses its own value. |

## `[preview_tags]`

| Setting | What it controls |
| --- | --- |
| `min_score` | Minimum score for general and character tags to appear in the WD preview report. The tagging and review thresholds still determine how the report labels the displayed scores. |

## `[import_from_booru]`

| Setting | What it controls |
| --- | --- |
| `wd_tagger` | Run WD inference in addition to importing the source booru's tags. Model and threshold settings come from `[auto_tagger]`. |
| `hide_progress` | Hide progress for booru imports. |

This section also accepts the [shared upload settings](#shared-upload-settings)
listed below.

## `[import_from_url]`

| Setting | What it controls |
| --- | --- |
| `wd_tagger` | Enable local WD tagging on URL imports using the model and thresholds in `[auto_tagger]`. |
| `tmp_path` | Base directory for temporary gallery-dl downloads. Each regular run creates a subdirectory for its files. |
| `queue_path` | Optional, writable directory for a single feed's persistent download archive and pending uploads. Use a quoted path such as `"./state/x-likes"`. Omit the key for temporary downloads. |
| `use_twitter_artist` | When Danbooru artist lookup fails, allow the X account name and display name to supply artist tags. |
| `update_tags_if_exists` | Append tags from the imported metadata to a recognized duplicate on the board. |
| `hide_progress` | Hide progress while uploading the downloaded files. |
| `workers` | Number of files to process concurrently. Regular imports can also download multiple supplied URLs concurrently. |

This section also accepts the [shared upload settings](#shared-upload-settings).
See [recurring imports from one feed](importing.md#recurring-imports-from-one-feed)
for the queue's download and retry behavior.

## `[reset_posts]`

| Setting | What it controls |
| --- | --- |
| `hide_progress` | Hide progress while clearing sources and resetting tags. |
| `workers` | Number of post updates to run concurrently. |

## `[tag_posts]`

| Setting | What it controls |
| --- | --- |
| `update_implications` | Add implied tags from the board's existing tag definitions after applying the requested edits. |
| `mode` | `"append"` merges supplied tags and sources into the post. `"overwrite"` replaces each field you supply. |
| `hide_progress` | Hide progress while editing posts. |
| `workers` | Number of posts to update concurrently. |

## `[upload_media]`

| Setting | What it controls |
| --- | --- |
| `src_path` | Directory that `upload-media` scans when you omit its path argument. Use a directory writable by the toolkit if you enable cleanup. The direct `import-from-url` command also validates this path when it starts. |
| `cleanup` | Remove source media once each file is uploaded or recognized as a duplicate. Also removes consumed tag sidecars, empty subdirectories, Windows `Thumbs.db` files and Synology `@eaDir` folders under the source. |
| `workers` | Number of local files to process concurrently. |
| `tags` | Array of default tags for local media without sidecar tags. Use an empty array to supply no default tags. |
| `read_sidecar_tags` | Read one tag per line from a neighboring `file.ext.txt` or `file.txt`, with the first naming form taking priority. |
| `update_tags_if_exists` | Append sidecar tags to a recognized duplicate. Enable `read_sidecar_tags` to use those tags. |
| `auto_tag` | Run automatic tagging for newly uploaded local files. The sample enables this option. The built-in default is off. |
| `hide_progress` | Hide progress while uploading local files. |

This section also accepts the [shared upload settings](#shared-upload-settings).

## Shared upload settings

These keys can appear in `[import_from_booru]`, `[import_from_url]` and
`[upload_media]`. Set them in the section for the workflow you use.

| Setting | What it controls |
| --- | --- |
| `max_similarity` | Similarity cutoff for treating a reverse-search match as a duplicate, from 0 to 1. Lower values make more similar files count as duplicates. Exact matches are always checked. |
| `convert_to_jpg` | Convert PNGs above `convert_threshold` to JPEG. |
| `convert_threshold` | File size above which an eligible PNG is converted. Use a size such as `"3MB"` or `"500KB"`. |
| `convert_quality` | JPEG quality used for conversion. Higher values preserve more detail at the cost of larger files. The maximum is 95. |
| `shrink` | Resize images whose total pixel count exceeds `shrink_threshold`. |
| `shrink_threshold` | Pixel count that triggers resizing when shrinking is enabled. `6000000` means six million pixels. |
| `shrink_dimensions` | Maximum width and height for a resized image in `WIDTHxHEIGHT` format. |
| `default_safety` | Rating used for an upload without a source rating. Choose `"safe"`, `"sketchy"` or `"unsafe"`. |
