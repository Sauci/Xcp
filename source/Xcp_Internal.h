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

/**
 * @brief how many absolute ODT numbers exist, across every DAQ list together.
 * @details An absolute ODT number IS the PID a DAQ DTO carries in an ABSOLUTE identification
 * field (XCP part 2 - Protocol Layer Specification 1.1/1.1.4.1), so it is bounded by the PID
 * space rather than by any configured dimension. The four highest slave-to-master PIDs are taken:
 * 0xFC is SERV, 0xFD is EV (XCP_PID_EVENT), 0xFE is ERR (XCP_PID_ERROR) and 0xFF is RES
 * (XCP_PID_RESPONSE). That leaves 0x00..0xFB, so the count is 0xFC -- the value below is both the
 * number of usable absolute ODT numbers and the first PID that is not one.
 * @note ALLOC_ODT enforces this at runtime, against what a master has actually allocated. The
 * generator deliberately does NOT guard daq_count x odt_count against it for a DAQ_DYNAMIC
 * configuration (DD31, script/source_cfg.c.jinja2): the pool's rectangle is an upper bound a
 * master rarely reaches, so guarding it there would refuse configurations that work.
 */
#define XCP_DAQ_ABSOLUTE_ODT_COUNT_MAX (0xFCu)

/**
 * @brief how many absolute ODT numbers a STIM-capable list may use, across every DAQ list
 * together.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.1.5.1. Master-to-slave STIM ODT
 * numbers run 0x00..0xBF, where slave-to-master DAQ numbers (1.1.5.2) run 0x00..0xFB -- 0xFC..0xFF
 * being SERV, EV, ERR and RES. A STIM-capable list whose absolute ODT numbers reach 0xC0 cannot be
 * addressed at all, so a configuration that can receive is held to the lower ceiling.
 * @note Same construction as XCP_DAQ_ABSOLUTE_ODT_COUNT_MAX above, and the same inclusive
 * convention: a total of exactly 0xC0 is legal (it lands on 0x00..0xBF exactly), and only a total
 * past it reaches the illegal value 0xC0 itself. Xcp_DTOCmdDaqAllocOdt (source/Xcp_Daq.c) chooses
 * between the two ceilings from the list's own declared type, since under DAQ_DYNAMIC every list
 * in the pool shares it; script/source_cfg.c.jinja2 applies the same 0xC0 bound to a STATIC
 * configuration's non-DAQ lists at generation time instead, since their FIRST_PID values are fixed
 * before this module ever runs.
 */
#define XCP_STIM_ABSOLUTE_ODT_COUNT_MAX (0xC0u)

/* SET_DAQ_LIST_MODE mode byte, XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.3.
 * Read off the specification's own bit table, which is identical in 1.0 and 1.1 except that 1.1
 * fills bit 0, which 1.0 left don't-care:
 *
 *   bit    7   6   5        4          3   2   1          0
 *   1.0    x   x   PID_OFF  TIMESTAMP  x   x   DIRECTION  x
 *   1.1    x   x   PID_OFF  TIMESTAMP  x   x   DIRECTION  ALTERNATING
 */
#define XCP_DAQ_LIST_MODE_REQ_ALTERNATING (0x01u << 0x00u)
#define XCP_DAQ_LIST_MODE_REQ_DIRECTION (0x01u << 0x01u)
#define XCP_DAQ_LIST_MODE_REQ_TIMESTAMP (0x01u << 0x04u)
#define XCP_DAQ_LIST_MODE_REQ_PID_OFF (0x01u << 0x05u)

/**
 * @brief every mode bit this implementation refuses outright, regardless of configuration.
 * @details TIMESTAMP is not in this mask: Xcp_DTOCmdDaqSetDaqListMode decides that bit itself,
 * depending on whether this build has a clock configured and whether ODT 0 still has room for
 * one. PID_OFF is not in this mask either, for the same reason: Xcp_DTOCmdDaqSetDaqListMode
 * decides it itself, depending on whether the identification field type is absolute and the
 * targeted DAQ list has exactly one ODT (1.1/1.1.2.1). DIRECTION is not in this mask either, and
 * for the same reason again: Xcp_DTOCmdDaqSetDaqListMode decides it itself, depending on whether
 * the addressed list's configured type can receive (STIM or DAQ_STIM), refusing it with
 * ERR_MODE_NOT_VALID otherwise. What remains here is refused unconditionally: ALTERNATING pairs a
 * DAQ list with a display event channel declared only in the A2L file
 * (DAQ_ALTERNATING_SUPPORTED), which this module does not emit -- and which 1.1 forbids combining
 * with TIMESTAMP in any case.
 *
 * Bits 2, 3, 6 and 7 are don't-care in both versions and are tolerated. An earlier revision of
 * this mask refused 6 and 7 believing ALTERNATING lived there; it does not, and refusing bits the
 * specification marks don't-care is over-strict.
 */
