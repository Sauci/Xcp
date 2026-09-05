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
