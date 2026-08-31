/**
 * @file Xcp_Std.c
 * @author
 * @date
 *
 * @defgroup XCP_STD_C STANDARD command group implementation
 * @ingroup XCP
 */

#include "Xcp_Internal.h"

/*------------------------------------------------------------------------------------------------*/
/* local function declarations (static).                                                          */
/*------------------------------------------------------------------------------------------------*/

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

/*------------------------------------------------------------------------------------------------*/
/* local constant definitions (static const).                                                     */
/*------------------------------------------------------------------------------------------------*/

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

/*------------------------------------------------------------------------------------------------*/
/* local function definitions (static).                                                           */
/*------------------------------------------------------------------------------------------------*/

void *Xcp_BuildChecksum11(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
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

void *Xcp_BuildChecksum12(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
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

void *Xcp_BuildChecksum14(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
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

void *Xcp_BuildChecksum22(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
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

void *Xcp_BuildChecksum24(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
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

void *Xcp_BuildChecksum44(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
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

void *Xcp_BuildChecksumCRC16(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
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

void *Xcp_BuildChecksumCRC16CITT(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
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

void *Xcp_BuildChecksumCRC32(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult) {
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
uint8 Xcp_DTOCmdStdUserCmd(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint8 result = E_OK;

    *responseExpected = TRUE;

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

uint8 Xcp_DTOCmdStdTransportLayerCmd(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    *responseExpected = TRUE;

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

uint8 Xcp_DTOCmdStdBuildChecksum(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    void *upper_address;
    uint32_least block_size;
    uint8 checksum_type;
    uint32 checksum;
    uint8 element_size;
    void * (*checksum_function)(void *, const void *, uint32 *) = NULL_PTR;

    *responseExpected = TRUE;

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

uint8 Xcp_DTOCmdStdShortUpload(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint8_least idx;
    uint32 address;

    const uint8_least element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    const uint8_least alignment = Xcp_GetNumberOfAlignmentBytes(0x01u, element_size, Xcp_Ptr->general->maxCto);

    *responseExpected = TRUE;

    if (pPduInfo->SduDataPtr[0x01u] != 0x00u)
    {
        if (element_size != 0x00u)
        {
            if ((pPduInfo->SduDataPtr[0x01u] * element_size) <= (Xcp_Ptr->general->maxCto - 0x01u))
            {
                // TODO: check if the received SduLength corresponds to the number of elements...
                Xcp_CopyToU32WithOrder(&pPduInfo->SduDataPtr[0x04u], &address, Xcp_Ptr->general->byteOrder);

                Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

                // TODO: use Xcp_BlockTransferReadSlaveMemory() here...

                for (idx = 0x01u; idx < alignment + 0x01u; idx++)
                {
                    Xcp_Internal.cto_response.pdu_info.SduDataPtr[idx] = Xcp_Ptr->general->trailingValue;
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
        else
        {
            /* TODO: raise a DET error here? */
        }
    }
    else
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdStdUpload(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    *responseExpected = TRUE;

    uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    const uint8_least alignment = Xcp_GetNumberOfAlignmentBytes(0x02u, element_size, Xcp_Ptr->general->maxCto);
    const uint8 number_of_data_elements = pPduInfo->SduDataPtr[0x01u];

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.7
     * If the slave device does not support block transfer mode, all uploaded data are transferred in a single response packet. Therefore, the number
     * of data elements parameter in the request has to be in the range [1..MAX_CTO-1]. An ERR_OUT_OF_RANGE will be returned, if the number of data
     * elements is more than MAX_CTO-1.*/
    if (((Xcp_Ptr->general->slaveBlockModeSupported == FALSE) &&
         ((number_of_data_elements * element_size) <= (Xcp_Ptr->general->maxCto - 0x01u - (element_size - 0x01u)))) ||
        (Xcp_Ptr->general->slaveBlockModeSupported == TRUE))
    {
        if (Xcp_DataTransferInitialize(number_of_data_elements,
                                       element_size,
                                       (uint8)alignment,
                                       (uint8)(Xcp_Ptr->general->maxCto - 0x01u),
                                       Xcp_Ptr->general->slaveBlockModeSupported,
                                       0x00u) == E_OK)
        {
            if (Xcp_BlockTransferReadSlaveMemory() == E_NOT_OK) {
                /* Do nothing, last frame is waiting for TX confirmation. */
            }
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

uint8 Xcp_DTOCmdStdSetMta(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    *responseExpected = TRUE;

    Xcp_Internal.memory_transfer.extension = pPduInfo->SduDataPtr[0x03u];
    Xcp_CopyToU32WithOrder(&pPduInfo->SduDataPtr[0x04u], (uint32 *)&Xcp_Internal.memory_transfer.address, Xcp_Ptr->general->byteOrder);

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
    Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

uint8 Xcp_DTOCmdStdUnlock(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint16_least key_idx;
    uint16_least num_of_bytes_to_copy;

    *responseExpected = TRUE;

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

uint8 Xcp_DTOCmdStdGetSeed(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint8_least idx;
    uint8_least num_of_bytes_to_copy;
    uint8 mode;
    uint8 resource;

    Std_ReturnType result = E_OK;

    (void)pPduInfo;

    *responseExpected = TRUE;

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

uint8 Xcp_DTOCmdStdSetRequest(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint8 mode;
    uint16 session_configuration_id;

    Std_ReturnType result = E_OK;

    *responseExpected = TRUE;

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

uint8 Xcp_DTOCmdStdGetId(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    Std_ReturnType result = E_OK;

    uint32 identification_length;

    *responseExpected = TRUE;

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

uint8 Xcp_DTOCmdStdGetCommModeInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

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

/*------------------------------------------------------------------------------------------------*/
/* command handler definitions.                                                                  */
/*------------------------------------------------------------------------------------------------*/

uint8 Xcp_CTOCmdStdSynch(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_ERROR;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = XCP_E_ASAM_CMD_SYNCH;

    Xcp_FinalizeResPacket(0x02u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

uint8 Xcp_CTOCmdStdGetStatus(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = Xcp_Internal.session_status;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = Xcp_GetProtectionStatus();
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u] = 0xABu; /* TODO: implement me... */
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x05u] = 0xCDu; /* TODO: implement me... */

    Xcp_FinalizeResPacket(0x06u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

uint8 Xcp_CTOCmdStdDisconnect(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

    Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);

    Xcp_Internal.connection_status = XCP_CONNECTION_STATE_DISCONNECTED;

    return E_OK;
}

uint8 Xcp_CTOCmdStdConnect(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint8 resource = 0x00u;
    uint8 comm_mode_basic = 0x00u;

    uint8 mode = XCP_CONNECT_MODE_NORMAL;

    uint8 daq_idx;

    *responseExpected = TRUE;

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

