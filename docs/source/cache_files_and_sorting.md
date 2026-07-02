# Cache files and sorting filenames

## Cache files

The Slocum gliders store their binary data files (dbd, ebd and
friends) in a compact form: the sensor list, along with the size and
type of each sensor, is only written to the file's header if it is
not already known. If it is known, the header only references it by
an ID. The full sensor list belonging to that ID is stored separately
in a so-called CAC (cache) file. To be able to read a data file,
dbdreader therefore also needs access to the matching CAC file(s).

By default, dbdreader keeps a copy of the CAC files it encounters in a
single, fixed cache directory, so that you do not have to hunt down
and supply CAC files yourself for every dbd/ebd file you want to
read. The {class}`dbdreader.DBDCache <dbdreader.dbdreader.DBDCache>` class manages this directory.

The default cache directory is set automatically when dbdreader is
imported:

- On Linux: `$HOME/.local/share/dbdreader`
- On Windows: `$HOME/.dbdreader`

For most use cases you never need to interact with
{class}`dbdreader.DBDCache <dbdreader.dbdreader.DBDCache>` directly, since {class}`dbdreader.DBD`,
{class}`dbdreader.MultiDBD` and {class}`dbdreader.DBDPatternSelect`
all fall back to this default directory automatically when no
`cacheDir` argument is given. There are, however, a few situations
where you may want to change or query where CAC files are stored.

### Example 1: overriding the default cache directory for the whole session

If you want *all* subsequently created `DBD`/`MultiDBD` objects to use
a different cache directory (for example because you keep CAC files
for a specific glider project in a dedicated folder), set it once at
the start of your script:

```python
import dbdreader

dbdreader.DBDCache.set_cachedir("/home/user/gliderdata/amadeus/cac")

# from here on, DBD and MultiDBD objects use this directory by default
dbd = dbdreader.DBD("data/amadeus-2014-204-05-000.sbd")
```

```{note}
`set_cachedir()` raises an error if the given directory does not
exist. Use the class constructor (see Example 2) instead if you want
the directory to be created automatically.
```

### Example 2: creating the cache directory if it does not exist yet

Calling {class}`dbdreader.DBDCache <dbdreader.dbdreader.DBDCache>` directly, rather than
`set_cachedir()`, has the same effect, except that the target
directory is created if it does not exist yet:

```python
import dbdreader

dbdreader.DBDCache("/home/user/gliderdata/amadeus/cac")
```

### Example 3: reading a single file from a non-default cache location

If you only need to read a handful of files from a cache directory
that is different from your session-wide default, you do not need to
touch {class}`dbdreader.DBDCache <dbdreader.dbdreader.DBDCache>` at all — simply pass `cacheDir` to
the constructor of {class}`dbdreader.DBD` or {class}`dbdreader.MultiDBD`
for that one call:

```python
import dbdreader

dbd = dbdreader.DBD("data/amadeus-2014-204-05-000.sbd",
                     cacheDir="/home/user/gliderdata/other_project/cac")
```

This leaves the session-wide default cache directory (as managed by
{class}`dbdreader.DBDCache <dbdreader.dbdreader.DBDCache>`) untouched for all other files.

## Sorting filenames

Slocum data filenames encode a segment number as four fields, for
example `unit204-2014-212-0-3.dbd`. Because these fields are not
zero-padded, a plain alphabetical sort of filenames does not put them
in the correct chronological order (`unit204-2014-212-0-30.dbd` would
sort before `unit204-2014-212-0-3.dbd`, for instance). The
{class}`dbdreader.DBDList <dbdreader.dbdreader.DBDList>` class is a `list` subclass that fixes this
by overriding `sort()` to compare files by their segment fields
instead of alphabetically.

```python
import dbdreader

filenames = dbdreader.DBDList(
    ["unit204-2014-212-0-30.dbd",
     "unit204-2014-212-0-3.dbd",
     "unit204-2014-212-0-100.dbd"]
)
filenames.sort()
print(filenames)
# ['unit204-2014-212-0-3.dbd', 'unit204-2014-212-0-30.dbd', 'unit204-2014-212-0-100.dbd']
```

`DBDList` behaves like a regular list in every other respect (it can
be indexed, iterated, appended to, and so on); only `sort()` is
specialised.
