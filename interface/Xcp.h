/**
 * @file Xcp.h
 * @author Guillaume Sottas
 * @date 15/01/2018
 *
 * @defgroup XCP CAN transport layer
 *
 * @defgroup XCP_H_GDEF identification informations
 * @ingroup XCP_H
 * @defgroup XCP_H_E errors classification
 * @ingroup XCP_H
 * @defgroup XCP_H_E_D development errors
 * @ingroup XCP_H_E
 * @defgroup XCP_H_E_R runtime errors
 * @ingroup XCP_H_E
 * @defgroup XCP_H_E_T transient faults
 * @ingroup XCP_H_E
 * @defgroup XCP_H_GTDEF global data type definitions
 * @ingroup XCP_H
 * @defgroup XCP_H_EFDECL external function declarations
 * @ingroup XCP_H
 * @defgroup XCP_H_GCDECL global constant declarations
 * @ingroup XCP_H
 * @defgroup XCP_H_GVDECL global variable declarations
 * @ingroup XCP_H
 * @defgroup XCP_H_GFDECL global function declarations
 * @ingroup XCP_H
 * @defgroup XCP_H_GSFDECL global scheduled function declarations
 * @ingroup XCP_H
 */

#ifndef XCP_H
#define XCP_H

#ifdef __cplusplus

