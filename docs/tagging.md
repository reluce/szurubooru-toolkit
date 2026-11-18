# Tagging and tag management

## Automatic tagging

`auto-tagger` works on existing posts matched by a szurubooru query. It can
look up an exact file checksum on supported boorus, use SauceNAO for reverse
image search and run the WD tagger locally. Enable the methods you want in
`[auto_tagger]` or with CLI flags. Use `--limit` to try a smaller batch.

```sh
szuru-toolkit auto-tagger --dry-run --limit 20 "tagme"
szuru-toolkit auto-tagger --wd-tagger --no-saucenao --no-md5-search --limit 20 "tagme"
```

Start with `--dry-run` to see proposed tag additions, removals and safety
changes. It still performs the enabled lookups and model inference. The
second example writes tags using only WD inference. For exact-match lookup,
keep `md5_search` enabled. For SauceNAO, see
[service credentials](setup.md#optional-service-credentials). The toolkit
can continue with MD5 lookup and WD tagging after hitting a SauceNAO quota
if those methods are enabled.

The tagger combines its results with existing tags. You can also supply
`--add-tags` and `--remove-tags` as comma-separated lists. It removes
`tagme` when it finds substantive tags and adds `tagme` when it finds none.
Pixiv lookups can supply artist names and tags when you enable
`use_pixiv_artist` or `use_pixiv_tags` and configure the Pixiv integration.

## WD tagger

Install the `wd-tagger` extra and set `wd_tagger = true` in
`[auto_tagger]`. To tag during an import, enable `wd_tagger` in that import's
config section or pass `--wd-tagger` to the import command.

The default model is [WD EVA02-Large v3](https://huggingface.co/SmilingWolf/wd-eva02-large-tagger-v3),
roughly 1.2 GB. Set `wd_tagger_model` to use another SmilingWolf WD v2 or v3
model, such as the smaller `SmilingWolf/wd-vit-tagger-v3` or
`SmilingWolf/wd-swinv2-tagger-v3`. The toolkit downloads and caches the model
on first use. You can also point it at a local model directory containing
`model.onnx` and `selected_tags.csv`.

Inference uses the CPU by default. Set `wd_tagger_providers` to a list such
as `["CoreMLExecutionProvider"]` on Apple Silicon or
`["CUDAExecutionProvider"]` on NVIDIA GPUs. For CUDA, install the
`wd-tagger-cuda` extra or use the [CUDA Docker image](docker.md#nvidia-acceleration).
The toolkit falls back to the CPU if the requested provider is unavailable.

WD normally supplements posts that lack a useful booru match. Set
`wd_tagger_forced = true` to run it even on posts with matching source
metadata. Use `wd_tagger_set_tag` to label WD-processed posts with
`wd_tagger`. `update_relations` can add tag implications when WD finds tags
for an otherwise unmatched post.

### Review scores and safety ratings

`wd_tagger_threshold` and `wd_tagger_character_threshold` control which
general and character tags are accepted. Set `wd_tagger_review = true` to
mark posts with `needs_review` if a character score is above
`wd_tagger_review_threshold` and falls short of the character cutoff.
Search for `needs_review` on the board to curate those results.

```sh
szuru-toolkit preview-tags "/path/to/sample.jpg"
szuru-toolkit preview-tags --min-score 0.2 1234
```

`preview-tags` uses the configured WD model and reports scores from a
local media file or a post ID. Use a representative sample to tune the
thresholds before tagging a large batch. The report marks accepted tags
with `✓`, character scores in the review band with `~` and rejected scores
with `✗`. `--min-score` filters the report independently of the tagging
thresholds.

With `wd_tagger_videos` enabled and ffmpeg on the path, the model tags videos
by averaging scores over sampled frames. Longer videos use more frames.

Booru matches can supply safety ratings, and WD inference can predict them.
Use `default_safety` as a fallback and `safety_overrides` to require a minimum
rating whenever certain tags appear. An override can only raise the rating.

```toml
[auto_tagger]
safety_overrides = { sketchy = ["see-through"], unsafe = ["sex"] }
```

## Automatic tag categories

New in 2.1.0.

Enable `[tag_categories]` to categorize new tags from `auto-tagger`, `import-from-booru`,
and `import-from-url`. The following example uses custom category names.

```toml
[tag_categories]
enabled = true
lookup_danbooru = false
category_map = { general = "General", artist = "Artist", character = "Character", copyright = "Copyright", meta = "Metadata" }
```

Create the target categories in your instance first. Existing tags (including aliases)
keep their categories. The built-in mapping uses `default`, `artist`,
`character`, `series`, and `meta`. Omitted entries retain these defaults. Category names on the right are case-sensitive.

Danbooru metadata provides source categories. The WD model provides general
and character categories without extra network requests. Imports ask gallery-dl for
categorized tags on Gelbooru, Konachan, Yandere and Sankaku, which can require
additional requests. When multiple tagging sources classify the same tag, the first
available category wins (MD5 matches, then SauceNAO, then the WD model).

Set `lookup_danbooru = true` to look up missing tags without source categories in
batches on Danbooru. The board uses its default category for tags that still
have no mapping. New classified tags are created
before the post is saved, and reused across workers. An auto-tagger dry run creates
no tags and updates no posts. Incorrect target categories and insufficient
permissions are reported as errors.

For compatibility, `[auto_tagger] remap_categories` and `category_map` are also
accepted and apply to imports as well. Explicit `[tag_categories]` settings take
precedence.

## Tag management

### Create relations

```sh
szuru-toolkit create-relations --threshold 3 "hitori_bocchi"
```

For a character and a series or parody that appear together often enough,
the command adds the series as an implication of the character. It also adds
the character as a suggestion on the series tag. In the example, the pair
`hitori_bocchi` and `bocchi_the_rock` must occur together on at least three posts.
Set the minimum with `--threshold` or `[create_relations].threshold`.

### Create tags

Use `create-tags` with a single tag name, a tag file, or a Danbooru tag query.
With no arguments it fetches up to 100 recent Danbooru tags used on at least
ten posts. Use `--query`, `--limit` and `--min-post-count` to change the
selection. `--overwrite` allows changing an existing tag's category.

```sh
szuru-toolkit create-tags
szuru-toolkit create-tags --query "genshin*" --overwrite
szuru-toolkit create-tags --query "genshin*" --import-implications
szuru-toolkit create-tags --tag-file tags.txt
szuru-toolkit create-tags --category character --implications "slime,monster_girl" slime_girl
```

A tag file is a comma-separated list with one tag per line. Put the tag
first, its category second, then any tags it should imply. Create the
categories in the board before importing. A missing category uses `default`.

```text
slime,default
monster_girl,default
slime_girl,character,slime,monster_girl
```

For tag files and single-tag creation, missing implied tags are created in
`default` unless their category is defined in the file. You can export tag
lists from tools such as [Grabber](https://github.com/Bionus/imgbrd-grabber).
For Danbooru queries, `--import-implications` also imports active Danbooru
implications and uses Danbooru categories for the implied tags.

### Edit tags on existing posts

```sh
szuru-toolkit tag-posts --add-tags "reviewed" --remove-tags "needs_review" "id:1234"
szuru-toolkit tag-posts --update-implications "character_tag"
```

`tag-posts` appends tags and source URLs by default. Use `--source` to add a
source URL. With `--mode overwrite`, supplied tags or source replace the
corresponding field. Use `--remove-tags` to remove selected tags, and
`--update-implications` to apply tag implications already defined in the
board. To clear tags and sources in bulk, see
[reset posts](maintenance.md#reset-posts).
