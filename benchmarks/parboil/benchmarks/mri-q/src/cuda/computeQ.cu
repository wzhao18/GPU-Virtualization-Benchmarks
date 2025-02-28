/***************************************************************************
 *cr
 *cr            (C) Copyright 2007 The Board of Trustees of the
 *cr                        University of Illinois
 *cr                         All Rights Reserved
 *cr
 ***************************************************************************/

#include <unistd.h>
#include <fcntl.h>

#include "cuda_profiler_api.h"


#define PI   3.1415926535897932384626433832795029f
#define PIx2 6.2831853071795864769252867665590058f

#define MIN(X,Y) ((X) < (Y) ? (X) : (Y))
#define K_ELEMS_PER_GRID 2048

#define KERNEL_PHI_MAG_THREADS_PER_BLOCK 512
#define KERNEL_Q_THREADS_PER_BLOCK 256
#define KERNEL_Q_K_ELEMS_PER_GRID 1024

#define CUDA_ERRCK							\
  {cudaError_t err;							\
    if ((err = cudaGetLastError()) != cudaSuccess) {			\
      fprintf(stderr, "CUDA error on line %d: %s\n", __LINE__, cudaGetErrorString(err)); \
      exit(-1);								\
    }									\
  }

struct kValues {
  float Kx;
  float Ky;
  float Kz;
  float PhiMag;
};

/* Values in the k-space coordinate system are stored in constant memory
 * on the GPU */
__constant__ __device__ kValues ck[KERNEL_Q_K_ELEMS_PER_GRID];

__global__ void
ComputePhiMag_GPU(float* phiR, float* phiI, float* phiMag, int numK) {
  int indexK = blockIdx.x*KERNEL_PHI_MAG_THREADS_PER_BLOCK + threadIdx.x;
  if (indexK < numK) {
    float real = phiR[indexK];
    float imag = phiI[indexK];
    phiMag[indexK] = real*real + imag*imag;
  }
}


extern volatile bool ready;
extern volatile bool should_stop;
const char * ready_fifo = "/tmp/ready"; 


__global__ void
ComputeQ_GPU(int numK, int kGlobalIndex,
	     float* x, float* y, float* z, float* Qr , float* Qi)
{
  float sX;
  float sY;
  float sZ;
  float sQr;
  float sQi;

  // Determine the element of the X arrays computed by this thread
  int xIndex = blockIdx.x*KERNEL_Q_THREADS_PER_BLOCK + threadIdx.x;

  // Read block's X values from global mem to shared mem
  sX = x[xIndex];
  sY = y[xIndex];
  sZ = z[xIndex];
  sQr = Qr[xIndex];
  sQi = Qi[xIndex];

  // Loop over all elements of K in constant mem to compute a partial value
  // for X.
  int kIndex = 0;
  if (numK % 2) {
    float expArg = PIx2 * (ck[0].Kx * sX + ck[0].Ky * sY + ck[0].Kz * sZ);
    sQr += ck[0].PhiMag * cos(expArg);
    sQi += ck[0].PhiMag * sin(expArg);
    kIndex++;
    kGlobalIndex++;
  }

  for (; (kIndex < KERNEL_Q_K_ELEMS_PER_GRID) && (kGlobalIndex < numK);
       kIndex += 2, kGlobalIndex += 2) {
    float expArg = PIx2 * (ck[kIndex].Kx * sX +
			   ck[kIndex].Ky * sY +
			   ck[kIndex].Kz * sZ);
    sQr += ck[kIndex].PhiMag * cos(expArg);
    sQi += ck[kIndex].PhiMag * sin(expArg);

    int kIndex1 = kIndex + 1;
    float expArg1 = PIx2 * (ck[kIndex1].Kx * sX +
			    ck[kIndex1].Ky * sY +
			    ck[kIndex1].Kz * sZ);
    sQr += ck[kIndex1].PhiMag * cos(expArg1);
    sQi += ck[kIndex1].PhiMag * sin(expArg1);
  }

  Qr[xIndex] = sQr;
  Qi[xIndex] = sQi;
}

void computePhiMag_GPU(int numK, float* phiR_d, float* phiI_d, float* phiMag_d)
{
  int phiMagBlocks = numK / KERNEL_PHI_MAG_THREADS_PER_BLOCK;
  if (numK % KERNEL_PHI_MAG_THREADS_PER_BLOCK)
    phiMagBlocks++;
  dim3 DimPhiMagBlock(KERNEL_PHI_MAG_THREADS_PER_BLOCK, 1);
  dim3 DimPhiMagGrid(phiMagBlocks, 1);

  ComputePhiMag_GPU <<< DimPhiMagGrid, DimPhiMagBlock >>> 
    (phiR_d, phiI_d, phiMag_d, numK);
}

