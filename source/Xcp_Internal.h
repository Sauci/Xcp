/**
 * @file Xcp_Internal.h
 * @author
 * @date
 *
 * @defgroup XCP_INTERNAL_H internal definitions shared across Xcp.c translation units
 * @ingroup XCP
 */

#ifndef XCP_INTERNAL_H

#define XCP_INTERNAL_H

#ifdef __cplusplus

extern "C" {

#endif /* #ifdef __cplusplus */

#ifndef XCP_H

#include "Xcp.h"

#endif /* #ifndef XCP_H */

#if (XCP_DEV_ERROR_DETECT == STD_ON)

#ifndef DET_H

#include "Det.h"

#endif /* #ifndef DET_H */

#endif /* #if (XCP_DEV_ERROR_DETECT == STD_ON) */

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
/* global variable declarations (extern).                                                         */
/*------------------------------------------------------------------------------------------------*/

extern Xcp_InternalType Xcp_Internal;
extern const Xcp_Type *Xcp_Ptr;

/*------------------------------------------------------------------------------------------------*/
/* global function declarations.                                                                  */
/*------------------------------------------------------------------------------------------------*/

void Xcp_FinalizeResPacket(const PduLengthType startIndex, PduInfoType *pPduInfo);
void Xcp_FillErrorPacket(const uint8 errorCode, PduInfoType *pPduInfo);
void Xcp_FillErrorPacketWithData(const uint8 errorCode, const uint8 *pData, const uint8 dataLength, PduInfoType *pPduInfo);
uint8 Xcp_ElementSizeForAddressGranularity(Xcp_AddressGranularityType ag);
uint8_least Xcp_GetNumberOfAlignmentBytes(uint8_least alignmentByteIndex, uint8_least elementSize, uint8 maxCto);
void Xcp_CopyFromU16WithOrder(const uint16 src, uint8 *pDest, Xcp_ByteOrderType endianness);
void Xcp_CopyFromU32WithOrder(const uint32 src, uint8 *pDest, Xcp_ByteOrderType endianness);
void Xcp_CopyToU16WithOrder(const uint8 *pSrc, uint16 *pDest, Xcp_ByteOrderType endianness);
void Xcp_CopyToU32WithOrder(const uint8 *pSrc, uint32 *pDest, Xcp_ByteOrderType endianness);
boolean Xcp_BlockTransferIsActive(void);
Std_ReturnType Xcp_DataTransferInitialize(uint8 numberOfDataElements, uint8 elementSize, uint8 alignment, uint8 budget, boolean blockModeSupported, uint8 maxBlockSize);
void Xcp_BlockTransferAcknowledgeFrame(void);
Std_ReturnType Xcp_BlockTransferReadSlaveMemory(void);
Std_ReturnType Xcp_BlockTransferWriteSlaveMemory(uint8 *pBuffer, uint8 elementSize);
void Xcp_BlockTransferAbort(void);
uint8 Xcp_GetProtectionStatus(void);
void Xcp_SetProtectionStatus(void);
void Xcp_ClearProtectionStatus(void);
Std_ReturnType Xcp_CheckMasterSlaveKeyMatch(uint16 slaveKeyLength, const uint8 *pSlaveKey, uint16 masterKeyLength, const uint8 *pMasterKey);

extern void(* const Xcp_ReadSlaveMemoryTable[])(void *address, uint8 extension, uint8 *pBuffer);
extern void(* const Xcp_WriteSlaveMemoryTable[])(void *address, uint8 *pBuffer);

uint8 Xcp_DTOCmdDaqAllocOdtEntry(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqAllocOdt(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqAllocDaq(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqFreeDaq(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqGetDaqEventInfo(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqGetDaqListInfo(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqGetDaqResolutionInfo(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqGetDaqProcessorInfo(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqReadDaq(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqGetDaqClock(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqStartStopSynch(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqStartStopDaqList(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqGetDaqListMode(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqSetDaqListMode(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqWriteDaq(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqSetDaqPtr(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqClearDaqList(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTODaqStimPacket(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTODaqPacket(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdShortDownload(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdDownloadMax(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdDownloadNext(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdDownload(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdModifyBits(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdUserCmd(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdTransportLayerCmd(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdBuildChecksum(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdShortUpload(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdUpload(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdSetMta(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdUnlock(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdGetSeed(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdSetRequest(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdGetId(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdStdGetCommModeInfo(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CTOCmdStdSynch(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CTOCmdStdGetStatus(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CTOCmdStdDisconnect(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CTOCmdStdConnect(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CmdNotImplemented(boolean *responseExpected, const PduInfoType *pPduInfo);

#ifdef __cplusplus

}

#endif /* ifdef __cplusplus */

#endif /* #ifndef XCP_INTERNAL_H */