#define XCP_DAQ_LIST_MODE_REQ_UNSUPPORTED (XCP_DAQ_LIST_MODE_REQ_ALTERNATING)

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

/* DAQ_LIST_PROPERTIES, 1.1/1.6.4.2.2.1. Note the section number: unlike the GET_DAQ_* commands
 * around GET_DAQ_LIST_INFO in the PID table (0xD9, 0xDA, 0xDB -- all 1.6.4.1.2.x), this one lives
 * in a different subtree. 1.6.4 is renumbered wholesale between 1.0 and 1.1, so this citation
 * does not carry over from a 1.0-era comment, and neither would a 1.0 one carry over here. */
#define XCP_DAQ_LIST_PROPERTIES_PREDEFINED (0x01u << 0x00u)
#define XCP_DAQ_LIST_PROPERTIES_EVENT_FIXED (0x01u << 0x01u)
#define XCP_DAQ_LIST_PROPERTIES_DAQ (0x01u << 0x02u)
#define XCP_DAQ_LIST_PROPERTIES_STIM (0x01u << 0x03u)

/* DAQ_EVENT_PROPERTIES, 1.1/1.6.4.1.2.7. Bits 0, 1, 4 and 5 are reserved. */
#define XCP_DAQ_EVENT_PROPERTIES_DAQ (0x01u << 0x02u)
#define XCP_DAQ_EVENT_PROPERTIES_STIM (0x01u << 0x03u)
#define XCP_DAQ_EVENT_PROPERTIES_CONSISTENCY_DAQ (0x01u << 0x06u)
#define XCP_DAQ_EVENT_PROPERTIES_CONSISTENCY_EVENT (0x01u << 0x07u)

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

/**
 * @brief where a dynamic DAQ list configuration sequence has got to.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.6.4.3.1 enumerates six ERR_SEQUENCE
 * cases, which reduce to these four states and the transition table in Xcp_Daq.c. The initial
 * value is XCP_DAQ_ALLOC_FREE: §1.6.4.3.1.1 requires the master to send FREE_DAQ first, but that
 * is a requirement on the master and the slave's enumerated refusals do not include an ALLOC_DAQ
 * with no preceding command -- nothing is allocated at that point, so accepting it is defined.
 * @note explicitly 0, since it may live in a cleared memory section.
 */
