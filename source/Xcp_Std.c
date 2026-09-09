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

                /* Bounded by what the master has allocated, not by the configured pool. Under a
                 * static configuration Xcp_Init seeds allocated_daq_count from daqCount, and the
                 * generator emits daqListCount and XcpDaqCount from one expression, so the two
                 * bounds are the same number and this reads exactly as it always did. Under a
                 * dynamic one they differ until ALLOC_DAQ runs, and scanning the whole pool would
                 * answer for a slot the master never allocated -- reporting a CAN-Id for a DAQ
                 * list that does not exist yet. Each pool slot carries its index as its number
                 * (script/source_cfg.c.jinja2), so an unallocated slot is simply not reached and
                 * the ERR_OUT_OF_RANGE below is what the master gets. */
                for (daq_list_idx = 0x00u; daq_list_idx < Xcp_Internal.allocated_daq_count; daq_list_idx ++) {
                    if (Xcp_Ptr->config->daqList[daq_list_idx].number == daq_list_number) {
                        object_found = TRUE;

                        break;
                    }
                }

                if (object_found == TRUE) {
                    if (Xcp_Ptr->config->daqList[daq_list_idx].dtoCount > 0x00u) {
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
                        /* CAN_ID_FIXED. Reported as fixed because it is: this slave has no way to
                         * change a DAQ list's transmit identifier, and SET_DAQ_ID below is
                         * deliberately not implemented, so the answer is truthful rather than
                         * provisional. It replaced a "TODO: support configurable CAN ID", which
                         * read as an unfinished feature.
                         *
                         * The field's polarity -- 1 meaning fixed -- comes from the XCP CAN
                         * Transport Layer specification, which is NOT in docs/external. Confirm it
                         * there before relying on it for anything new; what is independently sound
                         * is that this value must not change while SET_DAQ_ID stays unimplemented. */
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x01u;
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0x00u;
                        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u;
                        Xcp_CopyFromU32WithOrder((uint32)Xcp_Ptr->config->daqList[daq_list_idx].dto[0x00u].dto2PduMapping.txPdu.id,
                                                 &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u],
                                                 Xcp_Ptr->general->byteOrder);

                        Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);
                    } else {
                        /* Unreachable for any schema-valid configuration -- config/xcp.schema.json
                         * gives `dtos` minItems 1, so every generated DAQ list has at least one
                         * DTO. It was an empty branch, which is worse than unreachable: it left
                         * the response buffer holding whatever the previous command wrote while
                         * responseExpected stayed TRUE, so the master would have read a stale
                         * positive response. That is the defect class D2 and D7 fixed twice in
                         * SP1; an unreachable trap is still a trap. */
                        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
                    }
                } else {
                    Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
                }
            } else {
                Xcp_FillErrorPacket(XCP_E_ASAM_CMD_SYNTAX, &Xcp_Internal.cto_response.pdu_info);
            }
        }else if (sub_command == 0xFDu) {
            if (pPduInfo->SduLength >= 0x08u) {
                /* SET_DAQ_ID, and it is NOT implemented on purpose. AUTOSAR SWS XCP R4.3.1 §4.1
                 * Limitations: "The SET_DAQ_ID command according to the XCP CAN Transport Layer
                 * Specification is not part of the AUTOSAR XCP module". This module tracks that
                 * SWS -- test/autosar_sws_test.py asserts against it -- so the refusal is
                 * conformance, not an unfinished feature, and ERR_CMD_UNKNOWN is exactly what
                 * 1.1/1.4 prescribes for an optional command a slave does not implement.
                 *
                 * Two further obstacles, either of which would need settling first if the decision
                 * were ever revisited. The normative definition of this sub-command is in the XCP
                 * CAN Transport Layer specification, which is not in docs/external, so its request
                 * layout cannot be cited from anything held here -- only inferred from the length
                 * check above and from GET_DAQ_ID's response shape. And changing a transmit
                 * identifier at runtime means CanIf_SetDynamicTxId (SWS_CANIF_00189), an API this
                 * module has never called, which additionally requires every DAQ transmit PDU to be
                 * configured as a dynamic L-PDU -- an integrator-side guarantee this module can
                 * neither verify nor impose.
                 *
                 * The length check is kept ahead of the refusal so a malformed request still gets
                 * ERR_CMD_SYNTAX. A syntactically invalid frame is invalid whether or not the
                 * command behind it exists, and answering ERR_CMD_UNKNOWN to a 3-byte request
                 * would say the sub-command is unknown when what is wrong is the request.
                 *
                 * Two commented-out Xcp_CopyTo* calls stood here, drafting the parse. They read
                 * from Xcp_Internal.cto_response.pdu_info -- the RESPONSE buffer -- rather than
                 * from pPduInfo, so they would not have parsed the request at all. Removed rather
                 * than left as a starting point for whoever picks this up. */
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
                                       0x00u,
                                       TRUE) == E_OK) /* DD70: UPLOAD is slave block mode -- the
                                                        * slave sends the frames. */
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

#if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON)
    /* SP4c Task 3, design doc DD85: "the format resets to defaults on SET_MTA" -- one of the three
     * doors that end PROGRAM_FORMAT's own lifetime, and the one this module reaches through
     * Xcp_PgmFormatReset (source/Xcp_Pgm.c) rather than by writing Xcp_Internal.pgm_format's own
     * fields directly: SET_MTA is a STD command, and DD63 keeps every writer of PGM state inside
     * Xcp_Pgm.c -- a STD command reaching into PGM state directly is the shape that produced a
     * memory disclosure two branches ago (SP4b's DD70). */
    Xcp_PgmFormatReset();
