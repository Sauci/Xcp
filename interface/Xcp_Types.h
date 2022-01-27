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

#ifndef COMSTACK_TYPES_H
#include "ComStack_Types.h"
#endif /* #ifndef COMSTACK_TYPES_H */

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

typedef enum
{
    /**
     * @brief consistency on ODT level (default value)
     */
    ODT = 0x00u,

    /**
     * @brief consistency on DAQ list level
     */
    //DAQ,

    /**
     * @brief consistency on event channel level
     */
    EVENT
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
    LITTLE_ENDIAN = 0x00u,
    BIG_ENDIAN = 0x01u
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

typedef struct
{
    const uint8 id;
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
    const uint8 odtNumber;

    /**
     * @brief this reference maps the ODT to the according DTO in which it will be transmitted
     */
    const Xcp_DtoType *odt2DtoMapping;

    /**
     * @brief This container collects all configuration parameters that comprise an ODT entry
     */
    Xcp_OdtEntryType *odtEntry;
} Xcp_OdtType;

typedef struct
{
    const uint16 number;
    const Xcp_EventChannelTypeType type;
    const uint8 maxOdt;
    const uint8 maxOdtEntries;
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
     * @brief References all DAQ lists that are trigged by this event channel.
     */
    const Xcp_DaqListType *triggeredDaqListRef;
    const uint32 triggeredDaqListRefCount;
} Xcp_EventChannelType;

typedef struct
{
    const Xcp_DaqConfigTypeType daqConfigType;
    const uint16 daqCount;
    const boolean devErrorDetect;
    const boolean flashProgrammingEnabled;
    const Xcp_IdentificationFieldTypeType identificationFieldType;
    const ieee_float mainFunctionPeriod;
    const uint8 maxCto;
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
    const boolean xcpSetRequestApiEnable; /* not part of the specification... */
    const boolean xcpGetIdApiEnable; /* not part of the specification... */
    const boolean xcpGetSeedApiEnable; /* not part of the specification... */
    const boolean xcpDownloadApiEnable; /* not part of the specification... */
    const boolean xcpDownloadMaxApiEnable; /* not part of the specification... */
    const boolean xcpShortDownloadApiEnable; /* not part of the specification... */
    const boolean xcpSetCalPageApiEnable; /* not part of the specification... */
    const boolean xcpGetCalPageApiEnable; /* not part of the specification... */
    const boolean xcpClearDaqListApiEnable; /* not part of the specification... */
    const boolean xcpSetDaqPtrApiEnable; /* not part of the specification... */
    const boolean xcpWriteDaqApiEnable; /* not part of the specification... */
    const boolean xcpSetDaqListModeApiEnable; /* not part of the specification... */
    const boolean xcpGetDaqListModeApiEnable; /* not part of the specification... */
    const boolean xcpStartStopDaqListApiEnable; /* not part of the specification... */
    const boolean xcpStartStopSynchApiEnable; /* not part of the specification... */
    const boolean xcpGetDaqClockApiEnable; /* not part of the specification... */
    const boolean xcpReadDaqApiEnable; /* not part of the specification... */
    const boolean xcpGetDaqProcessorInfoApiEnable; /* not part of the specification... */
    const boolean xcpGetDaqResolutionInfoApiEnable; /* not part of the specification... */
    const boolean xcpGetDaqListInfoApiEnable; /* not part of the specification... */
    const boolean xcpGetDaqEventInfoApiEnable; /* not part of the specification... */
    const boolean xcpFreeDaqApiEnable; /* not part of the specification... */
    const boolean xcpAllocDaqApiEnable; /* not part of the specification... */
    const boolean xcpAllocOdtApiEnable; /* not part of the specification... */
    const boolean xcpAllocOdtEntryApiEnable; /* not part of the specification... */
    const boolean xcpProgramClearApiEnable; /* not part of the specification... */
    const boolean xcpProgramApiEnable; /* not part of the specification... */
    const boolean xcpProgramMaxApiEnable; /* not part of the specification... */
    const boolean xcpGetCommModeInfoApiEnable; /* not part of the specification... */
    const Xcp_ByteOrderType byteOrder; /* not part of the specification... */
    const Xcp_AddressGranularityType addressGranularity; /* not part of the specification... */
    const boolean slaveBlockModeSupported; /* not part of the specification... */
} Xcp_GeneralType;

/**
 * @brief this is the type of the data structure containing the initialization data for XCP.
 */
typedef struct
{
    const Xcp_CommunicationChannelType *communicationChannel;
    Xcp_DaqListType *daqList;
    const Xcp_EventChannelType *eventChannel;
    const void *pdu;
} Xcp_ConfigType;

typedef struct
{
    Xcp_ConfigType *config;
    const Xcp_GeneralType *general;
} Xcp_Type;

/** @} */

#ifdef __cplusplus
};

#endif /* ifdef __cplusplus */

#endif /* define XCP_TYPES_H */