extern "C" {

#endif /* #ifdef __cplusplus */

/*------------------------------------------------------------------------------------------------*/
/* included files (#include).                                                                     */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H
 * @{
 */

#include "Xcp_Types.h"

#include "Xcp_Errors.h"

#include "Xcp_SeedKey.h"

#include "Xcp_Checksum.h"

#include "Xcp_UserCmd.h"

#include "Xcp_MemoryAccess.h"

#include "SchM_Xcp.h"

#if (XCP_PAGING_SUPPORTED == STD_ON)

#include "Xcp_Paging.h"

#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */

#if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON)

#include "Xcp_DaqTimestamp.h"

#endif /* #if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON) */

#if defined(CFFI_ENABLE)

/**
 * @brief if CFFI_ENABLE is defined, expose the Xcp callback function to CFFI module as well as
 * the external functions.
 */
#include "XcpOnCan_Cbk.h"

#include "CanIf.h"

#if (XCP_DEV_ERROR_DETECT == STD_ON)

#include "Det.h"

#endif /* #if (XCP_DEV_ERROR_DETECT == STD_ON) */

#endif /* #if defined(CFFI_ENABLE) */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global definitions (#define).                                                                  */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GDEF
 * @{
 */

/**
 * @brief unique identifier of the XCP driver.
 * @note this value corresponds to document ID of corresponding Autosar software specification.
 */
#define XCP_MODULE_ID (0xFFu)

#ifndef XCP_SW_MAJOR_VERSION

/**
 * @brief XCP driver major version number.
 */
#define XCP_SW_MAJOR_VERSION (0x00u)

#endif /* #ifndef XCP_SW_MAJOR_VERSION */

#ifndef XCP_SW_MINOR_VERSION

/**
 * @brief XCP driver minor version number.
 */
#define XCP_SW_MINOR_VERSION (0x01u)

#endif /* #ifndef XCP_SW_MINOR_VERSION */

#ifndef XCP_SW_PATCH_VERSION

/**
 * @brief XCP driver patch version number.
 */
#define XCP_SW_PATCH_VERSION (0x00u)

#endif /* #ifndef XCP_SW_PATCH_VERSION */

/**
 * @brief @ref Xcp_Init API ID.
 */
#define XCP_INIT_API_ID (0x00u)

/**
 * @brief @ref Xcp_GetVersionInfo API ID.
 */
#define XCP_GET_VERSION_INFO_API_ID (0x01u)

/**
 * @brief @ref Xcp_SetTransmissionMode API ID.
 */
#define XCP_SET_TRANSMISSION_MODE_API_ID (0x05u)

/**
 * @brief @ref Xcp_MainFunction API ID.
 */
#define XCP_MAIN_FUNCTION_API_ID (0x04u)

/**
 * @brief API id of Xcp_TriggerEventChannel, for development error reporting.
 */
#define XCP_TRIGGER_EVENT_CHANNEL_API_ID (0x06u)

/**
 * @brief @ref Xcp_CanIfTxConfirmation API ID.
 */
#define XCP_CAN_IF_TX_CONFIRMATION_API_ID (0x40u)

/**
 * @brief @ref Xcp_CanIfTriggerTransmit API ID.
 */
#define XCP_CAN_IF_TRIGGER_TRANSMIT_API_ID (0x41u)

/**
 * @brief @ref Xcp_CanIfRxIndication API ID.
 */
#define XCP_CAN_IF_RX_INDICATION_API_ID (0x42u)

/** @} */

/**
 * @addtogroup XCP_H_E_D
 * @{
 */

/**
 * @brief Module not initialized.
 */
#define XCP_E_UNINIT (0x02u)

/**
 * @brief Initialization of XCP failed.
 */
#define XCP_E_INIT_FAILED (0x04u)

/**
 * @brief Null pointer has been passed as an argument.
 */
#define XCP_E_PARAM_POINTER (0x12u)

/**
 * @brief API call with wrong PDU ID.
 */
#define XCP_E_INVALID_PDUID (0x03u)

/**
 * @brief The stack tried to stack an event while the queue was full.
 * @note This error is not part of the specification.
 */
#define XCP_E_EVENT_QUEUE_FULL (0x04u)

/**
 * @brief The event channel number handed to Xcp_TriggerEventChannel does not exist.
 */
#define XCP_E_INVALID_EVENT_CHANNEL (0x05u)

/**
 * @brief A received stimulation frame was dropped instead of being buffered.
 * @details Raised by Xcp_DaqStoreStim for every frame it refuses (DD39): one it cannot resolve to
 * a DAQ list and an ODT, one addressing a list that cannot receive, is not running or is not
 * directed at stimulation, one whose payload is shorter than that ODT's entries need, and one
 * longer than the running configuration's MAX_DTO.
 * @note This error is not part of the specification, and Det is the only channel a rejection has:
 * XCP part 2 - Protocol Layer Specification 1.1/1.1.4.2's DTO is not a command, so there is no
 * error packet to answer it with and no master waiting on one.
 */
#define XCP_E_STIM_FRAME_REJECTED (0x06u)

/**
 * @brief Buffered stimulation data was not written to memory at the event trigger.
 * @details Raised by Xcp_DaqApplyStim (source/Xcp_DaqRuntime.c) for what it cannot honour, and for
 * two reasons only:
 *
 * - one or more ODT entries name a non-zero address extension. Xcp_WriteSlaveMemoryTable has no
 *   parameter for one, so such an entry cannot be written where it says (DD45); it is skipped and
 *   its siblings still apply. Raised once for the ODT, however many of its entries were skipped:
 *   this error carries no parameter that could say which one, so repeating it says nothing a
 *   single report does not, at a raster rate.
 * - the whole ODT, when the slot holds fewer bytes than its entries consume. The frame was long
 *   enough for the ODT when it arrived (DD39) and the ODT has been reconfigured since, so it is
 *   refused whole rather than applied in part.
 *
 * Deliberately NOT raised for the everyday case of a slot no frame has filled yet: DD35 makes that
 * a silent skip, and reporting it would fire on every event of every cycle until a master's first
 * frame arrives.
 * @note This error is not part of the specification, and Det is the only channel it has: the
 * trigger is a vendor API answering no master, so there is no error packet and nobody waiting on
 * one -- the same reasoning XCP_E_STIM_FRAME_REJECTED above records for the receive direction.
 * Distinct from that code because this is a different API (XCP_TRIGGER_EVENT_CHANNEL_API_ID) at a
 * different point in time: a frame this slave accepted and buffered, which it then could not
 * apply.
 */
#define XCP_E_STIM_NOT_APPLIED (0x07u)

/**
 * @brief A DAQ list was not sampled because its DTOs would have reached the master unidentifiable.
 * @details Raised by Xcp_TriggerEventChannel (source/Xcp_DaqRuntime.c) for a running list that has
 * PID_OFF set and more than one ODT. Such a list would put several DTOs on one PDU carrying no
 * identification field and nothing else to tell them apart, so it is skipped whole.
 *
 * The state is reachable only by drift. Xcp_DTOCmdDaqSetDaqListMode (source/Xcp_Daq.c) grants
 * PID_OFF against three conditions -- ABSOLUTE identification, a single ODT, and a TX PDU no other
 * list shares -- but a grant describes the moment the command ran. Under DAQ_DYNAMIC the master
 * may allocate further ODTs to that list afterwards: ALLOC_ODT is legal after ALLOC_ODT and no
 * ERR_SEQUENCE rule in XCP part 2 - Protocol Layer Specification 1.1/1.6.4.2.1.3 forbids it, so
 * the second allocation succeeds and leaves PID_OFF set on a list of two ODTs.
 * @note This error is not part of the specification, and Det is the only channel the skip has: the
 * trigger is a vendor API answering no master, so there is no error packet and nobody waiting on
 * one. The specification does not say what a slave does here. It requires only that PID_OFF go
 * with ABSOLUTE identification, and assigns the rest to the transport -- 1.1/1.1.2.1: "If the
 * Identification Field is not transferred in the XCP Packet, the unambiguous identification has to
 * be done on the level of the Transport Layer", of which one CAN-Id and one ODT per list is the
 * example it offers, not a rule it imposes. This module adopts that example as its grant rule
 * because on CAN every ODT of a list shares one TX PDU, leaving the transport nothing to
 * disambiguate with; skipping here keeps that self-imposed invariant true at the moment of use,
 * rather than emitting frames whose identification the specification requires and this transport
 * cannot supply. The master is told nothing -- no event code exists for "your configuration
 * became unrepresentable" -- so Det is where an integrator sees it.
 */
#define XCP_E_DAQ_LIST_NOT_IDENTIFIABLE (0x08u)

/** @} */

/**
 * @addtogroup XCP_H_E_R
 * @{
 */

/** @} */

/**
 * @addtogroup XCP_H_E_T
 * @{
 */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global data type definitions (typedef, struct).                                                */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GTDEF
 * @{
 */

typedef enum {
    XCP_UNINITIALIZED = 0x00u,
    XCP_INITIALIZED,
} Xcp_StateType;

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* external function declarations (extern).                                                       */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_EFDECL
 * @{
 */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global constant declarations (extern const).                                                   */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GCDECL
 * @{
 */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global variable declarations (extern).                                                         */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GVDECL
 * @{
 */

#ifdef CFFI_ENABLE

extern Xcp_StateType Xcp_State;

extern const Xcp_Type *Xcp_Ptr;

extern Xcp_RtType Xcp_Rt[];

#endif /* #ifndef CFFI_ENABLE */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global function declarations.                                                                  */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GFDECL
 * @{
 */

#define Xcp_START_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

/**
 * @brief this service initializes interfaces and variables of the AUTOSAR XCP layer.
 * @param [in] pConfig pointer to a selected configuration structure
 */
void Xcp_Init(const Xcp_Type *pConfig);

#define Xcp_STOP_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

#if (XCP_GET_VERSION_INFO_API == STD_ON)

#define Xcp_START_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

/**
 * @brief returns the version information of this module.
 * @param [out] pVersionInfo pointer to where to store the version information of this module
 */
void Xcp_GetVersionInfo(Std_VersionInfoType *pVersionInfo);

#define Xcp_STOP_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

#endif /* #if (XCP_GET_VERSION_INFO_API == STD_ON) */

#if (XCP_SUPPRESS_TX_SUPPORT == STD_ON)

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/**
 * @brief this API is used to turn on and off of the TX capabilities of used communication bus
 * channel in XCP module.
 * @param [in] channel the Network channel for the used bus communication
 * @param [in] mode enabled or disabled Transmission mode Parameters
 */
void Xcp_SetTransmissionMode(NetworkHandleType channel, Xcp_TransmissionModeType mode);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#endif /* #if (XCP_SUPPRESS_TX_SUPPORT == STD_ON) */

#if (XCP_PAGING_SUPPORTED == STD_ON)

#define Xcp_START_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

/**
 * @brief reports whether a calibration data segment has been selected for freezing.
 * @details The XCP master sets this flag with SET_SEGMENT_MODE. An integrator implementing
 * @ref Xcp_StoreCalibrationDataToNonVolatileMemory queries it per segment to decide what to
 * store.
 * @param [in] segment logical data segment number
 * @return TRUE if FREEZE mode is enabled for that segment, FALSE otherwise or if the segment
 * number is out of range
 */
boolean Xcp_GetSegmentFreezeState(uint8 segment);

#define Xcp_STOP_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */

#define Xcp_START_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

/**
 * @brief Saves the currently selected DAQ list configuration to non-volatile memory.
 * @param [in] sessionConfigurationId The session configuration id to commit alongside the stored
 * configuration -- SET_REQUEST's own bytes 2,3 (XCP part 2 - Protocol Layer Specification
 * 1.0/1.6.1.2.3), passed through unexamined by this module.
 * @param [out] pStatusCode Result of the store, read only when this function returns E_OK: zero for
 * success, non-zero for failure.
 * @retval E_OK: the store is finished (no matter if it was successfully terminated or not)
 * @retval E_NOT_OK: the store is not finished
 * @details Polled, but never from the SET_REQUEST handler itself: Xcp_DTOCmdStdSetRequest
 * (source/Xcp_Std.c) only sets the STORE_DAQ_REQ bit and stages the session configuration id, then
 * finalizes a positive response right away -- SET_REQUEST has no deferral path at all, and this
 * callback plays no part in answering it. Xcp_MainFunction is the only caller, once per cycle
 * while the bit is set, until this reports completion -- even an implementation whose work is
 * instantaneous is first called on the next Xcp_MainFunction cycle, not inline with the request,
 * so an integrator must not assume this callback's first invocation shares the SET_REQUEST
 * command's own calling context. Completion reaches the master separately, through EV_STORE_DAQ,
 * decoupled from the SET_REQUEST response that has already gone out.
 * @note Design doc DD97 places two ordering obligations on this callback, neither of which this
 * module can enforce from outside the integrator's own non-volatile storage:
 * - XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.3: "Upon saving, the slave first has to
 *   clear any DAQ list configuration that might already be stored in non-volatile memory" -- any
 *   existing stored configuration is cleared FIRST, before the new one is written.
 * - The session configuration id above is committed LAST, strictly after the DAQ lists themselves.
 *   A store interrupted midway then leaves no id behind, so a later read of the stored configuration
 *   reports none rather than a half-written one a master would mistake for complete.
 * @note Declared unconditionally, not behind an XCP_xxx_API compile switch: Xcp_MainFunction
 * (source/Xcp.c) references this symbol regardless of storeDaqConfigurationApiEnable, which gates
 * only a runtime if around the call, not whether the reference is compiled in. Every build must
 * link an implementation, flag on or off -- the same requirement
 * Xcp_StoreCalibrationDataToNonVolatileMemory already imposes unconditionally for STORE_CAL_REQ.
 */
extern Std_ReturnType Xcp_StoreDaqConfiguration(uint16 sessionConfigurationId, uint8 *pStatusCode);

/**
 * @brief Clears (erases) the DAQ list configuration held in non-volatile memory.
 * @param [out] pStatusCode Result of the clear, read only when this function returns E_OK: zero for
 * success, non-zero for failure.
 * @retval E_OK: the clear is finished (no matter if it was successfully terminated or not)
 * @retval E_NOT_OK: the clear is not finished
 * @details Polled, but never from the SET_REQUEST handler itself: Xcp_DTOCmdStdSetRequest
 * (source/Xcp_Std.c) only sets the CLEAR_DAQ_REQ bit, then finalizes a positive response right
 * away -- SET_REQUEST has no deferral path at all, and this callback plays no part in answering
 * it. Xcp_MainFunction is the only caller, once per cycle while the bit is set, until this reports
 * completion -- even an implementation whose work is instantaneous is first called on the next
 * Xcp_MainFunction cycle, not inline with the request, so an integrator must not assume this
 * callback's first invocation shares the SET_REQUEST command's own calling context. Completion
 * reaches the master separately, through EV_CLEAR_DAQ, decoupled from the SET_REQUEST response
 * that has already gone out.
 * @note XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.3's postcondition -- every ODT entry
 * reset to address = 0, extension = 0, size = 0, bit_offset = 0xFF, and the session configuration id
 * reset to 0 -- is stated here as an observable outcome rather than as byte patterns in memory this
 * module never sees: after a successful clear, a subsequent read of the stored configuration reports
 * none, and id 0.
 * @note The same unconditional-linkage requirement as @ref Xcp_StoreDaqConfiguration's own note:
 * Xcp_MainFunction references this symbol regardless of clearDaqConfigurationApiEnable, so a build
 * must supply an implementation even with the flag off.
 */
extern Std_ReturnType Xcp_ClearDaqConfiguration(uint8 *pStatusCode);

/**
 * @brief reports whether a DAQ list has been selected for a pending operation.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.4: the master sets this flag
 * with START_STOP_DAQ_LIST's SELECT mode. An integrator implementing @ref Xcp_StoreDaqConfiguration
 * queries it per list to decide what to store.
 * @note The selection is reset once the store it was made for completes (XCP part 2 - Protocol
 * Layer Specification 1.0/1.6.4.1.1.6), so this reports TRUE throughout the call to
 * @ref Xcp_StoreDaqConfiguration that persists it, and FALSE afterwards. A store reporting a
 * non-zero status leaves the selection standing, since it persisted nothing.
 * @param [in] daqListNumber DAQ list number
 * @return TRUE if the list is selected, FALSE otherwise or if daqListNumber is out of range
 */
boolean Xcp_GetDaqListSelectedState(uint16 daqListNumber);

/**
 * @brief reports how many ODTs a DAQ list has been allocated.
 * @details Under DAQ_STATIC this is the generated configuration's own ODT count; under DAQ_DYNAMIC
 * it is what the master has allocated with ALLOC_ODT so far, which may be less than the pool's
 * ceiling.
 * @param [in] daqListNumber DAQ list number
 * @return the ODT count, or 0 if daqListNumber is out of range
 */
uint8 Xcp_GetDaqListOdtCount(uint16 daqListNumber);

/**
 * @brief reports how many entries one ODT of a DAQ list has been allocated.
 * @param [in] daqListNumber DAQ list number
 * @param [in] odtNumber ODT number, relative to daqListNumber
 * @return the entry count, or 0 if daqListNumber or odtNumber is out of range
 */
uint8 Xcp_GetOdtEntryCount(uint16 daqListNumber, uint8 odtNumber);

/**
 * @brief reports one ODT entry's configuration.
 * @param [in] daqListNumber DAQ list number
 * @param [in] odtNumber ODT number, relative to daqListNumber
 * @param [in] odtEntryNumber ODT entry number, relative to odtNumber
 * @param [out] pEntry where address, bitOffset, addressExtension and length are copied, read only
 * when this function returns E_OK. Xcp_OdtEntryType::number is left untouched -- the caller
 * already supplied it as odtEntryNumber above, so a caller who allocates pEntry itself must not
 * read that field back expecting this call to have populated it.
 * @retval E_OK: pEntry was populated
 * @retval E_NOT_OK: daqListNumber, odtNumber or odtEntryNumber is out of range; pEntry is left
 * untouched
 */
Std_ReturnType Xcp_GetOdtEntry(uint16 daqListNumber, uint8 odtNumber, uint8 odtEntryNumber,
                               Xcp_OdtEntryType *pEntry);

/**
 * @brief Reads the session configuration id held in non-volatile memory, if any.
 * @param [out] pSessionConfigurationId Where the stored id is copied, read only when this function
 * returns E_OK with a zero pStatusCode. Left untouched otherwise.
 * @param [out] pStatusCode Result of the read, read only when this function returns E_OK: zero
 * when pSessionConfigurationId holds a valid stored configuration's id, non-zero when
 * non-volatile memory holds none.
 * @retval E_OK: the read is finished (whether or not a stored configuration was found)
 * @retval E_NOT_OK: non-volatile memory is not yet readable
 * @details Polled, on a contract close to @ref Xcp_StoreCalibrationDataToNonVolatileMemory's own
 * but with a different trigger: Xcp_Init arms the poll rather than calling this directly, and
 * Xcp_MainFunction is the only caller, once per cycle from the very first one after Xcp_Init until
 * this reports completion, after which it is never called again for the rest of the session. An
 * implementation whose work is instantaneous still returns E_OK only on that first
 * Xcp_MainFunction call, not from within Xcp_Init itself.
 * @note Design doc DD100: this is polled rather than called synchronously from Xcp_Init, because
 * this module can neither verify nor enforce that the integrator's own non-volatile memory
 * abstraction has finished populating its RAM mirror (e.g. AUTOSAR NvM's own NvM_ReadAll) by the
 * time Xcp_Init runs -- that depends on the EcuM/BswM start-up configuration and is itself
 * asynchronous. Calling this synchronously and trusting a first E_NOT_OK to mean "nothing stored"
 * would adopt 0 permanently, with nothing to indicate why.
 * @note Design doc DD101: while this read is outstanding, GET_STATUS answers
 * XCP part 2 - Protocol Layer Specification 1.1/1.7.3.2.1's own
 * ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE rather than a session configuration id this module does
 * not yet have -- reporting 0 in the meantime would be indistinguishable from a legitimate
 * "nothing stored" answer from pStatusCode above.
 * @note An implementation that never returns E_OK costs GET_STATUS for the life of the ECU: design
 * doc DD101 refuses it with ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE for as long as this read stays
 * outstanding, and no CONNECT/DISCONNECT cycle clears that -- DD99 already forbids CONNECT from
 * touching what non-volatile memory holds, and abandoning the read would mean adopting 0 in its
 * place, the exact fabricated answer the refusal exists to prevent. Only a power cycle re-arms
 * this poll, and a callback that can never complete -- a mis-scoped NvM block, one left out of
 * NvM_ReadAll, an unfinished stub -- meets it again immediately, so the refusal recurs for the
 * life of the ECU.
 * @note Design doc DD102: a successful read adopts the id alone. No DAQ list configuration is
 * restored, since RESUME -- the feature that would give a restored list somewhere to run -- is a
 * later phase and stays unadvertised (GET_DAQ_PROCESSOR_INFO's RESUME_SUPPORTED).
 * @note The same unconditional-linkage requirement as @ref Xcp_StoreDaqConfiguration's own note:
 * Xcp_MainFunction references this symbol regardless of
 * readStoredSessionConfigurationIdApiEnable, so a build must supply an implementation even with
 * the flag off.
 */
extern Std_ReturnType Xcp_ReadStoredSessionConfigurationId(uint16 *pSessionConfigurationId, uint8 *pStatusCode);

/**
 * @brief restores how many DAQ lists a previously stored configuration held.
 * @details Design doc DD103 (docs/superpowers/specs/2026-09-10-xcp-daq-resume-design.md): the
 * restore-side mirror of ALLOC_DAQ (XCP part 2 - Protocol Layer Specification 1.1/1.6.4.3.1.2).
 * Under a DAQ_DYNAMIC build this raises Xcp_Internal.allocated_daq_count exactly as ALLOC_DAQ
 * does, bounded by the same configured pool. Under DAQ_STATIC the list count is fixed at
 * generation time, so this only validates that daqListCount agrees with it -- an integrator
 * restoring a configuration stored by a differently generated build finds out here rather than by
 * writing entries into lists that do not exist.
 * @param [in] daqListCount how many DAQ lists to make available for the calls below
 * @retval E_OK the count was accepted
 * @retval E_NOT_OK daqListCount exceeds the configured DAQ_DYNAMIC pool, or disagrees with a
 * DAQ_STATIC build's own fixed count; also once @ref Xcp_ResumeComplete has run or a master has
 * connected (design doc DD107) -- restoration is a start-up activity, not a mid-session one
 */
Std_ReturnType Xcp_RestoreDaqListCount(uint16 daqListCount);

/**
 * @brief restores how many ODTs one DAQ list had been allocated.
 * @details Design doc DD103: the restore-side mirror of ALLOC_ODT (XCP part 2 - Protocol Layer
 * Specification 1.1/1.6.4.3.1.3) and of @ref Xcp_GetDaqListOdtCount, which is what an integrator
 * implementing @ref Xcp_StoreDaqConfiguration read to learn this value.
 * @param [in] daqListNumber DAQ list number
 * @param [in] odtCount how many ODTs to make available for the calls below
 * @retval E_OK the count was accepted
 * @retval E_NOT_OK daqListNumber is out of range, odtCount exceeds the configured pool; also once
 * @ref Xcp_ResumeComplete has run or a master has connected (design doc DD107)
 */
Std_ReturnType Xcp_RestoreOdtCount(uint16 daqListNumber, uint8 odtCount);

/**
 * @brief restores how many entries one ODT of a DAQ list had been allocated.
 * @details Design doc DD103: the restore-side mirror of ALLOC_ODT_ENTRY (XCP part 2 - Protocol
 * Layer Specification 1.1/1.6.4.3.1.4) and of @ref Xcp_GetOdtEntryCount, which is what an
 * integrator implementing @ref Xcp_StoreDaqConfiguration read to learn this value.
 * @param [in] daqListNumber DAQ list number
 * @param [in] odtNumber ODT number, relative to daqListNumber
 * @param [in] entryCount how many ODT entries to make available for @ref Xcp_RestoreOdtEntry
 * @retval E_OK the count was accepted
 * @retval E_NOT_OK daqListNumber or odtNumber is out of range, entryCount exceeds the configured
 * pool; also once @ref Xcp_ResumeComplete has run or a master has connected (design doc DD107)
 */
Std_ReturnType Xcp_RestoreOdtEntryCount(uint16 daqListNumber, uint8 odtNumber, uint8 entryCount);

/**
 * @brief restores one ODT entry's configuration.
 * @details Design doc DD103: the restore-side mirror of WRITE_DAQ (XCP part 2 - Protocol Layer
 * Specification 1.1/1.6.4.1.1.2) and of @ref Xcp_GetOdtEntry, which is what an integrator
 * implementing @ref Xcp_StoreDaqConfiguration read to learn this entry's configuration.
 * @param [in] daqListNumber DAQ list number
 * @param [in] odtNumber ODT number, relative to daqListNumber
 * @param [in] odtEntryNumber ODT entry number, relative to odtNumber
 * @param [in] pEntry address, bitOffset, addressExtension and length to restore.
 * Xcp_OdtEntryType::number is not read -- the entry's number follows odtEntryNumber above, the
 * same asymmetry @ref Xcp_GetOdtEntry leaves on its own out parameter.
 * @retval E_OK pEntry was applied
 * @retval E_NOT_OK daqListNumber, odtNumber or odtEntryNumber is out of range; also once
 * @ref Xcp_ResumeComplete has run or a master has connected (design doc DD107)
 */
Std_ReturnType Xcp_RestoreOdtEntry(uint16 daqListNumber, uint8 odtNumber, uint8 odtEntryNumber,
                                   const Xcp_OdtEntryType *pEntry);

/**
 * @brief restores one DAQ list's mode, event channel, prescaler and priority.
 * @details Design doc DD103: the restore-side mirror of GET_DAQ_LIST_MODE (XCP part 2 - Protocol
 * Layer Specification 1.1/1.6.4.1.2.6), whose response layout mode is given in -- the layout
 * Xcp_DaqListRtType::mode itself stores (interface/Xcp_Types.h), NOT SET_DAQ_LIST_MODE's request
 * layout. RUNNING and RESUME bits of mode are ignored: @ref Xcp_ResumeComplete is the only thing
 * that may set either, so an integrator cannot half-start a list by calling this alone.
 * @param [in] daqListNumber DAQ list number
 * @param [in] mode SELECTED/DIRECTION/TIMESTAMP/PID_OFF bits, GET_DAQ_LIST_MODE response layout
 * @param [in] eventChannelNumber event channel to bind this list to
 * @param [in] prescaler transmission rate prescaler; 1 means no reduction
 * @param [in] priority DAQ list priority
 * @retval E_OK the mode was accepted
 * @retval E_NOT_OK daqListNumber is out of range; also once @ref Xcp_ResumeComplete has run or a
 * master has connected (design doc DD107)
 */
Std_ReturnType Xcp_RestoreDaqListMode(uint16 daqListNumber, uint8 mode, uint16 eventChannelNumber,
                                      uint8 prescaler, uint8 priority);

/**
 * @brief makes every list restored through the setters above live.
 * @details Design doc DD105: nothing @ref Xcp_RestoreDaqListCount, @ref Xcp_RestoreOdtCount,
 * @ref Xcp_RestoreOdtEntryCount, @ref Xcp_RestoreOdtEntry or @ref Xcp_RestoreDaqListMode wrote
 * takes effect before this call. An integrator whose non-volatile read fails halfway simply never
 * calls this, and the slave resumes nothing rather than transmitting a half-built configuration at
 * a real event channel.
 * @param [in] sessionConfigurationId the session configuration id stored alongside the
 * configuration being restored
 * @retval E_OK every restored list had at least one written ODT entry; sessionConfigurationId is
 * adopted and every restored list is marked RESUME and RUNNING (XCP part 2 - Protocol Layer
 * Specification 1.1/1.6.4.1.1.4)
 * @retval E_NOT_OK at least one restored list has no written ODT entry -- the same configuration
 * START_STOP_DAQ_LIST would answer ERR_DAQ_CONFIG for -- so resuming must not create by the back
 * door a state the front door would refuse to start; nothing is changed
 */
Std_ReturnType Xcp_ResumeComplete(uint16 sessionConfigurationId);

#define Xcp_STOP_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

#if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON)

/**
 * @brief Enters non-volatile memory programming mode.
 * @param [out] pStatusCode Result of the sequence, read only when this function returns E_OK: zero
 * for success, non-zero for a slave that cannot permit programming.
 * @retval E_OK: the sequence is finished (no matter if it was successfully terminated or not)
 * @retval E_NOT_OK: the sequence is not finished
 * @details Polled, exactly as @ref Xcp_StoreCalibrationDataToNonVolatileMemory is: called once
 * from the PROGRAM_START handler to start the work and then once per Xcp_MainFunction until it
 * reports completion. An implementation whose work is instantaneous returns E_OK from the first
 * call and the command is answered without ever deferring.
 * @note XCP part 2 - Protocol Layer Specification 1.1/1.6.5.1.1 permits implementation-specific
 * preconditions -- "slave device in a secure physical state, additional code downloaded" -- and
 * names ERR_GENERIC as the answer when they are unmet. A non-zero pStatusCode produces exactly
 * that.
 */
extern Std_ReturnType Xcp_ProgramStart(uint8 *pStatusCode);

/**
 * @brief Ends a non-volatile memory programming sequence.
 * @param [out] pStatusCode Result of the sequence, read only when this function returns E_OK: zero
 * for success, non-zero for failure.
 * @retval E_OK: the sequence is finished (no matter if it was successfully terminated or not)
 * @retval E_NOT_OK: the sequence is not finished
 * @details Copies @ref Xcp_StoreCalibrationDataToNonVolatileMemory's polled contract exactly, the
 * same one @ref Xcp_ProgramStart above copies: called once from the PROGRAM_RESET handler to start
 * the work and then once per Xcp_MainFunction until it reports completion. An implementation whose
 * work is instantaneous returns E_OK from the first call and the command is answered without ever
 * deferring.
 * @note XCP part 2 - Protocol Layer Specification 1.1/1.6.5.1.4 has the slave go to the
 * disconnected state, suggesting a hardware reset is "usually" performed there. AUTOSAR
 * SWS_Xcp_00856 overrides that for this module: disconnected state, but without forcing a device
 * reset. This module performs no reset itself -- an integrator wanting one performs it from within
 * this callback, which is the only place that knows what else is running on the ECU.
 */
extern Std_ReturnType Xcp_ProgramReset(uint8 *pStatusCode);

/**
 * @brief Prepares non-volatile memory programming by declaring a code download's target and size.
 * @param [in] address The current MTA (set by SET_MTA), which points to the volatile memory
 * location where the code about to be downloaded will be stored.
 * @param [in] codeSize The request's Codesize: the size of the code that will be downloaded,
 * expressed in BYTE, WORD or DWORD elements according to this slave's address granularity, NOT in
 * bytes unconditionally. XCP part 2 - Protocol Layer Specification 1.1/1.6.5.2.3 says so in as many
 * words -- "Codesize is expressed in BYTE, WORD or DWORD depending upon AG" -- and this module
 * passes the wire value through verbatim rather than converting it, so an integrator on a WORD or
 * DWORD granularity multiplies by the element size itself. AG is a configuration property
 * (`protocol_layer.address_granularity`), constant for the build, and is also what CONNECT reports
 * in COMM_MODE_BASIC bits 2:1.
 * @param [out] pStatusCode Result of the sequence, read only when this function returns E_OK: zero
 * for success, non-zero if the target memory area is not available.
 * @retval E_OK: the sequence is finished (no matter if it was successfully terminated or not)
 * @retval E_NOT_OK: the sequence is not finished
 * @details Polled, exactly as @ref Xcp_StoreCalibrationDataToNonVolatileMemory is: called once from
 * the PROGRAM_PREPARE handler to start the work and then once per Xcp_MainFunction until it
 * reports completion. An implementation whose work is instantaneous returns E_OK from the first
 * call and the command is answered without ever deferring. Unlike @ref Xcp_ProgramStart above,
 * this carries no dependency on the programming session's state: XCP part 2 - Protocol Layer
 * Specification 1.1/1.6.5.2.3 makes PROGRAM_PREPARE a precondition FOR programming -- the master
 * downloads code to volatile memory before PROGRAM_START -- so it legitimately precedes the
 * session, and this callback is reached the same way whether or not one is open.
 * @note 1.1/1.6.5.2.3: "The slave device has to make sure that the target memory area is available
 * and it is in a operational state which permits the download of code." A non-zero pStatusCode
 * answers ERR_GENERIC, exactly as it does for @ref Xcp_ProgramStart.
 */
extern Std_ReturnType Xcp_ProgramPrepare(void *address, uint16 codeSize, uint8 *pStatusCode);

/**
 * @brief Clears (erases) a part of non-volatile memory prior to reprogramming.
 * @param [in] address The current MTA (set by SET_MTA), which points to the start of the memory
 * sector to be cleared. XCP part 2 - Protocol Layer Specification 1.1/1.6.5.1.2: "The MTA points to
 * the start of a memory sector inside the slave. Memory sectors are described in the ASAM MCD 2MC
 * slave device description file."
 * @param [in] clearRange The request's own Clear Range: the length, in bytes, of the memory part to
 * be cleared. 1.1/1.6.5.1.2: "The Clear Range indicates the length of the memory part to be
 * cleared. The PROGRAM_CLEAR service clears a complete sector or multiple sectors at once." Always
 * a length here: this callback answers absolute access mode alone (request mode byte 0x00). Under
 * functional access mode (0x01) the same request field is a bit mask of memory areas instead, and
 * reaches @ref Xcp_ProgramClearFunctional, a separate callback, never this one (design doc DD84,
 * DD93) -- a request naming a mode neither callback is configured for is refused ERR_OUT_OF_RANGE
 * before either is ever called.
 * @param [out] pStatusCode Result of the sequence, read only when this function returns E_OK: zero
 * for success, non-zero for failure.
 * @retval E_OK: the sequence is finished (no matter if it was successfully terminated or not)
 * @retval E_NOT_OK: the sequence is not finished
 * @details Polled, exactly as @ref Xcp_StoreCalibrationDataToNonVolatileMemory is: called once from
 * the PROGRAM_CLEAR handler to start the work and then once per Xcp_MainFunction until it reports
 * completion. An implementation whose work is instantaneous returns E_OK from the first call and
 * the command is answered without ever deferring -- though erasing non-volatile memory is normally
 * the slowest operation this module asks an integrator to perform, which is why XCP part 2 -
 * Protocol Layer Specification 1.1/1.7.3.2.5 gives PROGRAM_CLEAR the longer t4 timeout where an
 * ordinary command gets t1, and why deferring is expected to be the common case rather than the
 * exception @ref Xcp_ProgramStart and @ref Xcp_ProgramPrepare above tend to be.
 * @note Unlike @ref Xcp_ProgramPrepare above, this callback is reachable only once a programming
 * session is open (1.1/1.6.5.1.1): a request arriving before PROGRAM_START has succeeded is refused
 * ERR_SEQUENCE by the handler and never reaches this callback at all.
 * @note A non-zero pStatusCode answers ERR_ACCESS_DENIED, unlike @ref Xcp_ProgramStart and
 * @ref Xcp_ProgramPrepare above, which both answer ERR_GENERIC. PROGRAM_CLEAR's own error table
 * (1.1/1.7.3.2.5) does not list ERR_GENERIC at all; ERR_ACCESS_DENIED is both one of the codes it
 * does list and, per the specification's own error-code definitions, the precise description of
 * memory this callback could not erase -- "the memory location is not accessible" -- where
 * ERR_GENERIC would only be the closest available label.
 */
extern Std_ReturnType Xcp_ProgramClear(void *address, uint32 clearRange, uint8 *pStatusCode);

/**
 * @brief Writes a block of data into non-volatile memory.
 * @param [in] address The current MTA (set by SET_MTA), which points to where the data is to be
 * written. XCP part 2 - Protocol Layer Specification 1.1/1.6.5.1.3: "The data block ... will be
 * copied into memory, starting at the MTA."
 * @param [in] pData The data to write, `length` bytes, taken directly from the request. Valid only
 * for the duration of THIS call: the polled contract below presents the same underlying buffer on
 * every subsequent call for the same operation, so an implementation that needs the bytes after
 * returning E_NOT_OK must copy them itself rather than retain this pointer -- retaining it would be
 * correct only by accident, since the module does not promise the pointer stays valid past the call
 * that handed it over.
 * @param [in] length Number of bytes pData holds.
 * @param [out] pStatusCode Result of the write, read only when this function returns E_OK: zero for
 * success, non-zero for failure.
 * @retval E_OK: the write is finished (no matter if it was successfully terminated or not)
 * @retval E_NOT_OK: the write is not finished
 * @details Polled, exactly as @ref Xcp_StoreCalibrationDataToNonVolatileMemory is: called once to
 * start the work -- from the PROGRAM or PROGRAM_MAX handler directly, or, for a master block mode
 * block spanning more than one frame, from the PROGRAM_NEXT frame that completes it, since
 * 1.1/1.6.5.1.3 has the slave acknowledge only that last frame -- and then once per Xcp_MainFunction
 * until it reports completion. An implementation whose work is instantaneous returns E_OK from the
 * first call and the command is answered without ever deferring.
 * @note XCP part 2 - Protocol Layer Specification 1.1/1.6.5.1.3: "The MTA will be post-incremented
 * by the number of data bytes" -- but only when this call succeeds. A failed write leaves the MTA
 * where the master left it, since 1.7.3.2.5 gives PROGRAM the pre-action SYNCH+SET_MTA, so a master
 * recovering from a failure re-points the MTA itself.
 * @note A non-zero pStatusCode answers ERR_ACCESS_DENIED, not ERR_GENERIC: neither PROGRAM's nor
 * PROGRAM_MAX's own 1.7.3.2.5 row lists ERR_GENERIC at all, and ERR_ACCESS_DENIED is both one of
 * the codes PROGRAM's row does list and, per the specification's own error-code definitions, the
 * precise description of memory this callback could not write to -- the same choice
 * @ref Xcp_ProgramClear above makes for a failed erase, generalised here to a failed write.
 * @note This callback answers ABSOLUTE access mode alone. Once a PROGRAM_FORMAT has announced
 * functional access (access method non-zero, 1.6.5.2.4), the identical three commands reach
 * @ref Xcp_ProgramWriteFunctional instead -- a separate callback taking a block sequence counter
 * where this one takes an address, since under that mode the MTA is not one (design doc DD84,
 * DD86). A given data transfer reaches exactly one of the two.
 */
extern Std_ReturnType Xcp_ProgramWrite(void *address, const uint8 *pData, uint16 length, uint8 *pStatusCode);

/**
 * @brief Checks whether non-volatile memory content is valid.
 * @param [in] verificationMode The request's own Mode byte. XCP part 2 - Protocol Layer
 * Specification 1.1/1.6.5.2.7 gives this slave no meaning of its own to enforce on it, so it is
 * passed through verbatim, for an integrator whose ASAM MCD-2 MC description defines what its own
 * values mean.
 * @param [in] verificationType The request's own Verification Type, a bit mask of the areas to
 * verify. 1.1/1.6.5.2.7 defines bit 0x0001 (calibration areas), 0x0002 (code areas) and 0x0004
 * (complete flash), reserves 0x0008..0x0080, and leaves 0x0100..0xFF00 user defined. A request
 * naming a reserved bit is refused ERR_OUT_OF_RANGE before this callback is ever reached -- the one
 * structural check 1.1/1.6.5.2.7 itself permits a slave to make -- so every value this callback
 * actually receives already has every reserved bit clear.
 * @param [in] verificationValue The request's own Verification Value, in the configured byte
 * order. 1.1/1.6.5.2.7 leaves its meaning to the slave and its ASAM MCD-2 MC description; passed
 * through verbatim, the same way verificationMode is.
 * @param [out] pStatusCode Result of the verification, read only when this function returns E_OK:
 * zero for success, non-zero for a verification that completed but did not pass.
 * @retval E_OK: the verification is finished (no matter if it passed or not)
 * @retval E_NOT_OK: the verification is not finished
 * @details Polled, exactly as @ref Xcp_ProgramClear is: called once from the PROGRAM_VERIFY handler
 * to start the work and then once per Xcp_MainFunction until it reports completion. An
 * implementation whose work is instantaneous returns E_OK from the first call and the command is
 * answered without ever deferring -- though checking newly programmed content against the rest of
 * flash is exactly the kind of long-running work this module's polled contract exists for, the same
 * reason @ref Xcp_ProgramClear tends to defer more often than @ref Xcp_ProgramStart or
 * @ref Xcp_ProgramPrepare do.
 * @note A non-zero pStatusCode answers ERR_VERIFY, XCP part 2 - Protocol Layer Specification
 * 1.7.3.2.5's own code for a verification that completed but did not pass -- unlike @ref
 * Xcp_ProgramClear and @ref Xcp_ProgramWrite above, which both answer ERR_ACCESS_DENIED for a
 * failure of their own, different kind.
 */
extern Std_ReturnType Xcp_ProgramVerify(uint8 verificationMode, uint16 verificationType, uint32 verificationValue, uint8 *pStatusCode);

/**
 * @brief Tells the integrator how the flash content about to be downloaded is encoded.
 * @param [in] compressionMethod The request's own compression method, 0x00 for uncompressed
 * (default) or an implementation-specific non-zero value. XCP part 2 - Protocol Layer Specification
 * 1.1/1.6.5.2.4 leaves the meaning of a non-zero value to the ASAM MCD-2 MC description; passed
 * through verbatim, only checked structurally (design doc DD89, below) before this is ever called.
 * @param [in] encryptionMethod The request's own encryption method, 0x00 for unencrypted (default)
 * or an implementation-specific non-zero value. Same rule as compressionMethod above.
 * @param [in] programmingMethod The request's own programming method, 0x00 for sequential (default)
 * or an implementation-specific non-zero value (e.g. non-sequential). Same rule as
 * compressionMethod above.
 * @param [in] accessMethod The request's own access method: 0x00 Absolute Access Mode (default,
 * the MTA is a physical address), 0x01 Functional Access Mode (the MTA is a block sequence
 * number), 0x80..0xFF user defined. Anything but 0x00 requires PGM_PROPERTIES' FUNCTIONAL_MODE bit
 * advertised, which is this build's own configuration to grant (design doc DD92): a build
 * configuring both functional callbacks -- @ref Xcp_ProgramClearFunctional and
 * @ref Xcp_ProgramWriteFunctional -- passes 0x01 and the user-defined range through to this
 * callback, and one configuring neither refuses them ERR_OUT_OF_RANGE before ever reaching here.
 * Accepting a non-zero value here is what routes every following data transfer of this stream to
 * @ref Xcp_ProgramWriteFunctional instead of @ref Xcp_ProgramWrite.
 * @param [out] pStatusCode Result of the request, read only when this function returns E_OK: zero
 * to accept the format, non-zero for a value this integrator cannot honour -- the only case that
 * matters in practice is a user-defined compression/encryption/programming method (0x80..0xFF)
 * whose meaning only the integrator's own ASAM MCD-2 MC description knows (design doc DD89).
 * @retval E_OK: the format has been judged, successfully or not -- read pStatusCode.
 * @retval E_NOT_OK: must not be returned. Unlike every other PGM callback in this header, this one
 * is synchronous by contract (design doc DD91): PROGRAM_FORMAT only sets four bytes, so there is no
 * polled path for it and Xcp_MainFunction never calls this a second time for the same request. A
 * return value other than E_OK is treated exactly like a non-zero pStatusCode -- refused, since
 * PROGRAM_FORMAT's own XCP part 2 - Protocol Layer Specification 1.7.3.2.5 row leaves no other
 * failure code for an integrator that could not honour a structurally-permitted request.
 * @details Called once, synchronously, from the PROGRAM_FORMAT handler -- never polled, unlike
 * every other callback this file declares for the PGM command group. The module's own structural
 * check (design doc DD89: a non-default value is accepted only if PGM_PROPERTIES advertises the
 * matching capability) runs first, so this is reached only for a request this build has already
 * promised to support; what remains for the integrator to judge is a user-defined value's own
 * specific meaning.
 */
extern Std_ReturnType Xcp_ProgramFormat(uint8 compressionMethod, uint8 encryptionMethod, uint8 programmingMethod, uint8 accessMethod, uint8 *pStatusCode);

/**
 * @brief Clears (erases) memory by AREA rather than by address: PROGRAM_CLEAR's functional access
 * mode.
 * @param [in] clearRange The request's own Clear Range, reinterpreted under functional access mode
 * (design doc DD84, DD93): no longer a length, but a bit mask of the memory areas to clear. XCP
 * part 2 - Protocol Layer Specification 1.1/1.6.5.1.2 (both revisions): "The MTA has no influence on
 * the clearing functionality" under this mode -- which is why, unlike @ref Xcp_ProgramClear, this
 * callback takes no address parameter at all; passing one would invent a parameter the protocol does
 * not carry. 0x00000001 all calibration data areas, 0x00000002 all code areas (the boot area is not
 * covered), 0x00000004 NVRAM areas, 0x00000100..0xFFFFFF00 user defined. 0x00000008..0x00000080 are
 * reserved and refused ERR_OUT_OF_RANGE before this callback is ever reached -- the one structural
 * check this command's own 1.7.3.2.5 row permits a slave to make.
 * @param [out] pStatusCode Result of the sequence, read only when this function returns E_OK: zero
 * for success, non-zero for failure.
 * @retval E_OK: the sequence is finished (no matter if it was successfully terminated or not)
 * @retval E_NOT_OK: the sequence is not finished
 * @details Polled, exactly as @ref Xcp_ProgramClear is: called once from the PROGRAM_CLEAR handler
 * to start the work and then once per Xcp_MainFunction until it reports completion. An
 * implementation whose work is instantaneous returns E_OK from the first call and the command is
 * answered without ever deferring.
 * @note Reachable only once both PROGRAM_START has succeeded (1.1/1.6.5.1.1, the same session gate
 * @ref Xcp_ProgramClear itself carries) and this build's own configuration offers this callback
 * (xcp_program_clear_functional_api_enable, config/xcp.schema.json); a mode 0x01 request otherwise
 * is refused ERR_OUT_OF_RANGE and never reaches here.
 * @note A non-zero pStatusCode answers ERR_ACCESS_DENIED, the same code and the same reasoning
 * @ref Xcp_ProgramClear's own note gives for a failed erase.
 * @note Independent of PROGRAM_FORMAT's own access method (design doc DD93): XCP part 2 - Protocol
 * Layer Specification 1.1/1.6.5.2.4 states outright that "it is possible to use different access
 * modes for clearing and programming", so a master may reach this callback while
 * Xcp_Internal.pgm_format.access_method still reads absolute access mode, or the reverse for
 * @ref Xcp_ProgramWrite.
 */
extern Std_ReturnType Xcp_ProgramClearFunctional(uint32 clearRange, uint8 *pStatusCode);

/**
 * @brief Writes a block of data into non-volatile memory without being told where: PROGRAM's
 * functional access mode.
 * @param [in] blockSequenceCounter This module's own count of the data transfer requests received
 * since the PROGRAM_FORMAT that opened this stream. XCP part 2 - Protocol Layer Specification
 * 1.1/1.6.5.1.3 (both revisions): "The MTA works as a Block Sequence Counter and it is counted
 * inside the master and the server. The Block Sequence Counter allows an improved error handling in
 * case a programming service fails during a sequence of multiple programming requests." Initialised
 * so that the first data transfer after PROGRAM_FORMAT carries 1, advanced by one per data transfer
 * request, and rolling over to 0x00 past its maximum -- so an integrator can compare it against the
 * master's own count rather than re-deriving it. Not a value the master transmits: it is counted
 * independently on both sides, which is what makes a divergence detectable at all (design doc
 * DD86). **Two words in that sentence are readings of an ambiguous specification rather than
 * settled facts -- what counts as one "data transfer request", and how wide "its maximum" is. Both
 * are spelled out in the last two notes below; read them before treating a disagreement with a
 * master's own count as a defect on either side.**
 * @param [in] pData The data to write, `length` bytes, taken directly from the request. The same
 * lifetime rule @ref Xcp_ProgramWrite's own pData carries applies here unchanged: valid for the
 * duration of THIS call only.
 * @param [in] length Number of bytes pData holds.
 * @param [out] pStatusCode Result of the write, read only when this function returns E_OK: zero for
 * success, non-zero for failure.
 * @retval E_OK: the write is finished (no matter if it was successfully terminated or not)
 * @retval E_NOT_OK: the write is not finished
 * @details Polled, exactly as @ref Xcp_ProgramWrite is, and reached from the same three commands
 * (PROGRAM, PROGRAM_MAX, and the PROGRAM_NEXT frame that completes a master block mode block) --
 * this is that callback's functional-access twin, not an addition beside it: a given data transfer
 * reaches exactly one of the two.
 * @note **No address parameter, and that is not an omission.** 1.1/1.6.5.1.3's Functional Access
 * mode paragraph says "The ECU software knows the start address for the new flash content
 * automatically. It depends on the PROGRAM_CLEAR command. The ECU expects the new flash content in
 * one data stream and the assignment is done by the ECU automatically." There is no address in the
 * protocol for this module to pass on, and the MTA is not one either under this mode -- it is the
 * counter above. Passing @ref Xcp_ProgramWrite's own `void *address` here would hand the integrator
 * a pointer the specification never defined (design doc DD84).
 * @note The MTA is left exactly where the master last set it, unlike @ref Xcp_ProgramWrite's own
 * post-increment: 1.6.5.1.3 states that post-increment under *Absolute Access mode* only, and this
 * mode's own paragraph replaces it with the Block Sequence Counter.
 * @note Reachable only once PROGRAM_FORMAT has been accepted with a non-default access method,
 * which in turn requires this build to advertise PGM_PROPERTIES' FUNCTIONAL_MODE bit -- i.e. to
 * configure BOTH this callback and @ref Xcp_ProgramClearFunctional (design doc DD92,
 * xcp_program_write_functional_api_enable and xcp_program_clear_functional_api_enable,
 * config/xcp.schema.json). Generation refuses a configuration offering one without the other, so
 * "advertised" and "accepted" cannot drift apart.
 * @note A non-zero pStatusCode answers ERR_ACCESS_DENIED, the same code and the same reasoning
 * @ref Xcp_ProgramWrite's own note gives for a failed write -- the two share one completion path.
 * @note **"Per data transfer request" counts every FRAME of a master block mode block, and that is
 * a reading of 1.6.5.1.3 rather than a settled fact.** A block spanning PROGRAM plus two
 * PROGRAM_NEXT frames reaches this callback ONCE, carrying 3 -- the third request's own count --
 * not 1. The reading rests on both operative sentences naming a request message as the trigger
 * ("incremented by 1 for each subsequent data transfer request", "rolls over and starts at 0x00
 * with the next data transfer request message") and on PROGRAM_NEXT being one of the three data
 * transfer requests. The defensible alternative, recorded because an integrator comparing this
 * value against a real master's own count is exactly who would meet it: the same paragraph says
 * the MTA IS this counter, and the MTA advances once per completed BLOCK (@ref Xcp_ProgramWrite's
 * own post-increment note above), so a per-block count could be argued from the field's name alone.
 * A master built on that alternative disagrees with this slave by the number of PROGRAM_NEXT frames
 * per block -- which looks like a counter divergence but is a specification ambiguity. Design doc
 * DD86 (docs/superpowers/specs/2026-09-08-xcp-pgm-sp4c-design.md) carries the full reasoning. A
 * zero-element PROGRAM ("the end of the memory segment is indicated, when the number of data
 * elements is 0") does NOT count: it transfers no data and never reaches this callback.
 * @note **The counter's WIDTH is not stated anywhere in either revision, and uint32 is a choice.**
 * 1.6.5.1.3 names the MTA -- 32-bit -- as the counter, which argues for 32 bits, but writes the
 * rollover value as `0x00`, which reads byte-sized. uint32 is taken because it is the only width
 * the specification actually mentions; a byte-wide counter would be a narrowing nothing in the text
 * requires. An integrator whose master rolls over at 0xFF rather than 0xFFFFFFFF is meeting this
 * ambiguity, not a defect -- read DD86 first.
 */
extern Std_ReturnType Xcp_ProgramWriteFunctional(uint32 blockSequenceCounter, const uint8 *pData, uint16 length, uint8 *pStatusCode);

#endif /* #if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON) */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global scheduled function declarations.                                                        */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GSFDECL
 * @{
 */

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/**
 * @brief the main function for scheduling the CAN TP.
 */
void Xcp_MainFunction(void);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/**
 * @brief Samples every running DAQ list bound to an event channel and queues the result.
 *
 * @details The integrator calls this from whatever context the event actually occurs in -- a
 * periodic task, an interrupt, an end-of-conversion -- because that context is the "generic
 * signal source that effectively determines the data transmission timing" of XCP part 2 -
 * Protocol Layer Specification 1.1/1.6.4.1.1.3. The module holds no clock and will never trigger
 * a channel on its own. The rate at which this is called should match the time cycle the
 * configuration declares for the channel, because that is what the slave reports to the master.
 *
 * @note Not an AUTOSAR service. SWS_Xcp R4.3.1 defines no way to trigger a DAQ event channel, so
 * this is a vendor extension of this module.
 *
 * @param [in] eventChannelNumber Index of the event channel, as configured. Out-of-range values
 * raise XCP_E_INVALID_EVENT_CHANNEL and sample nothing.
 */
void Xcp_TriggerEventChannel(uint16 eventChannelNumber);

#ifdef CFFI_ENABLE

/**
 * @brief Second, CFFI-only declaration of an internal function. The real one, with the
 * documentation, is in source/Xcp_Internal.h; this is not part of the module's interface.
 * @details test/conftest.py builds the CFFI cdef by preprocessing exactly this header
 * (CMakeLists.txt passes --header interface/Xcp.h), and interface/Xcp.h never includes
 * Xcp_Internal.h -- so a function declared only there cannot be reached from a test at all,
 * however the compiled sources export it. Xcp_DaqReadIdentificationField computes the payload
 * offset of a received stimulation frame, where an error of one, two or four bytes applies the
 * master's data to the wrong addresses and nothing in the protocol reports it, so it is worth
 * pinning directly (test/stim_decode_test.py) rather than only through its callers.
 * @note Deliberately not `extern`: CFFIHeader (test/conftest.py) rewrites every `extern` function
 * declaration it finds in this header into `extern "Python+C"` and wires it to a Python mock,
 * which is right for an integrator callback and would displace this module's own definition.
 * Xcp_Internal.h's copy is visible in every translation unit that defines or calls this
 * (Xcp_Internal.h includes this header), so the compiler rejects any disagreement between the two.
 */
Std_ReturnType Xcp_DaqReadIdentificationField(const PduInfoType *pPduInfo,
                                              PduIdType rxPduId,
                                              uint16 *pDaqListNumber,
                                              uint8 *pOdtNumber,
                                              uint8 *pOffset);

#endif /* #ifdef CFFI_ENABLE */

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/** @} */

#ifdef __cplusplus
};

#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_H */
