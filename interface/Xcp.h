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
 * number), 0x80..0xFF user defined. This slave never passes anything but 0x00 here today: 0x01 and
 * the user-defined range both require PGM_PROPERTIES' FUNCTIONAL_MODE bit advertised, which is
 * this build's own configuration to grant (design doc DD92) and none does yet.
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