typedef enum {
    XCP_DAQ_ALLOC_FREE = 0x00u,
    XCP_DAQ_ALLOC_DAQ,
    XCP_DAQ_ALLOC_ODT,
    XCP_DAQ_ALLOC_ODT_ENTRY
} Xcp_DaqAllocStateType;

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

    Xcp_DaqAllocStateType daq_alloc_state;

    /**
     * @brief DAQ lists currently available to the master.
     * @details Equals Xcp_Ptr->general->daqCount under a STATIC configuration and is raised from
     * zero by ALLOC_DAQ under a DYNAMIC one, so Xcp_DaqListIsValid serves both models unchanged.
     */
    uint16 allocated_daq_count;
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
 * @brief SchM_Enter_Xcp_StimBuffer / SchM_Exit_Xcp_StimBuffer (DD37): a second exclusive area,
 * separate from SchM_Enter_Xcp_DtoQueue above -- see test/stub/SchM_Xcp.h for the declarations.
 * @details Guards one Xcp_StimSlotType at a time: its `length` together with its payload, written
 * by Xcp_DaqStoreStim in the receive callback's context and read by Xcp_DaqApplyStim in the event
 * trigger's. A length paired with the buffer it describes is the DD14 class -- the same class
 * Xcp_DaqListRtType's note (interface/Xcp_Types.h) says its own fields do NOT belong to, which is
 * exactly why that argument does not excuse this structure from an area.
 * @note Not folded into SchM_Enter_Xcp_DtoQueue, and NOT for the reason this note used to give.
 * It said one shared area would risk the apply section nesting inside the sampler's DtoQueue
 * section, because a DAQ_STIM list applied its slots and sampled its DTO within the same trigger.
 * That premise is gone: 1.1/1.6.4.1.1.3 makes DIRECTION a choice between synchronized data
 * acquisition OR synchronized data stimulation, so a list does one or the other (DD40, as
 * corrected), and Xcp_TriggerEventChannel's two passes run one after the other. Folding the two
 * areas together would produce no nesting to risk.
 * What survives is DD37's corrected footing, which the design document now states rather than
 * leaving it to be re-derived: two areas keep the receive path and the transmit ring INDEPENDENT
 * -- a stimulation frame arriving while the sampler holds DtoQueue must not wait on it, and the
 * apply's snapshot must not be serialised behind a queue push it has nothing to do with. One area
 * would couple two paths that share no state, which is the note below restated from the other
 * side: they guard different data against different preemptors.
 * @note Xcp_DaqApplyStim takes BOTH areas, one after the other and never one inside the other, and
 * they guard two different things for two different reasons. This area covers the slot -- the
 * payload and its length, against Xcp_DaqStoreStim in the receive context. SchM_Enter_Xcp_DtoQueue
 * covers the ODT entries the payload is about to be written through, against CLEAR_DAQ_LIST in
 * that same context (DD14): Xcp_DaqListClearEntries (source/Xcp_Daq.c) resets an entry's address
 * to NULL_PTR and its length to 0 as separate writes under that area, the command is legal against
 * a RUNNING list, and where Xcp_DaqSampleOdt would merely READ address 0 from a torn pair, the
 * apply would WRITE to it. So the apply is a StimBuffer section, then a DtoQueue section, then the
 * memory writes with neither held -- which is also the order that keeps DD40's claim literally
 * true: every StimBuffer section of the trigger closes before the sampler's first DtoQueue section
 * opens.
 */

/**
 * @brief Decodes the identification field of a received stimulation frame.
 * @param[in] pPduInfo the received frame. Must be non-NULL with a non-NULL SduDataPtr, which
 * Xcp_CanIfRxIndication (Xcp.c) has already established before any DTO reaches here.
 * @param[in] rxPduId the PDU the frame arrived on, which is what identifies the DAQ list when
 * PID_OFF has removed the identification field (1.1/1.1.2.1).
 * @param[out] pDaqListNumber the DAQ list the frame addresses.
 * @param[out] pOdtNumber the ODT of that list the frame addresses, relative to the list.
 * @param[out] pOffset index of the first payload byte, with the identification field and any
 * timestamp already accounted for. Never larger than the frame's own SduLength, so a caller may
 * subtract it from that length without underflow; equal to it for a frame carrying no payload.
 * @retval E_OK the frame names a DAQ list and an ODT this slave has, and is long enough to hold
 * the fields that precede its payload. The three out-parameters are written only in this case.
 * @retval E_NOT_OK anything else -- an unallocated list, an ODT the list does not have, a PID_OFF
 * list that no longer has exactly one ODT, or a frame too short for the fields the configuration
 * says precede its payload.
 * @details Defined in Xcp_DaqRuntime.c, in the global section; its two file-local helpers,
 * Xcp_DaqPidOffListForRxPdu and Xcp_DaqListForAbsolutePid, sit directly after
 * Xcp_DaqWriteIdentificationField, of which this is the exact inverse. That writer is the
 * authority on each of the five layouts, and any disagreement between the two is a defect here.
 * Whether the frame should be applied at all -- that the list is STIM-capable, RUNNING, and
 * directed at stimulation, and that its payload is long enough for the ODT's entries -- is DD39's,
 * checked by the caller, not here.
 * @note XCP part 2 - Protocol Layer Specification 1.1/1.1.2.1 (identification field, and the
 * single-ODT condition PID_OFF carries), 1.1/1.1.2.2 (timestamp field, DD44) and 1.1/1.6.4.1.1.3,
 * whose "The TIMESTAMP and PID_OFF flags can be used as well for DIRECTION = DAQ as for
 * DIRECTION = STIM" is what makes both flags reachable on the receive side at all.
 */
