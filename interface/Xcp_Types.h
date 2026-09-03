/**
 * @file Xcp_Types.h
 * @author Guillaume Sottas
 * @date 10/12/2021
 */

#ifndef XCP_TYPES_H
#define XCP_TYPES_H

#ifdef __cplusplus

extern "C" {

#endif /* ifdef __cplusplus */

/*------------------------------------------------------------------------------------------------*/
/* included files (#include).                                                                     */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_TYPES_H
 * @{
 */

#include "ComStack_Types.h"

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global definitions (#define).                                                                  */
/*------------------------------------------------------------------------------------------------*/

#ifndef XCP_EVENT_USER_DATA_SIZE

#define XCP_EVENT_USER_DATA_SIZE (0x10u)

#endif /* #ifndef XCP_EVENT_USER_DATA_SIZE */

#ifndef XCP_MAX_DTO

#define XCP_MAX_DTO (0x08u)

#endif /* #ifndef XCP_MAX_DTO */

#ifndef XCP_DAQ_TIMESTAMP_SUPPORTED

/* A literal rather than STD_OFF: the test harness's Preprocessor.on_directive_handle
 * (test/conftest.py) only records a #define's value when it tokenizes as an integer literal, and
 * handle.define('XCP_DAQ_TIMESTAMP_SUPPORTED') relies on that. Numerically identical to STD_OFF
 * either way once the preprocessor expands it for an #if. */
#define XCP_DAQ_TIMESTAMP_SUPPORTED (0x00u)

#endif /* #ifndef XCP_DAQ_TIMESTAMP_SUPPORTED */

#ifndef XCP_DAQ_TIMESTAMP_SIZE

#define XCP_DAQ_TIMESTAMP_SIZE (0u)

#endif /* #ifndef XCP_DAQ_TIMESTAMP_SIZE */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global data type definitions (typedef, struct).                                                */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GTDEF
 * @{
 */

typedef enum
{
    /**
     * @brief Transmission Disabled
     */
    XCP_TX_OFF = 0x00u,

    /**
     * @brief Transmission Enabled
     */
    XCP_TX_ON = 0x01u

} Xcp_TransmissionModeType;

typedef enum
{
    /**
     * @brief only DAQ supported (default value)
     */
    DAQ = 0x00u,

    /**
     * @brief both DAQ and STIM supported (simultaneously)
     */
    DAQ_STIM,

    /**
     * @brief only STIM supported
     */
    STIM
} Xcp_EventChannelTypeType;

typedef enum
{
    /**
     * @brief if XCP_DAQ_DYNAMIC is selected, the DAQ_CONFIG_TYPE bit is set to 1
     */
    DAQ_DYNAMIC,

    /**
     * @brief if XCP_DAQ_STATIC is selected, the DAQ_CONFIG_TYPE bit is set to 0
     */
    DAQ_STATIC
} Xcp_DaqConfigTypeType;

/**
 * @note These enumerator values are not arbitrary: XCP part 2 - Protocol Layer Specification
 * 1.1/1.6.4.1.2.4 transmits them directly as bits 7:6 of GET_DAQ_PROCESSOR_INFO's DAQ_KEY_BYTE,
 * so renumbering changes the wire format. An exhaustive test covers this and will fail loudly if
 * it ever happens, but check the section above before relying on that.
 */
typedef enum
{
    /**
     * @brief absolute ODT number
     */
    ABSOLUTE,

    /**
     * @brief relative ODT number, absolute DAQ list number (BYTE)
     */
    RELATIVE_BYTE,

    /**
     * @brief relative ODT number, absolute DAQ list number (WORD)
     */
    RELATIVE_WORD,

    /**
     * @brief relative ODT number, absolute DAQ list number (WORD, aligned)
     */
    RELATIVE_WORD_ALIGNED
} Xcp_IdentificationFieldTypeType;

typedef enum
{
    /**
     * @brief timestamp field is not available
     */
    NO_TIME_STAMP,

    /**
     * @brief timestamp field has the size of one byte
     */
    ONE_BYTE,

    /**
     * @brief timestamp field has the size of two byte
     */
    TWO_BYTE,

    /**
     * @brief timestamp field has the size of four byte
     */
    FOUR_BYTE
} Xcp_TimestampTypeType;

typedef enum
{
    /**
     * @brief unit is 100 millisecond
     */
    TIMESTAMP_UNIT_100MS = 0x08u,

    /**
     * @brief unit is 100 nanosecond
     */
    TIMESTAMP_UNIT_100NS = 0x02u,

    /**
     * @brief unit is 100 picosecond
    TIMESTAMP_UNIT_100PS,*/

    /**
     * @brief unit is 100 microsecond
     */
    TIMESTAMP_UNIT_100US = 0x05u,

    /**
     * @brief unit is 10 millisecond
     */
    TIMESTAMP_UNIT_10MS = 0x07u,

    /**
     * @brief unit is 10 nanosecond
     */
    TIMESTAMP_UNIT_10NS = 0x01u,

    /**
     * @brief unit is 10 picosecond
    TIMESTAMP_UNIT_10PS,*/

    /**
     * @brief unit is 10 microsecond
     */
    TIMESTAMP_UNIT_10US = 0x04u,

    /**
     * @brief unit is 1 millisecond
     */
    TIMESTAMP_UNIT_1MS = 0x06u,

    /**
     * @brief unit is 1 nanosecond
     */
    TIMESTAMP_UNIT_1NS = 0x00u,

    /**
     * @brief unit is 1 picosecond
    TIMESTAMP_UNIT_1PS,*/

    /**
     * @brief unit is 1 second
     */
    TIMESTAMP_UNIT_1S = 0x09u,

    /**
     * @brief unit is 1 microsecond
     */
    TIMESTAMP_UNIT_1US = 0x03u
} Xcp_TimestampUnitType;

/**
 * @note DAQ_LIST is appended with an explicit value rather than spelled DAQ and placed between
 * ODT and EVENT, where the specification's own ordering would put it. Two reasons, both binding
 * on anyone editing this enumeration. Inserting an enumerator here renumbers EVENT from 1 to 2,
 * which is an ABI break for any integrator holding an already-compiled Xcp_Cfg.o. And DAQ is
 * already an enumerator of Xcp_EventChannelTypeType above, so a member named DAQ here would not
 * be a redefinition -- both are plain C enumerators in the same scope, so the second declaration
 * is what would fail to compile, and the configuration generator emitting a bare `DAQ` would
 * resolve to whichever came first. It resolved to Xcp_EventChannelTypeType::DAQ == 0x00u, i.e.
 * silently to ODT, for as long as this member was commented out. script/source_cfg.c.jinja2 maps
 * the configuration's "DAQ" onto DAQ_LIST rather than emitting the configured string verbatim.
 */
typedef enum
{
    /**
     * @brief consistency on ODT level (default value)
     */
    ODT = 0x00u,

    /**
     * @brief consistency on event channel level
     */
    EVENT = 0x01u,

    /**
     * @brief consistency on DAQ list level
     */
    DAQ_LIST = 0x02u
} Xcp_EventChannelConsistencyType;

/**
 * @brief BYTE_ORDER indicates the byte order used for transferring multi-byte parameters in an XCP
 * Packet. BYTE_ORDER = 0 means Intel format, BYTE_ORDER = 1 means Motorola format. Motorola format
 * means MSB on lower address/position.
 *
 * @note This enumeration is not specified in the AUTOSAR specification, but in the ASAM XCP part
 * 2 - Protocol Layer Specification 1.0/1.6.1.1.1
 */
typedef enum
{
    XCP_LITTLE_ENDIAN = 0x00u,
    XCP_BIG_ENDIAN = 0x01u
} Xcp_ByteOrderType;

/**
 * @brief The address granularity indicates the size of an element contained at a single address. It
 * is needed if the master has to do address calculation.
 *
 * @note This enumeration is not specified in the AUTOSAR specification, but in the ASAM XCP part
 * 2 - Protocol Layer Specification 1.0/1.6.1.1.1
 */
typedef enum
{
    BYTE = 0x00u,
    WORD = 0x01u,
    DWORD = 0x02u
} Xcp_AddressGranularityType;

typedef enum
{
    XCP_ADD_11,
    XCP_ADD_12,
    XCP_ADD_14,
    XCP_ADD_22,
    XCP_ADD_24,
    XCP_ADD_44,
    XCP_CRC_16,
    XCP_CRC_16_CITT,
    XCP_CRC_32,
    XCP_USER_DEFINED
} Xcp_ChecksumType;

typedef struct
{
    const uint16 id;
    const void *pdu;
} Xcp_RxPduType;

typedef struct
{
    const uint16 id;
    const void *pdu;
} Xcp_TxPduType;

typedef struct
{
    const Xcp_RxPduType *channel_rx_pdu_ref;
    const Xcp_TxPduType *channel_tx_pdu_ref;
    const void *com_m_channel_ref;
} Xcp_CommunicationChannelType;

/**
 * @brief this container collects data transfer object specific parameters for the DAQ list.
 * @note ECUC_Xcp_00066 (XcpDtoPid) has no member here on purpose. The PID a DAQ list transmits is
 * FIRST_PID + ODT number, and FIRST_PID is assigned by the slave, not configured (XCP part 2 -
 * Protocol Layer Specification 1.1/1.6.4.1.1.4); it lives in Xcp_DaqListType::firstPid, derived at
 * generation time. A configured PID would be a second, unread copy of a value the slave owns.
 */
typedef struct
{
    const union
    {
        Xcp_RxPduType rxPdu;
        Xcp_TxPduType txPdu;
    } dto2PduMapping;
} Xcp_DtoType;

/**
 * @brief this container collects all configuration parameters that comprise an ODT entry.
 */
typedef struct
{
    /**
     * @brief memory address that the ODT entry is referencing to
     */
    uint32 *address;

    /**
     * @brief represent the bit offset in case of the element represents status bit
     */
    uint8 bitOffset;

    /**
     * @brief address extension of the memory the ODT entry references.
     * @note XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.2, WRITE_DAQ byte 3.
     */
    uint8 addressExtension;

    /**
     * @brief length of the referenced memory area that is referenced by the ODT entry
     */
    uint8 length;

    /**
     * @brief index number of the ODT entry
     */
    const uint8 number;
} Xcp_OdtEntryType;

/**
 * @brief this container contains ODT-specific parameter for the DAQ list.
 */
typedef struct
{
    /**
     * @brief this parameter indicates the upper limit for the size of the element described by an
     * ODT entry. depending on the DaqListType this ODT belongs to it describes the limit for a DAQ
     * (MAX_ODT_ENTRY_SIZE_DAQ) or a STIM (MAX_ODT_ENTRY_SIZE_STIM)
     */
    const uint8 odtEntryMaxSize;

    /**
     * @brief index number of this ODT within the DAQ list
     */
    uint8 odtNumber;

    /**
     * @brief number of ODT entries allocated to this ODT.
     * @details Under a STATIC configuration the generator seeds this with the DAQ list's
     * max_odt_entries for every ODT, so it equals maxOdtEntries throughout. Under DYNAMIC it
     * starts at zero and ALLOC_ODT_ENTRY raises it, which is what lets two ODTs of one list hold
     * different numbers of entries.
     * @note XCP part 2 - Protocol Layer Specification 1.1/1.6.4.3.1.4.
     */
    uint8 entryCount;

    /**
     * @brief this reference maps the ODT to the according DTO in which it will be transmitted
     */
    const Xcp_DtoType *odt2DtoMapping;

    /**
     * @brief This container collects all configuration parameters that comprise an ODT entry
     */
    Xcp_OdtEntryType *odtEntry;
} Xcp_OdtType;

/**
 * @note The members below are not const because a DAQ_DYNAMIC configuration assigns them at
 * runtime from ALLOC_DAQ, ALLOC_ODT and ALLOC_ODT_ENTRY (1.1/1.6.4.3.1). A struct definition
 * cannot differ between builds without an #if here, which would give the CFFI test harness a
 * second type to compile, so they are non-const in both. Flash placement is unaffected: it comes
 * from the Xcp_START_SEC_CONST_UNSPECIFIED MemMap section the generator emits around these
 * arrays, which a STATIC configuration keeps. Only the allocator writes them.
 */
typedef struct
{
    uint16 number;

    /**
     * @brief absolute ODT number of this DAQ list's first ODT.
     * @details Assigned by the slave, not the master, and reported in the positive response to
     * START_STOP_DAQ_LIST. The absolute ODT number of ODT i is firstPid + i.
     * @note XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.4.
     */
    uint8 firstPid;
    const Xcp_EventChannelTypeType type;
    uint8 maxOdt;
    uint8 maxOdtEntries;
    const Xcp_DtoType *dto;
    const uint32 dtoCount; /* TODO: check if this value can be retrieved from somewhere else... */
    Xcp_OdtType *odt;
} Xcp_DaqListType;

/**
 * @brief This container contains the configuration of event channels on the XCP slave.
 */
typedef struct
{
    /**
     * @brief Type of consistency used by event channel.
     */
    Xcp_EventChannelConsistencyType consistency;

    /**
     * @brief Maximum amount of DAQ lists that are handled by this event channel.
     */
    uint8 maxDaqList;

    /**
     * @brief Index number of the event channel.
     */
    uint16 number;

    /**
     * @brief Priority of the event channel.
     */
    uint8 priority;

    /**
     * @brief The event channel time cycle indicates which sampling period is used to process this
     * event channel. A value of 0 means 'Not cyclic'.
     */
    uint8 timeCycle;

    /**
     * @brief This configuration parameter indicates the unit of the event channel time cycle.
     */
    Xcp_TimestampUnitType timeUnit;

    /**
     * This configuration parameter indicates what kind of DAQ list can be allocated to this event
     * channel.
     */
    Xcp_EventChannelTypeType type;

    /**
     * @brief References all DAQ lists that are triggered by this event channel.
     * @details An array of pointers rather than one pointer plus a count: the configured
     * references name arbitrary DAQ lists, which a single pointer into the DAQ list array could
     * only express if they happened to be contiguous.
     */
    const Xcp_DaqListType * const *triggeredDaqListRef;
    const uint32 triggeredDaqListRefCount;

    /**
     * @brief ASCII name of this event channel, without NUL terminator, or NULL_PTR when names are
     * not published. GET_DAQ_EVENT_INFO sets the MTA here so the master can UPLOAD it.
     * @note XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.7.
     */
    const uint8 *namePtr;

    /**
     * @brief Length of namePtr in bytes. 0 means the name is not available, which
     * 1.1/1.6.4.1.2.7 permits explicitly.
     */
    const uint8 nameLength;
} Xcp_EventChannelType;

/**
 * @brief address range within a SEGMENT that has an address mapping applied.
 * @note XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2, mode 2.
 */
typedef struct
{
    const uint32 sourceAddress;
    const uint32 destinationAddress;
    const uint32 length;
} Xcp_AddressMappingType;

/**
 * @brief a single calibration PAGE of a SEGMENT.
 * @note XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.3.
 */
typedef struct
{
    /**
     * @brief SEGMENT that initializes this PAGE.
     */
    const uint8 initSegment;

    /**
     * @brief PAGE_PROPERTIES, packed as ecu access at bits 1:0, XCP read access at bits 3:2 and
     * XCP write access at bits 5:4.
     */
    const uint8 pageProperties;
} Xcp_PageType;

/**
 * @brief a logical calibration data SEGMENT.
 * @note XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2.
 */
typedef struct
{
    const uint32 address;
    const uint32 length;
    const uint8 addressExtension;
    const uint8 compressionMethod;
    const uint8 encryptionMethod;
    const uint8 maxPages;
    const Xcp_PageType *page;
    const uint8 maxMapping;
    const Xcp_AddressMappingType *addressMapping;
} Xcp_SegmentType;

typedef struct
{
    const Xcp_DaqConfigTypeType daqConfigType;
    const uint16 daqCount;
    const boolean devErrorDetect;
    const boolean flashProgrammingEnabled;
    const Xcp_IdentificationFieldTypeType identificationFieldType;
    const ieee_float mainFunctionPeriod;
    const uint16 maxCto;
    const uint16 maxDto;
    const uint16 maxEventChannel;
    const uint8 minDaq;
    const uint8 odtCount;
    const uint8 odtEntriesCount;
    const uint8 odtEntrySizeDaq;
    const uint8 odtEntrySizeStim;
    const boolean xcpOnCanEnabled;
    const boolean xcpOnCddEnabled;
    const boolean xcpOnEthernetEnable;
    const boolean xcpOnFlexRayEnabled;
    const boolean prescalerSupported;
    const boolean suppressTxSupport;
    const uint16 timestampTicks;
    const Xcp_TimestampTypeType timestampType;
    const Xcp_TimestampUnitType timestampUnit;
    const boolean versionInfoApi;
    /* TODO: pass a callback function here... */
    const void *counter;
    const void *nvRamBlockId;
    const uint8 ctoInfo[0x100u]; /* not part of the specification... */
    const Xcp_ByteOrderType byteOrder; /* not part of the specification... */
    const Xcp_AddressGranularityType addressGranularity; /* not part of the specification... */
    const boolean masterBlockModeSupported; /* not part of the specification... */
    const boolean slaveBlockModeSupported; /* not part of the specification... */
    const boolean interleavedModeSupported; /* not part of the specification... */
    const uint8 maxBS; /* not part of the specification... */
    const uint8 minST; /* not part of the specification... */
    const uint8 ctoQueueSize; /* not part of the specification... */
    const uint8 eventQueueSize; /* not part of the specification... */
    const uint8 protectedResource; /* not part of the specification... */
    const Xcp_ChecksumType checksumType; /* not part of the specification... */
    void *(*const userDefinedChecksumFunction)(void *lowerAddress, const void *upperAddress, uint32 *pResult); /* not part of the specification... */
    uint8 (*const userCmdFunction)(const PduInfoType *pCtoPduInfo, PduInfoType *pResErrPduInfo); /* not part of the specification... */
    const uint8 trailingValue; /* not part of the specification... */
    const char *identification; /* not part of the specification... */
    const uint8 maxSegment; /* not part of the specification... */
    const uint8 pagProperties; /* not part of the specification... */
    const boolean overloadEvent; /* not part of the specification... */
} Xcp_GeneralType;

/**
 * @brief this is the type of the data structure containing the initialization data for XCP.
 */
typedef struct
{
    const Xcp_CommunicationChannelType *communicationChannel;
    Xcp_DaqListType *daqList;
    const uint16 daqListCount; /* not part of the specification... */
    const Xcp_EventChannelType *eventChannel;
    const void *pdu;
    const Xcp_SegmentType *segment;
} Xcp_ConfigType;

typedef struct {
    uint8 packetID;
    uint8 eventCode;
    uint8 userData[XCP_EVENT_USER_DATA_SIZE];
    uint32 userDataSize;
} Xcp_EventType;

typedef struct {
    Xcp_EventType *queue;
    uint32 read;
    uint32 write;
} Xcp_EventQueueType;

typedef struct {
    /**
     * @brief FREEZE mode of this SEGMENT.
     * @note XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.4.
     */
    boolean freeze;
} Xcp_SegmentRtType;

/**
 * @brief mutable state of one DAQ list.
 * @details Everything the master changes through SET_DAQ_LIST_MODE and START_STOP_DAQ_LIST.
 * The configured part of a DAQ list -- its ODTs, its FIRST_PID, its PDU mapping -- lives in
 * Xcp_DaqListType and is generated const.
 * @note XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.3.
 * @note mode, eventChannelNumber, prescaler and prescalerCounter are read by
 * Xcp_TriggerEventChannel (a task or an ISR) and written by the command handlers of
 * source/Xcp_Daq.c (CanIf's receive context -- SET_DAQ_LIST_MODE, START_STOP_DAQ_LIST,
 * START_STOP_SYNCH, CLEAR_DAQ_LIST), with no exclusive area on either side. This is deliberate,
 * not an oversight: it is the mirror image of the state the DAQ transmit exclusive area (DD5 in
 * the design doc) does protect. A trigger interleaved with one of these writes can at worst see
 * a torn read of one field -- a skewed prescaler cycle, or a mode change that takes effect one
 * trigger later or earlier than intended, i.e. one extra or missing frame. None of these fields
 * is a pointer, or a length paired with a pointer the way the ODT entry array is (DD14), so no
 * interleaving here is ever memory-unsafe. That bound is what makes this acceptable rather than
 * a defect; before reusing the argument for a new field, confirm it still holds.
 */
typedef struct {
    /**
     * @brief event channel this DAQ list is bound to, assigned by SET_DAQ_LIST_MODE.
     */
    uint16 eventChannelNumber;

    /**
     * @brief current mode, in the GET_DAQ_LIST_MODE layout of 1.1/1.6.4.1.2.6.
     * @details Stored in the layout the slave reports rather than the one it receives:
     * SET_DAQ_LIST_MODE puts DIRECTION at bit 0, while this byte puts SELECTED there.
     */
    uint8 mode;

    /**
     * @brief transmission rate prescaler; 1 means no reduction.
     */
    uint8 prescaler;

    /**
     * @brief events counted towards the next transmission, in [0, prescaler).
     */
    uint8 prescalerCounter;

    /**
     * @brief DAQ list priority. Only 0 is accepted while prioritisation is unimplemented.
     */
    uint8 priority;
} Xcp_DaqListRtType;

/**
 * @brief one complete DTO packet, assembled at the sampling instant.
 * @note XCP part 2 - Protocol Layer Specification 1.1/1.1.4.1.
 */
typedef struct {
    /**
     * @brief Tx PDU this frame goes out on, from the DAQ list's pdu_mapping.
     */
    PduIdType txPduId;

    /**
     * @brief bytes used in data, identification field included.
     */
    uint8 length;

    uint8 data[XCP_MAX_DTO];
} Xcp_DtoFrameType;

/**
 * @brief ring of assembled DTO frames awaiting transmission.
 * @details count rather than a gap between read and write, so a full ring and an empty one are
 * distinguishable without wasting an element.
 */
typedef struct {
    Xcp_DtoFrameType *frame;
    uint8 depth;
    uint8 read;
    uint8 write;
    uint8 count;
} Xcp_DtoQueueType;

typedef struct {
    Xcp_EventQueueType *eventQueue;
    Xcp_SegmentRtType *segment;
    Xcp_DaqListRtType *daqList;
    Xcp_DtoQueueType *dtoQueue;
} Xcp_RtType;

typedef struct
{
    const Xcp_ConfigType *config;
    const Xcp_GeneralType *general;
    const uint8 xcpRtRef; /* not part of the specification... */
} Xcp_Type;

/** @} */

#ifdef __cplusplus
};

#endif /* ifdef __cplusplus */

#endif /* define XCP_TYPES_H */
