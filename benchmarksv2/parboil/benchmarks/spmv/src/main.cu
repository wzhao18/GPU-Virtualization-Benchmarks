
#include <parboil.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/time.h>

#include "file.h"
#include "gpu_info.h"
#include "spmv_jds.h"
#include "jds_kernels.cu"
#include "convert_dataset.h"
#include "interface.h"


/*
static int generate_vector(float *x_vector, int dim) 
{	
	srand(54321);	
	for(int i=0;i<dim;i++)
	{
		x_vector[i] = (rand() / (float) RAND_MAX);
	}
	return 0;
}
*/

extern bool set_and_check(int uid, bool start);


int main_spmv(int argc, char** argv, int uid, cudaStream_t & stream) {
	struct pb_TimerSet timers;
	struct pb_Parameters *parameters;
	
	
	printf("CUDA accelerated sparse matrix vector multiplication****\n");
	printf("Original version by Li-Wen Chang <lchang20@illinois.edu> and Shengzhao Wu<wu14@illinois.edu>\n");
	printf("This version maintained by Chris Rodrigues  ***********\n");
	parameters = pb_ReadParameters(&argc, argv);
	if ((parameters->inpFiles[0] == NULL) || (parameters->inpFiles[1] == NULL))
    {
      fprintf(stderr, "Expecting two input filenames\n");
      exit(-1);
    }

	
	pb_InitializeTimerSet(&timers);
	pb_SwitchToTimer(&timers, pb_TimerID_COMPUTE); //parameters declaration
	int len;
	int depth;
	int dim;
	int pad=32;
	int nzcnt_len;
	
	//host memory allocation
	//matrix
	float *h_data;
	int *h_indices;
	int *h_ptr;
	int *h_perm;
	int *h_nzcnt;
	//vector
	float *h_Ax_vector;
    float *h_x_vector;
	
	//device memory allocation
	//matrix
	float *d_data;
	int *d_indices;
	int *d_ptr;
	int *d_perm;
	int *d_nzcnt;
	//vector
	float *d_Ax_vector;
    float *d_x_vector;
	
    //load matrix from files
	pb_SwitchToTimer(&timers, pb_TimerID_IO);
	//inputData(parameters->inpFiles[0], &len, &depth, &dim,&nzcnt_len,&pad,
	//    &h_data, &h_indices, &h_ptr,
	//    &h_perm, &h_nzcnt);
	int col_count;
	coo_to_jds(
		parameters->inpFiles[0], // bcsstk32.mtx, fidapm05.mtx, jgl009.mtx
		1, // row padding
		pad, // warp size, IMPORTANT: change in kernel as well
		1, // pack size
		1, // is mirrored?
		0, // binary matrix
		1, // debug level [0:2]
		&h_data, &h_ptr, &h_nzcnt, &h_indices, &h_perm,
		&col_count, &dim, &len, &nzcnt_len, &depth
	);
	

  h_Ax_vector=(float*)malloc(sizeof(float)*dim); 
  h_x_vector=(float*)malloc(sizeof(float)*dim);
  input_vec( parameters->inpFiles[1],h_x_vector,dim);

	pb_SwitchToTimer(&timers, pb_TimerID_COMPUTE);
	
	cudaDeviceProp deviceProp;
    cudaGetDeviceProperties(&deviceProp, 0);
	
	
	pb_SwitchToTimer(&timers, pb_TimerID_COPY);
	//memory allocation
	cudaMalloc((void **)&d_data, len*sizeof(float));
	cudaMalloc((void **)&d_indices, len*sizeof(int));
	cudaMalloc((void **)&d_ptr, depth*sizeof(int));
	cudaMalloc((void **)&d_perm, dim*sizeof(int));
	cudaMalloc((void **)&d_nzcnt, nzcnt_len*sizeof(int));
	cudaMalloc((void **)&d_x_vector, dim*sizeof(float));
	cudaMalloc((void **)&d_Ax_vector,dim*sizeof(float));
	cudaMemset( (void *) d_Ax_vector, 0, dim*sizeof(float));
	
	//memory copy
	cudaMemcpyAsync(d_data, h_data, len*sizeof(float), 
      cudaMemcpyHostToDevice, stream);
	cudaMemcpyAsync(d_indices, h_indices, len*sizeof(int), 
      cudaMemcpyHostToDevice, stream);
	cudaMemcpyAsync(d_perm, h_perm, dim*sizeof(int), 
      cudaMemcpyHostToDevice, stream);
	cudaMemcpyAsync(d_x_vector, h_x_vector, dim*sizeof(int), 
      cudaMemcpyHostToDevice, stream);
	cudaMemcpyToSymbolAsync(jds_ptr_int, h_ptr, depth*sizeof(int), 0, 
      cudaMemcpyHostToDevice, stream);
	cudaMemcpyToSymbolAsync(sh_zcnt_int, h_nzcnt, nzcnt_len*sizeof(int), 0, 
      cudaMemcpyHostToDevice, stream);
	
  cudaStreamSynchronize(stream);

  pb_SwitchToTimer(&timers, pb_TimerID_COMPUTE);
  unsigned int grid;
  unsigned int block;
  compute_active_thread(&block, &grid, nzcnt_len,pad,
                        deviceProp.major,deviceProp.minor,
                        deviceProp.warpSize,deviceProp.multiProcessorCount);

	
  cudaFuncSetCacheConfig(spmv_jds, cudaFuncCachePreferL1);

  set_and_check(uid, true);
  while (!set_and_check(uid, true)) {
    usleep(100);
  }

  bool can_exit = false;

	//main execution
	pb_SwitchToTimer(&timers, pb_TimerID_KERNEL);
  while (!can_exit) {
    spmv_jds<<<grid, block, 0, stream>>>(d_Ax_vector,
        d_data,d_indices,d_perm,
        d_x_vector,d_nzcnt,dim);

    cudaStreamSynchronize(stream);

    can_exit = set_and_check(uid, false);
  }
						
  CUERR // check and clear any existing errors

  pb_SwitchToTimer(&timers, pb_TimerID_COPY);
  //HtoD memory copy
  cudaMemcpyAsync(h_Ax_vector, d_Ax_vector,dim*sizeof(float),
                  cudaMemcpyDeviceToHost, stream);

  cudaStreamSynchronize(stream);

  cudaFree(d_data);
  cudaFree(d_indices);
  cudaFree(d_ptr);
  cudaFree(d_perm);
  cudaFree(d_nzcnt);
  cudaFree(d_x_vector);
  cudaFree(d_Ax_vector);

  if (parameters->outFile) {
    pb_SwitchToTimer(&timers, pb_TimerID_IO);
    outputData(parameters->outFile,h_Ax_vector,dim);

  }
  pb_SwitchToTimer(&timers, pb_TimerID_COMPUTE);

  free (h_data);
  free (h_indices);
  free (h_ptr);
  free (h_perm);
  free (h_nzcnt);
  free (h_Ax_vector);
  free (h_x_vector);
  pb_SwitchToTimer(&timers, pb_TimerID_NONE);

  pb_PrintTimerSet(&timers);
  pb_FreeParameters(parameters);

  return 0;

}