Std_ReturnType Xcp_DaqReadIdentificationField(const PduInfoType *pPduInfo,
                                              PduIdType rxPduId,
                                              uint16 *pDaqListNumber,
                                              uint8 *pOdtNumber,
                                              uint8 *pOffset);

/**
 * @brief Buffers one received stimulation frame in the slot of the ODT it addresses.
 * @param[in] pPduInfo the received frame. Must be non-NULL with a non-NULL SduDataPtr and an
 * SduLength of at least one, all of which Xcp_CanIfRxIndication (Xcp.c) has established before any
 * DTO reaches here.
 * @param[in] rxPduId the PDU the frame arrived on, passed straight to
 * Xcp_DaqReadIdentificationField, which needs it to identify the list under PID_OFF.
 * @details Defined in Xcp_DaqRuntime.c. DD36: this is the whole of what a stimulation frame does
 * in the receive callback's context -- decode, check, copy into one slot, return. No memory is
 * written through Xcp_WriteSlaveMemoryTable here; Xcp_DaqApplyStim does that at the event trigger.
 *
 * That division is what keeps SWS_Xcp_00813 satisfiable. It makes Xcp_<Lo>RxIndication "Reentrant
 * for different PduIds. Non reentrant for the same PduId.", and every CTO arrives on one PduId --
 * which is why nothing on the CTO dispatch path guards Xcp_Internal.cto_response, last_pid or the
 * protection-status clear. A stimulation PDU is a DIFFERENT PduId and may preempt a CTO
 * mid-dispatch. This function touches none of that state, so that preemption cannot corrupt it,
 * and the CTO path needs no exclusive area of its own.
 *
 * DD39 gives the conditions a frame must meet, and there is no error response for one that does
 * not: 1.1/1.1.4.2's DTO is not a command, so a rejection's only channel is
 * Xcp_ReportError(XCP_E_STIM_FRAME_REJECTED) and the frame is dropped. A rejected frame leaves the
 * slot exactly as it was -- it is never partially written -- so the previous cycle's data keeps
 * being applied, which DD35 makes the defined behaviour when nothing new arrives.
 * @note The slot write takes SchM_Enter_Xcp_StimBuffer (DD37), held around that one slot and
 * nothing else: the payload and the `length` describing it are written together under it, because
 * a length paired with its buffer is the DD14 failure class.
 */
void Xcp_DaqStoreStim(const PduInfoType *pPduInfo, PduIdType rxPduId);

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
uint8 Xcp_DTOCmdDaqWriteDaqMultiple(boolean *responseExpected, const PduInfoType *pPduInfo);

/**
 * @brief READ_DAQ, XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.2.
 * @details Defined in Xcp_Daq.c, beside Xcp_DTOCmdDaqWriteDaq and
 * Xcp_DTOCmdDaqWriteDaqMultiple: all three read or write through the same DAQ pointer state
 * (Xcp_Internal.daq_pointer) and share its auto-post-increment (Xcp_DaqPointerAdvance).
 */
uint8 Xcp_DTOCmdDaqReadDaq(boolean *responseExpected, const PduInfoType *pPduInfo);

/**
 * @brief resets every ODT entry of one DAQ list to its power-up state.
 * @details Defined in Xcp_Daq.c, beside Xcp_DTOCmdDaqClearDaqList which is its main caller, but
 * declared here with external linkage because Xcp_Init (Xcp.c) calls it too, for every
 * configured DAQ list, so a re-initialised module never inherits a previous session's DAQ
 * configuration left in the generated (mutable, module-level static) ODT entry arrays.
 */
void Xcp_DaqListClearEntries(uint16 daqListNumber);
uint8 Xcp_DTOCmdDaqClearDaqList(boolean *responseExpected, const PduInfoType *pPduInfo);

