/**
 * @file SchM_Xcp.h
 * @brief BSW Scheduler exclusive areas used by the DAQ transmit and stimulation paths.
 *
 * @details An integrator replaces this with the SchM the RTE generates. SchM_Enter_Xcp_DtoQueue /
 * SchM_Exit_Xcp_DtoQueue protects the DTO ring indices, the event queue's read/write indices, and
 * Xcp_Internal.ongoing_transmit_type, which Xcp_TriggerEventChannel, Xcp_CanIfTxConfirmation and
 * Xcp_MainFunction all reach. The event queue has two producers (Xcp_MainFunction's EV_STORE_CAL
 * push, Xcp_TriggerEventChannel's EV_DAQ_OVERLOAD push) and one consumer (Xcp_TransmitOneFrame's
 * get, paired with Xcp_CanIfTxConfirmation's pop) that can all run in different contexts, exactly
 * as the DTO ring does for DAQ frames -- an integrator must exclude the event queue's accesses
 * under this same area, not only the DTO ring's. It must suspend anything that can call into this
 * module -- typically the CAN transmit interrupt -- and must never be held across a call to
 * CanIf_Transmit.
 *
 * "Anything that can call into this module" includes Xcp_CanIfTxConfirmation itself: it updates
 * ongoing_transmit_type outside the area before Xcp_StartNextTransmission reads it under one, so
 * the area must exclude the confirmation's execution context too, not just concurrent callers of
 * this module's other entry points. A primitive that does not -- a spinlock shared with a
 * confirmation handled on another core, for instance -- does not satisfy this.
 */

#ifndef SCHM_XCP_H

#define SCHM_XCP_H

#ifdef __cplusplus

extern "C" {

#endif /* #ifdef __cplusplus */

#include "Std_Types.h"

extern void SchM_Enter_Xcp_DtoQueue(void);
extern void SchM_Exit_Xcp_DtoQueue(void);

/**
 * @brief second exclusive area (DD37), guarding one Xcp_StimSlotType -- its payload and its
 * `length` together -- while Xcp_DaqStoreStim writes it in the receive callback's context or
 * Xcp_DaqApplyStim reads it in the event trigger's. Held per slot, not around the whole reception
 * or the whole apply loop, the same rule Xcp_DaqListClearEntries already follows for DD14.
 * @details A length paired with the buffer it describes is the DD14 class: a write or a read torn
 * by the other context would leave the two disagreeing about how much of the buffer is valid.
 *
 * Deliberately not SchM_Enter_Xcp_DtoQueue: a DAQ_STIM list applies its slots and samples its DTO
 * within the same trigger, so sharing one area would risk the apply section nesting inside the
 * sampler's DtoQueue section -- and test/conftest.py's exclusive-area bookkeeping asserts against
 * nesting globally, on every test, not only this module's own.
 */
extern void SchM_Enter_Xcp_StimBuffer(void);
extern void SchM_Exit_Xcp_StimBuffer(void);

#ifdef __cplusplus

}

#endif /* #ifdef __cplusplus */

#endif /* #ifndef SCHM_XCP_H */
