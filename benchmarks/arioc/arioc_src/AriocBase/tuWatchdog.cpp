/*
  tuWatchdog.cpp

    Copyright (c) 2015-2019 Johns Hopkins University.  All rights reserved.

    This file is part of the Arioc software distribution.  It is subject to the license terms
    in the LICENSE.txt file found in the top-level directory of the Arioc software distribution.
    The contents of this file, in whole or in part, may only be copied, modified, propagated, or
    redistributed in accordance with the license terms contained in LICENSE.txt.
*/
#include "stdafx.h"

#pragma region static member variables
UINT32 tuWatchdog::m_threadId[32];
UINT32 tuWatchdog::m_watchdogState[32];
UINT32 tuWatchdog::m_watchdogStateChanged;
UINT32 tuWatchdog::m_isWatchdogDevice;
#pragma endregion

#pragma region constructor/destructor
/// [private] constructor
tuWatchdog::tuWatchdog()
{
}

/// <summary>
/// Runs a "watchdog" thread to monitor execution status.
/// </summary>
tuWatchdog::tuWatchdog( AriocBase* _pab ) : m_pab(_pab), m_msInterval(0)
{
    INT32 i = _pab->paamb->Xparam.IndexOf( "watchdogInterval" );
    UINT32 wi = (i >= 0) ? static_cast<UINT32>(_pab->paamb->Xparam.Value( i )) : 0;
    if( (wi != 0) && ((wi < MININTERVAL) || (wi > MAXINTERVAL)) )
        throw new ApplicationException( __FILE__, __LINE__, "%s: invalid watchdog interval %u (must be either zero or between %u and %u)", __FUNCTION__, wi, MININTERVAL, MAXINTERVAL );
    m_msInterval = wi * 1000;
}

/// destructor
tuWatchdog::~tuWatchdog()
{
}
#pragma endregion

#pragma region virtual method implementations
/// <summary>
/// Reformats and consolidates the BRLEAs generated by gapped-alignment traceback
/// </summary>
void tuWatchdog::main()
{
    CDPrint( cdpCD0, "%s: watchdog interval %us", __FUNCTION__, m_msInterval/1000 );

    while( m_msInterval )
    {
        /* We "salt" the timeout interval so that it varies randomly by about 10%.  The idea is to avoid having the
            watchdog interval in lockstep with some other thread in the application.
        */
        UINT32 ms = (rand() % (m_msInterval/5)) + ((9*m_msInterval)/10);

        /* We sleep in 1-second "chunks" so that this thread does not sleep for more than 1000ms if the application terminates. */
        UINT32 chunkTotal = 0;
        while( (chunkTotal < ms) && m_msInterval )
        {
            Sleep( 1000 );
            chunkTotal += 1000;
        }

        // look for "stuck" states
        if( ((m_watchdogStateChanged & m_isWatchdogDevice) != m_isWatchdogDevice) && m_msInterval )
        {
            char buf[512];
            sprintf_s( buf, sizeof buf, "%s: stuck:", __FUNCTION__ );
            UINT32 stuck = (~m_watchdogStateChanged) & m_isWatchdogDevice;
            INT32 i = 0;
            for( UINT32 mask=1; (mask<=m_isWatchdogDevice) && (i<32); mask<<=1 )
            {
                if( stuck & mask )
                {
                    size_t cch = strlen( buf );
                    sprintf_s( buf+cch, (sizeof buf)-cch, " %08x(%u):%d@%u", m_threadId[i], m_threadId[i], i, m_watchdogState[i] );
                }

                ++i;
            }

            CDPrint( cdpCD0, buf );
        }

        // reset the state-changed flags
        m_watchdogStateChanged = 0;
    }

    if( m_msInterval )
        CDPrint( cdpCD0, "%s: watchdog stopped", __FUNCTION__ );
}
#pragma endregion

#pragma region public methods
/// [public] method Watch
void tuWatchdog::Watch( INT32 _deviceId )
{
    m_threadId[_deviceId] = GetCurrentThreadId();
    m_isWatchdogDevice |= (1 << _deviceId);
}

#if TODO_CHOP_IF_UNUSED
/// [public] method SetWatchdogState
void tuWatchdog::SetWatchdogState( INT32 _state )
{
    INT32 deviceId = CudaDeviceBinding::GetCudaDeviceId();

    if( m_watchdogState[deviceId] != _state )
    {
        m_watchdogState[deviceId] = _state;
        m_watchdogStateChanged |= (1 << deviceId);
    }
}
#endif

/// [public] method SetWatchdogState
void tuWatchdog::SetWatchdogState( INT32 _deviceId, UINT32 _state, bool _verifyDeviceId )
{
    if( _verifyDeviceId )
    {
        if( _deviceId != CudaDeviceBinding::GetCudaDeviceId() )
            throw new ApplicationException( __FILE__, __LINE__, "%s: device ID mismatch: %d != %d", __FUNCTION__, _deviceId, CudaDeviceBinding::GetCudaDeviceId() );
    }
    else
    if( _deviceId < 0 )
        throw new ApplicationException( __FILE__, __LINE__, "%s: invalid device ID: %d", __FUNCTION__, _deviceId );

    if( m_watchdogState[_deviceId] != _state )
    {
        m_watchdogState[_deviceId] = _state;
        m_watchdogStateChanged |= (1 << _deviceId);
    }
}

/// [public] method Halt
void tuWatchdog::Halt( INT32 _deviceId )
{
    // discard the thread ID and zero the flag that corresponds to the specified device ID
    m_threadId[_deviceId] = 0;
    m_isWatchdogDevice &= ~(1 << _deviceId);

    // if no more devices remain to be watched, fall out of the worker thread
    if( !m_isWatchdogDevice )
    {
        // zeroing the sleep interval causes the main loop to terminate
        m_msInterval = 0;
    }
}
#pragma endregion
