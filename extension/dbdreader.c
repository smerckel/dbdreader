#include <stdio.h>
#include <stdlib.h>

#include "dbdreader.h"


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
				int bs);

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

  fd=fopen(filename,"r");

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
  	FileInfo.bin_offset+17,0);
  
  while (1){
    r=read_state_bytes(vi,nv,FileInfo,offsets,&chunksize);
    fp_current=ftell(FileInfo.fd);
    if (r>=2) {
      /* we found (some of) the values we want to read (at least 2) */
      for(i=0; i<nv; i++){
	if (offsets[i]>=0){
	  /* found an updated value */
	  fseek(FileInfo.fd,
		fp_current+offsets[i],0);
	  read_result[i]=read_sensor_value(FileInfo.fd,
					   byteSizes[i]);
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
      for(i=0; i<nv; i++){
	if ((offsets[i]>=min_offset_value) && (i!=nti)){
	  j=i-(int)(i>nti);
	  /* add read_result to result */
	  add_to_array(read_result[nti],
		       read_result[i],
		       result[j],ndata[j]);
	  ndata[j]+=1;
	}
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
  /*return whether or not we found at least two variables,
   one of them is time, and should be present anyway.*/
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
				int bs)
{
  signed char   sc;
  unsigned char   uc;
  to_float_t F;
  to_double_t D;
  double value;
  int i;
  switch (bs){
  case sizeof(char):
    sc=(signed char) getc(fd);
    value = (double) sc;
    break;
  case sizeof(float):
    F.n=0;
    for (i=0;i<bs;i++){
      F.n<<=8;
      uc=getc(fd);
      F.n |= uc;
    }
    value=F.x;
    break;
  case sizeof(double):
    D.n=0;
    for (i=0;i<bs;i++){
      D.n<<=8;
      uc=getc(fd);
      D.n |= uc; 
    }
    value=D.x;
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
