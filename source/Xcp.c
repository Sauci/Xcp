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

#ifndef XCP_TYPES_H
#include "Xcp_Types.h"
#endif /* #ifndef XCP_TYPES_H */

#ifndef CANIF_H
#include "CanIf.h"
#endif /* #ifndef CANIF_H */

#include "Xcp_Cfg.h"

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

#define XCP_CONNECT_MODE_NORMAL (0x00u)
#define XCP_CONNECT_MODE_USER_DEFINED (0x01u)

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* local data type definitions (typedef, struct).                                                 */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_LTDEF
 * @{
 */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* local macros definitions (#define, inline).                                                    */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_LMDEF
 * @{
 */

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

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* local constant definitions (static const).                                                     */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_LCDEF
 * @{
 */

#define Xcp_START_SEC_VAR_FAST_INIT_UNSPECIFIED
#include "Xcp_MemMap.h"

static uint8 (* Xcp_PIDTable[0x100u])(PduIdType rxPduId, const PduInfoType *pPduInfo) = {
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

#define Xcp_STOP_SEC_VAR_FAST_INIT_UNSPECIFIED
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
    if (pConfig != NULL_PTR)
    {
        Xcp_Ptr = pConfig;

        Xcp_State = XCP_INITIALIZED;

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
    uint8 result;
    uint8_least daq_idx;
    uint32_least dto_idx;

    boolean valid_pdu_id = FALSE;

    if (Xcp_State == XCP_INITIALIZED)
    {
        if (pPduInfo != NULL_PTR)
        {
            /* First we check if the received PDU ID is the one which has been configured for CTO
             * reception. */
            if (rxPduId == Xcp_Ptr->config->communicationChannel->channel_rx_pdu_ref->id) {
                valid_pdu_id = TRUE;
            }
            else
            {
                for (daq_idx = 0x00u; daq_idx < Xcp_Ptr->general->daqCount; daq_idx++)
                {
                    /* Then, we check if the received PDU ID is one which has been configured for a
                     * DAQ stimulation. */
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
                    result = Xcp_PIDTable[pPduInfo->SduDataPtr[0x00u]](rxPduId, pPduInfo);

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
    if (Xcp_State == XCP_INITIALIZED) {
        
    } else {
        Xcp_ReportError(0x00u, XCP_CAN_IF_TX_CONFIRMATION_API_ID, XCP_E_UNINIT);
    }
}

Std_ReturnType Xcp_CanIfTriggerTransmit(PduIdType txPduId, PduInfoType *pPduInfo)
{
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
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqAllocOdt(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqAllocDaq(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqFreeDaq(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqGetDaqEventInfo(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


/**
 * Position Type Description
 * 0        BYTE Packet ID: 0xFF
 * 1        BYTE DAQ_LIST_PROPERTIES Specific properties for this DAQ list
 * 2        BYTE MAX_ODT Number of ODTs in this DAQ list
 * 3        BYTE MAX_ODT_ENTRIES Maximum number of entries in an ODT
 * 4,5      WORD FIXED_EVENT Number of the fixed event channel for this DAQ list
 */
static uint8 Xcp_DTOCmdDaqGetDaqListInfo(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


/**
 * Position Type Description
 * 0        BYTE Packet ID: 0xFF
 * 1        BYTE GRANULARITY_ODT_ENTRY_SIZE_DAQ Granularity for size of ODT entry (DIRECTION = DAQ)
 * 2        BYTE MAX_ODT_ENTRY_SIZE_DAQ Maximum size of ODT entry (DIRECTION = DAQ)
 * 3        BYTE GRANULARITY_ODT_ENTRY_SIZE_STIM Granularity for size of ODT entry (DIRECTION = STIM)
 * 4        BYTE MAX_ODT_ENTRY_SIZE_STIM Maximum size of ODT entry (DIRECTION = STIM)
 * 5        BYTE TIMESTAMP_MODE Timestamp unit and size
 * 6,7      WORD TIMESTAMP_TICKS Timestamp ticks per unit
 */
static uint8 Xcp_DTOCmdDaqGetDaqResolutionInfo(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


/**
 * Position Type Description
 * 0        BYTE Packet ID: 0xFF
 * 1        BYTE DAQ_PROPERTIES General properties of DAQ lists
 * 2,3      WORD MAX_DAQ Total number of available DAQ lists
 * 4,5      WORD MAX_EVENT_CHANNEL Total number of available event channels
 * 6        BYTE MIN_DAQ Total number of predefined DAQ lists
 * 7        BYTE DAQ_KEY_BYTE
 */
static uint8 Xcp_DTOCmdDaqGetDaqProcessorInfo(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqReadDaq(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqGetDaqClock(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqStartStopSynch(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqStartStopDaqList(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqGetDaqListMode(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqSetDaqListMode(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqWriteDaq(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqSetDaqPtr(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdDaqClearDaqList(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTODaqStimPacket(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTODaqPacket(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdStdUserCmd(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdStdTransportLayerCmd(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdStdBuildChecksum(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdStdShortUpload(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdStdUpload(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


/**
 * Position Type  Description
 * 0        BYTE  Command Code: 0xF6
 * 1,2      BYTE  Reserved
 * 3        BYTE  Address extension
 * 4.7      DWORD Address
 */
static uint8 Xcp_DTOCmdStdSetMta(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdStdUnlock(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdStdGetSeed(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdStdSetRequest(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_DTOCmdStdGetId(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}

/**
 * Position Type Description
 * 0        BYTE Packet ID: 0xFF
 * 1        BYTE Reserved
 * 2        BYTE COMM_MODE_OPTIONAL
 * 3        BYTE Reserved
 * 4        BYTE MAX_BS
 * 5        BYTE MIN_ST
 * 6        BYTE QUEUE_SIZE
 * 7        BYTE XCP Driver Version Number
 */
static uint8 Xcp_DTOCmdStdGetCommModeInfo(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


/**
 * Position Type Description
 * 0        BYTE Packet ID: 0xFE
 * 1        BYTE Error Code = ERR_CMD_SYNCH
 */
static uint8 Xcp_CTOCmdStdSynch(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


/**
 * position type description
 * 0        BYTE Packet ID: 0xFF
 * 1        BYTE Current session status
 * 2        BYTE Current resource protection status
 * 3        BYTE Reserved
 * 4,5      WORD Session configuration ID
 */
static uint8 Xcp_CTOCmdStdGetStatus(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


static uint8 Xcp_CTOCmdStdDisconnect(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}


/**
 * request payload description:
 * 0        BYTE Packet ID: 0xFF
 * 1        BYTE Mode (00 = Normal 01 = user defined)
 *
 * positive response payload description:
 * 0        BYTE Packet ID: 0xFF
 * 1        BYTE RESOURCE
 * 2        BYTE COMM_MODE_BASIC
 * 3        BYTE MAX_CTO, Maximum CTO size [BYTE]
 * 4,5      WORD MAX_DTO, Maximum DTO size [BYTE]
 * 6        BYTE XCP Protocol Layer Version Number (most significant byte only)
 * 7        BYTE XCP Transport Layer Version Number (most significant byte only)
 */
static uint8 Xcp_CTOCmdStdConnect(PduIdType rxPduId, const PduInfoType *pPduInfo)
{
    uint8 result = E_OK;

    uint8 mode;

    (void)rxPduId;

    if (pPduInfo->SduLength >= 0x02u) {
        mode = pPduInfo->SduDataPtr[0x01u];

        if ((mode == XCP_CONNECT_MODE_NORMAL) || (mode == XCP_CONNECT_MODE_USER_DEFINED)) {

        } else {
            result = XCP_E_ASAM_INVALID_CTO_PARAMETER;
        }
    } else {
        result = XCP_E_ASAM_INVALID_CTO_PACKET;
    }

    return result;
}

/** @} */

#ifdef __cplusplus
}

#endif /* ifdef __cplusplus */
