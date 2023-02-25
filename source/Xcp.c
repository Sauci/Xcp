/**
 * @file Xcp.c
 * @author
 * @date
 *
 * @defgroup XCP_C implementation
 * @ingroup XCP
 *
 * @defgroup XCP_C_LDEF local definitions
 * @ingroup XCP_C
 * @defgroup XCP_C_LTDEF local data type definitions
 * @ingroup XCP_C
 * @defgroup XCP_C_LMDEF local macros
 * @ingroup XCP_C
 * @defgroup XCP_C_LFDECL local function declarations
 * @ingroup XCP_C
 * @defgroup XCP_C_LCDEF local constant definitions
 * @ingroup XCP_C
 * @defgroup XCP_C_LVDEF local variable definitions
 * @ingroup XCP_C
 * @defgroup XCP_C_GCDEF global constant definitions
 * @ingroup XCP_C
 * @defgroup XCP_C_GVDEF global variable definitions
 * @ingroup XCP_C
 * @defgroup XCP_C_GFDEF global function definitions
 * @ingroup XCP_C
 * @defgroup XCP_C_GSFDEF global scheduled function definitions
 * @ingroup XCP_C
 * @defgroup XCP_C_GCFDEF global callback function definitions
 * @ingroup XCP_C
 * @defgroup XCP_C_LFDEF local function definitions
 * @ingroup XCP_C
 */

