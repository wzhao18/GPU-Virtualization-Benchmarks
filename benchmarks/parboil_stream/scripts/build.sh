if [ "$1" == "sim" ]; then
  back=$(pwd)
  cd ../build-docker
  make -j8

  # manually link executables with shared runtime
  nvcc  CMakeFiles/PAIR.dir/common/src/parboil.c.o CMakeFiles/PAIR.dir/common/src/parboil_cuda.c.o CMakeFiles/PAIR.dir/common/src/parboil_opencl.c.o CMakeFiles/PAIR.dir/benchmarks/sgemm/src/cuda/io.cc.o CMakeFiles/PAIR.dir/benchmarks/sgemm/src/cuda/main.cu.o CMakeFiles/PAIR.dir/benchmarks/sgemm/src/cuda/sgemm_kernel.cu.o CMakeFiles/PAIR.dir/benchmarks/spmv/src/cuda/file.cc.o CMakeFiles/PAIR.dir/benchmarks/spmv/src/cuda/gpu_info.cc.o CMakeFiles/PAIR.dir/benchmarks/spmv/src/cuda/jds_kernels.cu.o CMakeFiles/PAIR.dir/benchmarks/spmv/src/cuda/main.cu.o CMakeFiles/PAIR.dir/benchmarks/spmv/common_src/convert-dataset/convert_dataset.c.o CMakeFiles/PAIR.dir/benchmarks/spmv/common_src/convert-dataset/mmio.c.o CMakeFiles/PAIR.dir/pairs/main.cu.o CMakeFiles/PAIR.dir/cmake_device_link.o -o PAIR  -L"/usr/local/cuda/targets/x86_64-linux/lib/stubs" -L"/usr/local/cuda/targets/x86_64-linux/lib" -lcudart -cudart=shared -arch=sm_70 -lpthread -ldl

  cd $pwd

else
  (cd ../build && make -j8)
fi

