#ifndef NVIDIA_INTERFACE_H
#define NVIDIA_INTERFACE_H

int main_dxtc (int argc, char** argv, int uid, cudaStream_t & stream);
int main_fdtd3d (int argc, char** argv, int uid, cudaStream_t & stream);
int main_blackscholes(int argc, char** argv, int uid, cudaStream_t & stream);
int main_binomial(int argc, char** argv, int uid, cudaStream_t & stream);
int main_sobol(int argc, char** argv, int uid, cudaStream_t & stream);
int main_stereo(int argc, char** argv, int uid, cudaStream_t & stream);
int main_interval(int argc, char** argv, int uid, cudaStream_t & stream);
int main_conv(int argc, char** argv, int uid, cudaStream_t & stream);

#endif
