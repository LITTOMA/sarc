import os, zlib
from struct import pack, unpack, calcsize

def write_file(path, data):
    fs = open(path, 'wb')
    fs.write(data)
    fs.close()

def mkdirs(path):
    if not os.path.exists(path):
        os.makedirs(path)

def calchash(data, key):
    ret = 0
    for c in data:
        ret = (ret * key + ord(c)) & 0xffffffff
    return ret

def get_string(data):
    ret = ''
    for c in data:
        if '\x00' == c:
            break
        ret += c
    return ret

class Sarc:
    class BlockHeader(object):
        def check_valid(self):
            if self.signature != self.cSignature:
                raise ValueError('Invalid signature ( except: "%s", actual: "%s" )'%(self.cSignature, self.signature))
            if self.header_size != self.cStructSize:
                raise ValueError('Invalid header size ( except: %x, actual: %x )'\
                                 %(self.cStructSize, self.header_size))
    
    class ArchiveBlockHeader(BlockHeader):
        HEADER_STRUCT = '4sHHIIHH'
        cStructSize = calcsize(HEADER_STRUCT)
        cSignature = 'SARC'
        __cArchiveVersion = 0x0100
        
        def __init__(self, data = None, order = ''):
            if data:
                bom = data[6:8]
                self.order = '<' if (bom == '\xff\xfe') else '>'
                self.signature, self.header_size, self.bom, self.file_size,\
                                  self.data_block_offset, self.version, reserved = \
                                  unpack(self.order + self.HEADER_STRUCT, data[:self.cStructSize])
                self.__check_valid()
            else:
                self.order = order
                self.signature = self.cSignature
                self.header_size = self.cStructSize
                self.bom = 0xfeff
                self.file_size = 0
                self.data_block_offset = 0
                self.version = self.__cArchiveVersion
        
        def check_valid(self):
            super(Sarc.ArchiveBlockHeader, self).check_valid()
            if self.bom != 0xfeff:
                raise ValueError('Invalid BOM value ( except: %x, actual: %x )'%(0xfeff, self.bom))
            if self.version != self.__cArchiveVersion:
                raise ValueError('Invalid archive version ( except: %x, actual: %x )'\
                                 %(self.__cArchiveVersion, self.version))
        __check_valid = check_valid
        
        def pack(self):
            return pack(self.order + self.HEADER_STRUCT, self.cSignature, self.header_size, self.bom, self.file_size,\
                                  self.data_block_offset, self.version, 0)

    class FATBlockHeader(BlockHeader):
        HEADER_STRUCT = '4sHHI'
        cStructSize = calcsize(HEADER_STRUCT)
        cSignature = 'SFAT'
        __cArchiveEntryMax = 0x3fff
        
        def __init__(self, data = None, order = '', hash_key = 0x65):
            self.order = order
            if data:
                self.signature, self.header_size, self.file_count, self.hash_key = \
                            unpack(order + self.HEADER_STRUCT, data[:self.cStructSize])
                self.__check_valid()
            else:
                self.signature = self.cSignature
                self.header_size = self.cStructSize
                self.file_count = 0
                self.hash_key = hash_key
        
        def check_valid(self):
            super(Sarc.FATBlockHeader, self).check_valid()
            if self.file_count > self.__cArchiveEntryMax:
                raise ValueError('Invalid file count: %x'%self.file_count)
        __check_valid = check_valid
        
        def pack(self):
            return pack(self.order + self.HEADER_STRUCT, self.cSignature, \
                        self.header_size, self.file_count, self.hash_key)
    
    class FNTBlockHeader(BlockHeader):
        HEADER_STRUCT = '4sHH'
        cStructSize = calcsize(HEADER_STRUCT)
        cSignature = 'SFNT'
        
        def __init__(self, data = None, order = ''):
            self.order = order
            if data:
                self.signature, self.header_size, reserved = \
                            unpack(order + self.HEADER_STRUCT, data[:self.cStructSize])
                self.__check_valid()
            else:
                self.signature = self.cSignature
                self.header_size = self.cStructSize
        
        def check_valid(self):
            super(Sarc.FNTBlockHeader, self).check_valid()
        __check_valid = check_valid
        
        def pack(self):
            return pack(self.order + self.HEADER_STRUCT, self.signature, self.header_size, 0)
    
    class FATEntry:
        ENTYR_STRUCT = 'IIII'
        cStructSize = calcsize(ENTYR_STRUCT)
        __cFNTAlign = 4
        
        ARCHIVED = 0
        FILESYSTEM = 1
        
        def __init__(self, data = None, order = '', r_path = '', hash_key = 0x65):
            self.order = order
            if data:
                self.type = self.ARCHIVED
                self.hash, self.name_offset, self.data_start_offset, self.data_end_offset = \
                            unpack(order + self.ENTYR_STRUCT, data[:self.cStructSize])
                self.__check_valid()
            else:
                self.type = self.FILESYSTEM
                self.r_path = r_path
                self.hash = calchash(r_path, hash_key)
                self.name_offset = 0
                self.data_start_offset = 0
                self.data_end_offset = 0
        
        def check_valid(self):
            pass
        __check_valid = check_valid
        
        def extract(self, fnt_data, archive_data, path):
            name_offset = self.name_offset & 0x00ffffff
            r_path = get_string(fnt_data[name_offset * self.__cFNTAlign:])
            
            outpath = os.path.join(path, r_path)
            outdir, name = os.path.split(outpath)
            mkdirs(outdir)
            
            data = archive_data[self.data_start_offset:self.data_end_offset]
            write_file(outpath, data)
            return r_path, outpath
        
        def pack(self):
            return pack(self.order + self.ENTYR_STRUCT, \
                        self.hash, self.name_offset, self.data_start_offset, data_end_offset)

    def __init__(self, path = ''):
        if os.path.isfile(path):
            self.header, self.entries, self.fnt_data, self.archive_data = self.__read_archive(path)
        elif os.path.isdir(path):
            pass

    def __read_archive(self, path):
        cur_pos = 0
        data = open(path,'rb').read()
        header = Sarc.ArchiveBlockHeader(data[cur_pos:cur_pos + Sarc.ArchiveBlockHeader.cStructSize])
        cur_pos += header.header_size
        fatheader = Sarc.FATBlockHeader(data = data[cur_pos:cur_pos + Sarc.FATBlockHeader.cStructSize], order = header.order)
        cur_pos += fatheader.header_size
        fatentries = []
        for i in range(fatheader.file_count):
            fatentries.append(Sarc.FATEntry(data = data[cur_pos:cur_pos + Sarc.FATEntry.cStructSize], order = header.order))
            cur_pos += Sarc.FATEntry.cStructSize
        entries = {e.hash:e for e in fatentries}
        fntheader = Sarc.FNTBlockHeader(data = data[cur_pos:cur_pos+Sarc.FNTBlockHeader.cStructSize], order = header.order)
        cur_pos += fntheader.header_size
        fnt_data = data[cur_pos:header.data_block_offset]
        archive_data = data[header.data_block_offset:]
        return header, entries, fnt_data, archive_data
    
    def extract(self, path, all = False, name = None, hash = 0):
        if all:
            for k in self.entries:
                self.extract(path, all = False, name = None, hash = k)
        else:
            if name:
                hash = calchash(name, self.header.hash_key)
            if hash:
                r_path, out_path = self.entries[hash].extract(self.fnt_data, self.archive_data, path)
                print 'Save:', r_path
        
if '__main__' == __name__:
    pass
