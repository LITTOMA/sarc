# Nintendo Ware Layout SHArchive Tool
### Usage:
```
sarc.py [-h] [-v] (-x | -c | -l) [-e {big,little}] [-k HASHKEY]
        [-d DIR] -f ARCHIVE
```

```
optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Enable verbose output
  -x, --extract         Extract the archive
  -c, --create          Create an archive
  -l, --list            List contents in the archive
  -e {big,little}, --endianess {big,little}
                        Set archive endianess
  -k HASHKEY, --hashkey HASHKEY
                        Set hash key
  -d DIR, --dir DIR     Set working directory
  -f ARCHIVE, --archive ARCHIVE
                        Set archive file
```
