# Beta 1.1 CDX and media hotfix

## Malformed HTTP 200 CDX responses

The Wayback CDX service can occasionally return an HTTP 200 body that begins as valid JSON but contains a malformed, incomplete, or truncated row later in the response. Beta 1 treated some of these bodies as permanent local parsing failures.

Beta 1.1 uses this recovery order:

1. Parse the normal JSON response.
2. If JSON is malformed, repeat the same endpoint and query as uncompressed plain-text CDX.
3. Put `original` last in the fallback field order so historical URLs containing literal spaces can be parsed without losing columns.
4. Parse plain-text resume keys and page counts.
5. If both bodies are unusable, rotate to the alternate CDX endpoint.
6. If all endpoints fail, return a splittable transient error to the existing saved-window recovery system.

A JSON decoder failure therefore no longer bypasses endpoint rotation, date-window subdivision, or resumable indexing.

## Combined media indexing

Beta 1 used `~original:` for its combined extension filter. The supported field-filter form is `original:regex`. Beta 1.1 corrects the filter while preserving one combined extension expression per target and date window.

The filter and local validator now recognize legacy forms such as:

```text
photo.jpg&ref=thumbnail
movie.wmv;session=123
player?file=clip.flv&autoplay=1
```

Explicit `prefix`, `host`, and `domain` media targets are normalized before sending `matchType`, so a wildcard is not accidentally treated as literal target text.

The media-index state signature includes revision 2 while the capture signature remains stable. A Beta 1 project whose broken media index was already marked complete will therefore run a fresh corrected media index after upgrading.
