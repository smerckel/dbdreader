import os
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
            b = lz4.block.decompress(fp.read(size), size * Decompressor.COMPRESSION_FACTOR)
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
               
    def _generate_filename_for_output(self, filename):
        base, ext = os.path.splitext(filename)
        if len(ext)!=4:
            raise ValueError('Unhandled file extension.')
        if ext.endswith('cg'):
            s = 'lg'
        elif ext.endswith('cd'):
            s = 'bd'
        else:
            raise ValueError('Unhandled file extension.')
        return "".join((base, ext[:-2], s))
                         
    def decompress(self, filename):
        output_filename = self._generate_filename_for_output(filename)
        with Decompressor(filename) as d, open(output_filename, 'wb') as fp_out:
            for block in d.decompressed_blocks():
                fp_out.write(block)
        

def decompress_file(filename):
    FileDecompressor().decompress(filename)