/**
 * @brief returns every DAQ list, and the dynamic allocation state with it, to power-up values.
 * @details Defined in Xcp_Daq.c, beside Xcp_DTOCmdDaqFreeDaq, whose entire body it is
 * (1.1/1.6.4.3.1.1), but declared here with external linkage because two other places need the
 * same unwind -- the same arrangement, and for the same kind of reason, as Xcp_DaqListClearEntries
 * just above. The three callers are:
 *
 * - Xcp_DTOCmdDaqFreeDaq (Xcp_Daq.c), for which this is the whole command;
 * - Xcp_Init (Xcp.c), which has to establish the same invariant at start-up, and whose
 *   open-coded loop used to leave the descriptor's maxOdt, firstPid and per-ODT entryCount
 *   standing -- so a re-initialised DYNAMIC module reported nothing allocated while the
 *   descriptor still described the previous session's lists;
 * - Xcp_CTOCmdStdDisconnect (Xcp_Std.c), under DYNAMIC only. The allocation state machine starts
 *   in XCP_DAQ_ALLOC_FREE and accepts ALLOC_DAQ with no preceding FREE_DAQ (DD28), and repeats
 *   accumulate, so an allocation a master leaves standing at DISCONNECT is one the next master's
 *   ALLOC_DAQ adds to -- handing it more lists than it asked for, carrying the previous session's
 *   ODT entries.
 * @note the DISCONNECT caller is gated on DAQ_DYNAMIC. A STATIC configuration has no allocation
 * to release, and clearing its generated DAQ entries on disconnect would be a behaviour change to
 * the static model that SP2d is required not to make (DD25).
 */
void Xcp_DaqFreeAll(void);

/**
 * @brief ALLOC_ODT_ENTRY, XCP part 2 - Protocol Layer Specification 1.1/1.6.4.3.1.4.
 * @details Defined in Xcp_Daq.c, immediately before Xcp_DTOCmdDaqAllocOdt: 0xD3 precedes 0xD4 in
 * the PID table, and the allocation commands are kept together in that order.
 * @note DD34: raises Xcp_OdtType.entryCount (interface/Xcp_Types.h), the per-ODT field that lets
 * two ODTs of one list hold different numbers of entries -- daqList[n].maxOdtEntries cannot
 * express that, and keeps its own DYNAMIC meaning unchanged: the cap any one ODT may reach
 * (odt_entries_count).
 * @note DD28: like its three siblings, a repeat naming the same ODT accumulates onto its
 * entryCount rather than replacing it -- the specification forbids ALLOC_ODT_ENTRY only after
 * FREE and DAQ, so a repeat from ODT or ODT_ENTRY is permitted, and a permitted repeat that
 * merely replaced the previous grant would be indistinguishable from one that was refused.
 * @note this is the step that closes the running-list FIRST_PID safety argument: starting a list
 * (Xcp_DTOCmdDaqStartStopDaqList) requires Xcp_DaqListIsConfigured, which requires an ODT entry
 * of non-zero length, which requires entryCount > 0 -- the field only this command raises under
 * DYNAMIC. This command also leaves the state at XCP_DAQ_ALLOC_ODT_ENTRY, from which
 * Xcp_DTOCmdDaqAllocOdt answers ERR_SEQUENCE, so once a list has an entry, only FREE_DAQ (which
 * stops every running list first, DD30) can move its maxOdt, and so its FIRST_PID, again.
 */
uint8 Xcp_DTOCmdDaqAllocOdtEntry(boolean *responseExpected, const PduInfoType *pPduInfo);

/**
 * @brief ALLOC_ODT, XCP part 2 - Protocol Layer Specification 1.1/1.6.4.3.1.3.
 * @details Defined in Xcp_Daq.c, immediately before Xcp_DTOCmdDaqAllocDaq: 0xD4 precedes 0xD5 in
 * the PID table, and the allocation commands are kept together in that order.
 * @note DD28: like ALLOC_DAQ, repeated calls naming the same DAQ list accumulate onto its maxOdt
 * rather than replacing it -- the specification forbids ALLOC_ODT only after ALLOC_ODT_ENTRY, so
 * a repeat from DAQ or ODT is permitted, and a permitted repeat that merely replaced the previous
 * grant would be indistinguishable from one that was refused.
 * @note DD31: this is the command that assigns FIRST_PID, and it assigns every list's, not just
 * the addressed one's. See Xcp_DaqRecomputeFirstPids beside the definition for why a prefix sum
 * over list index is the only assignment that survives the accumulate rule above.
 */
