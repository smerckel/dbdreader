#include "Python.h"
#include <stdlib.h>
#include "dbdreader.h"

static char py_get_doc[]="to do";

static PyObject *
py_get(PyObject *self, PyObject *args)
{
  file_info_t FileInfo; /*FileInfo, see python code */
  double ***data;       /*three d data array        */
  int *ndata;           /* array of length of data each param*/
  int ti, *vi;          /*index for time and parmeters */ 
  int nv;               /*number of parameters to look up*/
  PyObject *viTuple;    /*tuple passed on from python with vi*/
  long bin_offset;      /*start of binary data */
  int n_state_bytes;    /*number of state bytes */
  int n_sensors;        /*number of sensors we have */
  PyObject *byteSizes;  /*byte sizes as passed on from python */
  int bs;               /*byte syze (counter) */
  char *filename;         
  PyObject *containerList;  /* list with [ti,vi] for each parameter */
  PyObject *tiList, *viList;
  PyObject *tmp;
  int i,j,k;
  int return_nans;       /* int flagging to return nans in the array or not.*/

  if (!PyArg_ParseTuple(args,"iilOsiOi:get",
			&n_state_bytes,
			&n_sensors,
			&bin_offset,
			&byteSizes,
			&filename,
			&ti,
			&viTuple,
			&return_nans))
    {
      return NULL;
    }

  FileInfo.byteSizes=(int*)malloc(n_sensors*sizeof(int));

  for(i=0;i<n_sensors;i++){
    bs=(int)PyLong_AsLong(PyTuple_GetItem(byteSizes,i));
    FileInfo.byteSizes[i]=bs;
  }
  nv=PyTuple_Size(viTuple);/* number of parameters passed (not including time)*/
  vi=(int*)malloc((nv)*sizeof(int)); 
  for(i=0;i<nv;i++){
    vi[i]=(int)PyLong_AsLong(PyTuple_GetItem(viTuple,i));
  }
  ndata=(int*)malloc(nv*sizeof(int));
  FileInfo.bin_offset=bin_offset;
  FileInfo.n_state_bytes=n_state_bytes;
  FileInfo.n_sensors=n_sensors;
  FileInfo.fd=open_dbd_file(filename);

  data=get_variable(ti,vi,nv,FileInfo,return_nans,ndata);
  close_dbd_file(FileInfo.fd);
  /* good, got the data, now populate the lists */
  containerList=PyList_New(2*nv);/* exclude time */
  for(i=0;i<nv;i++){
    tiList=PyList_New(ndata[i]);
    viList=PyList_New(ndata[i]);
    for(k=0;k<ndata[i];k++){
      tmp=PyFloat_FromDouble(data[i][0][k]);
      PyList_SetItem(tiList,k,tmp);
      tmp=PyFloat_FromDouble(data[i][1][k]);
      PyList_SetItem(viList,k,tmp);
    }
    PyList_SetItem(containerList,i,tiList);
    PyList_SetItem(containerList,nv+i,viList);
  }
  /* clean up dynamically allocated memory blocks */
  free(FileInfo.byteSizes);
  free(ndata);
  free(vi);

  for(i=0;i<nv;++i){
    for(j=0;j<2;++j){
      free(data[i][j]);
    }
    free(data[i]);
  }
  free(data);
  return Py_BuildValue("N",containerList);
}


static PyMethodDef _dbdreadermethods[]={
  {"get", py_get, METH_VARARGS,py_get_doc},
  {NULL    , NULL      ,0           ,NULL}
};

#if PY_MAJOR_VERSION <3
void init_dbdreader(void){
  PyObject *mod;
  mod = Py_InitModule("_dbdreader",_dbdreadermethods);
  /* if you want to add the value of a macro, defined in a header file
     to be known to the module, then use the following. Assumed is that
     a header file defines MAGIC (#define MAGIC 1)
  PyModule_AddIntMacro(mod,MAGIC)
  */
}
#else
/*python3 module initialisation */
static struct PyModuleDef _dbdreader_module = {
  PyModuleDef_HEAD_INIT,
  "_dbdreader", /*name of module */
  "DOCO (Todo)",
  -1,
  _dbdreadermethods
};

PyMODINIT_FUNC
PyInit__dbdreader(void){
  PyObject *mod;
  mod = PyModule_Create(&_dbdreader_module);
  /* not sure what this does:*/
  //PyModule_AddIntMacro(mod,MAGIC);
  return mod;
};
#endif