/*------------------------------------------------------------------------------------------------*/
/* included files (#include).                                                                     */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C
 * @{
 */

#ifdef __cplusplus

extern "C" {

#endif /* ifdef __cplusplus */

#ifndef XCP_H

#include "Xcp.h"

#endif /* #ifndef XCP_H */

#ifndef XCP_RT_H

#include "Xcp_Rt.h"

#endif /* #ifndef XCP_RT_H */

#ifndef XCP_TYPES_H
#include "Xcp_Types.h"
#endif /* #ifndef XCP_TYPES_H */

#ifndef CANIF_H
#include "CanIf.h"
#endif /* #ifndef CANIF_H */

#ifndef XCPONCAN_CBK_H
#include "XcpOnCan_Cbk.h"
#endif /* #ifndef XCPONCAN_CBK_H */

#ifndef COMSTACK_TYPES_H
#include "ComStack_Types.h"
#endif /* #ifndef COMSTACK_TYPES_H */

#if (XCP_DEV_ERROR_DETECT == STD_ON)

#ifndef DET_H
#include "Det.h"
#endif /* #ifndef DET_H */

#endif /* #if (XCP_DEV_ERROR_DETECT == STD_ON) */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* local definitions (#define).                                                                   */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_LDEF
 * @{
 */

#define XCP_CTO_INFO_ENABLED_MASK (0x01u << 0x07u)
#define XCP_CTO_INFO_IS_CTO_MASK (0x01u << 0x06u)
#define XCP_CTO_INFO_PROTECTED_MASK (0x01u << 0x05u)
#define XCP_CTO_INFO_MIN_REQUEST_SIZE_MASK (0b1111u)

#define XCP_PROTOCOL_LAYER_VERSION (0x01u)
#define XCP_TRANSPORT_LAYER_VERSION (0x01u)

#define XCP_PID_RESPONSE (0xFFu)
#define XCP_PID_ERROR (0xFEu)
#define XCP_PID_EVENT (0xFDu)

#define XCP_EVENT_STORE_CAL (0x03u)

#define XCP_PID_CMD_PROGRAM_VERIFY (0xC8u)
#define XCP_PID_CMD_PROGRAM_MAX (0xC9u)
#define XCP_PID_CMD_PROGRAM_NEXT (0xCAu)
#define XCP_PID_CMD_PROGRAM_FORMAT (0xCBu)
#define XCP_PID_CMD_PROGRAM_PREPARE (0xCCu)
#define XCP_PID_CMD_GET_SECTOR_INFO (0xCDu)
#define XCP_PID_CMD_GET_PGM_PROCESSOR_INFO (0xCEu)
#define XCP_PID_CMD_PROGRAM_RESET (0xCFu)
#define XCP_PID_CMD_PROGRAM (0xD0u)
#define XCP_PID_CMD_PROGRAM_CLEAR (0xD1u)
#define XCP_PID_CMD_PROGRAM_START (0xD2u)
#define XCP_PID_CMD_ALLOC_ODT_ENTRY (0xD3u)
#define XCP_PID_CMD_ALLOC_ODT (0xD4u)
#define XCP_PID_CMD_ALLOC_DAQ (0xD5u)
#define XCP_PID_CMD_FREE_DAQ (0xD6u)
#define XCP_PID_CMD_GET_DAQ_EVENT_INFO (0xD7u)
#define XCP_PID_CMD_GET_DAQ_LIST_INFO (0xD8u)
#define XCP_PID_CMD_GET_DAQ_RESOLUTION_INFO (0xD9u)
#define XCP_PID_CMD_GET_DAQ_PROCESSOR_INFO (0xDAu)
#define XCP_PID_CMD_READ_DAQ (0xDBu)
#define XCP_PID_CMD_GET_DAQ_CLOCK (0xDCu)
#define XCP_PID_CMD_START_STOP_SYNCH (0xDDu)
#define XCP_PID_CMD_START_STOP_DAQ_LIST (0xDEu)
#define XCP_PID_CMD_GET_DAQ_LIST_MODE (0xDFu)
#define XCP_PID_CMD_SET_DAQ_LIST_MODE (0xE0u)
#define XCP_PID_CMD_WRITE_DAQ (0xE1u)
#define XCP_PID_CMD_SET_DAQ_PTR (0xE2u)
#define XCP_PID_CMD_CLEAR_DAQ_LIST (0xE3u)
#define XCP_PID_CMD_COPY_CAL_PAGE (0xE4u)
#define XCP_PID_CMD_GET_SEGMENT_MODE (0xE5u)
#define XCP_PID_CMD_SET_SEGMENT_MODE (0xE6u)
#define XCP_PID_CMD_GET_PAGE_INFO (0xE7u)
#define XCP_PID_CMD_GET_SEGMENT_INFO (0xE8u)
#define XCP_PID_CMD_GET_PAG_PROCESSOR_INFO (0xE9u)
#define XCP_PID_CMD_GET_CAL_PAGE (0xEAu)
#define XCP_PID_CMD_SET_CAL_PAGE (0xEBu)
#define XCP_PID_CMD_MODIFY_BITS (0xECu)
#define XCP_PID_CMD_SHORT_DOWNLOAD (0xEDu)
#define XCP_PID_CMD_DOWNLOAD_MAX (0xEEu)
#define XCP_PID_CMD_DOWNLOAD_NEXT (0xEFu)
#define XCP_PID_CMD_DOWNLOAD (0xF0u)
#define XCP_PID_CMD_USER_CMD (0xF1u)
#define XCP_PID_CMD_TRANSPORT_LAYER_CMD (0xF2u)
#define XCP_PID_CMD_BUILD_CHECKSUM (0xF3u)
#define XCP_PID_CMD_SHORT_UPLOAD (0xF4u)
#define XCP_PID_CMD_UPLOAD (0xF5u)
#define XCP_PID_CMD_SET_MTA (0xF6u)
#define XCP_PID_CMD_UNLOCK (0xF7u)
#define XCP_PID_CMD_GET_SEED (0xF8u)
#define XCP_PID_CMD_SET_REQUEST (0xF9u)
#define XCP_PID_CMD_GET_ID (0xFAu)
#define XCP_PID_CMD_GET_COMM_MOD_INFO (0xFBu)
#define XCP_PID_CMD_SYNCH (0xFCu)
#define XCP_PID_CMD_GET_STATUS (0xFDu)
#define XCP_PID_CMD_DISCONNECT (0xFEu)
#define XCP_PID_CMD_CONNECT (0xFFu)

#define XCP_CONNECT_MODE_NORMAL (0x00u)
#define XCP_CONNECT_MODE_USER_DEFINED (0x01u)

#define XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE (0x00u)
#define XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG (0x01u)
#define XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ (0x01u << 0x02u)
#define XCP_RESOURCE_PROTECTION_STATUS_MASK_STIM (0x01u << 0x03u)
#define XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM (0x01u << 0x04u)

#define XCP_SESSION_STATUS_MASK_STORE_CAL_REQ (0x01u)
#define XCP_SESSION_STATUS_MASK_STORE_DAQ_REQ (0x01u << 0x02u)
#define XCP_SESSION_STATUS_MASK_CLEAR_DAQ_REQ (0x01u << 0x03u)

#define XCP_INTERNAL_ERR_CMD_SYNCH (0x00000001u << 0x01u)
#define XCP_INTERNAL_ERR_CMD_BUSY (0x00000001u << 0x02u)
#define XCP_INTERNAL_ERR_DAQ_ACTIVE (0x00000001u << 0x03u)
#define XCP_INTERNAL_ERR_PGM_ACTIVE (0x00000001u << 0x04u)
#define XCP_INTERNAL_ERR_CMD_UNKNOWN (0x00000001u << 0x05u)
#define XCP_INTERNAL_ERR_CMD_SYNTAX (0x00000001u << 0x06u)
#define XCP_INTERNAL_ERR_OUT_OF_RANGE (0x00000001u << 0x07u)
#define XCP_INTERNAL_ERR_WRITE_PROTECTED (0x00000001u << 0x08u)
#define XCP_INTERNAL_ERR_ACCESS_DENIED (0x00000001u << 0x09u)
#define XCP_INTERNAL_ERR_ACCESS_LOCKED (0x00000001u << 0x0Au)
#define XCP_INTERNAL_ERR_PAGE_NOT_VALID (0x00000001u << 0x0Bu)
#define XCP_INTERNAL_ERR_MODE_NOT_VALID (0x00000001u << 0x0Cu)
#define XCP_INTERNAL_ERR_SEGMENT_NOT_VALID (0x00000001u << 0x0Du)
#define XCP_INTERNAL_ERR_SEQUENCE (0x00000001u << 0x0Eu)
#define XCP_INTERNAL_ERR_DAQ_CONFIG (0x00000001u << 0x0Fu)
#define XCP_INTERNAL_ERR_MEMORY_OVERFLOW (0x00000001u << 0x10u)
#define XCP_INTERNAL_ERR_GENERIC (0x00000001u << 0x11u)
#define XCP_INTERNAL_ERR_VERIFY (0x00000001u << 0x12u)

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* local data type definitions (typedef, struct).                                                 */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_LTDEF
 * @{
 */

typedef enum {
    /**
     * @brief The connection state is disconnected. No valid CONNECT command has been received from
     * the master.
     *
     * @note This enumerated value is explicitly set to 0, as it might be stored in the cleared
     * memory section, and thus shall default to 0.
     */
    XCP_CONNECTION_STATE_DISCONNECTED = 0x00u,
    XCP_CONNECTION_STATE_CONNECTED,
    XCP_CONNECTION_STATE_RESUME
} Xcp_ConnectionState;

typedef struct {
    uint8 connect_mode;
    Xcp_ConnectionState connection_status;
    uint8 session_status;
    uint8 protection_status;
    uint8 requested_protected_resource;
    uint8 last_pid;

    /**
         * @brief Flag indicating which transmission type is in progress (if any). It is used to call CanIf_Transmit each time the
         * CanIf_TxConfirmation callback is called without success.
     */
    enum {
        ONGOING_TRANSMIT_TYPE_NONE,
        ONGOING_TRANSMIT_TYPE_CTO,
        ONGOING_TRANSMIT_TYPE_EVENT
    } ongoing_transmit_type;
    struct {
        /**
         * @brief Flag indicating if a CTO response is pending. This flag is set whenever a CTO request is received, and a response to this request is
         * expected.
         *
         * This flag is set in Xcp_CanIfRxIndication (after the processing of the request), and cleared in CanIf_TxConfirmation, as soon as the latter
         * callback succeeds, indicating that the response has properly been sent on the CAN.
         */
        boolean successful_transmission_pending;
        PduInfoType pdu_info;
        uint8 _packet[0x100u]; /* MAX_CTO is in range 8 to 255 */
    } cto_response;
    struct {
        boolean successful_transmission_pending;
        PduInfoType pdu_info;
        uint8 _packet[0x100u]; /* MAX_CTO is in range 8 to 255 */
    } event;
    struct {
        uint8 buffer[0x100u];
        uint16 total_length;
        uint16 current_index;
    } seed;
    struct {
        uint8 buffer[0x100u];
        uint16 total_length;
        uint16 current_index;
    } key_master;
    struct {
        uint8 buffer[0x100u];
        uint16 total_length;
        uint16 current_index;
    } key_slave;
    struct {
        void *address;
        uint8 extension;
    } memory_transfer;
    struct {
        uint8 requested_elements;
        uint8 frame_elements;
    } block_transfer;
    uint8 internal_buffer[0x08u];
} Xcp_InternalType;

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* local macros definitions (#define, inline).                                                    */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_LMDEF
 * @{
 */

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

LOCAL_INLINE void Xcp_ReportError(uint8 instanceId, uint8 apiId, uint8 errorId)
{
#if (XCP_DEV_ERROR_DETECT == STD_ON)

    (void)Det_ReportError(XCP_MODULE_ID, instanceId, apiId, errorId);

#else

    (void)instanceId;
    (void)apiId;
    (void)errorId;

#endif /* #if (XCP_DEV_ERROR_DETECT == STD_ON) */
}

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* local function declarations (static).                                                          */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_LFDECL
 * @{
 */

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqAllocOdtEntry(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqAllocOdt(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqAllocDaq(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqFreeDaq(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqGetDaqEventInfo(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqGetDaqListInfo(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqGetDaqResolutionInfo(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqGetDaqProcessorInfo(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqReadDaq(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqGetDaqClock(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqStartStopSynch(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqStartStopDaqList(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqGetDaqListMode(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqSetDaqListMode(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqWriteDaq(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqSetDaqPtr(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdDaqClearDaqList(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTODaqStimPacket(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTODaqPacket(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdStdUserCmd(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdStdTransportLayerCmd(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdStdBuildChecksum(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdStdShortUpload(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdStdUpload(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdStdSetMta(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdStdUnlock(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdStdGetSeed(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdStdSetRequest(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdStdGetId(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_DTOCmdStdGetCommModeInfo(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_CTOCmdStdSynch(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_CTOCmdStdGetStatus(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"


#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_CTOCmdStdDisconnect(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_CTOCmdStdConnect(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void *Xcp_BuildChecksum11(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void *Xcp_BuildChecksum12(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void *Xcp_BuildChecksum14(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void *Xcp_BuildChecksum22(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void *Xcp_BuildChecksum24(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void *Xcp_BuildChecksum44(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void *Xcp_BuildChecksumCRC16(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void *Xcp_BuildChecksumCRC16CITT(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void *Xcp_BuildChecksumCRC32(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void Xcp_CopyFromU16WithOrder(const uint16 src, uint8 *pDest, Xcp_ByteOrderType endianness);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void Xcp_CopyFromU32WithOrder(const uint32 src, uint8 *pDest, Xcp_ByteOrderType endianness);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void Xcp_CopyToU16WithOrder(const uint8 *pSrc, uint16 *pDest, Xcp_ByteOrderType endianness);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void Xcp_CopyToU32WithOrder(const uint8 *pSrc, uint32 *pDest, Xcp_ByteOrderType endianness);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void Xcp_EventQueueInit(Xcp_EventQueueType *pEventQueue);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static Std_ReturnType Xcp_EventQueuePush(Xcp_EventQueueType *pEventQueue, uint8 packetID, uint8 eventCode, const uint8 *pUserData, uint32 userDataSize);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static Std_ReturnType Xcp_EventQueueGet(Xcp_EventQueueType *pEventQueue, uint8 *pPacketID, uint8 *pEventCode);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static Std_ReturnType Xcp_EventQueuePop(Xcp_EventQueueType *pEventQueue);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void Xcp_FinalizeResPacket(const PduLengthType startIndex, PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void Xcp_FillErrorPacket(const uint8 errorCode, PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_ElementSizeForAddressGranularity(Xcp_AddressGranularityType ag);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static boolean Xcp_BlockTransferIsActive();

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static Std_ReturnType Xcp_BlockTransferInitialize(uint8 numberOfElements);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void Xcp_BlockTransferAcknowledgeFrame();

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static Std_ReturnType Xcp_BlockTransferPrepareNextFrame();

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static uint8 Xcp_GetProtectionStatus(void);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void Xcp_SetProtectionStatus(void);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static void Xcp_ClearProtectionStatus(void);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

static Std_ReturnType Xcp_CheckMasterSlaveKeyMatch(uint16 slaveKeyLength, const uint8 *pSlaveKey, uint16 masterKeyLength, const uint8 *pMasterKey);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* local constant definitions (static const).                                                     */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_LCDEF
 * @{
 */

#define Xcp_START_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

static uint8 (* const Xcp_PIDTable[0x100u])(PduIdType rxPduId, const PduInfoType *pPduInfo) = {
    Xcp_DTODaqStimPacket, /* 0x00 */
    Xcp_DTODaqStimPacket, /* 0x01 */
    Xcp_DTODaqStimPacket, /* 0x02 */
    Xcp_DTODaqStimPacket, /* 0x03 */
    Xcp_DTODaqStimPacket, /* 0x04 */
    Xcp_DTODaqStimPacket, /* 0x05 */
    Xcp_DTODaqStimPacket, /* 0x06 */
    Xcp_DTODaqStimPacket, /* 0x07 */
    Xcp_DTODaqStimPacket, /* 0x08 */
    Xcp_DTODaqStimPacket, /* 0x09 */
    Xcp_DTODaqStimPacket, /* 0x0A */
    Xcp_DTODaqStimPacket, /* 0x0B */
    Xcp_DTODaqStimPacket, /* 0x0C */
    Xcp_DTODaqStimPacket, /* 0x0D */
    Xcp_DTODaqStimPacket, /* 0x0E */
    Xcp_DTODaqStimPacket, /* 0x0F */
    Xcp_DTODaqStimPacket, /* 0x10 */
    Xcp_DTODaqStimPacket, /* 0x11 */
    Xcp_DTODaqStimPacket, /* 0x12 */
    Xcp_DTODaqStimPacket, /* 0x13 */
    Xcp_DTODaqStimPacket, /* 0x14 */
    Xcp_DTODaqStimPacket, /* 0x15 */
    Xcp_DTODaqStimPacket, /* 0x16 */
    Xcp_DTODaqStimPacket, /* 0x17 */
    Xcp_DTODaqStimPacket, /* 0x18 */
    Xcp_DTODaqStimPacket, /* 0x19 */
    Xcp_DTODaqStimPacket, /* 0x1A */
    Xcp_DTODaqStimPacket, /* 0x1B */
    Xcp_DTODaqStimPacket, /* 0x1C */
    Xcp_DTODaqStimPacket, /* 0x1D */
    Xcp_DTODaqStimPacket, /* 0x1E */
    Xcp_DTODaqStimPacket, /* 0x1F */
    Xcp_DTODaqStimPacket, /* 0x20 */
    Xcp_DTODaqStimPacket, /* 0x21 */
    Xcp_DTODaqStimPacket, /* 0x22 */
    Xcp_DTODaqStimPacket, /* 0x23 */
    Xcp_DTODaqStimPacket, /* 0x24 */
    Xcp_DTODaqStimPacket, /* 0x25 */
    Xcp_DTODaqStimPacket, /* 0x26 */
    Xcp_DTODaqStimPacket, /* 0x27 */
    Xcp_DTODaqStimPacket, /* 0x28 */
    Xcp_DTODaqStimPacket, /* 0x29 */
    Xcp_DTODaqStimPacket, /* 0x2A */
    Xcp_DTODaqStimPacket, /* 0x2B */
    Xcp_DTODaqStimPacket, /* 0x2C */
    Xcp_DTODaqStimPacket, /* 0x2D */
    Xcp_DTODaqStimPacket, /* 0x2E */
    Xcp_DTODaqStimPacket, /* 0x2F */
    Xcp_DTODaqStimPacket, /* 0x30 */
    Xcp_DTODaqStimPacket, /* 0x31 */
    Xcp_DTODaqStimPacket, /* 0x32 */
    Xcp_DTODaqStimPacket, /* 0x33 */
    Xcp_DTODaqStimPacket, /* 0x34 */
    Xcp_DTODaqStimPacket, /* 0x35 */
    Xcp_DTODaqStimPacket, /* 0x36 */
    Xcp_DTODaqStimPacket, /* 0x37 */
    Xcp_DTODaqStimPacket, /* 0x38 */
    Xcp_DTODaqStimPacket, /* 0x39 */
    Xcp_DTODaqStimPacket, /* 0x3A */
    Xcp_DTODaqStimPacket, /* 0x3B */
    Xcp_DTODaqStimPacket, /* 0x3C */
    Xcp_DTODaqStimPacket, /* 0x3D */
    Xcp_DTODaqStimPacket, /* 0x3E */
    Xcp_DTODaqStimPacket, /* 0x3F */
    Xcp_DTODaqStimPacket, /* 0x40 */
    Xcp_DTODaqStimPacket, /* 0x41 */
    Xcp_DTODaqStimPacket, /* 0x42 */
    Xcp_DTODaqStimPacket, /* 0x43 */
    Xcp_DTODaqStimPacket, /* 0x44 */
    Xcp_DTODaqStimPacket, /* 0x45 */
    Xcp_DTODaqStimPacket, /* 0x46 */
    Xcp_DTODaqStimPacket, /* 0x47 */
    Xcp_DTODaqStimPacket, /* 0x48 */
    Xcp_DTODaqStimPacket, /* 0x49 */
    Xcp_DTODaqStimPacket, /* 0x4A */
    Xcp_DTODaqStimPacket, /* 0x4B */
    Xcp_DTODaqStimPacket, /* 0x4C */
    Xcp_DTODaqStimPacket, /* 0x4D */
    Xcp_DTODaqStimPacket, /* 0x4E */
    Xcp_DTODaqStimPacket, /* 0x4F */
    Xcp_DTODaqStimPacket, /* 0x50 */
    Xcp_DTODaqStimPacket, /* 0x51 */
    Xcp_DTODaqStimPacket, /* 0x52 */
    Xcp_DTODaqStimPacket, /* 0x53 */
    Xcp_DTODaqStimPacket, /* 0x54 */
    Xcp_DTODaqStimPacket, /* 0x55 */
    Xcp_DTODaqStimPacket, /* 0x56 */
    Xcp_DTODaqStimPacket, /* 0x57 */
    Xcp_DTODaqStimPacket, /* 0x58 */
    Xcp_DTODaqStimPacket, /* 0x59 */
    Xcp_DTODaqStimPacket, /* 0x5A */
    Xcp_DTODaqStimPacket, /* 0x5B */
    Xcp_DTODaqStimPacket, /* 0x5C */
    Xcp_DTODaqStimPacket, /* 0x5D */
    Xcp_DTODaqStimPacket, /* 0x5E */
    Xcp_DTODaqStimPacket, /* 0x5F */
    Xcp_DTODaqStimPacket, /* 0x60 */
    Xcp_DTODaqStimPacket, /* 0x61 */
    Xcp_DTODaqStimPacket, /* 0x62 */
    Xcp_DTODaqStimPacket, /* 0x63 */
    Xcp_DTODaqStimPacket, /* 0x64 */
    Xcp_DTODaqStimPacket, /* 0x65 */
    Xcp_DTODaqStimPacket, /* 0x66 */
    Xcp_DTODaqStimPacket, /* 0x67 */
    Xcp_DTODaqStimPacket, /* 0x68 */
    Xcp_DTODaqStimPacket, /* 0x69 */
    Xcp_DTODaqStimPacket, /* 0x6A */
    Xcp_DTODaqStimPacket, /* 0x6B */
    Xcp_DTODaqStimPacket, /* 0x6C */
    Xcp_DTODaqStimPacket, /* 0x6D */
    Xcp_DTODaqStimPacket, /* 0x6E */
    Xcp_DTODaqStimPacket, /* 0x6F */
    Xcp_DTODaqStimPacket, /* 0x70 */
    Xcp_DTODaqStimPacket, /* 0x71 */
    Xcp_DTODaqStimPacket, /* 0x72 */
    Xcp_DTODaqStimPacket, /* 0x73 */
    Xcp_DTODaqStimPacket, /* 0x74 */
    Xcp_DTODaqStimPacket, /* 0x75 */
    Xcp_DTODaqStimPacket, /* 0x76 */
    Xcp_DTODaqStimPacket, /* 0x77 */
    Xcp_DTODaqStimPacket, /* 0x78 */
    Xcp_DTODaqStimPacket, /* 0x79 */
    Xcp_DTODaqStimPacket, /* 0x7A */
    Xcp_DTODaqStimPacket, /* 0x7B */
    Xcp_DTODaqStimPacket, /* 0x7C */
    Xcp_DTODaqStimPacket, /* 0x7D */
    Xcp_DTODaqStimPacket, /* 0x7E */
    Xcp_DTODaqStimPacket, /* 0x7F */
    Xcp_DTODaqStimPacket, /* 0x80 */
    Xcp_DTODaqStimPacket, /* 0x81 */
    Xcp_DTODaqStimPacket, /* 0x82 */
    Xcp_DTODaqStimPacket, /* 0x83 */
    Xcp_DTODaqStimPacket, /* 0x84 */
    Xcp_DTODaqStimPacket, /* 0x85 */
    Xcp_DTODaqStimPacket, /* 0x86 */
    Xcp_DTODaqStimPacket, /* 0x87 */
    Xcp_DTODaqStimPacket, /* 0x88 */
    Xcp_DTODaqStimPacket, /* 0x89 */
    Xcp_DTODaqStimPacket, /* 0x8A */
    Xcp_DTODaqStimPacket, /* 0x8B */
    Xcp_DTODaqStimPacket, /* 0x8C */
    Xcp_DTODaqStimPacket, /* 0x8D */
    Xcp_DTODaqStimPacket, /* 0x8E */
    Xcp_DTODaqStimPacket, /* 0x8F */
    Xcp_DTODaqStimPacket, /* 0x90 */
    Xcp_DTODaqStimPacket, /* 0x91 */
    Xcp_DTODaqStimPacket, /* 0x92 */
    Xcp_DTODaqStimPacket, /* 0x93 */
    Xcp_DTODaqStimPacket, /* 0x94 */
    Xcp_DTODaqStimPacket, /* 0x95 */
    Xcp_DTODaqStimPacket, /* 0x96 */
    Xcp_DTODaqStimPacket, /* 0x97 */
    Xcp_DTODaqStimPacket, /* 0x98 */
    Xcp_DTODaqStimPacket, /* 0x99 */
    Xcp_DTODaqStimPacket, /* 0x9A */
    Xcp_DTODaqStimPacket, /* 0x9B */
    Xcp_DTODaqStimPacket, /* 0x9C */
    Xcp_DTODaqStimPacket, /* 0x9D */
    Xcp_DTODaqStimPacket, /* 0x9E */
    Xcp_DTODaqStimPacket, /* 0x9F */
    Xcp_DTODaqStimPacket, /* 0xA0 */
    Xcp_DTODaqStimPacket, /* 0xA1 */
    Xcp_DTODaqStimPacket, /* 0xA2 */
    Xcp_DTODaqStimPacket, /* 0xA3 */
    Xcp_DTODaqStimPacket, /* 0xA4 */
    Xcp_DTODaqStimPacket, /* 0xA5 */
    Xcp_DTODaqStimPacket, /* 0xA6 */
    Xcp_DTODaqStimPacket, /* 0xA7 */
    Xcp_DTODaqStimPacket, /* 0xA8 */
    Xcp_DTODaqStimPacket, /* 0xA9 */
    Xcp_DTODaqStimPacket, /* 0xAA */
    Xcp_DTODaqStimPacket, /* 0xAB */
    Xcp_DTODaqStimPacket, /* 0xAC */
    Xcp_DTODaqStimPacket, /* 0xAD */
    Xcp_DTODaqStimPacket, /* 0xAE */
    Xcp_DTODaqStimPacket, /* 0xAF */
    Xcp_DTODaqStimPacket, /* 0xB0 */
    Xcp_DTODaqStimPacket, /* 0xB1 */
    Xcp_DTODaqStimPacket, /* 0xB2 */
    Xcp_DTODaqStimPacket, /* 0xB3 */
    Xcp_DTODaqStimPacket, /* 0xB4 */
    Xcp_DTODaqStimPacket, /* 0xB5 */
    Xcp_DTODaqStimPacket, /* 0xB6 */
    Xcp_DTODaqStimPacket, /* 0xB7 */
    Xcp_DTODaqStimPacket, /* 0xB8 */
    Xcp_DTODaqStimPacket, /* 0xB9 */
    Xcp_DTODaqStimPacket, /* 0xBA */
    Xcp_DTODaqStimPacket, /* 0xBB */
    Xcp_DTODaqStimPacket, /* 0xBC */
    Xcp_DTODaqStimPacket, /* 0xBD */
    Xcp_DTODaqStimPacket, /* 0xBE */
    Xcp_DTODaqStimPacket, /* 0xBF */
    Xcp_DTODaqPacket, /* 0xC0 */
    Xcp_DTODaqPacket, /* 0xC1 */
    Xcp_DTODaqPacket, /* 0xC2 */
    Xcp_DTODaqPacket, /* 0xC3 */
    Xcp_DTODaqPacket, /* 0xC4 */
    Xcp_DTODaqPacket, /* 0xC5 */
    Xcp_DTODaqPacket, /* 0xC6 */
    Xcp_DTODaqPacket, /* 0xC7 */
    Xcp_DTODaqPacket, /* 0xC8 */
    Xcp_DTODaqPacket, /* 0xC9 */
    Xcp_DTODaqPacket, /* 0xCA */
    Xcp_DTODaqPacket, /* 0xCB */
    Xcp_DTODaqPacket, /* 0xCC */
    Xcp_DTODaqPacket, /* 0xCD */
    Xcp_DTODaqPacket, /* 0xCE */
    Xcp_DTODaqPacket, /* 0xCF */
    Xcp_DTODaqPacket, /* 0xD0 */
    Xcp_DTODaqPacket, /* 0xD1 */
    Xcp_DTODaqPacket, /* 0xD2 */
    Xcp_DTOCmdDaqAllocOdtEntry, /* 0xD3, optional */
    Xcp_DTOCmdDaqAllocOdt, /* 0xD4, optional */
    Xcp_DTOCmdDaqAllocDaq, /* 0xD5, optional */
    Xcp_DTOCmdDaqFreeDaq, /* 0xD6, optional */
    Xcp_DTOCmdDaqGetDaqEventInfo, /* 0xD7, optional */
    Xcp_DTOCmdDaqGetDaqListInfo, /* 0xD8, optional */
    Xcp_DTOCmdDaqGetDaqResolutionInfo, /* 0xD9, optional */
    Xcp_DTOCmdDaqGetDaqProcessorInfo, /* 0xDA, optional */
    Xcp_DTOCmdDaqReadDaq, /* 0xDB, optional */
    Xcp_DTOCmdDaqGetDaqClock, /* 0xDC, optional */
    Xcp_DTOCmdDaqStartStopSynch, /* 0xDD */
    Xcp_DTOCmdDaqStartStopDaqList, /* 0xDE */
    Xcp_DTOCmdDaqGetDaqListMode, /* 0xDF */
    Xcp_DTOCmdDaqSetDaqListMode, /* 0xE0 */
    Xcp_DTOCmdDaqWriteDaq, /* 0xE1 */
    Xcp_DTOCmdDaqSetDaqPtr, /* 0xE2 */
    Xcp_DTOCmdDaqClearDaqList, /* 0xE3 */
    Xcp_DTODaqPacket, /* 0xE4 */
    Xcp_DTODaqPacket, /* 0xE5 */
    Xcp_DTODaqPacket, /* 0xE6 */
    Xcp_DTODaqPacket, /* 0xE7 */
    Xcp_DTODaqPacket, /* 0xE8 */
    Xcp_DTODaqPacket, /* 0xE9 */
    Xcp_DTODaqPacket, /* 0xEA */
    Xcp_DTODaqPacket, /* 0xEB */
    Xcp_DTODaqPacket, /* 0xEC */
    Xcp_DTODaqPacket, /* 0xED */
    Xcp_DTODaqPacket, /* 0xEE */
    Xcp_DTODaqPacket, /* 0xEF */
    Xcp_DTODaqPacket, /* 0xF0 */
    Xcp_DTOCmdStdUserCmd, /* 0xF1, optional */
    Xcp_DTOCmdStdTransportLayerCmd, /* 0xF2, optional */
    Xcp_DTOCmdStdBuildChecksum, /* 0xF3, optional */
    Xcp_DTOCmdStdShortUpload, /* 0xF4, optional */
    Xcp_DTOCmdStdUpload, /* 0xF5, optional */
    Xcp_DTOCmdStdSetMta, /* 0xF6, optional */
    Xcp_DTOCmdStdUnlock, /* 0xF7, optional */
    Xcp_DTOCmdStdGetSeed, /* 0xF8, optional */
    Xcp_DTOCmdStdSetRequest, /* 0xF9, optional */
    Xcp_DTOCmdStdGetId, /* 0xFA, optional */
    Xcp_DTOCmdStdGetCommModeInfo, /* 0xFB, optional */
    Xcp_CTOCmdStdSynch, /* 0xFC */
    Xcp_CTOCmdStdGetStatus, /* 0xFD */
    Xcp_CTOCmdStdDisconnect, /* 0xFE */
    Xcp_CTOCmdStdConnect, /* 0xFF */
};

#define Xcp_STOP_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

const uint8 Xcp_PIDToCmdGroupTable[0x100u] = {
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x00 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x01 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x02 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x03 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x04 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x05 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x06 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x07 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x08 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x09 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x0A */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x0B */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x0C */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x0D */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x0E */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x0F */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x10 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x11 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x12 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x13 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x14 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x15 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x16 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x17 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x18 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x19 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x1A */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x1B */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x1C */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x1D */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x1E */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x1F */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x20 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x21 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x22 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x23 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x24 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x25 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x26 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x27 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x28 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x29 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x2A */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x2B */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x2C */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x2D */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x2E */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x2F */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x30 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x31 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x32 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x33 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x34 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x35 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x36 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x37 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x38 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x39 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x3A */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x3B */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x3C */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x3D */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x3E */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x3F */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x40 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x41 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x42 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x43 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x44 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x45 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x46 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x47 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x48 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x49 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x4A */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x4B */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x4C */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x4D */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x4E */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x4F */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x50 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x51 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x52 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x53 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x54 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x55 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x56 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x57 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x58 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x59 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x5A */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x5B */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x5C */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x5D */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x5E */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x5F */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x60 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x61 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x62 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x63 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x64 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x65 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x66 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x67 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x68 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x69 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x6A */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x6B */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x6C */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x6D */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x6E */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x6F */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x70 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x71 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x72 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x73 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x74 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x75 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x76 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x77 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x78 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x79 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x7A */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x7B */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x7C */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x7D */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x7E */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x7F */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x80 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x81 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x82 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x83 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x84 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x85 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x86 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x87 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x88 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x89 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x8A */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x8B */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x8C */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x8D */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x8E */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x8F */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x90 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x91 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x92 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x93 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x94 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x95 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x96 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x97 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x98 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x99 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x9A */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x9B */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x9C */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x9D */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x9E */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0x9F */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xA0 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xA1 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xA2 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xA3 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xA4 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xA5 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xA6 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xA7 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xA8 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xA9 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xAA */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xAB */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xAC */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xAD */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xAE */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xAF */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xB0 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xB1 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xB2 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xB3 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xB4 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xB5 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xB6 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xB7 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xB8 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xB9 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xBA */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xBB */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xBC */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xBD */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xBE */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xBF */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xC0 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xC1 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xC2 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xC3 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xC4 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xC5 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xC6 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* 0xC7 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, /* PROGRAM_VERIFY 0xC8, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, /* PROGRAM_MAX 0xC9, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, /* PROGRAM_NEXT 0xCA, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, /* PROGRAM_FORMAT 0xCB, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, /* PROGRAM_PREPARE 0xCC, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, /* GET_SECTOR_INFO 0xCD, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, /* GET_PGM_PROCESSOR_INFO 0xCE, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, /* PROGRAM_RESET 0xCF */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, /* PROGRAM 0xD0 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, /* PROGRAM_CLEAR 0xD1 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, /* PROGRAM_START 0xD2 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* ALLOC_ODT_ENTRY 0xD3, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* ALLOC_ODT 0xD4, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* ALLOC_DAQ 0xD5, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* FREE_DAQ 0xD6, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* GET_DAQ_EVENT_INFO 0xD7, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* GET_DAQ_LIST_INFO 0xD8, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* GET_DAQ_RESOLUTION_INFO 0xD9, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* GET_DAQ_PROCESSOR_INFO 0xDA, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* READ_DAQ 0xDB, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* GET_DAQ_CLOCK 0xDC, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* START_STOP_SYNCH 0xDD */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* START_STOP_DAQ_LIST 0xDE */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* GET_DAQ_LIST_MODE 0xDF */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* SET_DAQ_LIST_MODE 0xE0 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* WRITE_DAQ 0xE1 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* SET_DAQ_PTR 0xE2 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ, /* CLEAR_DAQ_LIST 0xE3 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* COPY_CAL_PAGE 0xE4, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* GET_SEGMENT_MODE 0xE5, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* SET_SEGMENT_MODE 0xE6, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* GET_PAGE_INFO 0xE7, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* GET_SEGMENT_INFO 0xE8, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* GET_PAG_PROCESSOR_INFO 0xE9, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* GET_CAL_PAGE 0xEA */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* SET_CAL_PAGE 0xEB */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* MODIFY_BITS 0xEC, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* SHORT_DOWNLOAD 0xED, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* DOWNLOAD_MAX 0xEE, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* DOWNLOAD_NEXT 0xEF, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG, /* DOWNLOAD 0xF0 */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* USER_CMD 0xF1, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* TRANSPORT_LAYER_CMD 0xF2, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* BUILD_CHECKSUM 0xF3, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* SHORT_UPLOAD 0xF4, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* UPLOAD 0xF5, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* SET_MTA 0xF6, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* UNLOCK 0xF7, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* GET_SEED 0xF8, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* SET_REQUEST 0xF9, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* GET_ID 0xFA, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* GET_COMM_MOD_INFO 0xFB, optional */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* SYNCH 0xFC */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* GET_STATUS 0xFD */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* DISCONNECT0xFE */
    XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE, /* CONNECT 0xFF */
};

#define Xcp_STOP_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

const uint32_least Xcp_CTOErrorMatrix[0x100u] = {
    0x00000000u, /* 0x00 */
    0x00000000u, /* 0x01 */
    0x00000000u, /* 0x02 */
    0x00000000u, /* 0x03 */
    0x00000000u, /* 0x04 */
    0x00000000u, /* 0x05 */
    0x00000000u, /* 0x06 */
    0x00000000u, /* 0x07 */
    0x00000000u, /* 0x08 */
    0x00000000u, /* 0x09 */
    0x00000000u, /* 0x0A */
    0x00000000u, /* 0x0B */
    0x00000000u, /* 0x0C */
    0x00000000u, /* 0x0D */
    0x00000000u, /* 0x0E */
    0x00000000u, /* 0x0F */
    0x00000000u, /* 0x10 */
    0x00000000u, /* 0x11 */
    0x00000000u, /* 0x12 */
    0x00000000u, /* 0x13 */
    0x00000000u, /* 0x14 */
    0x00000000u, /* 0x15 */
    0x00000000u, /* 0x16 */
    0x00000000u, /* 0x17 */
    0x00000000u, /* 0x18 */
    0x00000000u, /* 0x19 */
    0x00000000u, /* 0x1A */
    0x00000000u, /* 0x1B */
    0x00000000u, /* 0x1C */
    0x00000000u, /* 0x1D */
    0x00000000u, /* 0x1E */
    0x00000000u, /* 0x1F */
    0x00000000u, /* 0x20 */
    0x00000000u, /* 0x21 */
    0x00000000u, /* 0x22 */
    0x00000000u, /* 0x23 */
    0x00000000u, /* 0x24 */
    0x00000000u, /* 0x25 */
    0x00000000u, /* 0x26 */
    0x00000000u, /* 0x27 */
    0x00000000u, /* 0x28 */
    0x00000000u, /* 0x29 */
    0x00000000u, /* 0x2A */
    0x00000000u, /* 0x2B */
    0x00000000u, /* 0x2C */
    0x00000000u, /* 0x2D */
    0x00000000u, /* 0x2E */
    0x00000000u, /* 0x2F */
    0x00000000u, /* 0x30 */
    0x00000000u, /* 0x31 */
    0x00000000u, /* 0x32 */
    0x00000000u, /* 0x33 */
    0x00000000u, /* 0x34 */
    0x00000000u, /* 0x35 */
    0x00000000u, /* 0x36 */
    0x00000000u, /* 0x37 */
    0x00000000u, /* 0x38 */
    0x00000000u, /* 0x39 */
    0x00000000u, /* 0x3A */
    0x00000000u, /* 0x3B */
    0x00000000u, /* 0x3C */
    0x00000000u, /* 0x3D */
    0x00000000u, /* 0x3E */
    0x00000000u, /* 0x3F */
    0x00000000u, /* 0x40 */
    0x00000000u, /* 0x41 */
    0x00000000u, /* 0x42 */
    0x00000000u, /* 0x43 */
    0x00000000u, /* 0x44 */
    0x00000000u, /* 0x45 */
    0x00000000u, /* 0x46 */
    0x00000000u, /* 0x47 */
    0x00000000u, /* 0x48 */
    0x00000000u, /* 0x49 */
    0x00000000u, /* 0x4A */
    0x00000000u, /* 0x4B */
    0x00000000u, /* 0x4C */
    0x00000000u, /* 0x4D */
    0x00000000u, /* 0x4E */
    0x00000000u, /* 0x4F */
    0x00000000u, /* 0x50 */
    0x00000000u, /* 0x51 */
    0x00000000u, /* 0x52 */
    0x00000000u, /* 0x53 */
    0x00000000u, /* 0x54 */
    0x00000000u, /* 0x55 */
    0x00000000u, /* 0x56 */
    0x00000000u, /* 0x57 */
    0x00000000u, /* 0x58 */
    0x00000000u, /* 0x59 */
    0x00000000u, /* 0x5A */
    0x00000000u, /* 0x5B */
    0x00000000u, /* 0x5C */
    0x00000000u, /* 0x5D */
    0x00000000u, /* 0x5E */
    0x00000000u, /* 0x5F */
    0x00000000u, /* 0x60 */
    0x00000000u, /* 0x61 */
    0x00000000u, /* 0x62 */
    0x00000000u, /* 0x63 */
    0x00000000u, /* 0x64 */
    0x00000000u, /* 0x65 */
    0x00000000u, /* 0x66 */
    0x00000000u, /* 0x67 */
    0x00000000u, /* 0x68 */
    0x00000000u, /* 0x69 */
    0x00000000u, /* 0x6A */
    0x00000000u, /* 0x6B */
    0x00000000u, /* 0x6C */
    0x00000000u, /* 0x6D */
    0x00000000u, /* 0x6E */
    0x00000000u, /* 0x6F */
    0x00000000u, /* 0x70 */
    0x00000000u, /* 0x71 */
    0x00000000u, /* 0x72 */
    0x00000000u, /* 0x73 */
    0x00000000u, /* 0x74 */
    0x00000000u, /* 0x75 */
    0x00000000u, /* 0x76 */
    0x00000000u, /* 0x77 */
    0x00000000u, /* 0x78 */
    0x00000000u, /* 0x79 */
    0x00000000u, /* 0x7A */
    0x00000000u, /* 0x7B */
    0x00000000u, /* 0x7C */
    0x00000000u, /* 0x7D */
    0x00000000u, /* 0x7E */
    0x00000000u, /* 0x7F */
    0x00000000u, /* 0x80 */
    0x00000000u, /* 0x81 */
    0x00000000u, /* 0x82 */
    0x00000000u, /* 0x83 */
    0x00000000u, /* 0x84 */
    0x00000000u, /* 0x85 */
    0x00000000u, /* 0x86 */
    0x00000000u, /* 0x87 */
    0x00000000u, /* 0x88 */
    0x00000000u, /* 0x89 */
    0x00000000u, /* 0x8A */
    0x00000000u, /* 0x8B */
    0x00000000u, /* 0x8C */
    0x00000000u, /* 0x8D */
    0x00000000u, /* 0x8E */
    0x00000000u, /* 0x8F */
    0x00000000u, /* 0x90 */
    0x00000000u, /* 0x91 */
    0x00000000u, /* 0x92 */
    0x00000000u, /* 0x93 */
    0x00000000u, /* 0x94 */
    0x00000000u, /* 0x95 */
    0x00000000u, /* 0x96 */
    0x00000000u, /* 0x97 */
    0x00000000u, /* 0x98 */
    0x00000000u, /* 0x99 */
    0x00000000u, /* 0x9A */
    0x00000000u, /* 0x9B */
    0x00000000u, /* 0x9C */
    0x00000000u, /* 0x9D */
    0x00000000u, /* 0x9E */
    0x00000000u, /* 0x9F */
    0x00000000u, /* 0xA0 */
    0x00000000u, /* 0xA1 */
    0x00000000u, /* 0xA2 */
    0x00000000u, /* 0xA3 */
    0x00000000u, /* 0xA4 */
    0x00000000u, /* 0xA5 */
    0x00000000u, /* 0xA6 */
    0x00000000u, /* 0xA7 */
    0x00000000u, /* 0xA8 */
    0x00000000u, /* 0xA9 */
    0x00000000u, /* 0xAA */
    0x00000000u, /* 0xAB */
    0x00000000u, /* 0xAC */
    0x00000000u, /* 0xAD */
    0x00000000u, /* 0xAE */
    0x00000000u, /* 0xAF */
    0x00000000u, /* 0xB0 */
    0x00000000u, /* 0xB1 */
    0x00000000u, /* 0xB2 */
    0x00000000u, /* 0xB3 */
    0x00000000u, /* 0xB4 */
    0x00000000u, /* 0xB5 */
    0x00000000u, /* 0xB6 */
    0x00000000u, /* 0xB7 */
    0x00000000u, /* 0xB8 */
    0x00000000u, /* 0xB9 */
    0x00000000u, /* 0xBA */
    0x00000000u, /* 0xBB */
    0x00000000u, /* 0xBC */
    0x00000000u, /* 0xBD */
    0x00000000u, /* 0xBE */
    0x00000000u, /* 0xBF */
    0x00000000u, /* 0xC0 */
    0x00000000u, /* 0xC1 */
    0x00000000u, /* 0xC2 */
    0x00000000u, /* 0xC3 */
    0x00000000u, /* 0xC4 */
    0x00000000u, /* 0xC5 */
    0x00000000u, /* 0xC6 */
    0x00000000u, /* 0xC7 */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_SEQUENCE | XCP_INTERNAL_ERR_GENERIC | XCP_INTERNAL_ERR_VERIFY, /* PROGRAM_VERIFY 0xC8, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_SEQUENCE | XCP_INTERNAL_ERR_MEMORY_OVERFLOW, /* PROGRAM_MAX 0xC9, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED | XCP_INTERNAL_ERR_MEMORY_OVERFLOW | XCP_INTERNAL_ERR_SEQUENCE, /* PROGRAM_NEXT 0xCA, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_SEQUENCE, /* PROGRAM_FORMAT 0xCB, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_SEQUENCE | XCP_INTERNAL_ERR_GENERIC, /* PROGRAM_PREPARE 0xCC, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_MODE_NOT_VALID | XCP_INTERNAL_ERR_SEGMENT_NOT_VALID, /* GET_SECTOR_INFO 0xCD, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX, /* GET_PGM_PROCESSOR_INFO 0xCE, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_SEQUENCE, /* PROGRAM_RESET 0xCF */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED | XCP_INTERNAL_ERR_SEQUENCE | XCP_INTERNAL_ERR_MEMORY_OVERFLOW, /* PROGRAM 0xD0 */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED | XCP_INTERNAL_ERR_SEQUENCE, /* PROGRAM_CLEAR 0xD1 */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_DAQ_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_ACCESS_LOCKED | XCP_INTERNAL_ERR_GENERIC, /* PROGRAM_START 0xD2 */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_SEQUENCE | XCP_INTERNAL_ERR_MEMORY_OVERFLOW, /* ALLOC_ODT_ENTRY 0xD3, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_SEQUENCE | XCP_INTERNAL_ERR_MEMORY_OVERFLOW, /* ALLOC_ODT 0xD4, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_SEQUENCE | XCP_INTERNAL_ERR_MEMORY_OVERFLOW, /* ALLOC_DAQ 0xD5, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX, /* FREE_DAQ 0xD6, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE, /* GET_DAQ_EVENT_INFO 0xD7, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE, /* GET_DAQ_LIST_INFO 0xD8, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX, /* GET_DAQ_RESOLUTION_INFO 0xD9, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX, /* GET_DAQ_PROCESSOR_INFO 0xDA, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX, /* READ_DAQ 0xDB, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX, /* GET_DAQ_CLOCK 0xDC, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_MODE_NOT_VALID | XCP_INTERNAL_ERR_DAQ_CONFIG, /* START_STOP_SYNCH 0xDD */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_MODE_NOT_VALID | XCP_INTERNAL_ERR_DAQ_CONFIG, /* START_STOP_DAQ_LIST 0xDE */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE, /* GET_DAQ_LIST_MODE 0xDF */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_DAQ_ACTIVE | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_MODE_NOT_VALID, /* SET_DAQ_LIST_MODE 0xE0 */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_DAQ_ACTIVE | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED | XCP_INTERNAL_ERR_WRITE_PROTECTED | XCP_INTERNAL_ERR_DAQ_CONFIG, /* WRITE_DAQ 0xE1 */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_DAQ_ACTIVE | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE, /* SET_DAQ_PTR 0xE2 */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_DAQ_ACTIVE | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED, /* CLEAR_DAQ_LIST 0xE3 */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_PAGE_NOT_VALID | XCP_INTERNAL_ERR_SEGMENT_NOT_VALID, /* COPY_CAL_PAGE 0xE4, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_SEGMENT_NOT_VALID, /* GET_SEGMENT_MODE 0xE5, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_MODE_NOT_VALID | XCP_INTERNAL_ERR_SEGMENT_NOT_VALID, /* SET_SEGMENT_MODE 0xE6, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_PAGE_NOT_VALID | XCP_INTERNAL_ERR_SEGMENT_NOT_VALID, /* GET_PAGE_INFO 0xE7, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_SEGMENT_NOT_VALID, /* GET_SEGMENT_INFO 0xE8, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX, /* GET_PAG_PROCESSOR_INFO 0xE9, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_PAGE_NOT_VALID | XCP_INTERNAL_ERR_MODE_NOT_VALID | XCP_INTERNAL_ERR_SEGMENT_NOT_VALID, /* GET_CAL_PAGE 0xEA */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_PAGE_NOT_VALID | XCP_INTERNAL_ERR_MODE_NOT_VALID | XCP_INTERNAL_ERR_SEGMENT_NOT_VALID, /* SET_CAL_PAGE 0xEB */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED | XCP_INTERNAL_ERR_WRITE_PROTECTED | XCP_INTERNAL_ERR_MEMORY_OVERFLOW, /* MODIFY_BITS 0xEC, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED | XCP_INTERNAL_ERR_WRITE_PROTECTED | XCP_INTERNAL_ERR_MEMORY_OVERFLOW, /* SHORT_DOWNLOAD 0xED, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED | XCP_INTERNAL_ERR_WRITE_PROTECTED | XCP_INTERNAL_ERR_MEMORY_OVERFLOW, /* DOWNLOAD_MAX 0xEE, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED | XCP_INTERNAL_ERR_WRITE_PROTECTED | XCP_INTERNAL_ERR_MEMORY_OVERFLOW | XCP_INTERNAL_ERR_SEQUENCE, /* DOWNLOAD_NEXT 0xEF, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED | XCP_INTERNAL_ERR_WRITE_PROTECTED | XCP_INTERNAL_ERR_MEMORY_OVERFLOW, /* DOWNLOAD 0xF0 */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE, /* USER_CMD 0xF1, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE, /* TRANSPORT_LAYER_CMD 0xF2, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED, /* BUILD_CHECKSUM 0xF3, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED, /* SHORT_UPLOAD 0xF4, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_DENIED | XCP_INTERNAL_ERR_ACCESS_LOCKED, /* UPLOAD 0xF5, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE, /* SET_MTA 0xF6, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_ACCESS_LOCKED | XCP_INTERNAL_ERR_SEQUENCE, /* UNLOCK 0xF7, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE, /* GET_SEED 0xF8, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE, /* SET_REQUEST 0xF9, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_CMD_UNKNOWN | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE, /* GET_ID 0xFA, optional */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_CMD_SYNTAX, /* GET_COMM_MOD_INFO 0xFB, optional */
    XCP_INTERNAL_ERR_CMD_SYNCH | XCP_INTERNAL_ERR_CMD_UNKNOWN, /* SYNCH 0xFC */
    0x00u, /* GET_STATUS 0xFD */
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE, /* DISCONNECT0xFE */
    0x00u, /* CONNECT 0xFF */
};

#define Xcp_STOP_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

static void(* const Xcp_ReadSlaveMemoryTable[])(void *address, uint8 extension, uint8 *pBuffer) = {
    Xcp_ReadSlaveMemoryU8,
    Xcp_ReadSlaveMemoryU16,
    Xcp_ReadSlaveMemoryU32
};

#define Xcp_STOP_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

static void(* const Xcp_WriteSlaveMemoryTable[])(void *address, uint8 *pBuffer) = {
    Xcp_WriteSlaveMemoryU8,
    Xcp_WriteSlaveMemoryU16,
    Xcp_WriteSlaveMemoryU32
};

#define Xcp_STOP_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CONST_16
#include "Xcp_MemMap.h"

static const uint16 Xcp_CRC16Table[] = {
    0x0000u, 0xC0C1u, 0xC181u, 0x0140u, 0xC301u, 0x03C0u, 0x0280u, 0xC241u, 0xC601u, 0x06C0u, 0x0780u, 0xC741u, 0x0500u, 0xC5C1u, 0xC481u, 0x0440u,
    0xCC01u, 0x0CC0u, 0x0D80u, 0xCD41u, 0x0F00u, 0xCFC1u, 0xCE81u, 0x0E40u, 0x0A00u, 0xCAC1u, 0xCB81u, 0x0B40u, 0xC901u, 0x09C0u, 0x0880u, 0xC841u,
    0xD801u, 0x18C0u, 0x1980u, 0xD941u, 0x1B00u, 0xDBC1u, 0xDA81u, 0x1A40u, 0x1E00u, 0xDEC1u, 0xDF81u, 0x1F40u, 0xDD01u, 0x1DC0u, 0x1C80u, 0xDC41u,
    0x1400u, 0xD4C1u, 0xD581u, 0x1540u, 0xD701u, 0x17C0u, 0x1680u, 0xD641u, 0xD201u, 0x12C0u, 0x1380u, 0xD341u, 0x1100u, 0xD1C1u, 0xD081u, 0x1040u,
    0xF001u, 0x30C0u, 0x3180u, 0xF141u, 0x3300u, 0xF3C1u, 0xF281u, 0x3240u, 0x3600u, 0xF6C1u, 0xF781u, 0x3740u, 0xF501u, 0x35C0u, 0x3480u, 0xF441u,
    0x3C00u, 0xFCC1u, 0xFD81u, 0x3D40u, 0xFF01u, 0x3FC0u, 0x3E80u, 0xFE41u, 0xFA01u, 0x3AC0u, 0x3B80u, 0xFB41u, 0x3900u, 0xF9C1u, 0xF881u, 0x3840u,
    0x2800u, 0xE8C1u, 0xE981u, 0x2940u, 0xEB01u, 0x2BC0u, 0x2A80u, 0xEA41u, 0xEE01u, 0x2EC0u, 0x2F80u, 0xEF41u, 0x2D00u, 0xEDC1u, 0xEC81u, 0x2C40u,
    0xE401u, 0x24C0u, 0x2580u, 0xE541u, 0x2700u, 0xE7C1u, 0xE681u, 0x2640u, 0x2200u, 0xE2C1u, 0xE381u, 0x2340u, 0xE101u, 0x21C0u, 0x2080u, 0xE041u,
    0xA001u, 0x60C0u, 0x6180u, 0xA141u, 0x6300u, 0xA3C1u, 0xA281u, 0x6240u, 0x6600u, 0xA6C1u, 0xA781u, 0x6740u, 0xA501u, 0x65C0u, 0x6480u, 0xA441u,
    0x6C00u, 0xACC1u, 0xAD81u, 0x6D40u, 0xAF01u, 0x6FC0u, 0x6E80u, 0xAE41u, 0xAA01u, 0x6AC0u, 0x6B80u, 0xAB41u, 0x6900u, 0xA9C1u, 0xA881u, 0x6840u,
    0x7800u, 0xB8C1u, 0xB981u, 0x7940u, 0xBB01u, 0x7BC0u, 0x7A80u, 0xBA41u, 0xBE01u, 0x7EC0u, 0x7F80u, 0xBF41u, 0x7D00u, 0xBDC1u, 0xBC81u, 0x7C40u,
    0xB401u, 0x74C0u, 0x7580u, 0xB541u, 0x7700u, 0xB7C1u, 0xB681u, 0x7640u, 0x7200u, 0xB2C1u, 0xB381u, 0x7340u, 0xB101u, 0x71C0u, 0x7080u, 0xB041u,
    0x5000u, 0x90C1u, 0x9181u, 0x5140u, 0x9301u, 0x53C0u, 0x5280u, 0x9241u, 0x9601u, 0x56C0u, 0x5780u, 0x9741u, 0x5500u, 0x95C1u, 0x9481u, 0x5440u,
    0x9C01u, 0x5CC0u, 0x5D80u, 0x9D41u, 0x5F00u, 0x9FC1u, 0x9E81u, 0x5E40u, 0x5A00u, 0x9AC1u, 0x9B81u, 0x5B40u, 0x9901u, 0x59C0u, 0x5880u, 0x9841u,
    0x8801u, 0x48C0u, 0x4980u, 0x8941u, 0x4B00u, 0x8BC1u, 0x8A81u, 0x4A40u, 0x4E00u, 0x8EC1u, 0x8F81u, 0x4F40u, 0x8D01u, 0x4DC0u, 0x4C80u, 0x8C41u,
    0x4400u, 0x84C1u, 0x8581u, 0x4540u, 0x8701u, 0x47C0u, 0x4680u, 0x8641u, 0x8201u, 0x42C0u, 0x4380u, 0x8341u, 0x4100u, 0x81C1u, 0x8081u, 0x4040u
};

#define Xcp_STOP_SEC_CONST_16
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CONST_16
#include "Xcp_MemMap.h"

static const uint16 Xcp_CRC16CITTTable[] = {
    0x0000u, 0x1021u, 0x2042u, 0x3063u, 0x4084u, 0x50A5u, 0x60C6u, 0x70E7u,0x8108u, 0x9129u, 0xA14Au, 0xB16Bu, 0xC18Cu, 0xD1ADu, 0xE1CEu, 0xF1EFu,
    0x1231u, 0x0210u, 0x3273u, 0x2252u, 0x52B5u, 0x4294u, 0x72F7u, 0x62D6u,0x9339u, 0x8318u, 0xB37Bu, 0xA35Au, 0xD3BDu, 0xC39Cu, 0xF3FFu, 0xE3DEu,
    0x2462u, 0x3443u, 0x0420u, 0x1401u, 0x64E6u, 0x74C7u, 0x44A4u, 0x5485u,0xA56Au, 0xB54Bu, 0x8528u, 0x9509u, 0xE5EEu, 0xF5CFu, 0xC5ACu, 0xD58Du,
    0x3653u, 0x2672u, 0x1611u, 0x0630u, 0x76D7u, 0x66F6u, 0x5695u, 0x46B4u,0xB75Bu, 0xA77Au, 0x9719u, 0x8738u, 0xF7DFu, 0xE7FEu, 0xD79Du, 0xC7BCu,
    0x48C4u, 0x58E5u, 0x6886u, 0x78A7u, 0x0840u, 0x1861u, 0x2802u, 0x3823u,0xC9CCu, 0xD9EDu, 0xE98Eu, 0xF9AFu, 0x8948u, 0x9969u, 0xA90Au, 0xB92Bu,
    0x5AF5u, 0x4AD4u, 0x7AB7u, 0x6A96u, 0x1A71u, 0x0A50u, 0x3A33u, 0x2A12u,0xDBFDu, 0xCBDCu, 0xFBBFu, 0xEB9Eu, 0x9B79u, 0x8B58u, 0xBB3Bu, 0xAB1Au,
    0x6CA6u, 0x7C87u, 0x4CE4u, 0x5CC5u, 0x2C22u, 0x3C03u, 0x0C60u, 0x1C41u,0xEDAEu, 0xFD8Fu, 0xCDECu, 0xDDCDu, 0xAD2Au, 0xBD0Bu, 0x8D68u, 0x9D49u,
    0x7E97u, 0x6EB6u, 0x5ED5u, 0x4EF4u, 0x3E13u, 0x2E32u, 0x1E51u, 0x0E70u,0xFF9Fu, 0xEFBEu, 0xDFDDu, 0xCFFCu, 0xBF1Bu, 0xAF3Au, 0x9F59u, 0x8F78u,
    0x9188u, 0x81A9u, 0xB1CAu, 0xA1EBu, 0xD10Cu, 0xC12Du, 0xF14Eu, 0xE16Fu,0x1080u, 0x00A1u, 0x30C2u, 0x20E3u, 0x5004u, 0x4025u, 0x7046u, 0x6067u,
    0x83B9u, 0x9398u, 0xA3FBu, 0xB3DAu, 0xC33Du, 0xD31Cu, 0xE37Fu, 0xF35Eu,0x02B1u, 0x1290u, 0x22F3u, 0x32D2u, 0x4235u, 0x5214u, 0x6277u, 0x7256u,
    0xB5EAu, 0xA5CBu, 0x95A8u, 0x8589u, 0xF56Eu, 0xE54Fu, 0xD52Cu, 0xC50Du,0x34E2u, 0x24C3u, 0x14A0u, 0x0481u, 0x7466u, 0x6447u, 0x5424u, 0x4405u,
    0xA7DBu, 0xB7FAu, 0x8799u, 0x97B8u, 0xE75Fu, 0xF77Eu, 0xC71Du, 0xD73Cu,0x26D3u, 0x36F2u, 0x0691u, 0x16B0u, 0x6657u, 0x7676u, 0x4615u, 0x5634u,
    0xD94Cu, 0xC96Du, 0xF90Eu, 0xE92Fu, 0x99C8u, 0x89E9u, 0xB98Au, 0xA9ABu,0x5844u, 0x4865u, 0x7806u, 0x6827u, 0x18C0u, 0x08E1u, 0x3882u, 0x28A3u,
    0xCB7Du, 0xDB5Cu, 0xEB3Fu, 0xFB1Eu, 0x8BF9u, 0x9BD8u, 0xABBBu, 0xBB9Au,0x4A75u, 0x5A54u, 0x6A37u, 0x7A16u, 0x0AF1u, 0x1AD0u, 0x2AB3u, 0x3A92u,
    0xFD2Eu, 0xED0Fu, 0xDD6Cu, 0xCD4Du, 0xBDAAu, 0xAD8Bu, 0x9DE8u, 0x8DC9u,0x7C26u, 0x6C07u, 0x5C64u, 0x4C45u, 0x3CA2u, 0x2C83u, 0x1CE0u, 0x0CC1u,
    0xEF1Fu, 0xFF3Eu, 0xCF5Du, 0xDF7Cu, 0xAF9Bu, 0xBFBAu, 0x8FD9u, 0x9FF8u,0x6E17u, 0x7E36u, 0x4E55u, 0x5E74u, 0x2E93u, 0x3EB2u, 0x0ED1u, 0x1EF0u
};

#define Xcp_STOP_SEC_CONST_16
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CONST_32
#include "Xcp_MemMap.h"

static const uint32 Xcp_CRC32Table[] = {
    0x00000000u, 0x77073096u, 0xEE0E612Cu, 0x990951BAu, 0x076DC419u, 0x706AF48Fu, 0xE963A535u, 0x9E6495A3u,
    0x0EDB8832u, 0x79DCB8A4u, 0xE0D5E91Eu, 0x97D2D988u, 0x09B64C2Bu, 0x7EB17CBDu, 0xE7B82D07u, 0x90BF1D91u,
    0x1DB71064u, 0x6AB020F2u, 0xF3B97148u, 0x84BE41DEu, 0x1ADAD47Du, 0x6DDDE4EBu, 0xF4D4B551u, 0x83D385C7u,
    0x136C9856u, 0x646BA8C0u, 0xFD62F97Au, 0x8A65C9ECu, 0x14015C4Fu, 0x63066CD9u, 0xFA0F3D63u, 0x8D080DF5u,
    0x3B6E20C8u, 0x4C69105Eu, 0xD56041E4u, 0xA2677172u, 0x3C03E4D1u, 0x4B04D447u, 0xD20D85FDu, 0xA50AB56Bu,
    0x35B5A8FAu, 0x42B2986Cu, 0xDBBBC9D6u, 0xACBCF940u, 0x32D86CE3u, 0x45DF5C75u, 0xDCD60DCFu, 0xABD13D59u,
    0x26D930ACu, 0x51DE003Au, 0xC8D75180u, 0xBFD06116u, 0x21B4F4B5u, 0x56B3C423u, 0xCFBA9599u, 0xB8BDA50Fu,
    0x2802B89Eu, 0x5F058808u, 0xC60CD9B2u, 0xB10BE924u, 0x2F6F7C87u, 0x58684C11u, 0xC1611DABu, 0xB6662D3Du,
    0x76DC4190u, 0x01DB7106u, 0x98D220BCu, 0xEFD5102Au, 0x71B18589u, 0x06B6B51Fu, 0x9FBFE4A5u, 0xE8B8D433u,
    0x7807C9A2u, 0x0F00F934u, 0x9609A88Eu, 0xE10E9818u, 0x7F6A0DBBu, 0x086D3D2Du, 0x91646C97u, 0xE6635C01u,
    0x6B6B51F4u, 0x1C6C6162u, 0x856530D8u, 0xF262004Eu, 0x6C0695EDu, 0x1B01A57Bu, 0x8208F4C1u, 0xF50FC457u,
    0x65B0D9C6u, 0x12B7E950u, 0x8BBEB8EAu, 0xFCB9887Cu, 0x62DD1DDFu, 0x15DA2D49u, 0x8CD37CF3u, 0xFBD44C65u,
    0x4DB26158u, 0x3AB551CEu, 0xA3BC0074u, 0xD4BB30E2u, 0x4ADFA541u, 0x3DD895D7u, 0xA4D1C46Du, 0xD3D6F4FBu,
    0x4369E96Au, 0x346ED9FCu, 0xAD678846u, 0xDA60B8D0u, 0x44042D73u, 0x33031DE5u, 0xAA0A4C5Fu, 0xDD0D7CC9u,
    0x5005713Cu, 0x270241AAu, 0xBE0B1010u, 0xC90C2086u, 0x5768B525u, 0x206F85B3u, 0xB966D409u, 0xCE61E49Fu,
    0x5EDEF90Eu, 0x29D9C998u, 0xB0D09822u, 0xC7D7A8B4u, 0x59B33D17u, 0x2EB40D81u, 0xB7BD5C3Bu, 0xC0BA6CADu,
    0xEDB88320u, 0x9ABFB3B6u, 0x03B6E20Cu, 0x74B1D29Au, 0xEAD54739u, 0x9DD277AFu, 0x04DB2615u, 0x73DC1683u,
    0xE3630B12u, 0x94643B84u, 0x0D6D6A3Eu, 0x7A6A5AA8u, 0xE40ECF0Bu, 0x9309FF9Du, 0x0A00AE27u, 0x7D079EB1u,
    0xF00F9344u, 0x8708A3D2u, 0x1E01F268u, 0x6906C2FEu, 0xF762575Du, 0x806567CBu, 0x196C3671u, 0x6E6B06E7u,
    0xFED41B76u, 0x89D32BE0u, 0x10DA7A5Au, 0x67DD4ACCu, 0xF9B9DF6Fu, 0x8EBEEFF9u, 0x17B7BE43u, 0x60B08ED5u,
    0xD6D6A3E8u, 0xA1D1937Eu, 0x38D8C2C4u, 0x4FDFF252u, 0xD1BB67F1u, 0xA6BC5767u, 0x3FB506DDu, 0x48B2364Bu,
    0xD80D2BDAu, 0xAF0A1B4Cu, 0x36034AF6u, 0x41047A60u, 0xDF60EFC3u, 0xA867DF55u, 0x316E8EEFu, 0x4669BE79u,
    0xCB61B38Cu, 0xBC66831Au, 0x256FD2A0u, 0x5268E236u, 0xCC0C7795u, 0xBB0B4703u, 0x220216B9u, 0x5505262Fu,
    0xC5BA3BBEu, 0xB2BD0B28u, 0x2BB45A92u, 0x5CB36A04u, 0xC2D7FFA7u, 0xB5D0CF31u, 0x2CD99E8Bu, 0x5BDEAE1Du,
    0x9B64C2B0u, 0xEC63F226u, 0x756AA39Cu, 0x026D930Au, 0x9C0906A9u, 0xEB0E363Fu, 0x72076785u, 0x05005713u,
    0x95BF4A82u, 0xE2B87A14u, 0x7BB12BAEu, 0x0CB61B38u, 0x92D28E9Bu, 0xE5D5BE0Du, 0x7CDCEFB7u, 0x0BDBDF21u,
    0x86D3D2D4u, 0xF1D4E242u, 0x68DDB3F8u, 0x1FDA836Eu, 0x81BE16CDu, 0xF6B9265Bu, 0x6FB077E1u, 0x18B74777u,
    0x88085AE6u, 0xFF0F6A70u, 0x66063BCAu, 0x11010B5Cu, 0x8F659EFFu, 0xF862AE69u, 0x616BFFD3u, 0x166CCF45u,
    0xA00AE278u, 0xD70DD2EEu, 0x4E048354u, 0x3903B3C2u, 0xA7672661u, 0xD06016F7u, 0x4969474Du, 0x3E6E77DBu,
    0xAED16A4Au, 0xD9D65ADCu, 0x40DF0B66u, 0x37D83BF0u, 0xA9BCAE53u, 0xDEBB9EC5u, 0x47B2CF7Fu, 0x30B5FFE9u,
    0xBDBDF21Cu, 0xCABAC28Au, 0x53B39330u, 0x24B4A3A6u, 0xBAD03605u, 0xCDD70693u, 0x54DE5729u, 0x23D967BFu,
    0xB3667A2Eu, 0xC4614AB8u, 0x5D681B02u, 0x2A6F2B94u, 0xB40BBE37u, 0xC30C8EA1u, 0x5A05DF1Bu, 0x2D02EF8Du
};

#define Xcp_STOP_SEC_CONST_32
#include "Xcp_MemMap.h"

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* local variable definitions (static).                                                           */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_LVDEF
 * @{
 */

#define Xcp_START_SEC_VAR_FAST_INIT_UNSPECIFIED
#include "Xcp_MemMap.h"

const Xcp_Type *Xcp_Ptr = NULL_PTR;

#define Xcp_STOP_SEC_VAR_FAST_INIT_UNSPECIFIED
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_VAR_FAST_POWER_ON_INIT_UNSPECIFIED
#include "Xcp_MemMap.h"

Xcp_StateType Xcp_State = XCP_UNINITIALIZED;

#define Xcp_STOP_SEC_VAR_FAST_POWER_ON_INIT_UNSPECIFIED
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_VAR_FAST_POWER_ON_INIT_UNSPECIFIED
#include "Xcp_MemMap.h"

Xcp_InternalType Xcp_Internal;

#define Xcp_STOP_SEC_VAR_FAST_POWER_ON_INIT_UNSPECIFIED
#include "Xcp_MemMap.h"

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global constant definitions (extern const).                                                    */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_GCDEF
 * @{
 */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global variable definitions (extern).                                                          */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_GVDEF
 * @{
 */

#ifdef CFFI_ENABLE

#endif /* #ifndef CFFI_ENABLE */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global function definitions.                                                                   */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_GFDEF
 * @{
 */

void Xcp_Init(const Xcp_Type *pConfig)
{
    uint8 element_size;
    uint32_least idx;

    if (pConfig != NULL_PTR)
    {
        Xcp_Ptr = pConfig;

        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.1
         * The following relations must always be fulfilled
         *  MAX_CTO mod AG = 0
         *  MAX_DTO mod AG = 0 */
        element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);

        if ((element_size != 0x00u) &&
            ((Xcp_Ptr->general->maxCto % element_size) == 0x00u) && ((Xcp_Ptr->general->maxDto % element_size) == 0x00u))
        {
            Xcp_Internal.connect_mode = XCP_CONNECT_MODE_NORMAL;
            Xcp_Internal.connection_status = XCP_CONNECTION_STATE_DISCONNECTED;
            Xcp_Internal.session_status = 0x00u;
            Xcp_Internal.protection_status = 0x00u;
            Xcp_Internal.requested_protected_resource = 0x00u;
            Xcp_Internal.last_pid = 0x00u;
            Xcp_Internal.ongoing_transmit_type = ONGOING_TRANSMIT_TYPE_NONE;
            Xcp_Internal.cto_response.successful_transmission_pending = FALSE;
            Xcp_Internal.cto_response.pdu_info.SduLength = 0x00u;
            Xcp_Internal.cto_response.pdu_info.SduDataPtr = &Xcp_Internal.cto_response._packet[0x00u];
            Xcp_Internal.cto_response.pdu_info.MetaDataPtr = NULL_PTR;
            for (idx = 0x00000000u; idx < (sizeof(Xcp_Internal.cto_response._packet) / sizeof(Xcp_Internal.cto_response._packet[0x00u])); idx ++) {
                Xcp_Internal.cto_response._packet[idx] = 0x00u;
            }
            Xcp_Internal.event.successful_transmission_pending = FALSE;
            Xcp_Internal.event.pdu_info.SduLength = 0x00u;
            Xcp_Internal.event.pdu_info.SduDataPtr = &Xcp_Internal.event._packet[0x00u];
            Xcp_Internal.event.pdu_info.MetaDataPtr = NULL_PTR;
            for (idx = 0x00000000u; idx < (sizeof(Xcp_Internal.event._packet) / sizeof(Xcp_Internal.event._packet[0x00u])); idx ++) {
                Xcp_Internal.event._packet[idx] = 0x00u;
            }
            Xcp_EventQueueInit(Xcp_Rt[Xcp_Ptr->xcpRtRef].eventQueue);
            for (idx = 0x00000000u; idx < (sizeof(Xcp_Internal.seed.buffer) / sizeof(Xcp_Internal.seed.buffer[0x00u])); idx ++) {
                Xcp_Internal.seed.buffer[idx] = 0x00u;
            }
            Xcp_Internal.seed.total_length = 0x00u;
            Xcp_Internal.seed.current_index = 0x00u;
            for (idx = 0x00000000u; idx < (sizeof(Xcp_Internal.key_master.buffer) / sizeof(Xcp_Internal.key_master.buffer[0x00u])); idx ++) {
                Xcp_Internal.key_master.buffer[idx] = 0x00u;
            }
            Xcp_Internal.key_master.total_length = 0x00u;
            Xcp_Internal.key_master.current_index = 0x00u;
            for (idx = 0x00000000u; idx < (sizeof(Xcp_Internal.key_slave.buffer) / sizeof(Xcp_Internal.key_slave.buffer[0x00u])); idx ++) {
                Xcp_Internal.key_slave.buffer[idx] = 0x00u;
            }
            Xcp_Internal.key_slave.total_length = 0x00u;
            Xcp_Internal.key_slave.current_index = 0x00u;
            Xcp_Internal.memory_transfer.address = NULL_PTR;
            Xcp_Internal.memory_transfer.extension = 0x00u;
            Xcp_Internal.block_transfer.requested_elements = 0x00u;
            Xcp_Internal.block_transfer.frame_elements = 0x00u;
            for (idx = 0x00000000u; idx < (sizeof(Xcp_Internal.internal_buffer) / sizeof(Xcp_Internal.internal_buffer[0x00u])); idx ++) {
                Xcp_Internal.internal_buffer[idx] = 0x00u;
            }

            Xcp_ClearProtectionStatus();

            Xcp_State = XCP_INITIALIZED;
        }
        else
        {
            Xcp_ReportError(0x00u, XCP_INIT_API_ID, XCP_E_INIT_FAILED);
        }
    }
    else
    {
        Xcp_ReportError(0x00u, XCP_INIT_API_ID, XCP_E_PARAM_POINTER);
    }
}

#if (XCP_GET_VERSION_INFO_API == STD_ON)

void Xcp_GetVersionInfo(Std_VersionInfoType *pVersionInfo)
{
    if (pVersionInfo != NULL_PTR)
    {
        pVersionInfo->vendorID = 0x00u;
        pVersionInfo->moduleID = (uint16)XCP_MODULE_ID;
        pVersionInfo->sw_major_version = XCP_SW_MAJOR_VERSION;
        pVersionInfo->sw_minor_version = XCP_SW_MINOR_VERSION;
        pVersionInfo->sw_patch_version = XCP_SW_PATCH_VERSION;
    }
    else
    {
        Xcp_ReportError(0x00u, XCP_GET_VERSION_INFO_API_ID, XCP_E_PARAM_POINTER);
    }
}

#endif /* #if (XCP_GET_VERSION_INFO_API == STD_ON) */

#if (XCP_SUPPRESS_TX_SUPPORT == STD_ON)

void Xcp_SetTransmissionMode(NetworkHandleType channel, Xcp_TransmissionModeType mode) {

}

#endif /* #if (XCP_SUPPRESS_TX_SUPPORT == STD_ON) */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global scheduled function definitions.                                                         */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_GSFDEF
 * @{
 */

void Xcp_MainFunction(void)
{
    uint8 store_calibration_status;
    uint8 event_packet_id;
    uint8 event_code;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.3
     * The STORE_CAL_REQ bit obtained by GET_STATUS will be reset by the slave, when the request is fulfilled. The slave device may indicate this
     * by transmitting an EV_STORE_CAL event packet. */
    if ((Xcp_Internal.session_status & XCP_SESSION_STATUS_MASK_STORE_CAL_REQ) != 0x00u)
    {
        if (Xcp_StoreCalibrationDataToNonVolatileMemory(&store_calibration_status) == E_OK)
        {
            Xcp_Internal.session_status &= ~XCP_SESSION_STATUS_MASK_STORE_CAL_REQ;

            if (Xcp_EventQueuePush(Xcp_Rt[Xcp_Ptr->xcpRtRef].eventQueue, XCP_PID_EVENT, XCP_EVENT_STORE_CAL, &store_calibration_status, 0x00000001u) == E_OK)
            {
                Xcp_Internal.event.successful_transmission_pending = TRUE;
            }
            else
            {
                /* There is not much we can do here except reporting the error during the development process. If this error arises, the stack should
                 * be recompiled with a bigger event queue size (defined by XCP_EVENT_QUEUE_SIZE), or the reason for receiving such a lot of events
                 * should be identified. */
                Xcp_ReportError(0x00u, XCP_MAIN_FUNCTION_API_ID, XCP_E_EVENT_QUEUE_FULL);
            }
        }
    }

    if (Xcp_Internal.ongoing_transmit_type == ONGOING_TRANSMIT_TYPE_NONE) {
        /* We prioritize the transmission of the CTO response first, then the asynchronous events. */
        if (Xcp_Internal.cto_response.successful_transmission_pending == TRUE) {
            if (CanIf_Transmit(Xcp_Ptr->config->communicationChannel->channel_tx_pdu_ref->id, &Xcp_Internal.cto_response.pdu_info) == E_OK) {
                Xcp_Internal.ongoing_transmit_type = ONGOING_TRANSMIT_TYPE_CTO;
            }
        } else if (Xcp_EventQueueGet(Xcp_Rt[Xcp_Ptr->xcpRtRef].eventQueue, &event_packet_id, &event_code) == E_OK) {
            Xcp_Internal.event.pdu_info.SduDataPtr[0x00u] = event_packet_id;
            Xcp_Internal.event.pdu_info.SduDataPtr[0x01u] = event_code;

            if (CanIf_Transmit(Xcp_Ptr->config->communicationChannel->channel_tx_pdu_ref->id, &Xcp_Internal.event.pdu_info) == E_OK) {
                Xcp_Internal.ongoing_transmit_type = ONGOING_TRANSMIT_TYPE_EVENT;
            }
        }
    }
}

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global callback function definitions.                                                          */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_GCFDEF
 * @{
 */

void Xcp_CanIfRxIndication(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    uint8 result = E_OK;
    uint8 pid;
    uint8_least daq_idx;
    uint32_least dto_idx;

    boolean valid_pdu_id = FALSE;

    if (Xcp_State == XCP_INITIALIZED)
    {
        if (pPduInfo != NULL_PTR)
        {
            /* First we check if the received PDU ID is the one which has been configured for CTO reception. */
            if (rxPduId == Xcp_Ptr->config->communicationChannel->channel_rx_pdu_ref->id) {
                valid_pdu_id = TRUE;
            }
            else
            {
                for (daq_idx = 0x00u; daq_idx < Xcp_Ptr->general->daqCount; daq_idx++)
                {
                    /* Then, we check if the received PDU ID is one which has been configured for a DAQ stimulation. */
                    if ((Xcp_Ptr->config->daqList[daq_idx].type == STIM) ||
                        (Xcp_Ptr->config->daqList[daq_idx].type == DAQ_STIM))
                    {
                        for (dto_idx = 0x00u; dto_idx < Xcp_Ptr->config->daqList[daq_idx].dtoCount;
                             dto_idx++)
                        {
                            if ((Xcp_Ptr->config->daqList[daq_idx]
                                     .dto[dto_idx]
                                     .dto2PduMapping.rxPdu.id) == rxPduId)
                            {
                                valid_pdu_id = TRUE;

                                break;
                            }
                        }
                    }

                    if (valid_pdu_id == TRUE)
                    {
                        break;
                    }
                }
            }

            if (valid_pdu_id == TRUE) {
                if ((pPduInfo->SduLength >= 0x01u) && (pPduInfo->SduDataPtr != NULL_PTR)) {

                    pid = pPduInfo->SduDataPtr[0x00u];

                    /* XCP part 1 - Overview 1.0/2.3
                     * In “DISCONNECTED” state, there’s no XCP communication. The session status,
                     * all DAQ lists and the protection status bits are reset, which means that DAQ
                     * list transfer is inactive and the seed and key procedure is necessary for all
                     * protected functions.
                     * In “DISCONNECTED” state, the slave processes no XCP commands except for
                     * CONNECT. */
                    if ((pid == XCP_PID_CMD_CONNECT) || (Xcp_Internal.connection_status != XCP_CONNECTION_STATE_DISCONNECTED)) {

                        /* XCP part 2 - Protocol Layer Specification 1.0/1.7.3.1
                         * Check if the received Command/Transfer object is activated/allowed. If it is not the case, return an error packet with the
                         * error code ERR_CMD_UNKNOWN. */
                        if ((Xcp_Ptr->general->ctoInfo[pid] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u)
                        {
                            /* Check if a CTO has been received, as the handling of such kind of
                             * packets is different from DTO packets. In the above lines, we handle all the behavior which is common for all CTOs.
                             */
                            if ((Xcp_Ptr->general->ctoInfo[pid] & XCP_CTO_INFO_IS_CTO_MASK) != 0x00u) {
                                /* XCP part 2 - Protocol Layer Specification 1.0/1.7.3.1
                                 * Check if the received CTO reacts to ERR_CMD_BUSY error. If so, check if the CTO response ongoing flag is set, and
                                 * return an error packet with the error code ERR_CMD_BUSY. */
                                if (((Xcp_CTOErrorMatrix[pid] & XCP_INTERNAL_ERR_CMD_BUSY) == 0x00u) ||
                                    (((Xcp_CTOErrorMatrix[pid] & XCP_INTERNAL_ERR_CMD_BUSY) != 0x00u) && (Xcp_Internal.cto_response.successful_transmission_pending == FALSE)))
                                {
                                    /* XCP part 2 - Protocol Layer Specification 1.0/1.7.3.1
                                     * Check if the received CTO reacts to ERR_CMD_SYNTAX error. If so, check if the received PDU size is at least the
                                     * minimum size of the request. We are not using an equality operator, as some payload might vary depending on the
                                     * static configuration. For those cases, the additional checks are performed within the CTO handler function. */
                                    if (((Xcp_CTOErrorMatrix[pid] & XCP_INTERNAL_ERR_CMD_SYNTAX) == 0x00u) ||
                                        (((Xcp_CTOErrorMatrix[pid] & XCP_INTERNAL_ERR_CMD_SYNTAX) != 0x00u) &&
                                         (pPduInfo->SduLength >= (Xcp_Ptr->general->ctoInfo[pid] & XCP_CTO_INFO_MIN_REQUEST_SIZE_MASK))))
                                    {
                                        /* XCP part 2 - Protocol Layer Specification 1.0/1.7.3.1
                                         * Check if the received CTO reacts to ERR_PGM_ACTIVE error. If so, check if there is an ongoing
                                         * calibration/DAQ storing/DAQ clearing process in the session. If so, we return an error packet with the
                                         * error code ERR_PGM_ACTIVE. */
                                        if (((Xcp_CTOErrorMatrix[pid] & XCP_INTERNAL_ERR_PGM_ACTIVE) == 0x00u) ||
                                            (((Xcp_CTOErrorMatrix[pid] & XCP_INTERNAL_ERR_PGM_ACTIVE) != 0x00u) &&
                                             ((Xcp_Internal.session_status & XCP_SESSION_STATUS_MASK_STORE_CAL_REQ) == 0x00u) &&
                                             ((Xcp_Internal.session_status & XCP_SESSION_STATUS_MASK_STORE_DAQ_REQ) == 0x00u) &&
                                             ((Xcp_Internal.session_status & XCP_SESSION_STATUS_MASK_CLEAR_DAQ_REQ) == 0x00u)))
                                        {
                                            if (((Xcp_PIDToCmdGroupTable[pid] & Xcp_Ptr->general->protectedResource) == 0x00u) ||
                                                ((Xcp_PIDToCmdGroupTable[pid] & Xcp_GetProtectionStatus()) != 0x00u))
                                            {
                                                result = Xcp_PIDTable[pid](rxPduId, pPduInfo);

                                                Xcp_Internal.last_pid = pid;

                                                if (pid != XCP_PID_CMD_UNLOCK) {
                                                    Xcp_ClearProtectionStatus();
                                                }
                                            }
                                        }
                                        else
                                        {
                                            Xcp_FillErrorPacket(XCP_E_ASAM_PGM_ACTIVE, &Xcp_Internal.cto_response.pdu_info);
                                        }
                                    }
                                    else
                                    {
                                        Xcp_FillErrorPacket(XCP_E_ASAM_CMD_SYNTAX, &Xcp_Internal.cto_response.pdu_info);
                                    }
                                }
                                else
                                {
                                    Xcp_FillErrorPacket(XCP_E_ASAM_CMD_BUSY, &Xcp_Internal.cto_response.pdu_info);
                                }

                                Xcp_Internal.cto_response.successful_transmission_pending = TRUE;
                            }
                            else
                            {
                                /* TODO: handle DTOs common code here... */
                            }
                        }
                        else
                        {
                            Xcp_FillErrorPacket(XCP_E_ASAM_CMD_UNKNOWN, &Xcp_Internal.cto_response.pdu_info);
                        }
                    }

                    if (result != E_OK) {
                        Xcp_ReportError(0x00u, XCP_CAN_IF_RX_INDICATION_API_ID, result);
                    }
                }
            } else {
                Xcp_ReportError(0x00u, XCP_CAN_IF_RX_INDICATION_API_ID, XCP_E_INVALID_PDUID);
            }
        }
        else
        {
            Xcp_ReportError(0x00u, XCP_CAN_IF_RX_INDICATION_API_ID, XCP_E_PARAM_POINTER);
        }
    }
    else
    {
        Xcp_ReportError(0x00u, XCP_CAN_IF_RX_INDICATION_API_ID, XCP_E_UNINIT);
    }
}

void Xcp_CanIfTxConfirmation(PduIdType txPduId, Std_ReturnType result)
{
    (void)txPduId;

    if (Xcp_State == XCP_INITIALIZED) {
        switch (Xcp_Internal.ongoing_transmit_type)
        {
            case ONGOING_TRANSMIT_TYPE_NONE:
            {

                break;
            }
            case ONGOING_TRANSMIT_TYPE_CTO:
            {
                Xcp_Internal.ongoing_transmit_type = ONGOING_TRANSMIT_TYPE_NONE;

                if (result == E_OK)
                {
                    if (Xcp_BlockTransferIsActive() == TRUE)
                    {
                        Xcp_BlockTransferAcknowledgeFrame();

                        if (Xcp_BlockTransferPrepareNextFrame() != E_OK)
                        {
                            Xcp_Internal.cto_response.successful_transmission_pending = FALSE;
                        }
                    }
                    else
                    {
                        Xcp_Internal.cto_response.successful_transmission_pending = FALSE;
                    }
                }

                break;
            }
            case ONGOING_TRANSMIT_TYPE_EVENT:
            {
                Xcp_Internal.ongoing_transmit_type = ONGOING_TRANSMIT_TYPE_NONE;

                if (result == E_OK)
                {
                    if (Xcp_EventQueuePop(Xcp_Rt[Xcp_Ptr->xcpRtRef].eventQueue) == E_OK) {
                        Xcp_Internal.event.successful_transmission_pending = FALSE;
                    }
                }

                break;
            }
        }
    } else {
        Xcp_ReportError(0x00u, XCP_CAN_IF_TX_CONFIRMATION_API_ID, XCP_E_UNINIT);
    }
}

Std_ReturnType Xcp_CanIfTriggerTransmit(PduIdType txPduId, PduInfoType *pPduInfo)
{
    (void)txPduId;
    (void)pPduInfo;

    Std_ReturnType result = E_NOT_OK;

    if (Xcp_State == XCP_INITIALIZED) {
        result = E_OK;
    } else {
        Xcp_ReportError(0x00u, XCP_CAN_IF_TRIGGER_TRANSMIT_API_ID, XCP_E_UNINIT);
    }

    return result;
}

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* local function definitions (static).                                                           */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_LFDEF
 * @{
 */

static uint8 Xcp_DTOCmdDaqAllocOdtEntry(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqAllocOdt(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqAllocDaq(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqFreeDaq(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqGetDaqEventInfo(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqGetDaqListInfo(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqGetDaqResolutionInfo(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqGetDaqProcessorInfo(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqReadDaq(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqGetDaqClock(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqStartStopSynch(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqStartStopDaqList(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqGetDaqListMode(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqSetDaqListMode(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqWriteDaq(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqSetDaqPtr(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdDaqClearDaqList(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTODaqStimPacket(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTODaqPacket(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    return E_OK;
}

static uint8 Xcp_DTOCmdStdUserCmd(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    uint8 result = E_OK;

    (void)rxPduId;

    if (Xcp_Ptr->general->userCmdFunction != NULL_PTR) {
        result = Xcp_Ptr->general->userCmdFunction(pPduInfo, &Xcp_Internal.cto_response.pdu_info);

        Xcp_FinalizeResPacket(Xcp_Internal.cto_response.pdu_info.SduLength, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        result = XCP_E_PARAM_POINTER;
    }

    return result;
}

static uint8 Xcp_DTOCmdStdTransportLayerCmd(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;

    uint8_least object_found;
    uint16 daq_list_idx;
    uint8 sub_command;
    uint8 mode;
    uint16 daq_list_number;
    // uint32 can_identifier;

    if (pPduInfo->SduLength >= 0x02u) {
        sub_command = pPduInfo->SduDataPtr[0x01u];

        if (sub_command == 0xFFu) {
            if (pPduInfo->SduLength >= 0x05u) {
                mode = pPduInfo->SduDataPtr[0x05u];

                if (((pPduInfo->SduDataPtr[0x02u] == 0x58u) && (pPduInfo->SduDataPtr[0x03u] == 0x43u) && (pPduInfo->SduDataPtr[0x04u] == 0x50u)) &&
                    ((mode == 0x00u) || (mode == 0x01u))) {

                    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

                    if (mode == 0x00u) {
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x58u;
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0x43u;
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x50u;
                    } else {
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0xA7u;
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0xBCu;
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0xAFu;
                    }

                    Xcp_CopyFromU32WithOrder((uint32)Xcp_Ptr->config->communicationChannel->channel_rx_pdu_ref->id,
                                             &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u],
                                             Xcp_Ptr->general->byteOrder);

                    Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);
                } else {
                    Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
                }
            } else {
                Xcp_FillErrorPacket(XCP_E_ASAM_CMD_SYNTAX, &Xcp_Internal.cto_response.pdu_info);
            }
        } else if (sub_command == 0xFEu) {
            if (pPduInfo->SduLength >= 0x04u) {
                Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &daq_list_number, Xcp_Ptr->general->byteOrder);

                object_found = FALSE;

                for (daq_list_idx = 0x00u; daq_list_idx < Xcp_Ptr->config->daqListCount; daq_list_idx ++) {
                    if (Xcp_Ptr->config->daqList[daq_list_idx].number == daq_list_number) {
                        object_found = TRUE;

                        break;
                    }
                }

                if (object_found == TRUE) {
                    if (Xcp_Ptr->config->daqList[daq_list_idx].dtoCount > 0x00u) {
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x01u; // TODO: support configurable CAN ID...
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0x00u;
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u;
                        Xcp_CopyFromU32WithOrder((uint32)Xcp_Ptr->config->daqList[daq_list_idx].dto[0x00u].dto2PduMapping.txPdu.id,
                                                 &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u],
                                                 Xcp_Ptr->general->byteOrder);

                        Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);
                    } else {

                    }
                } else {
                    Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
                }
            } else {
                Xcp_FillErrorPacket(XCP_E_ASAM_CMD_SYNTAX, &Xcp_Internal.cto_response.pdu_info);
            }
        }else if (sub_command == 0xFDu) {
            if (pPduInfo->SduLength >= 0x08u) {
                // Xcp_CopyToU16WithOrder(&Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u], &daq_list_number, Xcp_Ptr->general->byteOrder);
                // Xcp_CopyToU32WithOrder(&Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u], &can_identifier, Xcp_Ptr->general->byteOrder);

                // TODO: implement this feature...
                Xcp_FillErrorPacket(XCP_E_ASAM_CMD_UNKNOWN, &Xcp_Internal.cto_response.pdu_info);
            } else {
                Xcp_FillErrorPacket(XCP_E_ASAM_CMD_SYNTAX, &Xcp_Internal.cto_response.pdu_info);
            }
        } else {
            Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
        }
    } else {
        Xcp_FillErrorPacket(XCP_E_ASAM_CMD_SYNTAX, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

static uint8 Xcp_DTOCmdStdBuildChecksum(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    void *upper_address;
    uint32_least block_size;
    uint8 checksum_type;
    uint32 checksum;
    uint8 element_size;
    void * (*checksum_function)(void *, const void *, uint32 *) = NULL_PTR;

    (void)rxPduId;

    Xcp_CopyToU32WithOrder(&pPduInfo->SduDataPtr[0x04u], &block_size, Xcp_Ptr->general->byteOrder);

    if (block_size > 0x00u)
    {
        element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);

        upper_address = Xcp_Internal.memory_transfer.address + (element_size * block_size);

        switch (Xcp_Ptr->general->checksumType)
        {
            case XCP_ADD_11:
            {
                checksum_type = 0x01u;
                checksum_function = Xcp_BuildChecksum11;

                break;
            }
            case XCP_ADD_12:
            {
                checksum_type = 0x02u;
                checksum_function = Xcp_BuildChecksum12;

                break;
            }
            case XCP_ADD_14:
            {
                checksum_type = 0x03u;
                checksum_function = Xcp_BuildChecksum14;

                break;
            }
            case XCP_ADD_22:
            {
                checksum_type = 0x04u;
                checksum_function = Xcp_BuildChecksum22;

                break;
            }
            case XCP_ADD_24:
            {
                checksum_type = 0x05u;
                checksum_function = Xcp_BuildChecksum24;

                break;
            }
            case XCP_ADD_44:
            {
                checksum_type = 0x06u;
                checksum_function = Xcp_BuildChecksum44;

                break;
            }
            case XCP_CRC_16:
            {
                checksum_type = 0x07u;
                checksum_function = Xcp_BuildChecksumCRC16;

                break;
            }
            case XCP_CRC_16_CITT:
            {
                checksum_type = 0x08u;
                checksum_function = Xcp_BuildChecksumCRC16CITT;

                break;
            }
            case XCP_CRC_32:
            {
                checksum_type = 0x09u;
                checksum_function = Xcp_BuildChecksumCRC32;

                break;
            }
            case XCP_USER_DEFINED:
            {
                checksum_type = 0xFFu;
                checksum_function = Xcp_Ptr->general->userDefinedChecksumFunction;

                break;
            }
            default:
            {
                checksum_type = 0x0Au;

                break;
            }
        }

        if (checksum_type != 0x0Au) {
            if (checksum_function != NULL_PTR) {
                Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
                Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = checksum_type;
                Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0x00u;
                Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u;

                Xcp_Internal.memory_transfer.address = checksum_function(Xcp_Internal.memory_transfer.address, upper_address, &checksum);

                Xcp_CopyFromU32WithOrder(checksum, &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u], Xcp_Ptr->general->byteOrder);

                Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);
            } else {
                Xcp_ReportError(0x00u, XCP_CAN_IF_RX_INDICATION_API_ID, XCP_E_PARAM_POINTER);
                Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
            }
        } else {
            Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
        }
    }
    else
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

static uint8 Xcp_DTOCmdStdShortUpload(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    uint8_least idx;
    uint8_least element_size = 0x00u;
    uint32 address;

    (void)rxPduId;

    if (pPduInfo->SduDataPtr[0x01u] != 0x00u)
    {

        element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);

        if (element_size != 0x00u)
        {
            if ((pPduInfo->SduDataPtr[0x01u] * element_size) <= (Xcp_Ptr->general->maxCto - 0x01u))
            {
                Xcp_CopyToU32WithOrder(&pPduInfo->SduDataPtr[0x04u], &address, Xcp_Ptr->general->byteOrder);

                Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

                for (idx = 0x01u; idx < element_size; idx++)
                {
                    Xcp_Internal.cto_response.pdu_info.SduDataPtr[idx] = 0x00u;
                }

                for (idx = 0x00u; idx < pPduInfo->SduDataPtr[0x01u]; idx++)
                {
                    Xcp_ReadSlaveMemoryTable[Xcp_Ptr->general->addressGranularity](
                        (void *)address,
                        pPduInfo->SduDataPtr[0x03u],
                        &Xcp_Internal.cto_response.pdu_info.SduDataPtr[(idx + 0x01u) * element_size]);

                        //TODO: Set SduLength correctly here...

                    address += element_size;
                }
            }
            else
            {
                Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
            }
        }
    }
    else
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

static uint8 Xcp_DTOCmdStdUpload(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;

    const uint8 number_of_data_elements = pPduInfo->SduDataPtr[0x01u];
    uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.7
     * If the slave device does not support block transfer mode, all uploaded data are transferred in a single response packet. Therefore, the number
     * of data elements parameter in the request has to be in the range [1..MAX_CTO-1]. An ERR_OUT_OF_RANGE will be returned, if the number of data
     * elements is more than MAX_CTO-1.*/
    if (((Xcp_Ptr->general->slaveBlockModeSupported == FALSE) &&
         ((number_of_data_elements * element_size) <= (Xcp_Ptr->general->maxCto - 0x01u - (element_size - 0x01u)))) ||
        (Xcp_Ptr->general->slaveBlockModeSupported == TRUE))
    {
        if (Xcp_BlockTransferInitialize(number_of_data_elements) == E_OK)
        {
            /* It is not necessary to check the return value, as we have at least one element to transfer (checked above). */
            (void)Xcp_BlockTransferPrepareNextFrame();
        }
        else
        {
            Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
        }
    }
    else
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

static uint8 Xcp_DTOCmdStdSetMta(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;

    Xcp_Internal.memory_transfer.extension = pPduInfo->SduDataPtr[0x03u];
    Xcp_CopyToU32WithOrder(&pPduInfo->SduDataPtr[0x04u], (uint32 *)&Xcp_Internal.memory_transfer.address, Xcp_Ptr->general->byteOrder);

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
    Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

static uint8 Xcp_DTOCmdStdUnlock(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    uint16_least key_idx;
    uint16_least num_of_bytes_to_copy;

    (void)rxPduId;

    if ((Xcp_Internal.last_pid == XCP_PID_CMD_GET_SEED) || (Xcp_Internal.last_pid == XCP_PID_CMD_UNLOCK))
    {
        if (pPduInfo->SduDataPtr[0x01u] >= 0x01u)
        {
            /* Extract the key length from the size communicated in the first frame. */
            if (Xcp_Internal.key_master.total_length == 0x00u)
            {
                Xcp_Internal.key_master.total_length = pPduInfo->SduDataPtr[0x01u];
                Xcp_Internal.key_master.current_index = 0x00u;
            }

            /* Check if the length of the remaining part of the key fits in the size communicated in the first frame. */
            if (pPduInfo->SduDataPtr[0x01u] <= Xcp_Internal.key_master.total_length - Xcp_Internal.key_master.current_index)
            {
                /* Extract the number of byte to copy from the active frame into the master key buffer. */
                if (pPduInfo->SduDataPtr[0x01u] <= (Xcp_Ptr->general->maxCto - 0x02u))
                {
                    num_of_bytes_to_copy = pPduInfo->SduDataPtr[0x01u];
                }
                else
                {
                    num_of_bytes_to_copy = Xcp_Ptr->general->maxCto - 0x02u;
                }

                for (key_idx = 0x00u; key_idx < num_of_bytes_to_copy; key_idx++)
                {
                    Xcp_Internal.key_master.buffer[Xcp_Internal.key_master.current_index++] = pPduInfo->SduDataPtr[key_idx + 0x02u];
                }

                Xcp_FinalizeResPacket(0x02u, &Xcp_Internal.cto_response.pdu_info);

                if (Xcp_Internal.key_master.total_length == Xcp_Internal.key_master.current_index)
                {
                    if (Xcp_CalcKey(&Xcp_Internal.seed.buffer[0x00u],
                                    Xcp_Internal.seed.total_length,
                                    &Xcp_Internal.key_slave.buffer[0x00u],
                                    sizeof(Xcp_Internal.key_slave.buffer) / sizeof(Xcp_Internal.key_slave.buffer[0x00u]),
                                    &Xcp_Internal.key_slave.total_length) == E_OK)
                    {
                        if (Xcp_CheckMasterSlaveKeyMatch(Xcp_Internal.key_slave.total_length,
                                                         &Xcp_Internal.key_slave.buffer[0x00u],
                                                         Xcp_Internal.key_master.total_length,
                                                         &Xcp_Internal.key_master.buffer[0x00u]) == E_OK)
                        {
                            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
                            Xcp_SetProtectionStatus();
                            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = Xcp_GetProtectionStatus();

                            Xcp_FinalizeResPacket(0x02u, &Xcp_Internal.cto_response.pdu_info);
                        }
                        else
                        {
                            Xcp_FillErrorPacket(XCP_E_ASAM_ACCESS_LOCKED, &Xcp_Internal.cto_response.pdu_info);

                            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.5
                             * The key is checked after completion of the UNLOCK sequence. If the key is not accepted, ERR_ACCESS_LOCKED will be
                             * returned. The slave device will then go to disconnected state. A repetition of an UNLOCK sequence with a correct key
                             * will have a positive response and no other effect. */
                            Xcp_Internal.connection_status = XCP_CONNECTION_STATE_DISCONNECTED;
                        }
                    }

                    /* Discard the key buffer, as we received a full key. */
                    Xcp_Internal.key_master.total_length = 0x00u;

                    /* Discard the seed buffer, as we received a full key. This enforces a new seed to be requested prior to unlock a next resource.
                     */
                    Xcp_Internal.seed.total_length = 0x00u;
                }
                else
                {
                    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
                    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = Xcp_GetProtectionStatus();
                }
            }
            else
            {
                Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
            }
        }
        else
        {
            Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
        }
    }
    else
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

static uint8 Xcp_DTOCmdStdGetSeed(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    uint8_least idx;
    uint8_least num_of_bytes_to_copy;
    uint8 mode;
    uint8 resource;

    Std_ReturnType result = E_OK;

    (void)rxPduId;
    (void)pPduInfo;

    mode = pPduInfo->SduDataPtr[0x01u];
    resource = pPduInfo->SduDataPtr[0x02u];

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.3
     * Only one resource may be requested with one GET_SEED command. If more than one resource has to be unlocked, the (GET_SEED+UNLOCK) sequence has
     * to be performed multiple times. If the master does not request any resource or requests multiple resources at the same time, the slave will
     * respond with an ERR_OUT_OF_RANGE.*/
    if (((mode == 0x00u) || (mode == 0x01u)) &&
        ((resource == XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG) || (resource == XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ) ||
         (resource == XCP_RESOURCE_PROTECTION_STATUS_MASK_STIM) || (resource == XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM)))
    {
        if (mode == 0x00u)
        {
            Xcp_Internal.requested_protected_resource = resource;
            Xcp_Internal.seed.total_length = 0x00u;
            Xcp_Internal.seed.current_index = 0x00u;

            if (Xcp_GetSeed(&Xcp_Internal.seed.buffer[0x00u], sizeof(Xcp_Internal.seed.buffer) / sizeof(Xcp_Internal.seed.buffer[0x00u]), &Xcp_Internal.seed.total_length) !=
                E_OK)
            {
                result = XCP_E_ASAM_OUT_OF_RANGE;
            }

            if (Xcp_Internal.seed.total_length == 0x00u)
            {
                result = XCP_E_ASAM_OUT_OF_RANGE;
            }
        }
        else
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.4
             * The master has to use GET_SEED(Mode=1) in a defined sequence together
             * with GET_SEED(Mode=0). If the master sends a GET_SEED(Mode=1)
             * directly without a previous GET_SEED(Mode=0), the slave returns an
             * ERR_SEQUENCE as negative response. */
            if (Xcp_Internal.seed.total_length != 0x00u)
            {
                /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.4
                 * Only one resource may be requested with one GET_SEED command. If more than one
                 * resource has to be unlocked, the (GET_SEED+UNLOCK) sequence has to be performed
                 * multiple times. If the master does not request any resource or requests multiple resources at
                 * the same time, the slave will respond with an ERR_OUT_OF_RANGE. */
                if (resource != Xcp_Internal.requested_protected_resource)
                {
                    result = XCP_E_ASAM_OUT_OF_RANGE;
                }
            }
            else
            {
                result = XCP_E_ASAM_SEQUENCE;
            }
        }
    }
    else
    {
        result = XCP_E_ASAM_OUT_OF_RANGE;
    }

    if (result == E_OK)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = Xcp_Internal.seed.total_length - Xcp_Internal.seed.current_index;

        if ((Xcp_Internal.seed.total_length - Xcp_Internal.seed.current_index) <= (Xcp_Ptr->general->maxCto - (uint8)0x02u))
        {
            num_of_bytes_to_copy = (Xcp_Internal.seed.total_length - Xcp_Internal.seed.current_index);
            Xcp_Internal.seed.total_length = 0x00u;
        }
        else
        {
            num_of_bytes_to_copy = Xcp_Ptr->general->maxCto - 0x02u;
        }

        for (idx = 0x02u; idx < num_of_bytes_to_copy + 0x02u; idx++)
        {
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[idx] = Xcp_Internal.seed.buffer[Xcp_Internal.seed.current_index++];
        }

        /* Fill the remaining bytes with 0s. */
        for (; idx < (Xcp_Ptr->general->maxCto); idx++)
        {
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[idx] = 0x00u;
        }
    }
    else
    {
        Xcp_FillErrorPacket(result, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

static uint8 Xcp_DTOCmdStdSetRequest(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    uint8 mode;
    uint16 session_configuration_id;

    Std_ReturnType result = E_OK;

    (void)rxPduId;

    if ((pPduInfo->SduDataPtr[0x01u] & 0b11110010u) != 0x00u)
    {
        result = XCP_E_ASAM_OUT_OF_RANGE;
    }
    else
    {
        mode = pPduInfo->SduDataPtr[0x01u];
    }

    if (result == E_OK)
    {
        Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &session_configuration_id, Xcp_Ptr->general->byteOrder);

        /* TODO: this is most likely not the correct way to handle the session id, this must be implemented... */
        if (session_configuration_id != 0x00u)
        {
            result = XCP_E_ASAM_OUT_OF_RANGE;
        }

        Xcp_Internal.session_status |= mode;

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_FillErrorPacket(result, &Xcp_Internal.cto_response.pdu_info);
    }

    return result;
}

static uint8 Xcp_DTOCmdStdGetId(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    Std_ReturnType result = E_OK;

    uint32 identification_length;

    (void)rxPduId;

    const uint8 identification_type = pPduInfo->SduDataPtr[0x01u];
    const char *identification = Xcp_Ptr->general->identification;

    for (identification_length = 0x00000000u; identification_length < 0xFFFFFFFFu; identification_length++)
    {
        if (identification[identification_length] == 0x00u)
        {
            break;
        }
    }

    if (identification_type == 0x00u)
    {
        Xcp_Internal.memory_transfer.address = (void *)Xcp_Ptr->general->identification;

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0x00u;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u;
        Xcp_CopyFromU32WithOrder(identification_length, &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u], Xcp_Ptr->general->byteOrder);

        Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }

    return result;
}

static uint8 Xcp_DTOCmdStdGetCommModeInfo(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    uint8 comm_mode_optional = 0x00u;

    if (Xcp_Ptr->general->masterBlockModeSupported == TRUE)
    {
        comm_mode_optional |= (0x01u << 0x00u);
    }

    if (Xcp_Ptr->general->interleavedModeSupported == TRUE)
    {
        comm_mode_optional |= (0x01u << 0x01u);
    }

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = comm_mode_optional;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u] = Xcp_Ptr->general->maxBS;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x05u] = Xcp_Ptr->general->minST;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x06u] = Xcp_Ptr->general->ctoQueueSize;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x07u] = ((XCP_SW_MAJOR_VERSION & 0x0Fu) << 0x04u) | (XCP_SW_MINOR_VERSION & 0x0F);

    Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

static uint8 Xcp_CTOCmdStdSynch(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_ERROR;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = XCP_E_ASAM_CMD_SYNCH;

    Xcp_FinalizeResPacket(0x02u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

static uint8 Xcp_CTOCmdStdGetStatus(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = Xcp_Internal.session_status;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = Xcp_GetProtectionStatus();
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u] = 0xABu; /* TODO: implement me... */
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x05u] = 0xCDu; /* TODO: implement me... */

    Xcp_FinalizeResPacket(0x06u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

static uint8 Xcp_CTOCmdStdDisconnect(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    (void)rxPduId;
    (void)pPduInfo;

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

    Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);

    Xcp_Internal.connection_status = XCP_CONNECTION_STATE_DISCONNECTED;

    return E_OK;
}

static uint8 Xcp_CTOCmdStdConnect(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    uint8 resource = 0x00u;
    uint8 comm_mode_basic = 0x00u;

    uint8 mode = XCP_CONNECT_MODE_NORMAL;

    uint8 daq_idx;

    (void)rxPduId;

    if ((pPduInfo->SduLength >= 0x02u) && (pPduInfo->SduDataPtr[0x01u] != XCP_CONNECT_MODE_NORMAL))
    {
        mode = XCP_CONNECT_MODE_USER_DEFINED;
    }

    Xcp_Internal.connect_mode = mode;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.1
     * CALibration and PAGing
     * 0 = calibration/ paging not available
     * 1 = calibration/ paging available
     * The commands DOWNLOAD, DOWNLOAD_MAX, SHORT_DOWNLOAD, SET_CAL_PAGE, GET_CAL_PAGE are
     * available. */
    if (((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_DOWNLOAD] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_DOWNLOAD_MAX] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_SHORT_DOWNLOAD] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_SET_CAL_PAGE] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_GET_CAL_PAGE] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u)) {
        resource |= 0x01u;
    }

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.1
     * DAQ lists supported
     * 0 = DAQ lists not available
     * 1 = DAQ lists available
     * The DAQ commands (GET_DAQ_PROCESSOR_INFO, GET_DAQ_LIST_INFO, ...) are available. */
    if (((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_CLEAR_DAQ_LIST] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_SET_DAQ_PTR] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_WRITE_DAQ] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_SET_DAQ_LIST_MODE] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_GET_DAQ_LIST_MODE] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_START_STOP_DAQ_LIST] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_START_STOP_SYNCH] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_GET_DAQ_CLOCK] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_READ_DAQ] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_GET_DAQ_PROCESSOR_INFO] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_GET_DAQ_RESOLUTION_INFO] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_GET_DAQ_LIST_INFO] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_GET_DAQ_EVENT_INFO] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_FREE_DAQ] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_ALLOC_DAQ] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_ALLOC_ODT] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_ALLOC_ODT_ENTRY] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u))
    {
        resource |= (0x01u << 0x02u);
    }

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.1
     * STIMulation
     * 0 = stimulation not available
     * 1 = stimulation available
     * data stimulation mode of a DAQ list available. */
    for (daq_idx = 0x00u; daq_idx < Xcp_Ptr->general->daqCount; daq_idx ++) {
        if ((Xcp_Ptr->config->daqList[daq_idx].type == STIM) ||
            (Xcp_Ptr->config->daqList[daq_idx].type == DAQ_STIM))
        {
            resource |= (0x01u << 0x03u);

            break;
        }
    }

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.1
     * ProGraMming
     * 0 = Flash programming not available
     * 1 = Flash programming available
     * The commands PROGRAM_CLEAR, PROGRAM, PROGRAM_MAX are available. */
    if (((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_PROGRAM_CLEAR] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_PROGRAM] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_PROGRAM_MAX] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u)) {
        resource |= (0x01u << 0x04u);
    }

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.1
     * BYTE_ORDER indicates the byte order used for transferring multi-byte parameters in an
     * XCP Packet. BYTE_ORDER = 0 means Intel format, BYTE_ORDER = 1 means Motorola format.
     * Motorola format means MSB on lower address/position. */
    if (Xcp_Ptr->general->byteOrder == XCP_BIG_ENDIAN) {
        comm_mode_basic |= 0x01u;
    }

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.1
     * The address granularity indicates the size of an element contained at a single
     * address. It is needed if the master has to do address calculation. */
    if (Xcp_Ptr->general->addressGranularity == WORD) {
        comm_mode_basic |= (0x01u << 0x01u);
    } else if (Xcp_Ptr->general->addressGranularity == DWORD) {
        comm_mode_basic |= (0x01u << 0x02u);
    } else {
        /* we leave BYTE granularity by default here... */
    }

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.1
     * The SLAVE_BLOCK_MODE flag indicates whether the Slave Block Mode is available. */
    if (Xcp_Ptr->general->slaveBlockModeSupported == TRUE) {
        comm_mode_basic |= (0x01u << 0x06u);
    }

    if ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_GET_COMM_MOD_INFO] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) {
        comm_mode_basic |= (0x01u << 0x07u);
    }

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = resource;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = comm_mode_basic;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = Xcp_Ptr->general->maxCto;
    Xcp_CopyFromU16WithOrder(Xcp_Ptr->general->maxDto, &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u], Xcp_Ptr->general->byteOrder);
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x06u] = XCP_PROTOCOL_LAYER_VERSION;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x07u] = XCP_TRANSPORT_LAYER_VERSION;

    Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);

    Xcp_Internal.connection_status = XCP_CONNECTION_STATE_CONNECTED;

    return E_OK;
}

static void *Xcp_BuildChecksum11(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
    void *p_current_address;
    uint8 crc = 0x00u;

    for (p_current_address = pLowerAddress; p_current_address < pUpperAddress; p_current_address ++)
    {
        Xcp_ReadSlaveMemoryU8(p_current_address, Xcp_Internal.memory_transfer.extension, &Xcp_Internal.internal_buffer[0x00u]);

        crc += Xcp_Internal.internal_buffer[0x00u];
    }

    *pResult = (uint32)crc;

    return p_current_address;
}

static void *Xcp_BuildChecksum12(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
    void *p_current_address;
    uint16 crc = 0x0000u;

    for (p_current_address = pLowerAddress; p_current_address < pUpperAddress; p_current_address ++)
    {
        Xcp_ReadSlaveMemoryU8(p_current_address, Xcp_Internal.memory_transfer.extension, &Xcp_Internal.internal_buffer[0x00u]);

        crc += Xcp_Internal.internal_buffer[0x00u];
    }

    *pResult = (uint32)crc;

    return p_current_address;
}

static void *Xcp_BuildChecksum14(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
    void *p_current_address;
    uint32 crc = 0x00000000u;

    for (p_current_address = pLowerAddress; p_current_address < pUpperAddress; p_current_address ++)
    {
        Xcp_ReadSlaveMemoryU8(p_current_address, Xcp_Internal.memory_transfer.extension, &Xcp_Internal.internal_buffer[0x00u]);

        crc += Xcp_Internal.internal_buffer[0x00u];
    }

    *pResult = (uint32)crc;

    return p_current_address;
}

static void *Xcp_BuildChecksum22(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
    uint16 u16_data;
    void *p_current_address;
    uint16 crc = 0x0000u;

    for (p_current_address = pLowerAddress; p_current_address < pUpperAddress; p_current_address += 0x02u)
    {
        Xcp_ReadSlaveMemoryU16(p_current_address, Xcp_Internal.memory_transfer.extension, &Xcp_Internal.internal_buffer[0x00u]);

        Xcp_CopyToU16WithOrder(&Xcp_Internal.internal_buffer[0x00u], &u16_data, Xcp_Ptr->general->byteOrder);

        crc += u16_data;
    }

    *pResult = (uint32)crc;

    return p_current_address;
}

static void *Xcp_BuildChecksum24(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
    uint16 u16_data;
    void *p_current_address;
    uint32 crc = 0x00000000u;

    for (p_current_address = pLowerAddress; p_current_address < pUpperAddress; p_current_address += 0x02u)
    {
        Xcp_ReadSlaveMemoryU16(p_current_address, Xcp_Internal.memory_transfer.extension, &Xcp_Internal.internal_buffer[0x00u]);

        Xcp_CopyToU16WithOrder(&Xcp_Internal.internal_buffer[0x00u], &u16_data, Xcp_Ptr->general->byteOrder);

        crc += u16_data;
    }

    *pResult = crc;

    return p_current_address;
}

static void *Xcp_BuildChecksum44(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
    uint32 u32_data;
    void *p_current_address;
    uint32 crc = 0x00000000u;

    for (p_current_address = pLowerAddress; p_current_address < pUpperAddress; p_current_address += 0x04u)
    {
        Xcp_ReadSlaveMemoryU32(p_current_address, Xcp_Internal.memory_transfer.extension, &Xcp_Internal.internal_buffer[0x00u]);

        Xcp_CopyToU32WithOrder(&Xcp_Internal.internal_buffer[0x00u], &u32_data, Xcp_Ptr->general->byteOrder);

        crc += u32_data;
    }

    *pResult = crc;

    return p_current_address;
}

static void *Xcp_BuildChecksumCRC16(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
    void *p_current_address;
    uint16 remainder = 0x0000u;

    for (p_current_address = pLowerAddress; p_current_address < pUpperAddress; p_current_address ++)
    {
        Xcp_ReadSlaveMemoryU8(p_current_address, Xcp_Internal.memory_transfer.extension, &Xcp_Internal.internal_buffer[0x00u]);
        remainder = (remainder >> 0x08u) ^ Xcp_CRC16Table[(remainder ^ Xcp_Internal.internal_buffer[0x00u]) & 0xFFu];
    }

    remainder ^= 0x0000u;

    *pResult = remainder;

    return p_current_address;
}

static void *Xcp_BuildChecksumCRC16CITT(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
    void *p_current_address;
    uint16 remainder = 0xFFFFu;

    for (p_current_address = pLowerAddress; p_current_address < pUpperAddress; p_current_address ++)
    {
        Xcp_ReadSlaveMemoryU8(p_current_address, Xcp_Internal.memory_transfer.extension, &Xcp_Internal.internal_buffer[0x00u]);
        remainder = (remainder << 0x08u) ^ Xcp_CRC16CITTTable[(remainder >> 0x08u) ^ Xcp_Internal.internal_buffer[0x00u]];
    }

    remainder ^= 0x0000u;

    *pResult = remainder;

    return p_current_address;
}

static void *Xcp_BuildChecksumCRC32(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
    void *p_current_address;
    uint32 remainder = 0xFFFFFFFFu;

    for (p_current_address = pLowerAddress; p_current_address < pUpperAddress; p_current_address ++)
    {
        Xcp_ReadSlaveMemoryU8(p_current_address, Xcp_Internal.memory_transfer.extension, &Xcp_Internal.internal_buffer[0x00u]);
        remainder = (remainder >> 0x08u) ^ Xcp_CRC32Table[(remainder ^ Xcp_Internal.internal_buffer[0x00u]) & 0xFFu];
    }

    remainder ^= 0xFFFFFFFFu;

    *pResult = remainder;

    return p_current_address;
}

static void Xcp_CopyFromU16WithOrder(const uint16 src, uint8 *pDest, Xcp_ByteOrderType endianness)
{
    if (endianness == XCP_LITTLE_ENDIAN) {
        pDest[0x00u] = (uint8)(src & 0xFFu);
        pDest[0x01u] = (uint8)((src >> 0x08u) & 0xFFu);
    } else {
        pDest[0x01u] = (uint8)(src & 0xFFu);
        pDest[0x00u] = (uint8)((src >> 0x08u) & 0xFFu);
    }
}

static void Xcp_CopyFromU32WithOrder(const uint32 src, uint8 *pDest, Xcp_ByteOrderType endianness)
{
    if (endianness == XCP_LITTLE_ENDIAN) {
        pDest[0x00u] = (uint8)(src & 0xFFu);
        pDest[0x01u] = (uint8)((src >> 0x08u) & 0xFFu);
        pDest[0x02u] = (uint8)((src >> 0x10u) & 0xFFu);
        pDest[0x03u] = (uint8)((src >> 0x18u) & 0xFFu);
    } else {
        pDest[0x03u] = (uint8)(src & 0xFFu);
        pDest[0x02u] = (uint8)((src >> 0x08u) & 0xFFu);
        pDest[0x01u] = (uint8)((src >> 0x10u) & 0xFFu);
        pDest[0x00u] = (uint8)((src >> 0x18u) & 0xFFu);
    }
}

static void Xcp_CopyToU16WithOrder(const uint8 *pSrc, uint16 *pDest, Xcp_ByteOrderType endianness)
{
    if (endianness == XCP_LITTLE_ENDIAN)
    {
        *pDest = ((uint16)pSrc[0x00u] |
                  ((uint16)pSrc[0x01u] << 0x08u));
    }
    else
    {
        *pDest = ((uint16)pSrc[0x01u] |
                  ((uint16)pSrc[0x00u] << 0x08u));
    }
}

static void Xcp_CopyToU32WithOrder(const uint8 *pSrc, uint32 *pDest, Xcp_ByteOrderType endianness)
{
    if (endianness == XCP_LITTLE_ENDIAN)
    {
        *pDest = ((uint32)pSrc[0x00u] |
                  ((uint32)pSrc[0x01u] << 0x08u) |
                  ((uint32)pSrc[0x02u] << 0x10u) |
                  ((uint32)pSrc[0x03u] << 0x18u));
    }
    else
    {
        *pDest = ((uint32)pSrc[0x03u] |
                  ((uint32)pSrc[0x02u] << 0x08u) |
                  ((uint32)pSrc[0x01u] << 0x10u) |
                  ((uint32)pSrc[0x00u] << 0x18u));
    }
}

static void Xcp_EventQueueInit(Xcp_EventQueueType *pEventQueue) {
    uint32_least idx0;
    uint32_least idx1;

    pEventQueue->read = 0x00u;
    pEventQueue->write = 0x00u;

    for (idx0 = 0x00000000u; idx0 < Xcp_Ptr->general->eventQueueSize; idx0++)
    {
        pEventQueue->queue[idx0].packetID = 0x00u;
        pEventQueue->queue[idx0].eventCode = 0x00u;

        for (idx1 = 0x00000000u; idx1 < XCP_EVENT_USER_DATA_SIZE; idx1++)
        {
            pEventQueue->queue[idx0].userData[idx1] = 0x00u;
        }
    }
}

static Std_ReturnType Xcp_EventQueuePush(Xcp_EventQueueType *pEventQueue, uint8 packetID, uint8 eventCode, const uint8 *pUserData, uint32 userDataSize)
{
    Std_ReturnType result;
    uint32_least idx;

    const uint32 next = (pEventQueue->write + 0x01u) & (Xcp_Ptr->general->eventQueueSize - 0x01u);

    if ((pEventQueue->read != next) && (userDataSize <= XCP_EVENT_USER_DATA_SIZE)) {
        pEventQueue->queue[pEventQueue->write].packetID = packetID;
        pEventQueue->queue[pEventQueue->write].eventCode = eventCode;
        pEventQueue->queue[pEventQueue->write].userDataSize = userDataSize;

        for (idx = 0x00000000u; idx < userDataSize; idx ++)
        {
            pEventQueue->queue[pEventQueue->write].userData[idx] = pUserData[idx];
        }

        pEventQueue->write = next;

        result = E_OK;
    } else {
        result = E_NOT_OK;
    }

    return result;
}

static Std_ReturnType Xcp_EventQueueGet(Xcp_EventQueueType *pEventQueue, uint8 *pPacketID, uint8 *pEventCode) {
    Std_ReturnType result;

    if (pEventQueue->read != pEventQueue->write) {
        *pPacketID = pEventQueue->queue[pEventQueue->read].packetID;
        *pEventCode = pEventQueue->queue[pEventQueue->read].eventCode;

        result = E_OK;
    } else {
        result = E_NOT_OK;
    }

    return result;
}

static Std_ReturnType Xcp_EventQueuePop(Xcp_EventQueueType *pEventQueue) {
    Std_ReturnType result;

    if (pEventQueue->read != pEventQueue->write) {
        pEventQueue->read = (pEventQueue->read + 0x00000001u) & (Xcp_Ptr->general->eventQueueSize - 0x01u);

        result = E_OK;
    } else {
        result = E_NOT_OK;
    }

    return result;
}

static void Xcp_FinalizeResPacket(const PduLengthType startIndex, PduInfoType *pPduInfo)
{
    uint16_least idx;

    pPduInfo->SduLength = startIndex;

    for (idx = startIndex; idx < Xcp_Ptr->general->maxCto; idx ++)
    {
        pPduInfo->SduDataPtr[idx] = Xcp_Ptr->general->trailingValue;
    }
}

static void Xcp_FillErrorPacket(const uint8 errorCode, PduInfoType *pPduInfo)
{
    pPduInfo->SduDataPtr[0x00u] = XCP_PID_ERROR;
    pPduInfo->SduDataPtr[0x01u] = errorCode;

    Xcp_FinalizeResPacket(0x02u, pPduInfo);
}

static uint8 Xcp_ElementSizeForAddressGranularity(Xcp_AddressGranularityType ag) {
    uint8 result = 0x00u;

    if (ag == BYTE)
    {
        result = 0x01u;
    }
    else if (ag == WORD)
    {
        result = 0x02u;
    }
    else if (ag == DWORD)
    {
        result = 0x04u;
    }
    else
    {
        /* Do nothing. If we fall here, an invalid configuration has been provided to the Xcp_Init function... */
    }

    return result;
}

static boolean Xcp_BlockTransferIsActive()
{
    boolean result;

    if (Xcp_Internal.block_transfer.requested_elements != 0x00u)
    {
        result = TRUE;
    }
    else
    {
        result = FALSE;
    }

    return result;
}

static Std_ReturnType Xcp_BlockTransferInitialize(uint8 numberOfElements)
{
    Std_ReturnType result = E_OK;

    if (numberOfElements != 0x00u)
    {
        Xcp_Internal.block_transfer.requested_elements = numberOfElements;
        Xcp_Internal.block_transfer.frame_elements = 0x00u;
    }
    else
    {
        result = E_NOT_OK;
    }

    return result;
}

static void Xcp_BlockTransferAcknowledgeFrame()
{
    Xcp_Internal.block_transfer.requested_elements -= Xcp_Internal.block_transfer.frame_elements;
}

static Std_ReturnType Xcp_BlockTransferPrepareNextFrame()
{
    Std_ReturnType result = E_OK;

    uint8_least idx;
    uint8_least element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

    if ((Xcp_Internal.block_transfer.requested_elements * element_size) <= (Xcp_Ptr->general->maxCto - 0x01u))
    {
        Xcp_Internal.block_transfer.frame_elements = Xcp_Internal.block_transfer.requested_elements;
    }
    else
    {
        Xcp_Internal.block_transfer.frame_elements = ((Xcp_Ptr->general->maxCto - 0x01u) / element_size);
    }

    /* Fill alignment bytes with zeros. */
    for (idx = 0x01u; idx < element_size; idx++)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[idx] = 0x00u;
    }

    for (idx = 0x00u; idx < Xcp_Internal.block_transfer.frame_elements; idx++)
    {
        Xcp_ReadSlaveMemoryTable[Xcp_Ptr->general->addressGranularity](Xcp_Internal.memory_transfer.address,
                                                                       Xcp_Internal.memory_transfer.extension,
                                                                       &Xcp_Internal.cto_response.pdu_info.SduDataPtr[(idx + 0x01u) * element_size]);

        Xcp_Internal.memory_transfer.address += element_size;
    }

    Xcp_FinalizeResPacket(0x01u + (element_size - 0x01u) + (Xcp_Internal.block_transfer.frame_elements * element_size), &Xcp_Internal.cto_response.pdu_info);

    if (Xcp_Internal.block_transfer.frame_elements == 0x00u)
    {
        result = E_NOT_OK;
    }

    return result;
}

static uint8 Xcp_GetProtectionStatus(void) {
    return Xcp_Internal.protection_status;
}

static void Xcp_SetProtectionStatus(void) {
    Xcp_Internal.protection_status = Xcp_Internal.requested_protected_resource;
}

static void Xcp_ClearProtectionStatus(void) {
    Xcp_Internal.protection_status = 0x00u;
}

static Std_ReturnType Xcp_CheckMasterSlaveKeyMatch(uint16 slaveKeyLength, const uint8 *pSlaveKey, uint16 masterKeyLength, const uint8 *pMasterKey) {
    Std_ReturnType result = E_OK;
    uint16_least key_idx;

    if (slaveKeyLength == masterKeyLength) {
        for (key_idx = 0x00u; key_idx < slaveKeyLength; key_idx ++) {
            if (pSlaveKey[key_idx] != pMasterKey[key_idx])
            {
                result = E_NOT_OK;

                break;
            }
        }
    } else {
        result = E_NOT_OK;
    }

    return result;
}

/** @} */

#ifdef __cplusplus
}

#endif /* ifdef __cplusplus */
