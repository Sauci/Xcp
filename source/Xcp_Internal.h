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

#include "Xcp.h"

#if (XCP_DEV_ERROR_DETECT == STD_ON)

#include "Det.h"

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

#define XCP_PID_CMD_WRITE_DAQ_MULTIPLE (0xC7u)
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

#define XCP_CAL_PAGE_MODE_ECU (0x01u)
#define XCP_CAL_PAGE_MODE_XCP (0x02u)
#define XCP_CAL_PAGE_MODE_ALL (0x80u)

#define XCP_SEGMENT_MODE_FREEZE (0x01u)

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
#define XCP_SESSION_STATUS_MASK_DAQ_RUNNING (0x01u << 0x06u)

/* SET_DAQ_LIST_MODE mode byte, XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.3. */
#define XCP_DAQ_LIST_MODE_REQ_DIRECTION (0x01u << 0x00u)
#define XCP_DAQ_LIST_MODE_REQ_TIMESTAMP (0x01u << 0x04u)
#define XCP_DAQ_LIST_MODE_REQ_PID_OFF (0x01u << 0x05u)

/**
 * @brief every mode bit this implementation does not honour.
 * @details Bits 1, 2 and 3 are marked don't-care in 1.0 and are tolerated. Everything else is
 * refused: DIRECTION selects STIM, TIMESTAMP and PID_OFF are unimplemented, and 1.1 places
 * ALTERNATING somewhere in bits 6..7. Refusing the whole class is conformant whichever bit
 * ALTERNATING turns out to occupy.
 */
#define XCP_DAQ_LIST_MODE_REQ_UNSUPPORTED \
    (XCP_DAQ_LIST_MODE_REQ_DIRECTION | XCP_DAQ_LIST_MODE_REQ_TIMESTAMP | XCP_DAQ_LIST_MODE_REQ_PID_OFF | \
     (0x01u << 0x06u) | (0x01u << 0x07u)) /* bits 6-7 reserved: 1.1 places ALTERNATING somewhere in them */

/* GET_DAQ_LIST_MODE mode byte, 1.1/1.6.4.1.2.6. This is the layout Xcp_DaqListRtType stores. */
#define XCP_DAQ_LIST_MODE_SELECTED (0x01u << 0x00u)
#define XCP_DAQ_LIST_MODE_DIRECTION (0x01u << 0x01u)
#define XCP_DAQ_LIST_MODE_TIMESTAMP (0x01u << 0x04u)
#define XCP_DAQ_LIST_MODE_PID_OFF (0x01u << 0x05u)
#define XCP_DAQ_LIST_MODE_RUNNING (0x01u << 0x06u)
#define XCP_DAQ_LIST_MODE_RESUME (0x01u << 0x07u)

/* START_STOP_DAQ_LIST and START_STOP_SYNCH mode parameters, 1.1/1.6.4.1.1.4 and .5. */
#define XCP_DAQ_START_STOP_MODE_STOP (0x00u)
#define XCP_DAQ_START_STOP_MODE_START (0x01u)
#define XCP_DAQ_START_STOP_MODE_SELECT (0x02u)
#define XCP_DAQ_SYNCH_MODE_STOP_ALL (0x00u)
#define XCP_DAQ_SYNCH_MODE_START_SELECTED (0x01u)
#define XCP_DAQ_SYNCH_MODE_STOP_SELECTED (0x02u)

/* DAQ_PROPERTIES, 1.1/1.6.4.1.2.4. */
#define XCP_DAQ_PROPERTIES_DAQ_CONFIG_TYPE (0x01u << 0x00u)
#define XCP_DAQ_PROPERTIES_PRESCALER_SUPPORTED (0x01u << 0x01u)
#define XCP_DAQ_PROPERTIES_RESUME_SUPPORTED (0x01u << 0x02u)
#define XCP_DAQ_PROPERTIES_BIT_STIM_SUPPORTED (0x01u << 0x03u)
#define XCP_DAQ_PROPERTIES_TIMESTAMP_SUPPORTED (0x01u << 0x04u)
#define XCP_DAQ_PROPERTIES_PID_OFF_SUPPORTED (0x01u << 0x05u)
#define XCP_DAQ_PROPERTIES_OVERLOAD_MSB (0x01u << 0x06u)
#define XCP_DAQ_PROPERTIES_OVERLOAD_EVENT (0x01u << 0x07u)