uint8 Xcp_DTOCmdDaqAllocOdt(boolean *responseExpected, const PduInfoType *pPduInfo);

/**
 * @brief ALLOC_DAQ, XCP part 2 - Protocol Layer Specification 1.1/1.6.4.3.1.2.
 * @details Defined in Xcp_Daq.c, immediately before Xcp_DTOCmdDaqFreeDaq: 0xD5 precedes 0xD6 in
 * the PID table, and the two are the allocation state machine's grant and release halves.
 * @note DD28: repeated ALLOC_DAQ calls accumulate onto Xcp_Internal.allocated_daq_count rather
 * than replacing it -- the specification's ERR_SEQUENCE cases forbid ALLOC_DAQ only after
 * ALLOC_ODT and ALLOC_ODT_ENTRY, so a repeat from FREE or DAQ is permitted, and a permitted
 * repeat that merely replaced the previous grant would be indistinguishable from one that was
 * refused.
 */
uint8 Xcp_DTOCmdDaqAllocDaq(boolean *responseExpected, const PduInfoType *pPduInfo);

/**
 * @brief FREE_DAQ, XCP part 2 - Protocol Layer Specification 1.1/1.6.4.3.1.1.
 * @details Defined in Xcp_Daq.c, immediately after Xcp_DTOCmdDaqClearDaqList: the two are the
 * module's two reset commands and share Xcp_DaqListReset, differing in scope -- CLEAR_DAQ_LIST
 * resets one list and keeps its allocation, FREE_DAQ resets every list and releases the
 * allocation as well.
 */
uint8 Xcp_DTOCmdDaqFreeDaq(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqSetDaqListMode(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_DTOCmdDaqGetDaqListMode(boolean *responseExpected, const PduInfoType *pPduInfo);

/**
 * @brief GET_DAQ_EVENT_INFO, XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.7.
 * @details Defined in Xcp_Daq.c, immediately before Xcp_DTOCmdDaqGetDaqListInfo: 0xD7 precedes
 * 0xD8 in the PID table, and the two share the same shape -- a channel/list number in, an
 * ERR_OUT_OF_RANGE for one that does not exist, and a PROPERTIES byte built the same way.
 */
uint8 Xcp_DTOCmdDaqGetDaqEventInfo(boolean *responseExpected, const PduInfoType *pPduInfo);

/**
 * @brief GET_DAQ_LIST_INFO, XCP part 2 - Protocol Layer Specification 1.1/1.6.4.2.2.1.
 * @details Defined in Xcp_Daq.c, beside Xcp_DTOCmdDaqGetDaqListMode: both take a DAQ_LIST_NUMBER
 * and answer ERR_OUT_OF_RANGE for one Xcp_DaqListIsValid rejects. Unlike its neighbours in the
 * PID table, this command's own section sits in a different subtree -- 1.6.4 is renumbered
 * wholesale between 1.0 and 1.1, so no 1.6.4 citation carries over between them either way.
 */
uint8 Xcp_DTOCmdDaqGetDaqListInfo(boolean *responseExpected, const PduInfoType *pPduInfo);

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

/**
 * @brief GET_DAQ_CLOCK, XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.3.
 * @details Defined in Xcp_Daq.c, guarded there by XCP_DAQ_TIMESTAMP_SUPPORTED, same as the
 * Xcp_GetDaqTimestamp() call it makes directly. Declared unconditionally here -- the same
 * convention the XCP_PAGING_SUPPORTED-guarded Xcp_DTOCmdPag* handlers above already use -- because
 * nothing references this declaration when the feature is off: the PID table falls back to
 * Xcp_CmdNotImplemented in that build instead.
 */
uint8 Xcp_DTOCmdDaqGetDaqClock(boolean *responseExpected, const PduInfoType *pPduInfo);

uint8 Xcp_CTOCmdStdSynch(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CTOCmdStdGetStatus(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CTOCmdStdDisconnect(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CTOCmdStdConnect(boolean *responseExpected, const PduInfoType *pPduInfo);
uint8 Xcp_CmdNotImplemented(boolean *responseExpected, const PduInfoType *pPduInfo);

#ifdef __cplusplus

}

#endif /* ifdef __cplusplus */

#endif /* #ifndef XCP_INTERNAL_H */
