/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * <h2><center>&copy; Copyright (c) 2021 STMicroelectronics.
  * All rights reserved.</center></h2>
  *
  * This software component is licensed by ST under BSD 3-Clause license,
  * the "License"; You may not use this file except in compliance with the
  * License. You may obtain a copy of the License at:
  *                        opensource.org/licenses/BSD-3-Clause
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "adc.h"
#include "aes.h"
#include "dma.h"
#include "spi.h"
#include "tim.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <string.h>
#include "arm_math.h"
#include "adc_dblbuf.h"
#include "retarget.h"
#include "s2lp.h"
#include "spectrogram.h"
#include "eval_radio.h"
#include "packet.h"
#include "config.h"
#include "utils.h"
#include "usart.h"

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */

volatile uint8_t btn_press;

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
	if (GPIO_Pin == B1_Pin) {
		btn_press = 1;
	}
	else if (GPIO_Pin == RADIO_INT_Pin)
		S2LP_IRQ_Handler();
}

uint32_t analogRead_LowPower(void)
{
    // Turn on ADC2
    HAL_ADC_Start(&hadc2);

    // Wait for it to be ready (if you have AutoOff enabled)
    HAL_ADC_PollForConversion(&hadc2, HAL_MAX_DELAY);

    uint32_t value = HAL_ADC_GetValue(&hadc2);

    // Turn off ADC2 (optional if AutoOff is enabled)
    HAL_ADC_Stop(&hadc2);

    return value;
}

uint8_t analogRead_CapaLvl(void)
{
  // Max value is 4.5V, min is 3.6V
  // ADC is 6 bit -> 0-63
  // Vdd can be 3.3V to 1.8V
  // The 4.5V max goes through a voltage divider to 1.72V (safe for 1.8V)
  // 4.5V -> 1.72V -> 60 ; 3.6V -> 1.35V -> 48

  uint8_t value = (uint8_t)analogRead_LowPower();

  // CAPAC_LVL_X are the percentage of the battery level
  // True value = value * 12 + 48
  // 0% = 48 ; 100% = 60

  DEBUG_PRINT("Battery Level: %d\r\n", value);
  DEBUG_PRINT("CAPAC_LVL_1: %d\r\n", ((uint8_t)( CAPA_LVL_1*12.0f) + 48));
  DEBUG_PRINT("CAPAC_LVL_2: %d\r\n", ((uint8_t)( CAPA_LVL_2*12.0f) + 48));

  // Give a level depending on the threshold reached
  if (value < ((uint8_t)(CAPA_LVL_1*12.0f) + 48)) {
    return 0; // Low
  } else if (value < ((uint8_t)(CAPA_LVL_2*12.0f) + 48)) {
    return 1; // Medium
  } else {
    return 2; // Full
  }
}

void run(void)
{
	btn_press = 0;

  // Initialize the S2LP to the sleep mode if configured
  #if NO_S2LP_SLEEP == 0
    int s2lp_Check = S2LP_Standby();
    if (s2lp_Check != HAL_OK) {
      DEBUG_PRINT("[S2LP] Error while putting the S2LP to sleep: %d\r\n", s2lp_Check);
      Error_Handler();
    }
  #endif

  //while (1) {
  //  HAL_Delay(100);
  //  DEBUG_PRINT_FAST("TEST\r\n", 6);
  //}

	while (1)
	{
    // If NO_BUTTON is set, we acquire and send the packet directly and continuously
    // Otherwise, we wait for the button press to acquire and send the packet
    #if USE_BUTTON == 0
      // Start the ADC acquisition
      if (StartADCAcq() != HAL_OK) {
        DEBUG_PRINT("Error while starting the ADC acquisition\r\n");
        Error_Handler();
      }
      // Continuous acquisition
      while (1) {
        ProcessADCData();
        HAL_PWR_EnterSLEEPMode(PWR_LOWPOWERREGULATOR_ON, PWR_SLEEPENTRY_WFI);
        __WFI();
      }
    #else
      // Wait for the button press
      while (!btn_press) {
        HAL_GPIO_WritePin(GPIOB, LD2_Pin, GPIO_PIN_SET);
        HAL_Delay(200);
        HAL_GPIO_WritePin(GPIOB, LD2_Pin, GPIO_PIN_RESET);
        HAL_Delay(200);
      }
      // Start the ADC acquisition
      if (StartADCAcq() != HAL_OK) {
        DEBUG_PRINT("Error while starting the ADC acquisition\r\n");
        Error_Handler();
      }
      btn_press = 0;
      // Continuous acquisition while the button is not pressed
      while (!btn_press) {
        ProcessADCData();
        HAL_PWR_EnterSLEEPMode(PWR_LOWPOWERREGULATOR_ON, PWR_SLEEPENTRY_WFI);
      }
      // Stop the acquisition
      StopADCAcq();
      // Reset the button press flag
      btn_press = 0;
    #endif
	}
}

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_SPI1_Init();
  MX_TIM3_Init();
  MX_ADC1_Init();
  MX_AES_Init();
  MX_ADC2_Init();
  /* USER CODE BEGIN 2 */

  if (NO_UART == 0) {
	  MX_LPUART1_UART_Init();
  }

  RetargetInit(&hlpuart1);
  DEBUG_PRINT("Hello world\r\n");

  // Enable S2LP Radio
  HAL_StatusTypeDef err = S2LP_Init(&hspi1);
  if (err)  {
	  DEBUG_PRINT("[S2LP] Error while initializing: %u\r\n", err);
	  Error_Handler();
  } else {
	  DEBUG_PRINT("[S2LP] Init OK\r\n");
  }

  if (HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED) != HAL_OK) {
	  DEBUG_PRINT("Error while calibrating the ADC\r\n");
	  Error_Handler();
  }
  if (HAL_TIM_Base_Start(&htim3) != HAL_OK) {
	  DEBUG_PRINT("Error while enabling timer TIM3\r\n");
	  Error_Handler();
  }
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
    run();

    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */

  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_MSI;
  RCC_OscInitStruct.MSIState = RCC_MSI_ON;
  RCC_OscInitStruct.MSICalibrationValue = 0;
  RCC_OscInitStruct.MSIClockRange = RCC_MSIRANGE_5;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_MSI;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  __disable_irq();
  DEBUG_PRINT("Entering error Handler\r\n");
  while (1)
  {
	  // Blink LED3 (red)
	  HAL_GPIO_WritePin(GPIOB, LD3_Pin, GPIO_PIN_SET);
	  for (volatile int i=0; i < SystemCoreClock/200; i++);
	  HAL_GPIO_WritePin(GPIOB, LD3_Pin, GPIO_PIN_RESET);
	  for (volatile int i=0; i < SystemCoreClock/200; i++);
  }
  /* USER CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: DEBUG_PRINT("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
