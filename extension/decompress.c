#include <assert.h>
#include <stdint.h>
#include "decompress.h"

// private function declarations
static int write_compressed_file_to_memory(const char *filename, FILE* fpmem);

static size_t get_block_size(FILE* fp);

static size_t get_file_size(FILE* fp);

static int decompress_block(size_t* decompressed_size, char* data, FILE* fp);

static FILE* fopen_compressed_file_fmemopen(const char* filename, int* errorno);

static FILE* fopen_compressed_file_fopen(const char* filename, int* errorno);

static void get_filename_base(const char* filename, char*filename_base);

static void get_filename_ext(const char *filename, char* extension);


// public functions


const int is_file_compressed(const char *filename)
{
  int return_value;
  char* ext = (char*) malloc(4);
  get_filename_ext(filename, ext);
  return_value = (int) (ext[1]=='c');
  free(ext);
  return return_value;
}


FILE* fopen_compressed_file(const char* filename, int* errorno){

  FILE* fpmem;
#ifdef __linux__
  fpmem = fopen_compressed_file_fmemopen(filename, errorno);
#elif _WIN32
  fpmem = fopen_compressed_file_fopen(filename, errorno);
#else
  fpmem = fopen_compressed_file_fopen(filename, errorno);
#endif
  return fpmem;
  
}


/* private functions */

static FILE* fopen_compressed_file_fopen(const char* filename, int* errorno){

  char* base;
  char* extension_decompressed;
  char* extension;

  *errorno = NO_ERROR;
  
  base = (char*) malloc(strlen(filename));
  get_filename_base(filename, base);

  extension = (char*) malloc(4);
  get_filename_ext(filename, extension);

  extension_decompressed = (char*) malloc(strlen(extension));

  extension_decompressed = strcpy(extension_decompressed, extension);
  extension_decompressed[1] = 'b';
  // We know for sure that base is long enought to be added by 4
  // characters, as we stripped them before.
  base = strcat(base, ".");
  base = strcat(base, extension_decompressed);

  // Try to open the file, in case it has been written already:
  FILE* fpmem;
  fpmem = fopen(base, "rb");
  if (fpmem==NULL) {
    /* opening of decompressed file failed, assume it is not there,
       and so we write it now. */
    fpmem = fopen(base, "wb");
    if (fpmem!=NULL){
      size_t uncompressed_file_size;
      *errorno = write_compressed_file_to_memory(filename, fpmem);
      fclose(fpmem);
      if (*errorno == NO_ERROR){
	/* Writing was successfull, now reopen the file for reading.*/
	fpmem = fopen(base, "rb");
      }
      else{
	fpmem=NULL;
      }
    }
  }
  else {
    /* Writing operation failed. This is fatal. */
    *errorno = ERROR_FAILED_TO_WRITE_BASE_FILE;
    fpmem=NULL;
  }
  /* Here fpmem is either NULL (and all failed, or it points to the
     decompressed file.*/
  free(extension_decompressed);
  free(extension);
  free(base);
  return fpmem;
}


static void get_filename_ext(const char *filename, char* extension)
{
  const char *dot = strrchr(filename, '.');
  if(!dot || dot == filename){
    extension[0]='\0';
  }
  else{
    dot+=1;
    extension = strcpy(extension, dot);
  }
}


static void get_filename_base(const char *filename, char* filename_base)
{
  filename_base = strcpy(filename_base, filename);
  const char *dot = strrchr(filename_base, '.');
  if(dot && dot != filename_base){
    int offset =  dot - filename_base;
    filename_base[offset]='\0';
  }
}

static FILE* fopen_compressed_file_fmemopen(const char* filename, int* errorno){

  size_t uncompressed_file_size;

  FILE* fpmem;
  
  // We provide a large enough space, but using append mode, gives
  // control to fmemopen to update the size of its internal buffer as
  // it needs.
  fpmem = fmemopen(NULL, MAX_IN_MEMORY_FILE_SIZE, "a+");
  *errorno = write_compressed_file_to_memory(filename, fpmem);
  return fpmem;
  
}

static int write_compressed_file_to_memory(const char *filename, FILE* fpmem)
{
    FILE* fp;
    size_t decompressed_block_size;
    size_t compressed_file_size;
    size_t file_size = 0;
    size_t current_position;
    int errorno = 0;
    
    fp = fopen(filename, "rb");
    if (fp==NULL){
    }
    else{
        compressed_file_size = get_file_size(fp);
        char data[CHUNKSIZE];
        while((current_position=ftell(fp))<compressed_file_size){
	  errorno = decompress_block(&decompressed_block_size, data, fp);
	  if (errorno != NO_ERROR){
	    break;
	  }
	  file_size+= decompressed_block_size;
	  for(size_t i=0; i< decompressed_block_size; ++i){
	    fwrite(&(data[i]), 1, 1, fpmem);
	  }
        }
    }
    fclose(fp);
    rewind(fpmem);
    return errorno;
}


static size_t get_block_size(FILE* fp){

    uint16_t size=0;
    uint8_t b[2];
    size_t bytes_read;
    
    bytes_read = fread(&b, sizeof(b), 1, fp);
    if(bytes_read==0)
      size = 0;
    else
      size = (b[0]<<8) + b[1];
    return size;
}

static size_t get_file_size(FILE* fp)
{
    size_t current_position = ftell(fp);
    fseek(fp, 0, 2);
    size_t file_size = ftell(fp);
    fseek(fp, current_position, 0);
    return file_size;
}

static int decompress_block(size_t* decompressed_size, char* data, FILE* fp)
{
  size_t block_size;
  char* buffer;
  int errorno=NO_ERROR;
  
  block_size = get_block_size(fp);
  buffer = (char*) malloc(sizeof(char)*block_size);
  for(size_t i=0; i<block_size; ++i){
    if (fread(&(buffer[i]), sizeof(char), 1, fp)==0){
      /* stream ended unexpectedly */
      errorno=ERROR_UNEXPECTED_END_OF_FILE;
      break;
    }
  }
  if (errorno==NO_ERROR){
    *decompressed_size = LZ4_decompress_safe_partial (buffer, data, block_size, CHUNKSIZE, CHUNKSIZE);
  }
  else {
    *decompressed_size=0;
  }
  free(buffer);
  return errorno;
}



