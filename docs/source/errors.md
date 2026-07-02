# Handling errors: DbdError

All errors raised by dbdreader — corrupt files, missing cache files,
unreadable parameters, and so on — are reported as a single exception
type: {class}`dbdreader.DbdError <dbdreader.dbdreader.DbdError>`. Catching this one
exception is therefore sufficient to guard against any error dbdreader
itself might raise.

```python
import dbdreader

try:
    dbd = dbdreader.DBD("data/amadeus-2014-204-05-000.sbd")
    t, d = dbd.get("m_depth_nonexistent")
except dbdreader.DbdError as e:
    print(f"Could not read data: {e}")
```

Printing (or `str()`-ing) a `DbdError` yields a human readable message
describing what went wrong, for example `"The requested parameter(s)
was(were) not found."` for the example above.

## Inspecting the error in more detail

Besides the message, a `DbdError` carries two attributes that let you
handle specific error conditions programmatically instead of parsing
the message text:

- `value`: an integer identifying the kind of error, one of the
  `DBD_ERROR_*` constants defined in the `dbdreader.dbdreader` module
  (for example `DBD_ERROR_NO_VALID_PARAMETERS` or
  `DBD_ERROR_CACHE_NOT_FOUND`).
- `data`: an optional payload with extra information about the
  error. Its content depends on `value`; for example, when the error
  is caused by missing CAC cache files, `data` is a
  `DbdError.MissingCacheFileData` namedtuple with fields
  `missing_cache_files` and `cache_dir`.

```python
import dbdreader

try:
    dbd = dbdreader.DBD("data/some_file_without_matching_cache.sbd")
except dbdreader.DbdError as e:
    if e.value == dbdreader.dbdreader.DBD_ERROR_CACHE_NOT_FOUND:
        print("Missing CAC file(s):", e.data.missing_cache_files)
        print("Looked in:", e.data.cache_dir)
    else:
        raise
```

```{note}
See {doc}`cache_files_and_sorting` for how the cache directory that
`cache_dir` refers to is determined and how to change it.
```
