# Board maintenance

The query in these examples targets your szurubooru instance. Verify broad
queries in the board's search before running commands that modify posts.

## Find duplicate images

```sh
szuru-toolkit find-duplicates --threshold 4 --limit 100 "date:today"
```

The toolkit downloads matching images and compares their perceptual hashes.
`--threshold` is the maximum Hamming distance between hashes. A larger
threshold includes looser matches. Review the printed links before deciding
what to do with each group.

By default the command reports groups. With `--set-relations`, it links
the posts in each group to each other. Membership can be transitive. If
A matches B and B matches C, A and C can appear in the same group. The
command does not delete or merge posts.

## Complete post relations

```sh
szuru-toolkit fix-relations "date:today"
```

`fix-relations` follows existing post relations from the matching posts and
ensures every member of a connected group is related to every other member.
Related posts outside the query can also receive relation updates. To create
implications and suggestions between **tags**, see
[create relations](tagging.md#create-relations).

## Repair Sankaku source URLs

```sh
szuru-toolkit fix-sankaku-sources --dry-run "source:*sankaku*"
```

The command normalizes old Sankaku post URLs. For old MD5-based links, it
tries to resolve the corresponding post via Sankaku search. It reports
unresolvable URLs and preserves other source URLs. After reviewing the
dry run, omit `--dry-run` to apply the changes.

## Reset posts

```sh
szuru-toolkit reset-posts --add-tags "tagme" --except-ids "23,44" "id:10..50"
```

`reset-posts` clears the source and replaces the tag list with
`--add-tags`, or clears the tags when no replacement is supplied. The
media remains on the board. Use `--except-ids` to skip individual posts.

## Delete posts

```sh
szuru-toolkit delete-posts --except-ids "23,44" "id:10..50"
```

`delete-posts` deletes matching posts directly. It has no confirmation or
dry-run option. Check the exact query in szurubooru first, and use
`--except-ids` for posts you want to keep.
