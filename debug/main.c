//
// Created by Guillaume Sottas on 2019-07-16.
//

#include <Xcp_Types.h>
#include "Xcp.h"
#include "Xcp_Cfg.h"
#include "XcpOnCan_Cbk.h"
#include "Xcp_SeedKey.h"

Std_ReturnType Xcp_GetSeed(uint8 *pSeedBuffer,
                           const uint16 maxSeedLength,
                           uint16 *pSeedLength)
{
    (void)maxSeedLength;

    pSeedBuffer[0x00u] = 0x01u;
    pSeedBuffer[0x01u] = 0x02u;
    pSeedBuffer[0x02u] = 0x03u;
    pSeedBuffer[0x03u] = 0x04u;
    pSeedBuffer[0x04u] = 0x05u;
    pSeedBuffer[0x05u] = 0x06u;
    pSeedBuffer[0x06u] = 0x07u;
    pSeedBuffer[0x07u] = 0x08u;
    pSeedBuffer[0x08u] = 0x09u;
    pSeedBuffer[0x09u] = 0x0Au;
    pSeedBuffer[0x0Au] = 0x0Bu;

    *pSeedLength = 0x0Bu;

    return E_OK;
}

Std_ReturnType Xcp_CalcKey(const uint8 *pSeedBuffer,
                           const uint16 seedLength,
                           uint8* pKeyBuffer,
                           const uint16 maxKeyLength,
                           uint16 *pKeyLength)
{
    (void)pSeedBuffer;
    (void)seedLength;
    (void)pKeyBuffer;
    (void)maxKeyLength;
    (void)pKeyLength;

    return E_OK;
}

Std_ReturnType CanIf_Transmit(PduIdType txPduId, const PduInfoType *pPduInfo)
{
    return E_OK;
}

Std_ReturnType Det_ReportError(uint16 moduleId,
                               uint8 instanceId,
                               uint8 apiId,
                               uint8 errorId)
{
    (void)moduleId;
    (void)instanceId;
    (void)apiId;
    (void)errorId;

    return E_OK;
}

Std_ReturnType Det_ReportRuntimeError(uint16 moduleId,
                                      uint8 instanceId,
                                      uint8 apiId,
                                      uint8 errorId)
{
    (void)moduleId;
    (void)instanceId;
    (void)apiId;
    (void)errorId;

    return E_OK;
}

Std_ReturnType Det_ReportTransientFault(uint16 moduleId,
                                        uint8 instanceId,
                                        uint8 apiId,
                                        uint8 faultId)
{
    (void)moduleId;
    (void)instanceId;
    (void)apiId;
    (void)faultId;

    return E_OK;
}

void PduR_CanTpRxIndication(PduIdType rxPduId, Std_ReturnType result)
{
    (void)rxPduId;
    (void)result;
}

void PduR_CanTpTxConfirmation(PduIdType txPduId, Std_ReturnType result)
{
    (void)txPduId;
    (void)result;
}

BufReq_ReturnType PduR_CanTpCopyRxData(PduIdType rxPduId,
                                       const PduInfoType *pPduInfo,
                                       PduLengthType *pBuffer)
{
    (void)rxPduId;
    (void)pPduInfo;
    (void)pBuffer;

    return E_OK;
}

BufReq_ReturnType PduR_CanTpCopyTxData(PduIdType txPduId,
                                       const PduInfoType *pPduInfo,
                                       const RetryInfoType *pRetryInfo,
                                       PduLengthType *pAvailableData)
{
    (void)txPduId;
    (void)pPduInfo;
    (void)pRetryInfo;
    (void)pAvailableData;

    return E_OK;
}

BufReq_ReturnType PduR_CanTpStartOfReception(PduIdType pduId,
                                             const PduInfoType *pPduInfo,
                                             PduLengthType tpSduLength,
                                             PduLengthType *pBufferSize)
{
    (void)pduId;
    (void)pPduInfo;
    (void)tpSduLength;
    (void)pBufferSize;

    *pBufferSize = 8;

    return E_OK;
}

int main(int argc, char *argv[])
{
    int i;
    uint8 rx_data[0x08u];
    uint8 tx_data[0x08u];

    PduInfoType rx_pdu;
    PduInfoType tx_pdu;

    rx_pdu.SduDataPtr = &rx_data[0x00u];
    rx_pdu.MetaDataPtr = NULL_PTR;
    rx_pdu.SduLength = sizeof(rx_data);

    tx_pdu.SduDataPtr = &tx_data[0x00u];
    tx_pdu.MetaDataPtr = NULL_PTR;
    tx_pdu.SduLength = sizeof(tx_data);

    Xcp_Init(&Xcp[0x00u]);

    rx_data[0x00u] = 0xFFu;
    rx_data[0x01u] = 0x00u;
    rx_data[0x02u] = 0x00u;
    rx_data[0x03u] = 0x00u;
    rx_data[0x04u] = 0x00u;
    rx_data[0x05u] = 0x00u;
    rx_data[0x06u] = 0x00u;
    rx_data[0x07u] = 0x00u;
    Xcp_CanIfRxIndication(0x01u, &rx_pdu);
    Xcp_MainFunction();
    Xcp_CanIfTxConfirmation(0x01u, E_OK);

    rx_data[0x00u] = 0xF8u;
    rx_data[0x01u] = 0x00u;
    rx_data[0x02u] = 0x01u;
    rx_data[0x03u] = 0x02u;
    rx_data[0x04u] = 0x03u;
    rx_data[0x05u] = 0x04u;
    rx_data[0x06u] = 0x05u;
    rx_data[0x07u] = 0x06u;
    Xcp_CanIfRxIndication(0x01u, &rx_pdu);
    Xcp_MainFunction();
    Xcp_CanIfTxConfirmation(0x01u, E_OK);

    rx_data[0x00u] = 0xF7u;
    rx_data[0x01u] = 0x02u;
    rx_data[0x02u] = 0x07u;
    rx_data[0x03u] = 0x08u;
    rx_data[0x04u] = 0x00u;
    rx_data[0x05u] = 0x00u;
    rx_data[0x06u] = 0x00u;
    rx_data[0x07u] = 0x00u;
    Xcp_CanIfRxIndication(0x01u, &rx_pdu);
    Xcp_MainFunction();
    Xcp_CanIfTxConfirmation(0x01u, E_OK);

    return 0;
}
