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

#ifndef XCP_INTERNAL_H
#include "Xcp_Internal.h"
#endif /* #ifndef XCP_INTERNAL_H */

/*------------------------------------------------------------------------------------------------*/
/* local function declarations (static).                                                          */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_C_LFDECL
 * @{
 */

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

static uint8 (* const Xcp_PIDTable[0x100u])(boolean *responseExpected, const PduInfoType *pPduInfo) = {
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
#if (XCP_PAGING_SUPPORTED == STD_ON)
    Xcp_DTOCmdStdGetSegmentMode, /* GET_SEGMENT_MODE 0xE5, optional */
#else
    Xcp_CmdNotImplemented, /* GET_SEGMENT_MODE 0xE5, optional */
#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
#if (XCP_PAGING_SUPPORTED == STD_ON)
    Xcp_DTOCmdStdSetSegmentMode, /* SET_SEGMENT_MODE 0xE6, optional */
#else
    Xcp_CmdNotImplemented, /* SET_SEGMENT_MODE 0xE6, optional */
#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
    Xcp_DTODaqPacket, /* 0xE7 */
    Xcp_DTODaqPacket, /* 0xE8 */
#if (XCP_PAGING_SUPPORTED == STD_ON)
    Xcp_DTOCmdStdGetPagProcessorInfo, /* GET_PAG_PROCESSOR_INFO 0xE9, optional */
#else
    Xcp_CmdNotImplemented, /* GET_PAG_PROCESSOR_INFO 0xE9, optional */
#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
#if (XCP_PAGING_SUPPORTED == STD_ON)
    Xcp_DTOCmdStdGetCalPage, /* GET_CAL_PAGE 0xEA */
#else
    Xcp_CmdNotImplemented, /* GET_CAL_PAGE 0xEA */
#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
#if (XCP_PAGING_SUPPORTED == STD_ON)
    Xcp_DTOCmdStdSetCalPage, /* SET_CAL_PAGE 0xEB */
#else
    Xcp_CmdNotImplemented, /* SET_CAL_PAGE 0xEB */
#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
    Xcp_DTOCmdStdModifyBits, /* MODIFY_BITS 0xEC, optional */
    Xcp_DTOCmdStdShortDownload, /* SHORT_DOWNLOAD 0xED, optional */
    Xcp_DTOCmdStdDownloadMax, /* DOWNLOAD_MAX 0xEE, optional */
    Xcp_DTOCmdStdDownloadNext, /* 0xEF */
    Xcp_DTOCmdStdDownload, /* 0xF0 */
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

void(* const Xcp_ReadSlaveMemoryTable[])(void *address, uint8 extension, uint8 *pBuffer) = {
    Xcp_ReadSlaveMemoryU8,
    Xcp_ReadSlaveMemoryU16,
    Xcp_ReadSlaveMemoryU32
};

#define Xcp_STOP_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

void(* const Xcp_WriteSlaveMemoryTable[])(void *address, uint8 *pBuffer) = {
    Xcp_WriteSlaveMemoryU8,
    Xcp_WriteSlaveMemoryU16,
    Xcp_WriteSlaveMemoryU32
};

#define Xcp_STOP_SEC_CONST_UNSPECIFIED
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
    boolean dependencies_satisfied;

    if (pConfig != NULL_PTR)
    {
        Xcp_Ptr = pConfig;

        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.1
         * The following relations must always be fulfilled
         *  MAX_CTO mod AG = 0
         *  MAX_DTO mod AG = 0 */
        element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);

        /* XCP part 2 - Protocol Layer Specification 1.0/1.4
         * If SET_CAL_PAGE is implemented, GET_CAL_PAGE is required.
         * If GET_SEED is implemented, UNLOCK is required. */
        dependencies_satisfied = TRUE;

        if (((pConfig->general->ctoInfo[XCP_PID_CMD_SET_CAL_PAGE] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
            ((pConfig->general->ctoInfo[XCP_PID_CMD_GET_CAL_PAGE] & XCP_CTO_INFO_ENABLED_MASK) == 0x00u))
        {
            dependencies_satisfied = FALSE;
        }

        if (((pConfig->general->ctoInfo[XCP_PID_CMD_GET_SEED] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
            ((pConfig->general->ctoInfo[XCP_PID_CMD_UNLOCK] & XCP_CTO_INFO_ENABLED_MASK) == 0x00u))
        {
            dependencies_satisfied = FALSE;
        }

        if ((element_size != 0x00u) && (dependencies_satisfied == TRUE) &&
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
            for (idx = 0x00000000u; idx < Xcp_Ptr->general->maxSegment; idx ++) {
                Xcp_Rt[Xcp_Ptr->xcpRtRef].segment[idx].freeze = FALSE;
            }
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
    boolean response_expected = TRUE;

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
                                                result = Xcp_PIDTable[pid](&response_expected, pPduInfo);

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

                                Xcp_Internal.cto_response.successful_transmission_pending = response_expected;
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

                        if (Xcp_BlockTransferReadSlaveMemory() != E_OK)
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

void Xcp_CopyFromU16WithOrder(const uint16 src, uint8 *pDest, Xcp_ByteOrderType endianness)
{
    if (endianness == XCP_LITTLE_ENDIAN) {
        pDest[0x00u] = (uint8)(src & 0xFFu);
        pDest[0x01u] = (uint8)((src >> 0x08u) & 0xFFu);
    } else {
        pDest[0x01u] = (uint8)(src & 0xFFu);
        pDest[0x00u] = (uint8)((src >> 0x08u) & 0xFFu);
    }
}

void Xcp_CopyFromU32WithOrder(const uint32 src, uint8 *pDest, Xcp_ByteOrderType endianness)
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

void Xcp_CopyToU16WithOrder(const uint8 *pSrc, uint16 *pDest, Xcp_ByteOrderType endianness)
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

void Xcp_CopyToU32WithOrder(const uint8 *pSrc, uint32 *pDest, Xcp_ByteOrderType endianness)
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

void Xcp_FinalizeResPacket(const PduLengthType startIndex, PduInfoType *pPduInfo)
{
    uint16_least idx;

    pPduInfo->SduLength = startIndex;

    for (idx = startIndex; idx < Xcp_Ptr->general->maxCto; idx ++)
    {
        pPduInfo->SduDataPtr[idx] = Xcp_Ptr->general->trailingValue;
    }
}

void Xcp_FillErrorPacket(const uint8 errorCode, PduInfoType *pPduInfo)
{
    pPduInfo->SduDataPtr[0x00u] = XCP_PID_ERROR;
    pPduInfo->SduDataPtr[0x01u] = errorCode;

    Xcp_FinalizeResPacket(0x02u, pPduInfo);
}

void Xcp_FillErrorPacketWithData(const uint8 errorCode,
                                 const uint8 *pData,
                                 const uint8 dataLength,
                                 PduInfoType *pPduInfo)
{
    uint8_least idx;

    pPduInfo->SduDataPtr[0x00u] = XCP_PID_ERROR;
    pPduInfo->SduDataPtr[0x01u] = errorCode;

    for (idx = 0x00u; idx < dataLength; idx++)
    {
        pPduInfo->SduDataPtr[0x02u + idx] = pData[idx];
    }

    Xcp_FinalizeResPacket((PduLengthType)(0x02u + dataLength), pPduInfo);
}

void Xcp_BlockTransferAbort(void)
{
    Xcp_Internal.block_transfer.requested_elements = 0x00u;
    Xcp_Internal.block_transfer.frame_elements = 0x00u;
}

uint8 Xcp_ElementSizeForAddressGranularity(Xcp_AddressGranularityType ag) {
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

uint8_least Xcp_GetNumberOfAlignmentBytes(uint8_least alignmentByteIndex, uint8_least elementSize, uint8 maxCto)
{
    return (maxCto - alignmentByteIndex) - (((maxCto - alignmentByteIndex) / elementSize) * elementSize);
}

boolean Xcp_BlockTransferIsActive()
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

/**
 * @brief Initializes the internal memory transfer state.
 * @retval E_OK: The provided parameters are valid, and the transfer will start.
 * @retval E_NOT_OK: The provided parameters are not valid, and the transfer will be discarded.
 */
Std_ReturnType Xcp_DataTransferInitialize(uint8 numberOfDataElements,
                                          uint8 elementSize,
                                          uint8 alignment,
                                          uint8 budget,
                                          boolean blockModeSupported,
                                          uint8 maxBlockSize)
{
    Std_ReturnType result = E_OK;
    uint16 capacity;

    if ((numberOfDataElements != 0x00u) && (elementSize != 0x00u) && (budget >= alignment))
    {
        /* Number of elements that fit into a single frame, once the command header and any
         * address-granularity alignment bytes have been accounted for. */
        capacity = (uint16)((uint16)(budget - alignment) / elementSize);

        if (blockModeSupported == FALSE)
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.7 and 1.6.2.1.1
             * Without block transfer mode the whole payload travels in a single packet. */
            if ((uint16)numberOfDataElements > capacity)
            {
                result = E_NOT_OK;
            }
        }
        else if (maxBlockSize != 0x00u)
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1
             * In block mode the master may send up to MAX_BS consecutive packets. */
            if ((uint32)numberOfDataElements > ((uint32)capacity * (uint32)maxBlockSize))
            {
                result = E_NOT_OK;
            }
        }
        else
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.7
             * For slave block transfer no maximum block size applies, so the uint8 range of the
             * request parameter is the only bound. */
        }

        if (result == E_OK)
        {
            Xcp_Internal.block_transfer.requested_elements = numberOfDataElements;
            Xcp_Internal.block_transfer.frame_elements = 0x00u;
        }
    }
    else
    {
        result = E_NOT_OK;
    }

    return result;
}

void Xcp_BlockTransferAcknowledgeFrame()
{
    Xcp_Internal.block_transfer.requested_elements -= Xcp_Internal.block_transfer.frame_elements;
}

/**
 * @brief Processes memory read accesses on behalf of the master.
 * @retval E_OK: More frames awaited, the master expects consecutive frames from the slave.
 * @retval E_NOT_OK: No more frames awaited by the master, the slave will stop sending frames.
 */
Std_ReturnType Xcp_BlockTransferReadSlaveMemory()
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
        // TODO: fill with padding byte value here...
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

/**
 * @brief Processes memory write accesses on behalf of the master.
 * @retval E_OK: More frames awaited, the slave expects consecutive frames from the master.
 * @retval E_NOT_OK: No more frames awaited by the slave, the master will stop sending frames.
 */
Std_ReturnType Xcp_BlockTransferWriteSlaveMemory(uint8 *pBuffer, uint8 elementSize)
{
    Std_ReturnType result = E_OK;

    uint8_least idx;

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

    if ((Xcp_Internal.block_transfer.requested_elements * elementSize) <= (Xcp_Ptr->general->maxCto - 0x02u))
    {
        Xcp_Internal.block_transfer.frame_elements = Xcp_Internal.block_transfer.requested_elements;
    }
    else
    {
        Xcp_Internal.block_transfer.frame_elements = ((Xcp_Ptr->general->maxCto - 0x02u) / elementSize);
    }

    for (idx = 0x00u; idx < Xcp_Internal.block_transfer.frame_elements; idx++)
    {
        Xcp_WriteSlaveMemoryTable[Xcp_Ptr->general->addressGranularity](Xcp_Internal.memory_transfer.address, &pBuffer[idx * elementSize]);

        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1
         * The data block of the specified length (size) contained in the CMD will be copied into memory, starting at the MTA. The MTA will be
         * post-incremented by the number of data bytes. */
        Xcp_Internal.memory_transfer.address += elementSize;
    }

    Xcp_BlockTransferAcknowledgeFrame();

    /* Check if the currently processed frame is the last one. If so, inform the caller that the data transfer is terminated. */
    if (Xcp_Internal.block_transfer.requested_elements == 0x00u)
    {
        result = E_NOT_OK;
    }

    return result;
}

uint8 Xcp_GetProtectionStatus(void) {
    return Xcp_Internal.protection_status;
}

void Xcp_SetProtectionStatus(void) {
    Xcp_Internal.protection_status = Xcp_Internal.requested_protected_resource;
}

void Xcp_ClearProtectionStatus(void) {
    Xcp_Internal.protection_status = 0x00u;
}

uint8 Xcp_CmdNotImplemented(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.4
     * An attempt to execute a not implemented optional command will return ERR_CMD_UNKNOWN and
     * does not have any effect. */
    Xcp_FillErrorPacket(XCP_E_ASAM_CMD_UNKNOWN, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

/** @} */

#ifdef __cplusplus
}

#endif /* ifdef __cplusplus */