/**
 * @brief BIT_OFFSET value meaning "this entry is a normal element, ignore the field".
 * @note XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.2.
 */
#define XCP_ODT_ENTRY_BIT_OFFSET_NONE (0xFFu)

/**
 * @brief highest BIT_OFFSET that designates a single bit.
 */
#define XCP_ODT_ENTRY_BIT_OFFSET_MAX (0x1Fu)

#define XCP_EVENT_DAQ_OVERLOAD (0x06u)

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
        ONGOING_TRANSMIT_TYPE_EVENT,
        ONGOING_TRANSMIT_TYPE_DAQ
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

    /**
     * @brief target of the next WRITE_DAQ, set by SET_DAQ_PTR.
     * @details valid goes FALSE past the last ODT entry of an ODT, where 1.1/1.6.4.1.1.2 leaves
     * the pointer undefined and makes correct repositioning the master's responsibility.
     */
    struct {
        uint16 daqListNumber;
        uint8 odtNumber;
        uint8 odtEntryNumber;
        boolean valid;
    } daq_pointer;
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

/**
 * @brief Defined in Xcp.c. Only interface/Xcp.h's CFFI_ENABLE block declared this before now, so
 * Xcp.c (which defines it) was the only translation unit that could reference it; a second one
 * -- Xcp_DaqRuntime.c's Xcp_TriggerEventChannel -- now does too and needs it declared here, same
 * as Xcp_Ptr immediately above.
 */
extern Xcp_StateType Xcp_State;

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

/**
 * @brief number of elements the current frame of a block transfer carries.
 * @details The count a master announces may span several frames; this is how many of them the
 * current one holds, which is what a handler must find in the received PDU before reading it.
 */
uint8 Xcp_BlockTransferFrameElements(uint8 numberOfDataElements, uint8 elementSize);
void Xcp_BlockTransferAbort(void);
uint8 Xcp_GetProtectionStatus(void);
void Xcp_SetProtectionStatus(void);
void Xcp_ClearProtectionStatus(void);

/**
 * @brief Hands CanIf the next packet awaiting transmission, if the module is idle.
 * @details Safe from any context and at any time; a call arriving while another is inside
 * CanIf_Transmit records the wish and returns, and the outer call carries it out before
 * returning. Callers therefore never need to know whether a transmission is already running.
 * @note Reads Xcp_Internal.ongoing_transmit_type under the exclusive area, but
 * Xcp_CanIfTxConfirmation updates that field outside one before calling here. Correct only if
 * SchM_Enter_Xcp_DtoQueue excludes the confirmation's own execution context, not merely other
 * callers of this function -- see test/stub/SchM_Xcp.h.
 */
void Xcp_StartNextTransmission(void);

/**
 * @brief Hands back the PduIdType and PduInfoType of the frame at the head of the DTO ring.
 * @retval E_NOT_OK the ring is empty; *pTxPduId and *ppPduInfo are not written.
 * @details Defined in Xcp_DaqRuntime.c. The caller is expected to already hold the exclusive
 * area (Xcp_TransmitOneFrame's selection, Xcp.c). *ppPduInfo points at storage the ring itself
 * owns, valid only until the corresponding Xcp_DaqQueuePop.
 */
Std_ReturnType Xcp_DaqQueuePeek(PduIdType *pTxPduId, PduInfoType **ppPduInfo);

/**
 * @brief Releases the frame at the head of the DTO ring after its transmission is confirmed.
 * @details Defined in Xcp_DaqRuntime.c. The caller is expected to already hold the exclusive
 * area (Xcp_CanIfTxConfirmation, Xcp.c). A no-op on an empty ring.
 */
void Xcp_DaqQueuePop(void);

