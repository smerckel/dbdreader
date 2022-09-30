#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#include "dbdreader.h"

/*
  bswap_ = functions for swapping the byte-order of shorts, floats and doubles
*/

static short bswap_s(short val);

static float bswap_f(float val);

static double bswap_d(double val);

static unsigned char read_known_cycle(FILE *fd);

static int read_state_bytes(int *vi,
			    int nvt,
			    file_info_t FileInfo,
			    signed *offsets, 
			    unsigned *chunksize);

static void get_by_read_per_byte(int ti,
				 int *vi,
				 int nv,
				 file_info_t FileInfo,
				 int return_nans,
				 double ***data,
				 int *ndata);

static double read_sensor_value(FILE *fd,
				int bs, unsigned char flip);

static void add_to_array(double t,
			 double x,
			 double **r,
			 int size);

static int contains(int q,
		    int list[],
		    int n);


/* Public functions */

FILE *open_dbd_file(char *filename)
{
  FILE *fd;

  fd=fopen(filename,"rb");

  return(fd);
}

void close_dbd_file(FILE *fd)
{
  fclose(fd);
}

double ***get_variable(int ti,
		       int *vi,
		       int nv,
		       file_info_t FileInfo,
		       int return_nans,
		       int *ndata)
{
  int i,j;
  double ***data;
  int *vit;
  int nvt;
  int nti;

  nvt=nv+1;
  vit=(int *)malloc(nvt*sizeof(int));

  /*create an array of pointers of nv layers, 2 rows, BLOCKSIZE columns*/
  data=(double ***)malloc(nv*sizeof(double **));
  for (i=0;i<nv;i++){
    data[i]=(double **)malloc(2*sizeof(double *));
    for (j=0;j<2;j++){
      data[i][j]=(double *)malloc(BLOCKSIZE*sizeof(double));
    }
  }
  /* Check whether the operation has succeeded:*/
  if (data==NULL){
    printf("Memory fault!\n");
    exit(1);
  }

  /* insert ti in vi such that vi remains sorted. */
  for(i=0;i<nv;i++){
    if(vi[i]>ti){
      break;
    }
    vit[i]=vi[i];
  }
  vit[i]=ti; /*inserts ti*/
  nti=i; /* ti is the nti'th variable */
  i++;
  for(i=i;i<nv+1;i++){
    vit[i]=vi[i-1];
  }
  get_by_read_per_byte(nti,vit,nvt,FileInfo,return_nans,data,ndata);
  free(vit);
  return(data);
}


/*   PRIVATE FUNCTIONS  */

static short bswap_s(short val) {
    int size = sizeof(short);
    short retVal;
    char *pVal = (char*) &val;
    char *pRetVal = (char*)&retVal;
    for(int i=0; i<size; i++) {
        pRetVal[size-1-i] = pVal[i];
    }
    return retVal;
}

static float bswap_f(float val) {
    int size = sizeof(float);
    float retVal;
    char *pVal = (char*) &val;
    char *pRetVal = (char*)&retVal;
    for(int i=0; i<size; i++) {
        pRetVal[size-1-i] = pVal[i];
    }
    return retVal;
}

static double bswap_d(double val) {
    int size = sizeof(double);
    double retVal;
    char *pVal = (char*) &val;
    char *pRetVal = (char*)&retVal;
    for(int i=0; i<size; i++) {
        pRetVal[size-1-i] = pVal[i];
    }
    return retVal;
}

static unsigned char read_known_cycle(FILE *fd)
{
  // the first 2 bytes are:
  // s                  Cycle Tag (this is an ASCII s char).
  // a                  One byte integer.
  // but just skip over them
  int pos = ftell(fd);
  fseek(fd, pos + 2, 0);

  // followed by, the value we want to check for:
  // 0x1234             Two byte integer.
  // which is 4660
  unsigned short two_byte_int;
  fread((void*)(&two_byte_int), sizeof(two_byte_int), 1, fd);
  //printf("two_byte_int : %d\n", two_byte_int);

  // the next 12 bytes are:
  //     123.456            Four byte float.
  //     123456789.12345    Eight byte double.
  // but by this point we already know the byte order, so just skip the bytes
  pos = ftell(fd);
  fseek(fd, pos + 13, 0);

  // if we can successfully read the value, the glider byte order == host order
  if (two_byte_int == 4660) {
    return 0;
  }
  // otherwise, we need to flip shorts, floats and doubles when reading
  return 1;
}

