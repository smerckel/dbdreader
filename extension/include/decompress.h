#ifndef DECOMPRESS_H
#define DECOMPRESS_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <lz4.h>

#define CHUNKSIZE 1024*32
#define MAX_IN_MEMORY_FILE_SIZE 1024*1024*1024


/* Returns 0/1 if filename is compressed.
 * Essentially the extension is tested for the second character
 * to be a 'c'
 */
const int is_file_compressed(const char *filename);


FILE* fopen_compressed_file(const char* filename);


#endif
