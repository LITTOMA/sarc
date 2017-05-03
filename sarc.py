#!/usr/bin/python2

'''
MIT License

Copyright (c) 2017 LIT

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

import os, argparse
from struct import pack, unpack, calcsize

DEFAULT_HASH_KEY = 0x65

class Sarc(object):
    """SHArchive class

    A class for handling SHArchive.

    Attributes:
        header: Archive file header
        fatheader: FAT block header
        entries: File entries
        fnt_data: Binary File Name Table (FNT) data
        archive_data: Archive file data
    """


    def __init__(self, path='', order='', hash_key=DEFAULT_HASH_KEY):
        """Initialize Sarc class.

        Args:
            path: Path to an archive file when initializing with an archive for extraction or adding files,
                  or path to a directory when initializing with a directory for creation.
            order: Required only if you are creating an archive. Must be '>' or '<'.
            hash_key: Required only if you are creating an archive. Default 0x65 (101).

        Returns:
            None
        """
        if os.path.isfile(path):
            (self.header, self.fatheader, self.entries, 
             self.fnt_data, self.archive_data) = self._read_archive(path)
        elif os.path.isdir(path):
            self._base_path = path
            self._create_archive(order, hash_key)
    
    
    def _create_archive(self, order, hash_key):
        self.header = Sarc.ArchiveBlockHeader(order=order)
        self.fatheader = Sarc.FATBlockHeader(order=order, hash_key=hash_key)
        self.entries = None
        file_list = walk(self._base_path)
        for f in file_list:
            self._add_file_entry(f)
        self.fnt_data = ''
        self.archive_data = ''
    
    
    def _read_archive(self, path):
        cur_pos = 0
        data = open(path,'rb').read()
        header = Sarc.ArchiveBlockHeader(data[cur_pos:cur_pos + Sarc.ArchiveBlockHeader.C_STRUCTURE_SIZE])
        cur_pos += header.header_size
        fatheader = Sarc.FATBlockHeader(data=data[cur_pos:cur_pos + Sarc.FATBlockHeader.C_STRUCTURE_SIZE],
                                        order=header.order)
        cur_pos += fatheader.header_size
        fatentries = []
        for i in range(fatheader.file_count):
            fatentries.append(Sarc.FATEntry(data=data[cur_pos:cur_pos + Sarc.FATEntry.C_STRUCTURE_SIZE],
                                            order=header.order))
            cur_pos += Sarc.FATEntry.C_STRUCTURE_SIZE
        entries = {e.hash:e for e in fatentries}
        fntheader = Sarc.FNTBlockHeader(data=data[cur_pos:cur_pos+Sarc.FNTBlockHeader.C_STRUCTURE_SIZE],
                                        order=header.order)
        cur_pos += fntheader.header_size
        fnt_data = data[cur_pos:header.data_block_offset]
        archive_data = data[header.data_block_offset:]
        return header, fatheader, entries, fnt_data, archive_data
    
    
    def add_file_entry(self, path):
        """Add a file entry from file system to the 'entries' attribute.

        Args:
            path: Path to the file.

        Returns:
            None
        """
        entry = Sarc.FATEntry(order=self.header.order,
                              base_path=self._base_path,
                              file_path=path,
                              hash_key=self.fatheader.hash_key)
        if self.entries:
            self.entries[entry.hash] = entry
        else:
            self.entries = {entry.hash:entry}
    _add_file_entry = add_file_entry
    
    
    def archive(self, archive_path, verbose=False):
        """Archive the Sarc class instance to a binary file.
        
        Args:
            archive_path: Path to output.
            verbose: Print verbose information.
        
        Returns:
            None
        """
        fnt_list = []
        data_list = []
        packed_fat_entries = []
        cur_fnt_offset = len(self.fnt_data)
        cur_data_offset = len(self.archive_data)
        sorted_entries = [self.entries[k] for k in sorted(self.entries.keys())]
        
        for e in sorted_entries:
            cur_fnt_offset, cur_data_offset = e.archive(
                                            fnt_list,
                                            data_list,
                                            cur_fnt_offset,
                                            cur_data_offset)
            packed_fat_entries.append(e.pack())
            self.fatheader.file_count += 1
            if verbose:
                print 'Archived:', e.r_path
        
        if self.fatheader.file_count > Sarc.FATBlockHeader._C_ARCHIVE_ENTRY_MAX:
            print 'WARNING: File entries exceed.'
        
        archived_data = ''.join([self.header.pack(), self.fatheader.pack()])
        archived_data += ''.join(packed_fat_entries)
        archived_data += Sarc.FNTBlockHeader(order=self.header.order).pack()
        archived_data += self.fnt_data + ''.join(fnt_list)
        self.header.data_block_offset = len(archived_data)
        
        archived_data += self.archive_data + ''.join(data_list)
        self.header.file_size = len(archived_data)
        
        archive_file = open(archive_path, 'wb')
        archive_file.write(archived_data)
        archive_file.seek(0, 0)
        archive_file.write(self.header.pack())
        archive_file.close()
    
    
    def extract(self, path, all=False, name=None, hash=0, save_file=True, verbose=False):
        """Extract archived files.

        Args:
            path: Path to output.
            all: Extract all files.
            name: File name to extract.
            hash: Hash of the file to extract. If 'name' argument is set, this argument will be ignored.
            save_file: Save the file to file system. False for listing file(s).
            verbose: Print verbose infomation.

        Returns:
            None
        
        Raises:
            KeyError: When input file name or hash doesn't exist.
        """
        if all:
            for k in sorted(self.entries):
                self.extract(path,
                             all=False,
                             name=None,
                             hash=k,
                             save_file=save_file,
                             verbose=verbose)
        else:
            if name:
                hash = calchash(name, self.header.hash_key)
            if hash:
                r_path, full_path = self.entries[hash].extract(self.fnt_data,
                                                               self.archive_data,
                                                               path, save_file)
                if save_file and full_path and verbose:
                    print 'Saved:', full_path
                elif not save_file and r_path:
                    print 'Hash: %08X  Path: %s'%(hash, r_path)

    
    class BlockHeader(object):
        """Base class of blocks header.
        
        Attributes:
            signature: Signature of the class instance.
            header_size: Header size of the class instance.
            C_SIGNATURE: Constant signature value.
            C_STRUCTURE_SIZE: Constant structure size.
        """
        
        
        def check_valid(self):
            """Check if the class instance is valid.
            
            Raises:
                ValueError: Error occurred when class attribute invalid.
            """
            if self.signature != self.C_SIGNATURE:
                raise ValueError('Invalid signature ( except: "%s", actual: "%s" )'
                                 %(self.C_SIGNATURE, self.signature))
            if self.header_size != self.C_STRUCTURE_SIZE:
                raise ValueError('Invalid header size ( except: %x, actual: %x )'
                                 %(self.C_STRUCTURE_SIZE, self.header_size))
    
    
    class ArchiveBlockHeader(BlockHeader):
        """Archive block header class.
        
        Attributes:
            signature: Signature of the class instance.
            header_size: Header size of the class instance.
            bom: Byte-order mark. Always 0xfeff.
            file_size: Archive file size.
            data_block_offset: Data block offset relate to zero.
            version: Archive version.
            order: Byte order.
            C_SIGNATURE: Constant signature value.
            C_STRUCTURE_SIZE: Constant structure size.
            HEADER_STRUCT: Structure of the binary archive's header.
        """
        HEADER_STRUCT = '4sHHIIHH'
        C_STRUCTURE_SIZE = calcsize(HEADER_STRUCT)
        C_SIGNATURE = 'SARC'
        _C_ARCHIVE_VERSION = 0x0100
        
        def __init__(self, data=None, order=''):
            """Initialize ArchiveBlockHeader class.

            Args:
                data: Required only if you are initializing the Sarc class with an archive.
                order: Required only if you are creating an archive. Must be '>' or '<'.

            Returns:
                None
            """
            if data:
                bom = data[6:8]
                self.order = '<' if (bom == '\xff\xfe') else '>'
                (self.signature,
                 self.header_size,
                 self.bom,
                 self.file_size,
                 self.data_block_offset,
                 self.version,
                 reserved) = unpack(self.order + self.HEADER_STRUCT,
                                    data[:self.C_STRUCTURE_SIZE])
                self._check_valid()
            else:
                self.order = order
                self.signature = self.C_SIGNATURE
                self.header_size = self.C_STRUCTURE_SIZE
                self.bom = 0xfeff
                self.file_size = 0
                self.data_block_offset = 0
                self.version = self._C_ARCHIVE_VERSION
        
        
        def check_valid(self):
            """Check if the class instance is valid.
            
            Raises:
                ValueError: Error occurred when class attribute invalid.
            """
            super(Sarc.ArchiveBlockHeader, self).check_valid()
            if self.bom != 0xfeff:
                raise ValueError('Invalid BOM value ( except: %x, actual: %x )'
                                 %(0xfeff, self.bom))
            if self.version != self._C_ARCHIVE_VERSION:
                raise ValueError('Invalid archive version ( except: %x, actual: %x )'
                                 %(self._C_ARCHIVE_VERSION, self.version))
        _check_valid = check_valid
        
        
        def pack(self):
            """Pack the class instance to a str according to 'HEADER_STRUCT'.
            
            Args:
                None
            
            Returns:
                Packed structure data.
            """
            return pack(self.order + self.HEADER_STRUCT, self.C_SIGNATURE, self.header_size, self.bom, 
                        self.file_size, self.data_block_offset, self.version, 0)
    
    
    class FATBlockHeader(BlockHeader):
        """Archive file entry block header class.
        
        Attributes:
            signature: Signature of the class instance.
            header_size: Header size of the class instance.
            file_count: Number of file entries.
            hash_key: Hash key of file name hash.
            order: Byte order.
            C_SIGNATURE: Constant signature value.
            C_STRUCTURE_SIZE: Constant structure size.
            HEADER_STRUCT: Structure of the binary archive's FAT header.
        """
        HEADER_STRUCT = '4sHHI'
        C_STRUCTURE_SIZE = calcsize(HEADER_STRUCT)
        C_SIGNATURE = 'SFAT'
        _C_ARCHIVE_ENTRY_MAX = 0x3fff
        
        def __init__(self, data=None, order='', hash_key=DEFAULT_HASH_KEY):
            self.order = order
            if data:
                (self.signature,
                 self.header_size,
                 self.file_count,
                 self.hash_key) = unpack(order + self.HEADER_STRUCT,
                                         data[:self.C_STRUCTURE_SIZE])
                self._check_valid()
            else:
                self.signature = self.C_SIGNATURE
                self.header_size = self.C_STRUCTURE_SIZE
                self.file_count = 0
                self.hash_key = hash_key
        
        
        def check_valid(self):
            """Check if the class instance is valid.
            
            Raises:
                ValueError: Error occurred when class attribute invalid.
            """
            super(Sarc.FATBlockHeader, self).check_valid()
            if self.file_count > self._C_ARCHIVE_ENTRY_MAX:
                raise ValueError('Invalid file count: %x'%self.file_count)
        _check_valid = check_valid
        
        
        def pack(self):
            """Pack the class instance to a str according to 'HEADER_STRUCT'.
            
            Args:
                None
            
            Returns:
                Packed structure data.
            """
            return pack(self.order + self.HEADER_STRUCT, self.C_SIGNATURE,
                        self.header_size, self.file_count, self.hash_key)
    
    
    class FATEntry(object):
        """Archive file entry class.
        
        Attributes:
            hash: File name hash
            name_offset: File name offset. Relate to file name table start.
            data_start_offset: File data start offset. Relate to file data block start.
            data_end_offset: File data end offset. Relate to file data block start.
            order: Byte order.
            type: Entry type.
            C_STRUCTURE_SIZE: Constant structure size.
            ENTYR_STRUCT: Structure of the binary archive entry.
            ARCHIVED: Archived file entry.
            FILESYSTEM: File system file entry.
        """
        ENTYR_STRUCT = 'IIII'
        C_STRUCTURE_SIZE = calcsize(ENTYR_STRUCT)
        _C_FNT_ALIGNMENT = 4
        
        ARCHIVED = 0
        FILESYSTEM = 1
        
        def __init__(self, data=None, order='', base_path='',
                     file_path='', hash_key=DEFAULT_HASH_KEY):
            self.order = order
            if data:
                self.type = self.ARCHIVED
                (self.hash,
                 self.name_offset,
                 self.data_start_offset,
                 self.data_end_offset) = unpack(order + self.ENTYR_STRUCT,
                                                data[:self.C_STRUCTURE_SIZE])
                self._check_valid()
            else:
                self.type = self.FILESYSTEM
                self.path = file_path
                self.r_path = getrpath(base_path, file_path)
                self.hash = calchash(self.r_path, hash_key)
                self.name_offset = 0
                self.data_start_offset = 0
                self.data_end_offset = 0
        
        
        def _align_data(self, data, cur_pos):
            if self._is_bflim(data):
                alignment = self._read_bflim_alignment(data)
                return align(cur_pos, alignment) - cur_pos
            else:
                return 0
        
        
        def _align_fn(self, fn, alignment):
            return align(len(fn), alignment) - len(fn)
        
        
        def _is_bflim(self, data):
            return ((data[-0x28:-0x24] == 'FLIM') and
                    (len(data) == unpack(self.order + 'I', data[-0x1C:-0x18])[0]))
        
        
        def _read_bflim_alignment(self, data):
            return unpack(self.order + 'H', data[-8:-6])[0]
        
        
        def archive(self, fnt_list, data_list, cur_fnt_offset, cur_data_offset):
            if self.type == self.ARCHIVED:
                return cur_fnt_offset, cur_data_offset
            elif self.type == self.FILESYSTEM:
                file_data = open(self.path, 'rb').read()
                feed = self._align_data(file_data, cur_data_offset)
                if feed > 0:
                    data_list.append(feed * '\x00')
                    cur_data_offset += feed
                data_list.append(file_data)
                
                self.data_start_offset = cur_data_offset
                self.data_end_offset = cur_data_offset + len(file_data)
                self.name_offset = ((cur_fnt_offset / self._C_FNT_ALIGNMENT)
                                    & 0x00ffffff) | (1 << 24) # Always (1 << 24) ?
                
                r_path = self.r_path + '\x00'
                r_path += self._align_fn(r_path, self._C_FNT_ALIGNMENT) * '\x00'
                cur_fnt_offset += len(r_path)
                fnt_list.append(r_path)
                
                return cur_fnt_offset, self.data_end_offset
        
        
        def check_valid(self):
            pass
        _check_valid = check_valid
        
        
        def extract(self, fnt_data, archive_data, path, save_file):
            if self.type == self.ARCHIVED:
                name_offset = self.name_offset & 0x00ffffff
                r_path = get_string(fnt_data[name_offset * self._C_FNT_ALIGNMENT:])
                
                outpath = os.path.join(path, r_path)
                outdir, name = os.path.split(outpath)
                
                if save_file:
                    mkdirs(outdir)
                    data = archive_data[self.data_start_offset:self.data_end_offset]
                    write_file(outpath, data)
                return r_path, outpath
            else:
                return '', ''
        
        
        def pack(self):
            """Pack the class instance to a str according to 'HEADER_STRUCT'.
            
            Args:
                None
            
            Returns:
                Packed structure data.
            """
            return pack(self.order + self.ENTYR_STRUCT, self.hash, self.name_offset, 
                        self.data_start_offset, self.data_end_offset)
    
    
    class FNTBlockHeader(BlockHeader):
        HEADER_STRUCT = '4sHH'
        C_STRUCTURE_SIZE = calcsize(HEADER_STRUCT)
        C_SIGNATURE = 'SFNT'
        
        def __init__(self, data=None, order=''):
            self.order = order
            if data:
                (self.signature,
                 self.header_size,
                 reserved) = unpack(order + self.HEADER_STRUCT,
                                    data[:self.C_STRUCTURE_SIZE])
                self._check_valid()
            else:
                self.signature = self.C_SIGNATURE
                self.header_size = self.C_STRUCTURE_SIZE
        
        
        def check_valid(self):
            """Check if the class instance is valid.
            
            Raises:
                ValueError: Error occurred when class attribute invalid.
            """
            super(Sarc.FNTBlockHeader, self).check_valid()
        _check_valid = check_valid
        
        
        def pack(self):
            """Pack the class instance to a str according to 'HEADER_STRUCT'.
            
            Args:
                None
            
            Returns:
                Packed structure data.
            """
            return pack(self.order + self.HEADER_STRUCT, 
                        self.signature, self.header_size, 0)
    
    
def align(value, alignment):
    return (value + alignment -1) / alignment * alignment


def calchash(data, key):
    """Calculate file name hash.
    
    Args:
        data: File name data.
        key: Hash key.
    
    Returns:
        Hash value.
    """
    ret = 0
    for c in data:
        ret = (ret * key + ord(c)) & 0xffffffff
    return ret


def get_string(data):
    """Get string ending with '\0'.
    
    Args:
        data: Data containing string.
    
    Returns:
        String without '\0'.
    """
    ret = ''
    for c in data:
        if '\x00' == c:
            break
        ret += c
    return ret


def getrpath(base, full):
    """Get relative path."""
    ret = full[len(base):]
    while ret[0] in ['/','\\']:
        ret = ret[1:]
    return ret.replace('\\','/')

    
def mkdirs(path):
    if not os.path.exists(path):
        os.makedirs(path)


def walk(dirname):
    filelist = []
    for root,dirs,files in os.walk(dirname):
        for filename in files:
            fullname=os.path.join(root,filename)
            filelist.append(fullname)
    return filelist


def write_file(path, data):
    fs = open(path, 'wb')
    fs.write(data)
    fs.close()


#Helper methods
def create_archive(path, archive, order, hash_key, verbose):
    """Create an archive from the input directory.
    
    Args:
        path: Path to a directory.
        archive: Path to the archive.
        order: Byte order of the archive. Must be '>' or '<'.
        hash_key: File name hash key. Default 0x65.
        verbose: Enable verbose output.
    
    Returns:
        Boolean
    """
    if (not path) or (not os.path.exists(path)):
        print 'Directory does not exist. Create archive failed.'
        return False
    sarc = Sarc(path=path, order=order, hash_key=hash_key)
    sarc.archive(archive_path=archive, verbose=verbose)


def extract_archive(path, archive, verbose):
    """Extract an archive to the specified directory.
    
    Args:
        path: Path to output directory.
        archive: Path to the archive.
        verbose: Enable verbose output.
    
    Returns:
        Boolean
    """
    if not path:
        print "Output directory hasn't set. Extract archive failed."
        return False
    sarc = Sarc(path=archive)
    sarc.extract(path=path, all=True, verbose=verbose)


def list_archive(archive):
    """List contents in the archive.
    
    Args:
        archive: Path to the archive.
    
    Returns:
        None
    """
    sarc = Sarc(path=archive)
    sarc.extract(path='', all=True, save_file=False)

if '__main__' == __name__:
    endianess = {'big':'>', 'little':'<'}
    parser = argparse.ArgumentParser(description='Nintendo Ware Layout SHArchive Tool')
    parser.add_argument('-v', '--verbose', help='Enable verbose output', action='store_true', default=False)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-x', '--extract', help='Extract the archive', action='store_true', default=False)
    group.add_argument('-c', '--create', help='Create an archive', action='store_true',default=False)
    group.add_argument('-l', '--list', help='List contents of the archive', action='store_true', default=False)
    parser.add_argument('-e', '--endianess', help='Set archive endianess', choices=['big', 'little'], type=str, default='little')
    parser.add_argument('-k', '--hashkey', help='Set hash key', default=DEFAULT_HASH_KEY)
    parser.add_argument('-d', '--dir', help='Set working directory')
    parser.add_argument('-f', '--archive', help='Set archive file', required=True)
    args = parser.parse_args()
    
    if args.create:
        create_archive(args.dir, args.archive, endianess[args.endianess], args.hashkey, args.verbose)
    if args.extract:
        extract_archive(args.dir, args.archive, args.verbose)
    if args.list:
        list_archive(args.archive)
    
