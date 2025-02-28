/*
  CudaCommon.h

    Copyright (c) 2015-2019 Johns Hopkins University.  All rights reserved.

    This file is part of the Arioc software distribution.  It is subject to the license terms
    in the LICENSE.txt file found in the top-level directory of the Arioc software distribution.
    The contents of this file, in whole or in part, may only be copied, modified, propagated, or
    redistributed in accordance with the license terms contained in LICENSE.txt.
*/
#pragma once
#define __CudaCommon__

#pragma region global defines
#define CUDAMINCC                   "3.5"           // minimum CUDA compute capability
#define CUDASHAREDL1CUTOFF          (16*1024)
#define CUDAMAXSHAREDMEMORY         (48*1024)
#define CUDATHREADSPERWARP          32
#define CUDAMINRESERVEDGLOBALMEMORY (10*1024*1024)  // minimum amount of CUDA global memory to reserve for kernel launches
#define LBCTW                       5               // (x >> LBCTW) == (x / CUDATHREADSPERWARP)  and  (x << LBCTW) == (x * CUDATHREADSPERWARP)

/* The following defines make it possible to inject a comment (associated with the C++ filename and line number) into the .PTX file
    generated by NVCC v4.1.  In previous versions, NVCC interleaved C/C++ code with generated PTX, but this capability no longer exists in v4.1,
    although NVCC does inject C++ source-code line numbers with the PTX .loc directive.

   Sample usage:
    PTX_INJECT_COMMENT( "Top of main loop" );
    PTX_INJECT_LINENUMBER;

   The macros work as follows:
    The _2 macros stringize the filename and line number; the result is a set of double-quoted strings which can be concatenated by the compiler into a single string.
    The _1 macros are needed so that the predefined macros __FILE__ and __LINE__ can be resolved.  Without this indirection, these macros are not dereferenced; the
     strings "__FILE__" and "__LINE__" appear instead.
*/
#define INTERNAL_PTX_INJECT_COMMENT_2(l,f,c) asm volatile ( "// line " #l " in " #f "\n\t// " c)
#define INTERNAL_PTX_INJECT_COMMENT_1(f,l,c) INTERNAL_PTX_INJECT_COMMENT_2(l,f,c)
#define PTX_INJECT_COMMENT(c) INTERNAL_PTX_INJECT_COMMENT_1(__FILE__, __LINE__, c)

#define INTERNAL_PTX_INJECT_LINENUMBER_2(l,f) asm volatile ( "// line " #l " in " #f )
#define INTERNAL_PTX_INJECT_LINENUMBER_1(f,l) INTERNAL_PTX_INJECT_LINENUMBER_2(l,f)
#define PTX_INJECT_LINENUMBER INTERNAL_PTX_INJECT_LINENUMBER_1(__FILE__, __LINE__)

/* inline PTX macros */
#ifdef __CUDACC__
/* [device] method __lanemask_eq

   Because this method is inline, and because the compiler optimizes away the register accesses implied by defining and returning the contents of
    a local variable, the net effect of this entire function definition is to generate a PTX instruction that loads a register with the current
    value of the PTX "special register" %lanemask_eq, e.g.:

        mov.u32 %r67, %lanemask_eq;
*/
static __device__ __inline__ UINT32 __lanemask_eq()
{
	UINT32 d;
	asm volatile ( "mov.u32 %0, %lanemask_eq;" : "=r"(d) );
	return d;
}

/// [device] method __clz32
static __device__ __inline__ UINT32 __clz32( UINT32 a )
{
	UINT32 d;
	asm volatile ( "clz.b32 %0,%1;" : "=r" (d) : "r" (a) );
	return d;
}

/// [device] method __bfinds32
static __device__ __inline__ UINT32 __bfinds32( INT32 a )
{
	UINT32 d;
	asm volatile ( "bfind.s32 %0,%1;" : "=r" (d) : "r" (a) );
	return d;
}

/// [device] method __bfindu32
static __device__ __inline__ UINT32 __bfindu32( UINT32 a )
{
	UINT32 d;
	asm volatile ( "bfind.u32 %0,%1;" : "=r" (d) : "r" (a) );
	return d;
}