void computeQ_GPU(int numK, int numX,
                  float* x_d, float* y_d, float* z_d,
                  kValues* kVals,
                  float* Qr_d, float* Qi_d)
{
  int QGrids = numK / KERNEL_Q_K_ELEMS_PER_GRID;
  if (numK % KERNEL_Q_K_ELEMS_PER_GRID)
    QGrids++;
  int QBlocks = numX / KERNEL_Q_THREADS_PER_BLOCK;
  if (numX % KERNEL_Q_THREADS_PER_BLOCK)
    QBlocks++;
  dim3 DimQBlock(KERNEL_Q_THREADS_PER_BLOCK, 1);
  dim3 DimQGrid(QBlocks, 1);

  /* Create CUDA start & stop events to record total elapsed time of kernel execution */
  cudaEvent_t start;
  cudaError_t error = cudaEventCreate(&start);

  if (error != cudaSuccess)
  {   
      fprintf(stderr, "Failed to create start event (error code %s)!\n", 
                                              cudaGetErrorString(error));   
      exit(EXIT_FAILURE);
  }

  cudaEvent_t stop;
  error = cudaEventCreate(&stop);

  if (error != cudaSuccess)
  {   
      fprintf(stderr, "Failed to create stop event (error code %s)!\n", 
                                              cudaGetErrorString(error));
      exit(EXIT_FAILURE);
  }

  /* End event creation */ 
  
  
  /* Write to pipe to signal the wrapper script that we are done with data setup */
  char pid[10];
  sprintf(pid, "%d", getpid());

  int fd = open(ready_fifo, O_WRONLY);
  int res = write(fd, pid, strlen(pid));
  close(fd);

  if (res > 0) printf("Parboil spmv write success to the pipe!\n");
  /* End pipe writing */
  
  
  /* Spin until master tells me to start kernels */
  while (!ready);
  /* End spinning */
  
  
  /* Record the start event and start nvprof profiling */
  cudaProfilerStart();
  
  error = cudaEventRecord(start, NULL);

  if (error != cudaSuccess)
  {
      fprintf(stderr, "Failed to record start event (error code %s)!\n", 
                                              cudaGetErrorString(error));
      exit(EXIT_FAILURE);
  }
  
  /* End CUDA start records */

  /* Main loop to do real work */
  while (!should_stop){ 
    for (int QGrid = 0; QGrid < QGrids; QGrid++) {
      // Put the tile of K values into constant mem
      int QGridBase = QGrid * KERNEL_Q_K_ELEMS_PER_GRID;
      kValues* kValsTile = kVals + QGridBase;
      int numElems = MIN(KERNEL_Q_K_ELEMS_PER_GRID, numK - QGridBase);

      cudaMemcpyToSymbol(ck, kValsTile, numElems * sizeof(kValues), 0);

      ComputeQ_GPU <<< DimQGrid, DimQBlock >>>
        (numK, QGridBase, x_d, y_d, z_d, Qr_d, Qi_d);
    }
  }

  /* Record and wait for the stop event */
  error = cudaEventRecord(stop, NULL);

  if (error != cudaSuccess)
  {
      fprintf(stderr, "Failed to record stop event (error code %s)!\n", 
                                              cudaGetErrorString(error));
      exit(EXIT_FAILURE);
  }
  
  cudaThreadSynchronize();

  error = cudaEventSynchronize(stop);

  if (error != cudaSuccess)
  {
      fprintf(stderr, "Failed to synchronize on the stop event (error code %s)!\n", 
                                                          cudaGetErrorString(error));
      exit(EXIT_FAILURE);
  }
  
  cudaProfilerStop();
  
  /* End stop CUDA event handling */
  
  
  /* Output total elapsed time */
  float msecTotal = 0.0f;
  // !!! Important: must use this print format, the data processing 
  // script requires this information 
  error = cudaEventElapsedTime(&msecTotal, start, stop);
  printf("Total elapsed time: %f ms\n", msecTotal);
  /* End elpased time recording */




}

void createDataStructsCPU(int numK, int numX, float** phiMag,
	 float** Qr, float** Qi)
{
  *phiMag = (float* ) memalign(16, numK * sizeof(float));
  *Qr = (float*) memalign(16, numX * sizeof (float));
  *Qi = (float*) memalign(16, numX * sizeof (float));
}