/**
 * @brief Appends one packet to an event queue.
 * @retval E_NOT_OK the queue was full; nothing was written.
 * @details Defined in Xcp.c, static there until now; given external linkage, the same move SP1
 * made for the block-transfer helpers, because Xcp_TriggerEventChannel (Xcp_DaqRuntime.c) needs
 * it too, to raise EV_DAQ_OVERLOAD. Tolerates pUserData == NULL_PTR when userDataSize == 0x00u:
 * the definition's copy loop is bounded by userDataSize and never runs when it is zero, so
 * pUserData is not dereferenced in that case.
 */
Std_ReturnType Xcp_EventQueuePush(Xcp_EventQueueType *pEventQueue, uint8 packetID, uint8 eventCode, const uint8 *pUserData, uint32 userDataSize);

extern void(* const Xcp_ReadSlaveMemoryTable[])(void *address, uint8 extension, uint8 *pBuffer);
extern void(* const Xcp_WriteSlaveMemoryTable[])(void *address, uint8 *pBuffer);

uint8 Xcp_DTODaqStimPacket(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdCalShortDownload(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdCalDownloadMax(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdCalDownloadNext(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdCalDownload(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdCalModifyBits(boolean *responseExpected, const PduInfoType *pPduInfo);
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
uint8 Xcp_DTOCmdPagSetCalPage(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdPagGetCalPage(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdPagGetPagProcessorInfo(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdPagSetSegmentMode(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdPagGetSegmentMode(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdPagGetSegmentInfo(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdPagGetPageInfo(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdPagCopyCalPage(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqSetDaqPtr(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqWriteDaq(boolean *responseExpected, const PduInfoType *pPduInfo);

/**
 * @brief resets every ODT entry of one DAQ list to its power-up state.
 * @details Defined in Xcp_Daq.c, beside Xcp_DTOCmdDaqClearDaqList which is its main caller, but
 * declared here with external linkage because Xcp_Init (Xcp.c) calls it too, for every
 * configured DAQ list, so a re-initialised module never inherits a previous session's DAQ
 * configuration left in the generated (mutable, module-level static) ODT entry arrays.
 */
void Xcp_DaqListClearEntries(uint16 daqListNumber);
uint8 Xcp_DTOCmdDaqClearDaqList(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqSetDaqListMode(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqGetDaqListMode(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqStartStopDaqList(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqStartStopSynch(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqGetDaqProcessorInfo(boolean *responseExpected, const PduInfoType *pPduInfo);

/**
 * @brief maps Xcp_TimestampTypeType onto the TIMESTAMP_MODE size field (0, 1, 2 or 4).
 * @details Defined in Xcp_Daq.c, beside Xcp_DTOCmdDaqGetDaqResolutionInfo which is its first
 * caller, but declared here with external linkage because per-configuration DTO encoding needs
 * the same enumerator-to-wire-size mapping and must call this on
 * Xcp_Ptr->general->timestampType rather than use XCP_DAQ_TIMESTAMP_SIZE for arithmetic: that
 * macro is the maximum across every configuration, correct for compile-time sizing and #if
 * gating, but wrong as the wire width of one particular configuration's DTO.
 * @note XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.5 encodes the size in bits 2:0
 * as 0, 1, 2 or 4, and marks 3 "Not allowed". Xcp_TimestampTypeType's enumerators are implicit,
 * so FOUR_BYTE is 3 -- passing the enumerator through unmapped would transmit precisely the
 * value the specification forbids.
 */
uint8 Xcp_TimestampWireSize(Xcp_TimestampTypeType type);

uint8 Xcp_DTOCmdDaqGetDaqResolutionInfo(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CTOCmdStdSynch(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CTOCmdStdGetStatus(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CTOCmdStdDisconnect(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CTOCmdStdConnect(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CmdNotImplemented(boolean *responseExpected, const PduInfoType *pPduInfo);

#ifdef __cplusplus

}

#endif /* ifdef __cplusplus */

#endif /* #ifndef XCP_INTERNAL_H */