#endif /* #if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON) */

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
    Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

uint8 Xcp_DTOCmdStdUnlock(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint16_least key_idx;
    uint16_least num_of_bytes_to_copy;

    *responseExpected = TRUE;

    /* DD81. Two terms answering two different questions, and both are load-bearing.
     *
     * last_pid asks whether the immediately preceding command was a successful GET_SEED or a prior
     * frame of this same key. It cannot say WHICH -- it is a two-element set-membership test -- so
     * it cannot answer "was a seed actually issued", and on its own it admitted an UNLOCK against a
     * seed that never existed (XCP part 2 1.0/1.6.1.2.5: "The master only can send an UNLOCK
     * sequence if previously there was a GET_SEED sequence").
     *
     * seed.total_length asks exactly that second question. The mechanism already existed and
     * nothing read it: the sequence below zeroes this field once a full key arrives, to "enforce a
     * new seed to be requested prior to unlock a next resource". It stays non-zero for every frame
     * of a multi-frame key, so this admits the whole legitimate sequence and refuses a replay.
     *
     * ERR_SEQUENCE is not a deviation: UNLOCK's own 1.7.3.2.1 row lists it, with GET_SEED as its
     * prescribed pre-action. */
    if (((Xcp_Internal.last_pid == XCP_PID_CMD_GET_SEED) || (Xcp_Internal.last_pid == XCP_PID_CMD_UNLOCK)) &&
        (Xcp_Internal.seed.total_length != 0x00u))
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
                            Xcp_UnlockResources(Xcp_Internal.requested_protected_resource);
                            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.5: "The answer
                             * upon UNLOCK contains the Current Resource Protection Mask as described
                             * at GET_STATUS" -- so this byte reports what is STILL protected after
                             * the grant above, not the resource just granted. DD78: it used to
                             * report the granted set, which made a successful UNLOCK of CAL_PAG
                             * answer 0x01, i.e. "CAL_PAG is protected", at the moment it stopped
                             * being. */
                            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = Xcp_GetLockedResources();

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
                    else
                    {
                        /* Pre-existing, found by the acceptance pass over this branch's own
                         * earlier shared-state fixes (task 7,
                         * .superpowers/sdd/2026-09-07-xcp-shared-state-defects/task-7-report.md),
                         * not introduced by any of them. This `if` used to have no `else`: when
                         * the integrator's Xcp_CalcKey fails, nothing was written to
                         * cto_response.pdu_info and responseExpected (set TRUE at this function's
                         * entry) stayed TRUE, so whatever the previous command had left in that
                         * shared response buffer -- measured as GET_SEED's own positive answer,
                         * seed bytes included -- was transmitted as THIS UNLOCK's answer instead.
                         * The GET_DAQ_ID sub-command above (dtoCount == 0 branch) names this exact
                         * defect class in its own comment: D2/D7, fixed twice in SP1 -- an empty
                         * branch with responseExpected TRUE is a stale positive response, not a
                         * no-op, whether or not the branch is easy to reach.
                         *
                         * It also fed a stale non-error byte 0 to Xcp_CanIfRxIndication's last_pid
                         * gate (source/Xcp.c, DD72), which only advances last_pid when byte 0 is
                         * NOT XCP_PID_ERROR: a failed UNLOCK was indistinguishable from a
                         * successful one, so last_pid recorded a success this dispatch never
                         * earned. Filling a real error packet here, before that gate runs, is what
                         * a fix for either half needs -- there is only the one buffer and the one
                         * flag.
                         *
                         * XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.1's UNLOCK row
                         * (verified against the 1.0 PDF -- pdftotext -layout extracts it cleanly,
                         * the 1.1 copy does not) lists seven codes: ERR_CMD_BUSY, ERR_PGM_ACTIVE,
                         * ERR_CMD_UNKNOWN, ERR_CMD_SYNTAX, ERR_OUT_OF_RANGE, ERR_ACCESS_LOCKED and
                         * ERR_SEQUENCE. None fits an integrator's key-derivation callback failing
                         * outright: this is not a busy/active/unknown/syntax condition; the
                         * master's own key bytes are not what is "out of range" (the slave never
                         * got as far as evaluating them); ERR_ACCESS_LOCKED is the sibling branch
                         * immediately above, for a KEY MISMATCH -- 1.0/1.6.1.2.5's own "the key is
                         * checked ... if the key is not accepted" presupposes a key WAS computed
                         * and compared, which did not happen here, and reusing it would also pull
                         * in a disconnect this condition never reached that check to earn;
                         * ERR_SEQUENCE is the row's OTHER UNLOCK user, for the master's own
                         * chunking mistake -- nothing about this request is out of sequence, the
                         * master sent a well-formed UNLOCK after a genuine GET_SEED.
                         *
                         * This is the identical shape DD57 already recorded for PROGRAM_RESET's own
                         * integrator-callback failure (source/Xcp_Pgm.c, Xcp_PgmCompleteProgramReset):
                         * PROGRAM_RESET's own 1.7.3.2.5 row lists no ERR_GENERIC either (only
                         * ERR_CMD_BUSY, ERR_PGM_ACTIVE, ERR_CMD_SYNTAX, ERR_SEQUENCE -- checked
                         * against the same 1.0 PDF), and that comment records "of the listed [codes]
                         * only ERR_SEQUENCE could be pressed into service -- a worse fit, since
                         * nothing about the request is out of sequence", the same reasoning that
                         * rules it out here. The same deviation is kept: XCP_E_ASAM_GENERIC, matching
                         * 1.0/1.1.3.3's own description of that code ("the error packet contains an
                         * implementation specific slave device error code"). This is NOT the same as
                         * PROGRAM_START/PROGRAM_PREPARE's own use of it (source/Xcp_Pgm.c,
                         * interface/Xcp.h) -- checked, and their own 1.7.3.2.5 rows list ERR_GENERIC
                         * directly, so answering it there is direct compliance, not a deviation; only
                         * PROGRAM_RESET's row is the genuine precedent for "listed nowhere, chosen
                         * anyway", and this UNLOCK branch follows that one specifically, rather than a
                         * listed code that would misattribute an internal failure to the master's own
                         * request. */
                        Xcp_FillErrorPacket(XCP_E_ASAM_GENERIC, &Xcp_Internal.cto_response.pdu_info);
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
                    /* An intermediate frame of a multi-frame key: nothing has been granted yet, so
                     * this reports the mask unchanged -- the same Current Resource Protection Mask
                     * (1.0/1.6.1.1.3) the completed sequence above reports, read at a moment when it
                     * still holds everything it held before the sequence began. */
                    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = Xcp_GetLockedResources();
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

            /* DD72 (authentication bypass, pre-existing). This used to assign
             * requested_protected_resource unconditionally, before either check above could
             * refuse the request, and never rolled it back on failure -- so a GET_SEED that never
             * produced a seed still left this resource requestable. Xcp_UnlockResources
             * (source/Xcp.c) clears this field's bits out of locked_resource once UNLOCK's key
             * matches, with no way to tell "GET_SEED succeeded for this resource" from "GET_SEED
             * was merely asked for this resource and refused". Committing the write only once
             * both checks above have passed is a true rollback rather than a reset to a fixed
             * value: whatever resource (or none, XCP_RESOURCE_PROTECTION_STATUS_MASK_NONE) was
             * requested before this attempt is what stays in effect. This is one of two
             * independent legs the defect needs both of -- the other is last_pid's own write in
             * Xcp_CanIfRxIndication (source/Xcp.c), which Xcp_DTOCmdStdUnlock below reads as "the
             * previous command was a successful GET_SEED"; see test/seed_key_defects_test.py. */
            if (result == E_OK)
            {
                Xcp_Internal.requested_protected_resource = resource;
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

        /* DD73 (key not bound to the seed, pre-existing). This branch used to also set
         * Xcp_Internal.seed.total_length to 0x00u right here, once the final chunk of the seed
         * had been queued for this response, to mean "nothing left to send" for GET_SEED's own
         * pacing. Xcp_DTOCmdStdUnlock above reads that very same field as the seed's LENGTH when
         * it calls Xcp_CalcKey, once the master's key has fully arrived -- so an integrator
         * honouring that parameter always computed its key from a zero-length seed, regardless of
         * what had actually been transmitted: XCP part 2 - Protocol Layer Specification
         * 1.1/1.6.1.2.4 and 1.1/1.6.1.2.5 both depend on the key being a function of the seed the
         * slave issued, which a length of zero cannot be. The two meanings cannot share one
         * field. total_length now always holds the seed's true, constant length once
         * Xcp_GetSeed has produced it; every line below already computes what remains to be sent
         * from current_index, so removing the reset here does not change GET_SEED's own
         * multi-frame pacing -- nor GET_SEED(mode=1)'s own sequence gate above, which only asks
         * whether a seed is currently held at all, never whether its transmission has finished.
         * Xcp_DTOCmdStdUnlock's own reset of this same field, a few lines above (after
         * Xcp_CalcKey has already been called), is what actually discards the seed once its key
         * has been consumed, and still enforces a new seed being required before the next UNLOCK.
         * See test/seed_key_defects_test.py. */
        if ((Xcp_Internal.seed.total_length - Xcp_Internal.seed.current_index) <= (Xcp_Ptr->general->maxCto - (uint8)0x02u))
        {
            num_of_bytes_to_copy = (Xcp_Internal.seed.total_length - Xcp_Internal.seed.current_index);
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
    Std_ReturnType result = E_OK;
    uint8 accepted_request_mask = XCP_SESSION_STATUS_MASK_STORE_CAL_REQ;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.3, mode byte:
     *
     *   bit    7   6   5   4   3              2              1   0
     *          x   x   x   x   CLEAR_DAQ_REQ  STORE_DAQ_REQ  x   STORE_CAL_REQ
     *
     * STORE_CAL_REQ is unconditional: Xcp_MainFunction fulfils it through the integrator's
     * store-calibration callback, then clears the bit and raises EV_STORE_CAL. STORE_DAQ_REQ and
     * CLEAR_DAQ_REQ each act on a non-volatile DAQ list configuration this module keeps only when
     * the matching integrator callback is configured in -- Xcp_StoreDaqConfiguration and
     * Xcp_ClearDaqConfiguration (interface/Xcp.h), polled from Xcp_MainFunction on the identical
     * contract STORE_CAL_REQ's own callback follows. Each mode bit is therefore folded into the
     * accepted mask below only when its own xcp_store_daq_configuration_api_enable /
     * xcp_clear_daq_configuration_api_enable flag is enabled (Xcp_Ptr->general, generated by
     * script/source_cfg.c.jinja2); an unconfigured build has nothing to fulfil either request and
     * refuses both under this same section's "If the slave device does not support the requested
     * mode, an ERR_OUT_OF_RANGE will be returned" -- exactly as it always has.
     *
     * Accepting a mode with nothing behind it is not merely inaccurate, it is a session-wide denial
     * of service. Nothing would clear a request bit that no code fulfils, and Xcp_CanIfRxIndication
     * refuses every command carrying ERR_PGM_ACTIVE -- 42 of them in the default build, 38 with
     * flash programming enabled (four Xcp_CTOErrorMatrix rows carry the bit only with that gate
     * off) -- for as long as one is set, so a single conformant SET_REQUEST would disable most of
     * the command set until the next CONNECT.
     * Design doc DD95 (docs/superpowers/specs/2026-09-09-xcp-daq-nv-storage-design.md) is what makes
     * accepting them safe: both new callbacks copy STORE_CAL_REQ's own rule, applied below in
     * Xcp_MainFunction (Xcp.c) -- E_OK means finished, whatever the status code says, so the request
     * bit clears on every exit and only a callback that never finishes can wedge it.
     *
     * These bit positions coincide with the GET_STATUS session status bits of 1.0/1.6.1.1.3,
     * which is what makes the assignment below sound; both bit tables were read to confirm it. */
    if (Xcp_Ptr->general->storeDaqConfigurationApiEnable == TRUE)
    {
        accepted_request_mask |= XCP_SESSION_STATUS_MASK_STORE_DAQ_REQ;
    }

    if (Xcp_Ptr->general->clearDaqConfigurationApiEnable == TRUE)
    {
        accepted_request_mask |= XCP_SESSION_STATUS_MASK_CLEAR_DAQ_REQ;
    }

    if ((pPduInfo->SduDataPtr[0x01u] & (uint8)(~accepted_request_mask)) != 0x00u)
    {
        result = XCP_E_ASAM_OUT_OF_RANGE;
    }

    if (result == E_OK)
    {
        /* The session configuration id in bytes 2,3 belongs to STORE_DAQ_REQ: 1.0/1.6.1.2.3 has the
         * slave store it in non-volatile memory alongside the DAQ lists, and CLEAR_DAQ_REQ reset it
         * to 0. Staged into requested_session_configuration_id unconditionally, regardless of which
         * mode bit(s) this request actually carried: Xcp_MainFunction (Xcp.c) reads it only while
         * STORE_DAQ_REQ is pending, and this handler's own dispatch gate refuses every SET_REQUEST
         * with ERR_PGM_ACTIVE (Xcp_CTOErrorMatrix, Xcp_CanIfRxIndication in Xcp.c) for as long as
         * any of the three session-status request bits is set -- so a store already in flight can
         * never have its id overwritten by a later, unrelated SET_REQUEST landing here first.
         * Xcp_StoreDaqConfiguration itself is still called from Xcp_MainFunction, not here (design
         * doc DD99/DD100, docs/superpowers/specs/2026-09-09-xcp-daq-nv-storage-design.md): reading
         * the bytes is this handler's job, committing them is the polled callback's. The check that
         * once stood here rejected a non-zero id, but did so after this branch had already been
         * entered: it set `result` and then finalized a positive response regardless, so it never
         * reached the master. 1.0/1.6.1.2.3 gives the id the full uint16 range and reserves no
         * values, so nothing here validates it either. */
        Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &Xcp_Internal.requested_session_configuration_id, Xcp_Ptr->general->byteOrder);

        Xcp_Internal.session_status |= pPduInfo->SduDataPtr[0x01u];

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
        /* DD75 (docs/superpowers/specs/2026-09-07-xcp-shared-state-defects-design.md). XCP part 2
         * - Protocol Layer Specification 1.1/1.6.1.2.2 (1.0/1.6.1.2.2, identical wording): with
         * mode 0, "the slave device sets the Memory Transfer Address (MTA) to the location from
         * which the master device may upload the requested identification". 1.1/1.6.1.2.6
         * (1.0/1.6.1.2.6, same wording) defines the MTA itself as one complete pointer -- "32Bit
         * address + 8Bit extension" -- not an address alone, so setting it means setting both
         * members. Only .address used to be assigned here, leaving .extension holding whatever an
         * earlier, unrelated SET_MTA last left there for the UPLOAD that follows this command to
         * read the identification through -- source/Xcp.c and the checksum helpers in this file
         * both read the pair, never .address alone.
         *
         * GET_ID's own text never states which extension value to use here -- the specification
         * does not settle it, the same kind of gap already found for the MTA's pre-SET_MTA value
         * (this file, Xcp_CTOCmdStdConnect). What the specification does define is what a
         * non-zero extension is FOR: 1.1/1.6.3.1.4 (1.0/1.6.3.2.2, identical wording,
         * GET_SEGMENT_INFO) reads "ADDRESS_EXTENSION is used in SET_MTA, SHORT_UPLOAD and
         * SHORT_DOWNLOAD when accessing a PAGE within this SEGMENT" -- a non-zero extension
         * selects a PAGE within a configured CAL/PAG SEGMENT. Xcp_Ptr->general->identification is
         * not part of any segments[] entry; it is plain, slave-owned descriptive data that lives
         * entirely outside the page-switching model, so there is no SEGMENT for a non-zero
         * extension to name here.
         * 0x00u is also the specification's own vocabulary for "nothing meaningful on this pair":
         * 1.1/1.6.1.2.3 (1.0/1.6.1.2.3, SET_REQUEST) reads "All ODT entries reset to address = 0,
         * extension = 0" for the identical kind of pointer with nothing of its own to report. And
         * it is what this module already uses whenever it hands the MTA a plain descriptive
         * pointer of its own rather than an address the master supplied: Xcp_Init and
         * Xcp_CTOCmdStdConnect both pair NULL_PTR with extension = 0x00u, and
         * Xcp_DTOCmdDaqGetDaqEventInfo (source/Xcp_Daq.c) sets this exact pair when it points the
         * MTA at an event channel's name for a following UPLOAD -- checked to actually apply here,
         * not copied on sight: that pointer and this one are the same category of thing for the
         * same structural reason above, neither living in a CAL/PAG segment. */
        Xcp_Internal.memory_transfer.address = (void *)Xcp_Ptr->general->identification;
        Xcp_Internal.memory_transfer.extension = 0x00u;

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

    /* Design doc DD101 (docs/superpowers/specs/2026-09-09-xcp-daq-nv-storage-design.md): while
     * DD100's start-up read of the session configuration id is still outstanding, this module
     * does not yet know it, and reporting the field's pre-read value below would be
     * indistinguishable from a legitimate "nothing stored" answer. XCP part 2 - Protocol Layer
     * Specification 1.1/1.7.3.2.1 gives GET_STATUS's row exactly one error code for this,
     * ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE, with the prescribed master action "display error /
     * repeat" -- precisely "ask again once the read has finished". 1.0 has no error codes on this
     * row at all. Reachable only once readStoredSessionConfigurationIdApiEnable has armed
     * Xcp_Internal.session_configuration_id_read_state OUTSTANDING (Xcp_Init, source/Xcp.c), so a
     * build with nothing to read never takes this branch and GET_STATUS answers normally from the
     * first call, exactly as it always has. */
    if (Xcp_Internal.session_configuration_id_read_state == XCP_NV_READ_OUTSTANDING)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_RESOURCE_TEMPORARY_NOT_ACCESSIBLE, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = Xcp_Internal.session_status;
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.3, byte 2: the Current Resource
         * Protection Status -- a set bit means that group IS protected. Transmitted verbatim, because
         * Xcp_Internal.locked_resource holds exactly that (DD78). */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = Xcp_GetLockedResources();
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u;
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.3, bytes 4,5: session configuration id,
         * in the configured byte order. Xcp_Internal.session_configuration_id (source/Xcp_Internal.h)
         * is the module's own held copy of what design doc DD99
         * (docs/superpowers/specs/2026-09-09-xcp-daq-nv-storage-design.md) tracks: adopted from a
         * SET_REQUEST carrying STORE_DAQ_REQ once Xcp_StoreDaqConfiguration reports a zero status
         * (Xcp_MainFunction, source/Xcp.c), reset to 0 once CLEAR_DAQ_REQ similarly completes clean,
         * adopted from non-volatile storage once DD100's own read above completes (the condition
         * this branch's own gate exists to wait out), and left untouched by CONNECT -- it reflects
         * what non-volatile memory holds, which a reconnect does not alter. Transmitted verbatim,
         * the same shape Xcp_Internal.locked_resource above already has for byte 2. This reported
         * the hardcoded constant 0 -- honest only because no code fulfilled STORE_DAQ_REQ yet --
         * until Task 2 gave the field a real value; before that it reported the fabricated constant
         * 0xABCD, until defect D9 was closed. */
        Xcp_CopyFromU16WithOrder(Xcp_Internal.session_configuration_id, &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u], Xcp_Ptr->general->byteOrder);

        Xcp_FinalizeResPacket(0x06u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

void Xcp_DisconnectSession(void)
{
    Xcp_Internal.connection_status = XCP_CONNECTION_STATE_DISCONNECTED;

    /* Release a dynamic allocation the disconnecting master never freed, so it cannot leak into
     * the next session. DYNAMIC only, and deliberately so: the gap being closed is that the
     * allocation state machine starts in XCP_DAQ_ALLOC_FREE and accepts ALLOC_DAQ with no
     * preceding FREE_DAQ (DD28), and repeated ALLOC_DAQ accumulates -- so an allocation left
     * standing at DISCONNECT is one the NEXT master's ALLOC_DAQ adds to, handing it more lists
     * than it asked for, carrying the previous session's ODT entries. A STATIC configuration has
     * no allocation to leak: its lists are generated, not allocated, so there is nothing here for
     * it to release.
     *
     * This therefore does not touch a static build's configured DAQ entries. Whether DISCONNECT
     * ought to clear those as well is a separate question about XCP part 1 - Overview 2.3 and is
     * not settled here; changing it would be a behaviour change to the static model, which SP2d
     * is required to leave byte-for-byte as it is (DD25).
     *
     * SP3 puts a stimulation slot behind this same gate, so state the resulting invariant rather
     * than leaving it to be inferred: a slot is released on Xcp_Init always, on FREE_DAQ always,
     * and on DISCONNECT only under DAQ_DYNAMIC. A STATIC configuration's slot therefore survives a
     * disconnect, keeping whatever the last master stimulated with -- which is the same residue
     * that model already has for its DAQ direction, where DISCONNECT leaves a running list running
     * and sampling. Stimulation inherits that behaviour rather than adding a class of its own, and
     * closing it means answering the Overview 2.3 question above for the whole static model, not
     * for the slot alone.
     *
     * Shared with PROGRAM_RESET (Xcp_Pgm.c, DD57): factored out of Xcp_CTOCmdStdDisconnect below
     * because a second door to XCP_CONNECTION_STATE_DISCONNECTED is a second place to forget this
     * unwind -- which is exactly what happened before this function existed, fix round 1 finding
     * 2. Sharing it is what makes the two doors structurally incapable of diverging again. */
    if (Xcp_Ptr->general->daqConfigType == DAQ_DYNAMIC)
    {
        Xcp_DaqFreeAll();
    }
}

uint8 Xcp_CTOCmdStdDisconnect(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

    Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);

    Xcp_DisconnectSession();

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

    /* XCP part 2 - Protocol Layer Specification 1.1/1.6.1.1.1
     * "0 = DAQ lists not available / 1 = DAQ lists available". The bit describes the group, and
     * the specification's own note names commands by example. Requiring every optional command
     * made disabling one -- GET_DAQ_CLOCK, say -- report that the slave cannot do DAQ at all.
     * These six are what an available DAQ list actually needs: clear it, point at it, fill it,
     * set its mode, and start or stop it, individually or synchronously. */
    if (((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_CLEAR_DAQ_LIST] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_SET_DAQ_PTR] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_WRITE_DAQ] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_SET_DAQ_LIST_MODE] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_START_STOP_DAQ_LIST] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
        ((Xcp_Ptr->general->ctoInfo[XCP_PID_CMD_START_STOP_SYNCH] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u))
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

#if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON)
    /* Final-review finding 1. A CONNECT begins a new session, and no state of the previous one may
     * survive into it: XCP part 1 - Overview 1.0/2.3, quoted in full at Xcp_CanIfRxIndication's own
     * disconnected-state gate (source/Xcp.c), has the session status, the DAQ lists and the
     * protection status bits all reset between sessions. A programming session is exactly that kind
     * of state, and until this line it was the one piece of it that outlived a reconnect.
     *
     * That is not a theoretical leak. PROGRAM_RESET is the only other writer that clears an ACTIVE
     * pgm_state (Xcp_PgmCompleteProgramReset, Xcp_Pgm.c), and a master that dies mid-sequence never
     * sends one: DISCONNECT is itself refused ERR_PGM_ACTIVE by DD51's gate while the session is
     * open, so the shared unwind is never reached from that door either, and the next master
     * inherited ~38 commands -- all of CAL, all of DAQ, GET_SEED, SET_REQUEST -- refused
     * ERR_PGM_ACTIVE forever, with no command able to clear it. Two configurations reach the same
     * place without any master dying: xcp_program_reset_api_enable disabled (DD59 makes each PGM
     * command independently configurable, and nothing couples the two keys), and an
     * Xcp_ProgramReset that reports failure.
     *
     * DD50 is why this is the module's job at all. 1.1/1.6.5.1.4 assumes a hardware reset ends the
     * sequence; AUTOSAR SWS_Xcp_00856 makes this module decline that reset, so clearing the state
     * falls to the module -- and it was cleared on exactly one of the paths the reset would have
     * covered.
     *
     * CONNECT, and not Xcp_DisconnectSession above, deliberately. DISCONNECT is refused while the
     * session is ACTIVE, so the shared unwind is not a door that can be relied upon to run; CONNECT
     * is (its Xcp_CTOErrorMatrix row is 0x00u, and Xcp_CanIfRxIndication admits it from the
     * disconnected state by name), which is why Xcp_Init already does the same thing here for the
     * same reason. Putting it in Xcp_DisconnectSession instead would not fix the defect at all.
     *
     * This line does have one cost, and it is stated here rather than discovered later: it makes
     * Xcp_PgmCompleteProgramReset's own reset (Xcp_Pgm.c, DD57) unobservable. A successful
     * PROGRAM_RESET disconnects, the disconnected-state gate then admits nothing but CONNECT, and
     * CONNECT arrives here -- so whichever of the two ran, the next session starts idle, and
     * pgm_session_test.py's test_program_reset_leaves_pgm_state_ready_for_a_new_session no longer
     * fails when DD57's reset is deleted (measured). That reset is kept regardless: the command
     * that ends a sequence owning the sequence's state is not something to trade for a shorter
     * function, and the alternative leaves Xcp_PgmCompleteProgramReset correct only because of a
     * line in another file. It is recorded as a third documented-untestable guard beside the two
     * in Xcp.c (design §9 criterion 7, final-review finding 7).
     *
     * No race with a PROGRAM_START still in flight: DD55's ERR_CMD_BUSY gate (Xcp.c) refuses every
     * command but SYNCH while pending_command.active is TRUE, CONNECT included, so this line cannot
     * run underneath a deferred operation. */
    Xcp_Internal.pgm_state = XCP_PGM_IDLE;

    /* Final review F2. A block left open by an abandoned session is state exactly like pgm_state
     * itself -- "no state of the previous one may survive into it" (this function's own reasoning
     * two paragraphs up) applies to it precisely because it is not covered by the pgm_state write
     * alone: Xcp_PgmBlockIsActive() reads Xcp_Internal.pgm_block.requested_elements, a separate
     * field this function never touched before. Measured before this fix: PROGRAM declaring 10
     * with 6 delivered, then CONNECT, then a fresh PROGRAM_START and SET_MTA -- a PROGRAM_NEXT
     * carrying the abandoned block's own still-expected count was accepted, and the integrator was
     * handed the previous session's 6 leftover bytes at the new session's MTA. Xcp_Init (Xcp.c)
     * already clears this on its own door into a fresh session; this is the same clearing on the
     * other one. */
    Xcp_PgmBlockAbort();

    /* SP4c Task 3, design doc DD85: CONNECT is one of the three doors that end PROGRAM_FORMAT's
     * own lifetime, the same session-boundary reasoning the two paragraphs above already give for
     * pgm_state and pgm_block -- a programming session's format is exactly the kind of state
     * 1.0/2.3 has reset between sessions, and until this line it would have been the one piece
     * still surviving a reconnect. */
    Xcp_PgmFormatReset();
#endif /* #if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON) */

    /* DD74 (docs/superpowers/specs/2026-09-07-xcp-shared-state-defects-design.md). This
     * function's own reasoning above -- no state of the previous session may survive into the
     * next, XCP part 2 - Protocol Layer Specification 1.1/1.6.1.1.1 makes CONNECT the start of
     * one -- applies just as much to a block transfer, a partial key, a seed and the MTA as it
     * does to pgm_state/pgm_block above; until here none of the four was touched. Three measured
     * consequences (test/session_teardown_test.py):
     *
     * - An UPLOAD (slave block mode) left open -- its first frame sent but never confirmed --
     *   answered a later, unrelated transmission confirmation by continuing to read and transmit
     *   the PREVIOUS session's memory into the new one: DD70's disclosure, reopened across a
     *   reconnect.
     * - A partial key -- GET_SEED then an UNLOCK that announces N bytes and delivers fewer --
     *   left standing let a new session's UNLOCK complete it with only the still-missing bytes,
     *   granting a resource the new session never actually supplied a full key for.
     * - An MTA set in the previous session and never reset let a DOWNLOAD with no SET_MTA in the
     *   new session write at the previous session's address.
     *
     * Xcp_BlockTransferAbort() (source/Xcp.c) already exists for the first -- Xcp_Cal.c's own
     * DOWNLOAD/DOWNLOAD_MAX/DOWNLOAD_NEXT handlers already reuse it, at five call sites, to
     * abandon a block whose own request turns out malformed or out of sequence -- so it is
     * reused here too, rather than the two fields it clears being written directly.
     * A stale block_transfer.slave_block_mode surviving this call is harmless, and deliberately
     * left to Xcp_BlockTransferAbort() to not touch, for the same reason the DD70 fix that added
     * it leaves it alone in every other caller: every reader of it is already gated on
     * Xcp_BlockTransferIsActive() (== requested_elements != 0) first, which this call clears.
     *
     * key_master/key_slave: total_length back to 0x00u, matching Xcp_DTOCmdStdUnlock's own reset
     * once a key completes (source/Xcp_Std.c below) -- total_length == 0 is that function's own
     * "no transfer in progress" reading
     * (`if (Xcp_Internal.key_master.total_length == 0x00u)`), the same value a fresh session must
     * present. current_index is reset alongside it for the identical reason
     * Xcp_DTOCmdStdUnlock's own completion does not bother resetting it there: nothing reads a
     * stale current_index once its own total_length is 0, but a field that means nothing this
     * session is reset to nothing instead of to a number that used to mean something in the one
     * before it.
     *
     * seed: total_length back to 0x00u, for the identical reason as key_master's above -- an
     * earlier task (DD73) corrected this field to mean the seed's own length rather than "bytes
     * still to send", and 0 is that meaning's own "no seed issued this session" value, matching
     * Xcp_DTOCmdStdGetSeed's mode=1 continuation gate
     * (`if (Xcp_Internal.seed.total_length != 0x00u)`) and Xcp_DTOCmdStdUnlock's own
     * post-completion reset of the same field, both below. current_index reset alongside it for
     * the same reason as key_master's own above.
     *
     * memory_transfer: XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.6 lists SET_MTA as
     * "Category: Standard, optional", and neither it nor 1.1/1.6.2.1.1 (DOWNLOAD, which uses the
     * MTA) states what the MTA holds before a session's first SET_MTA -- checked against both the
     * local 1.1 PDF's own OCR text and the 1.0 PDF (pdftotext -layout) for this comment, neither
     * uses the word "undefined" anywhere in connection with the MTA; the only "undefined" in
     * either document is 1.1/1.6.4.1.1.2's DAQ pointer, a different field with its own explicit
     * daq_pointer.valid flag (source/Xcp_Internal.h) that this pair has no equivalent of. So: a
     * master that omits SET_MTA is unaddressed by the letter of the text, not named
     * non-conformant by it -- but the previous session's own address is still the worst available
     * value, being the one this defect is measured writing through.
     *
     * A true "refuses to use" reset -- one this module would actively decline to write through --
     * is not achievable here without inventing a validity flag this pair does not have, matching
     * daq_pointer's own .valid above: Xcp_ReadSlaveMemoryTable/Xcp_WriteSlaveMemoryTable
     * (source/Xcp.c) are integrator callbacks this module calls through unconditionally, with no
     * address check of its own anywhere in this file, so nothing here can be made to refuse a
     * write the way an exhausted daq_pointer already refuses WRITE_DAQ. Adding that concept for
     * the MTA would mean a new field AND a new check at every one of memory_transfer's readers --
     * Xcp_Cal.c, Xcp_Pag.c, the checksum helpers in this file, and, under
     * XCP_FLASH_PROGRAMMING_ENABLED, Xcp_Pgm.c -- disproportionate to this task and a change of
     * its own. Chosen instead: NULL_PTR, matching the one place this module already makes exactly
     * this choice for exactly this reason -- Xcp_Init (source/Xcp.c) resets
     * memory_transfer.address to NULL_PTR (and .extension to 0x00u) on its own entry into a fresh
     * session, with no more of a "refuses to use it" guarantee than this line has, for the
     * identical reason. This does not make a NULL write impossible; it makes any write land at a
     * NEW address rather than the previous session's, which is what this defect is measured doing
     * and what this line ends. */
    Xcp_BlockTransferAbort();

    Xcp_Internal.key_master.total_length = 0x00u;
    Xcp_Internal.key_master.current_index = 0x00u;
    Xcp_Internal.key_slave.total_length = 0x00u;
    Xcp_Internal.key_slave.current_index = 0x00u;

    Xcp_Internal.seed.total_length = 0x00u;
    Xcp_Internal.seed.current_index = 0x00u;

    Xcp_Internal.memory_transfer.address = NULL_PTR;
    Xcp_Internal.memory_transfer.extension = 0x00u;

    /* Final review, R1. The session-status REQUEST bits, and only those. XCP part 1 - Overview
     * 1.0/2.3 -- quoted in full at Xcp_CanIfRxIndication (Xcp.c) and already the justification for
     * every reset above -- names "the session status, all DAQ lists and the protection status
     * bits" among what a DISCONNECTED slave has reset. This block honoured that citation for five
     * fields it does not name while leaving standing the one it does.
     *
     * It is not cosmetic. STORE_CAL_REQ is cleared in exactly one place, Xcp_MainFunction (Xcp.c),
     * and only when Xcp_StoreCalibrationDataToNonVolatileMemory returns E_OK. An integrator whose
     * NVM write never succeeds returns E_NOT_OK forever, the bit never clears, and the
     * ERR_PGM_ACTIVE gate (Xcp.c) then refuses every command whose Xcp_CTOErrorMatrix row carries
     * XCP_INTERNAL_ERR_PGM_ACTIVE -- 42 rows in the default build, 38 with flash programming
     * enabled (four rows carry the bit only with that gate off; counted from the matrix's own
     * initializer entries per preprocessor branch, not by grepping the macro name, which also
     * matches the dispatch gate's own uses), DISCONNECT (0xFE) among them. CONNECT itself is
     * ungated (its row is 0x00u), so before this line a master could reconnect and recover
     * NOTHING: only Xcp_Init, i.e. a power cycle, cleared it.
     *
     * The trade this makes, deliberately: if the integrator is still storing when a new master
     * connects, clearing the bit stops Xcp_MainFunction polling it, so that store is no longer
     * tracked and no EV_STORE_CAL will follow. That is the lesser harm. The new master never
     * requested the store, GET_STATUS reporting a pending request it cannot influence would be
     * the more misleading answer, and the alternative being traded away is a permanent refusal of
     * DISCONNECT.
     *
     * Masked rather than assigned, because session_status is not only request bits: DAQ_RUNNING
     * (bit 6) is maintained by Xcp_DaqStartStop (Xcp_Daq.c) from whether DAQ lists are actually
     * running. Zeroing the byte here would make GET_STATUS report a stopped DAQ while it runs --
     * this module does not stop DAQ on CONNECT, that being the parked DD25/SP2d question, so the
     * bit must keep tracking the truth rather than be reset to a state nothing enforces. */
    Xcp_Internal.session_status &= (uint8)(~(XCP_SESSION_STATUS_MASK_STORE_CAL_REQ |
                                             XCP_SESSION_STATUS_MASK_STORE_DAQ_REQ |
                                             XCP_SESSION_STATUS_MASK_CLEAR_DAQ_REQ));

    /* Final review, R2. The DAQ pointer is a per-session cursor exactly as the MTA above is, and
     * survived CONNECT for the same reason the MTA did -- nothing reset it. Session 1 sends
     * SET_DAQ_PTR(0,0,0) and vanishes without DISCONNECT (this block's whole threat model);
     * session 2 sends WRITE_DAQ with no SET_DAQ_PTR of its own, and Xcp_DaqApplyOdtEntry
     * (Xcp_Daq.c) finds valid == TRUE and writes the PREVIOUS session's ODT entry.
     *
     * Xcp_DaqFreeAll (Xcp_Daq.c) does clear this, but runs only from DISCONNECT and only under a
     * DYNAMIC configuration, so neither a STATIC build nor a vanished master reached it.
     *
     * Only `valid` is cleared, not the three coordinates: FALSE is already how this module
     * represents the undefined pointer of 1.1/1.6.4.1.1.2 (see Xcp_DaqPointerAdvance), so the
     * next Xcp_DaqApplyOdtEntry fails its validity check and answers ERR_OUT_OF_RANGE, telling
     * the master to position the pointer it never set. Clearing the whole DAQ list content is a
     * different and larger question -- the DD25/SP2d one this does not settle. */
    Xcp_Internal.daq_pointer.valid = FALSE;

    /* DD79. With the clear-after-dispatch gone, this is the ONLY thing that re-locks a resource
     * inside a running module, and XCP part 1 - Overview 1.0/2.3 -- quoted in full at
     * Xcp_CanIfRxIndication (Xcp.c) -- names the protection status bits among what a DISCONNECTED
     * slave has reset. A grant belongs to the session that earned it.
     *
     * DD78: re-seeded from the configuration rather than zeroed. Zero is now "nothing is
     * protected", which would hand every new session an unconditional grant of every group; the
     * configured mask is what a freshly initialised module holds (Xcp_Init, Xcp.c) and is what
     * re-locking means on a field that stores what the wire means. */
    Xcp_Internal.locked_resource = Xcp_Ptr->general->protectedResource;

    Xcp_Internal.connection_status = XCP_CONNECTION_STATE_CONNECTED;

    return E_OK;
}

