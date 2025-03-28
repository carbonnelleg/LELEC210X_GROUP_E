    /******************************************************************************/
    /*                                                                            */
    /*             AES 256 CMAC mode authentication tag computation               */     
    /*                          (polling mode)                                    */
    /*                                                                            */    
// https://github.com/STMicroelectronics/STM32CubeL4/blob/master/Projects/STM32L476G-EVAL/Examples/CRYP/CRYP_GCM_GMAC_CMAC_Modes/Src/main.c#L545
  
    CrypHandle.Init.DataType      = CRYP_DATATYPE_32B ;
    CrypHandle.Init.KeySize       = CRYP_KEYSIZE_256B ;
    CrypHandle.Init.pKey          = AES256key_CMAC;
    
    
    CrypHandle.Init.OperatingMode = CRYP_ALGOMODE_TAG_GENERATION;
    CrypHandle.Init.ChainingMode  = CRYP_CHAINMODE_AES_CMAC;
    CrypHandle.Init.GCMCMACPhase  = CRYP_GCMCMAC_HEADER_PHASE;  
    CrypHandle.Init.KeyWriteFlag  = CRYP_KEY_WRITE_ENABLE;  
    CrypHandle.Init.Header        = (uint8_t *)aHeaderMessage_CMAC; 
    CrypHandle.Init.HeaderSize    = CMAC_HEADER_SIZE;       
  

    /* Display Header */
    Display_Header((uint8_t *)aHeaderMessage_CMAC, CMAC, CMAC_HEADER_SIZE);  
    
    /* Display Expected Authentication tag */
    /* According to RFC 3610 Counter with CBC-MAC (CCM),
      Since BBlocks[0] = 0x0x6EAA1E6A, Octet 0 of B0 block is 0x6A.
      (DataType is 32-bit: the less-significant data occupies the lowest address location.)
    
      Therefore, M' = 0b 101 (bits 3 to 5) = 5.
      M = 2*M'+2 = 12. The authentication tag is 12-byte long */     
    Display_AuthenticationTag((uint8_t *)aExpectedAuthTAG_CMAC, CMAC_TAG_SIZE);
  
    /****************************************************************************/
    /* De-initialize then initialize the AES peripheral                         */
    /****************************************************************************/
    if (HAL_CRYP_DeInit(&CrypHandle) != HAL_OK)
    {
        Error_Handler();
    } 
    /* Set the CRYP parameters */
    if (HAL_CRYP_Init(&CrypHandle) != HAL_OK)
    {
        Error_Handler();
    } 
    
    
    /*----------------------------------------------------------------------------------------------*/     
    /* CMAC header phase */
    if (HAL_CRYPEx_AES_Auth(&CrypHandle, (uint8_t *)BBlocks, CMAC_B_SIZE, NULL, TIMEOUT_VALUE)!= HAL_OK)
    {
      Error_Handler();
    }
    /*----------------------------------------------------------------------------------------------*/       
    /* CMAC final phase */
    CrypHandle.Init.GCMCMACPhase  = CRYP_GCMCMAC_FINAL_PHASE;
    if (HAL_CRYPEx_AES_Auth(&CrypHandle, (uint8_t *)CBlock, CMAC_C_SIZE, (uint8_t *)aAuthTAG, TIMEOUT_VALUE)!= HAL_OK)
    {
      Error_Handler();
    } 
    /*----------------------------------------------------------------------------------------------*/       
  
  
    /* Display Computed Authentication tag */        
    Display_ComputedTag(CMAC, CMAC_TAG_SIZE);  
  
     
    /* Compare the GMAC authentication tag with the expected one *******************/ 
    data_cmp(aAuthTAG, (uint8_t *)aExpectedAuthTAG_CMAC, CMAC_TAG_SIZE);     

  printf("\n==============================================\n ");
  printf("\n\r CMAC authentication tag computation done.\n ");
  printf("No issue detected.\n ");
  
  /* Turn LED1 on */
  BSP_LED_On(LED1);
  
  while (1)
  {
  }