static void get_by_read_per_byte(int nti,
				 int *vi,
				 int nv,
				 file_info_t FileInfo,
				 int return_nans,
				 double ***result,
				 int *ndata)
{

  unsigned chunksize;
  signed *offsets;
  unsigned *byteSizes;
  
  int r;
  int fp_end, fp_current;
  int i,j;

  double *read_result;
  double *memory_result;
  int *read_vi;

  int min_offset_value;
  byte writing_first_line = 1;

  if (return_nans==1)
    min_offset_value=-2; // include the notfound/samevalue/update
  else
    min_offset_value=-1; // include samevalue/update
  
  byteSizes=(unsigned *)malloc(nv*sizeof(unsigned));
  offsets=(signed *)malloc(nv*sizeof(signed));
  read_result=(double *)malloc(nv*sizeof(double));
  memory_result=(double *)malloc(nv*sizeof(double));
  read_vi=(int *)malloc(nv*sizeof(int));

  /* setting for variables AND time:*/
  for(i=0;i<nv-1;++i){ /* no time */
    ndata[i]=0;
  }
  for(i=0;i<nv;++i){
    j=vi[i];
    byteSizes[i]=FileInfo.byteSizes[j];
    offsets[i]=0;
  }

  /* look up the end of the file: */
  fseek(FileInfo.fd,0,2);
  fp_end=ftell(FileInfo.fd);
  
  /* start where binary data begin: */
  fseek(FileInfo.fd,
  	FileInfo.bin_offset,0);

  /* extract byte order from known cycle */
  unsigned char flip = read_known_cycle(FileInfo.fd);

  while (1){
    r=read_state_bytes(vi,nv,FileInfo,offsets,&chunksize);
    fp_current=ftell(FileInfo.fd);
    if (r>=1) {
      /* we found (some of) the values we want to read (at least 1) */
      for(i=0; i<nv; i++){
	if (offsets[i]>=0){
	  /* found an updated value */
	  fseek(FileInfo.fd,
		fp_current+offsets[i],0);
	  read_result[i]=read_sensor_value(FileInfo.fd,
					   byteSizes[i], flip);
	  memory_result[i]=read_result[i];
	}
	else if (offsets[i]==-1){
	  /*update value with previous value*/
	  read_result[i]=memory_result[i];
	}
	else if (offsets[i]==-2){
	  /* parameter is not found
	     This will happen only when read_state_bytes is set to return nans
	  */
	  read_result[i]=FILLVALUE;
	}
      }
      
      if (!writing_first_line){
	for(i=0; i<nv; i++){
	  if ((offsets[i]>=min_offset_value) && (i!=nti)){// && isfinite(read_result[i])){
	    j=i-(int)(i>nti);
	    /* add read_result to result */
	    add_to_array(read_result[nti],
			 read_result[i],
			 result[j],ndata[j]);
	    ndata[j]+=1;
	  }
	}
      }
      else {
	writing_first_line=0;
      }
    }
    /* jump to the next state block */
    fp_current+=chunksize+1;
    if (fp_current >= fp_end){
      break; /* reached end of the file */
    }
    fseek(FileInfo.fd,fp_current,0);
  }
  free(byteSizes);
  free(offsets);
  free(read_result);
  free(memory_result);
  free(read_vi);
}