/// [device] method __bfindu64
static __device__ __inline__ UINT32 __bfindu64( UINT64 a )
{
	UINT32 d;
	asm volatile ( "bfind.u64 %0,%1;" : "=r" (d) : "l" (a) );
	return d;
}

/// [device] method __popc32
static __device__ __inline__ UINT32 __popc32( UINT32 a )
{
	UINT32 d;
	asm volatile ( "popc.b32 %0,%1;" : "=r" (d) : "r" (a) );
	return d;
}

/// [device] method __popc64
static __device__ __inline__ UINT32 __popc64( UINT64 a )
{
	UINT32 d;
	asm volatile (  "popc.b64 %0,%1;" : "=r" (d) : "l" (a) );
	return d;
}

// TODO: CHOP #define __bfi32(f,a,b,c,d)  asm( "bfi.b32 %0,%1,%2,%3,%4;" : "=r" (f) : "r" (a), "r" (b), "r" (c), "r" (d) )

/// [device] method __bfi32
static __device__ __inline__ UINT32 __bfi32( UINT32 a, UINT32 b, UINT32 c, UINT32 d )
{
    /* Align and insert a bit field from a into b, and place the result in f.
    
       Source c gives the starting bit position for the insertion, and source d gives the bit field length in bits.
    */
	UINT32 f;
	asm volatile ( "bfi.b32 %0,%1,%2,%3,%4;" : "=r" (f) : "r" (a), "r" (b), "r" (c), "r" (d) );
	return f;
}

/// [device] method __bfi64
static __device__ __inline__ UINT64 __bfi64( UINT64 a, UINT64 b, UINT32 c, UINT32 d )
{
	UINT64 f;
	asm volatile ( "bfi.b64 %0,%1,%2,%3,%4;" : "=l" (f) : "l" (a), "l" (b), "r" (c), "r" (d) );
	return f;
}


// TODO: CHOP #define __bfi64(f,a,b,c,d)  asm( "bfi.b64 %0,%1,%2,%3,%4;" : "=l" (f) : "l" (a), "l" (b), "r" (c), "r" (d) )
// TODO: CHOP #define __bfe32(d,a,b,c)    asm( "bfe.u32 %0,%1,%2,%3;" : "=r" (d) : "r" (a), "r" (b), "r" (c) )
// TODO: CHOP #define __bfe64(d,a,b,c)    asm( "bfe.u64 %0,%1,%2,%3;" : "=l" (d) : "l" (a), "r" (b), "r" (c) )

/// [device] method __bfe32
static __device__ __inline__ UINT32 __bfe32( UINT32 a, UINT32 b, UINT32 c )
{
    /* Extract bit field from a and place the zero or sign-extended result in d.
    
       Source b gives the bit field starting bit position, and source c gives the bit field length in bits.
    */
	UINT32 d;
	asm volatile ( "bfe.u32 %0,%1,%2,%3;" : "=r" (d) : "r" (a), "r" (b), "r" (c) );
	return d;
}

/// [device] method __bfe64
static __device__ __inline__ UINT64 __bfe64( UINT64 a, UINT32 b, UINT32 c )
{
	UINT64 d;
	asm volatile ( "bfe.u64 %0,%1,%2,%3;" : "=l" (d) : "l" (a), "r" (b), "r" (c) );
	return d;
}
#endif
#pragma endregion

#pragma region structs
struct cudaDevicePropEx : cudaDeviceProp        // (struct cudaDeviceProp is defined in %CUDA_INC_PATH%\driver_types.h)
{
    INT32   cudaDeviceId;   // the device ID returned by cudaGetDevice() and used for calls into the CUDA APIs
};
#pragma endregion

/// <summary>
/// Class <c>CudaCommon</c> implements basic CUDA device functionality in a set of static methods.
/// </summary>
class CudaCommon
{
    private:
        static char m_cudaVersionString[256];

    private:
        CudaCommon( void );
        static CudaCommon m_instance;

    public:
        virtual ~CudaCommon( void );
        static INT32 GetDeviceCount( void );
        static void GetDeviceProperties( cudaDevicePropEx* pcdpe, INT32 deviceId );
        static char* GetCudaVersionString( void );
};
