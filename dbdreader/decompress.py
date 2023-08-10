import os
from io import BytesIO as ioBytesIO
from re import search as re_match
import lz4.block


class Decompressor:
    '''Class to decompress glider files

    Parameters
    ----------
    filename : str
        name of file to decompress

    This class is designed to be used with a context manager

    >>> with Decompressor(filename) as d:
             data = d.decompress()

    Alternatively, a file can be opened a priori


    >>> d = Decompressor()
    >>> fd = open(filename ,'rb')
    >>> data = d.decompress(fd)
    '''
    SIZEFIELDSIZE = 2
    ENDIANESS = 'big'
    COMPRESSION_FACTOR=10
    CHUNKSIZE = 1024*32
    def __init__(self, filename=None, fp=None):
        self.filename = filename
        self.fp = fp
    
        
    def __enter__(self, *p, **kwds):
        # Try to open file is self.filename is given, otherwise check wheter self.fp is given.
        # if not, raise an error.
        if not self.filename is None:
            self.fp = open(self.filename,'rb')
        if self.fp is None:
            raise ValueError('Supply either a filename or file descriptor to the class constructor.')
        return self

    def __exit__(self, *p, **kwds):
        # close the file and leave.
        self.fp.close()
        
    def _decompress_block(self, fp=None):
        fp = fp or self.fp
        sb = fp.read(Decompressor.SIZEFIELDSIZE)
        if sb:
            size = int.from_bytes(sb, Decompressor.ENDIANESS)
            b = lz4.block.decompress(fp.read(size), Decompressor.CHUNKSIZE)
        else:
            b = None
        return b
    
    def decompressed_blocks(self, n=None, fp=None):
        ''' Generator that returns decompressed data blocks

        Parameters
        ----------
        n : int or None
            limits the number of blocks read and returned. If None (default) all blocks are returned
        fp : file descriptor or None
            file descriptor to use. If None (default), the file descriptor assigned by the constructor is used.

        Yields
        ------
        bytes:
             decompressed data block
        '''
        counter = 0
        if n is None:
            counter_increment = 0
            n = 1
        else:
            counter_increment = 1
        while counter < n:
            block = self._decompress_block(fp)
            if block is None:
                break
            yield block
            counter+=counter_increment

    def decompress(self, fp=None):
        ''' Decompresses a an entire file (in memory)

        Parameters
        ----------
        fp : file descriptor or None
            file descriptor to use. If None (default), the file descriptor assigned by the constructor is used.

        Returns
        -------
        bytes:
            decompressed file data as bytes
        '''
        fp = fp or self.fp
        if fp is None:
            raise ValueError('Supply a file handler or use this class within a context manager')
        data =b''
        for block in self.decompressed_blocks(fp=fp):
            data += block
        return data
        

class FileDecompressor:
    '''Class that provides an easy way to automatically decompress a compressed glider
       data file and write it into a normal binary data file.

    The factual decompressing is done by decompress method.

    Example
    -------

    >>> FileDecompressor.decompress("01600000.dcd")

    which would result in the writing of a decompressed file 01600000.dbd.
    
    '''
    def _generate_filename_for_output(self, filename):
        base, ext = os.path.splitext(filename)
        if len(ext)!=4:
            raise ValueError('Unhandled file extension.')
        if ext.endswith('cg'):
            s = 'lg'
        elif ext.endswith('cd'):
            s = 'bd'
        elif ext.endswith('cc'):
            s = 'ac'
        else:
            raise ValueError('Unhandled file extension.')
        return "".join((base, ext[:-2], s))
                         
    def decompress(self, filename):
        ''' Decompresses a file

        Parameters
        ----------
        filename : str
            (compressed) filename

        Returns
        -------
        str:
            uncompressed filename

       '''
        output_filename = self._generate_filename_for_output(filename)
        with Decompressor(filename) as d, open(output_filename, 'wb') as fp_out:
            for block in d.decompressed_blocks():
                fp_out.write(block)
        return output_filename

def decompress_file(filename):
    '''Decompreses a glider data file and writes the normal binary file.'''
    return FileDecompressor().decompress(filename)

def is_compressed(filename):
    [basename,ext]=os.path.splitext(filename)
    # all compressed [demnst]bd files end in [demnst]cd
    return bool(re_match("[demnst]c[dg]$", ext))


class BytesIORW:
    ''' Helper class implementing a BytesIO buffer that can be written to and read from.

    Note that the methods write() and readline() are implemented only.
    '''
    def __init__(self, source):
        self.bytesIO = ioBytesIO()
        self.pointer_start = 0
        self.pointer_end = 0
        self.source = source
        
    def write(self, b):
        self.pointer_start = self.bytesIO.tell()
        self.bytesIO.write(b)
        self.pointer_end = self.bytesIO.tell()
        self.bytesIO.seek(self.pointer_start)
        self.is_exhausted = False
        
    def readline(self):
        line = self.bytesIO.readline()
        pointer = self.bytesIO.tell()
        if pointer == self.pointer_end:
            try:
                self.write(next(self.source))
            except StopIteration:
                pass
            else:
                line+=self.bytesIO.readline()
        return line
        

class CompressedFile:
    ''' Class to access a compressed file, providing a method

    readline() that returns a decompressed line of data. The compressed
    file is read block by block, as long as needed.

    The main reason for the class is to be able to read the header of a compressed
    glider data file.
    '''
    

    def __init__(self, filename):
        self.filename = filename
        self.decompressor = Decompressor()
        self.bytesIO = None

    def __enter__(self, *p, **kwds):
        self.fp = open(self.filename, 'rb')
        source = self.decompressor.decompressed_blocks(fp=self.fp)
        self.bytesIO = BytesIORW(source)
        return self

    
    def __exit__(self, *p, **kwds):
        self.fp.close()

    def readline(self):
        line = self.bytesIO.readline()
        return line
    
    def readlines(self):
        while True:
            line = self.readline()
            if not line:
                break
            yield line

    def seek(self, offset):
        return self.bytesIO.bytesIO.seek(offset)

    def tell(self):
        return self.bytesIO.bytesIO.tell()
    

    def close(self):
        self.fp.close()