static int read_state_bytes(int *vi,
			    int nvt,
			    file_info_t FileInfo,
			    signed *offsets, 
			    unsigned *chunksize)
{

  static int bitshift;
  static int fields_per_byte;
  int sb,fld,field;
  int nsb=FileInfo.n_state_bytes;
  int c;
  int variable_index;
  int variable_counter;
  int idx;
  bitshift=bits_per_byte - bits_per_field;
  fields_per_byte=bits_per_byte/bits_per_field;

  *chunksize=0;

  variable_index=0;
  variable_counter=0;
  for(sb=0;sb<nvt;sb++){
      offsets[sb]=-2; /* defaults to not found*/
  }
  for (sb=0;sb<nsb; sb++){
    c=getc(FileInfo.fd);
    for (fld=0;fld<fields_per_byte;fld++){
      field=(c>>bitshift) & mask;
      c<<=bits_per_field;
      if (field == UPDATED) {
	idx=contains(variable_index,vi,nvt);
	if (idx!=-1){
	  /* the update value is one of the wanted variables 
	     so record its position */
	  offsets[idx]=*chunksize;
	  variable_counter+=1;
	}
	*chunksize+=FileInfo.byteSizes[variable_index];
      }
      else if (field==SAME) {
	idx=contains(variable_index,vi,nvt);
	if (idx!=-1){
	  /* this variable is asked for but has an old value.
	     Therefore it is not being read. Offset marked -1*/
	  offsets[idx]=-1;
	  variable_counter+=1;
	}
      }
      else if (field==NOTSET) {
	idx=contains(variable_index,vi,nvt);
	if (idx!=-1){
	  /* this variable is asked for but has no value set.
	     Therefore it is not being read. Offset marked -2*/
	  offsets[idx]=-2;
	  variable_counter+=1;
	}
      }
      variable_index+=1;
    }
  }
  /* If a variable index appears twice in vi, as can happen when
     m_present_time is asked for explicitly, then only the first gets
     an offset assigned. This results in the other entry not to be
     set. So, if time is asked, the time vector itself gets bogus
     values. We can correct that by ensuring that the offset is copied
     over. vi is in ascending order, so two identical entries should be neighbours.*/
  if (nvt>1){
    for(int i=1; i<nvt; ++i){
      if (vi[i]==vi[i-1])
	offsets[i]=offsets[i-1];
    }
  }

  /*return the number of variables found. */
  return (variable_counter);
}

static int contains(int q,
		    int list[],
		    int n)
{
  int i;
  int r=-1;
  for (i=0;i<n;i++){
    if(q==list[i]){
      r=i;
      break;
    }
  }
  return r;
}

static double read_sensor_value(FILE *fd,
				int bs, unsigned char flip)
{
  signed char   sc;
  signed short  ss;
  float  sf;
  double sd;
  double value;
  switch (bs){
  case sizeof(char):
    fread((void*)(&sc), sizeof(sc), 1, fd);
    value = (double) sc;
    break;
  case sizeof(short):
    fread((void*)(&ss), sizeof(ss), 1, fd);
    if (flip == 1) {
      ss = bswap_s(ss);
    }
    value = (double) ss;
    break;
  case sizeof(float):
    fread((void*)(&sf), sizeof(sf), 1, fd);
    if (flip == 1) {
       sf = bswap_f(sf);
    }
    value = (double) sf;
    break;
  case sizeof(double):
    fread((void*)(&sd), sizeof(sd), 1, fd);
    if (flip == 1) {
      sd = bswap_d(sd);
    }
    value = sd;
    break;
  default:
    printf("Should not be here!!!!\n");
    printf("byte size : %d\n",bs);
    exit(1);
  }
  return value;
}
		    

static void add_to_array(double t,
			 double x,
			 double **r,
			 int size)
{

  int nblocks;
  int i;
  
  nblocks=(int) size/BLOCKSIZE;

  if(size%BLOCKSIZE==0){
    /* we consumed up our last data element, add some more.*/
    for (i=0;i<2;i++){
      r[i]=(double *)realloc(r[i],(nblocks+1)*BLOCKSIZE*sizeof(double));
      if (r[i]==NULL){
	printf("Memory fault!\n");
	exit(1);
      }
    }
  }
  r[0][size]=t;
  r[1][size]=x;
}
