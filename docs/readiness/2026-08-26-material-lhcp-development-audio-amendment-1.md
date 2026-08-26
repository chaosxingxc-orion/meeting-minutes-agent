# E-MATERIAL-LHCP-DEVELOPMENT-AUDIO amendment 1

## Trigger

The first acquisition attempt completed the first registered development Parquet
and wrote five valid WAV files. While reading the second Parquet, one HTTP Range
response requested 448,670,644 bytes and disconnected after 111,762,743 bytes.
The run stopped with `ChunkedEncodingError` before producing a download manifest
or success receipt. No confirmation shard, reference column, front end, or model
was accessed.

## Transport-only correction

Keep the source revision, six development files, projected columns, 25-item set,
and all gates unchanged. Satisfy each range requested by `pyarrow` through ordered
subranges of at most 16 MiB, with at most five transport attempts per subrange.
Every successful subrange must have status 206 and exact requested length.

On restart, an existing WAV may be reused only after the same frozen source payload
is downloaded again and its byte count and SHA-256 exactly match the existing file.
Any mismatch fails closed. This rule avoids deleting valid outputs while preventing
an unbound local file from entering the final manifest.

This amendment changes transport reliability only. It does not authorize a new
column, split, item, retry at the model layer, or any outcome-dependent choice.
