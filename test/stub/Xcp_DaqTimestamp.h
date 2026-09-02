/**
 * @file Xcp_DaqTimestamp.h
 * @author Guillaume Sottas
 *
 * @brief data acquisition clock callback, to be implemented by the integrator.
 */

#ifndef XCP_DAQ_TIMESTAMP_H
#define XCP_DAQ_TIMESTAMP_H

#ifdef __cplusplus

extern "C" {

#endif /* #ifdef __cplusplus */

#include "Std_Types.h"

/**
 * @brief returns the current value of the slave's data acquisition clock.
 *
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.1.2.2 requires "a free running counter
 * in the slave, which is never reset or modified and wraps around if an overflow occurs". This
 * module holds no clock and nothing in its configuration can describe one, so the counter is the
 * integrator's. Its resolution is declared through protocol_layer.timestamp and reported to the
 * master by GET_DAQ_RESOLUTION_INFO; this function must agree with that declaration.
 *
 * @note Called from two contexts: from Xcp_TriggerEventChannel, once per cycle of each running
 * timestamped DAQ list, in whatever context the integrator triggers the event from; and from
 * Xcp_CanIfRxIndication on receipt of GET_DAQ_CLOCK, which may be an interrupt. It must be
 * re-entrant and must not block.
 *
 * @return the current counter value. Always uint32 regardless of the configured timestamp size,
 * because GET_DAQ_CLOCK transmits a DWORD whatever the DTO field width is; the DTO truncates.
 */
extern uint32 Xcp_GetDaqTimestamp(void);

#ifdef __cplusplus

}

#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_DAQ_TIMESTAMP_H */
