# Archive recovery and analysis

The archive-analysis system was introduced during Archive Scout 2.0 Alpha 3 and remains part of Archive Scout 3.0.

Analysis runs against documents already saved in the project. It does not need to redownload text pages unless an external-asset lookup is explicitly enabled.

## Forum reconstruction

Archive Scout canonicalizes thread URLs, removes common pagination/session/tracking values, detects several forum families, and groups parsed posts across saved snapshots.

Supported profiles include:

- automatic
- generic
- vBulletin
- phpBB
- Invision
- Futaba
- 2channel-style

## Extraction

Built-in extractors cover common legacy identifiers and media references. Custom rules use:

```text
name :: regular expression
name :: field :: regular expression
```

Fields are `title`, `body`, `url`, `source`, and `links`.

## Legacy assets

The parser inspects `object`, `embed`, `param`, `iframe`, `frame`, `video`, `audio`, `source`, FlashVars, and common script configuration patterns.

## Duplicate, snapshot, and provenance research

- exact and normalized duplicate groups
- SimHash near-duplicate candidates
- adjacent snapshot comparisons
- first and last appearances of extracted values
- possible source-to-mirror relationships based on capture order and similarity

These outputs are research leads and do not prove authorship or original publication.
