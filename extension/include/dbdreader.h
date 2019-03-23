#ifndef DBDREADER_H
#define DBDREADER_H

#include <stdio.h>

#define bits_per_byte   8
#define bits_per_field  2
#define mask            3

#define UPDATED         2
#define SAME            1
#define NOTSET          0

#define FILLVALUE       1e9
#define BLOCKSIZE 1000

typedef char byte;

typedef union {
  long long n;
  double x;
} to_double_t;

typedef union {
  long n;
  float x;
} to_float_t;


typedef struct {
  FILE *fd;
  long bin_offset;
  int n_state_bytes;
  int n_sensors;
  int *byteSizes;
} file_info_t;


FILE *open_dbd_file(char *filename);
void close_dbd_file(FILE *fd);
double ***get_variable(int ti,
		       int *vi,
		       int nv,
		       file_info_t FileInfo,
		       int return_nans,
		       int *n_data);


#endif
