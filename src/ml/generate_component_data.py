"""BOM 元件类型分类训练数据生成器

使用模板 + 术语表替换生成多样化的元件分类样本。
输出 JSON 格式：{"text": str, "type": str}

使用方式:
    python src/ml/generate_component_data.py              # 生成默认 ~828 条
    python src/ml/generate_component_data.py --count 80   # 每类 80 条训练样本
    python src/ml/generate_component_data.py --output data/component_train.json
"""

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

# ── 术语表 ──

_TERMS = {
    # ── IC 类 ──
    "{mcu_pn}": [
        "STM32F103C8T6", "STM32F407VET6", "STM32F103RCT6", "ESP32-WROOM-32",
        "ESP32-S3", "GD32F103C8T6", "CH32V307", "ATmega328P", "RP2040",
        "nRF52840", "i.MX RT1062", "STM32H743IIT6", "STM32G030F6P6",
        "ATtiny85", "MSP430G2553", "LPC1768", "MK66FX1M0",
    ],
    "{fpga_pn}": [
        "EP4CE6E22C8N", "XC6SLX9-2TQG144C", "EPM240T100C5N", "GW1NR-9",
        "MAX10M08", "LFE5U-25F", "ICE40UP5K",
    ],
    "{ldo_pn}": [
        "AMS1117-3.3", "AMS1117-5.0", "LM1117-3.3", "ME6211C33M5G",
        "HT7333", "XC6206P332MR", "TLV1117-33", "LP2985-33",
        "SPX3819M5-L-3-3", "NCP1117ST33T3G", "RT9193-33",
    ],
    "{dcdc_pn}": [
        "MP1584", "MP2307", "LM2596", "TPS5430", "XL6009", "MT3608",
        "SY8120B", "RT7272", "TPS562201", "LMR16030",
    ],
    "{opamp_pn}": [
        "LM358", "LM324", "TL072", "NE5532", "OPA2134", "AD8605",
        "MCP6002", "LMV358", "TL084", "OP07", "INA226", "AD620",
    ],
    "{interface_pn}": [
        "CH340G", "CH340C", "CP2102", "FT232RL", "CH343P",
        "MAX3232", "SP3232", "SN65HVD230", "MAX485", "ADM3202",
        "TXB0104", "TXS0108E", "USBLC6-2SC6", "USB2514",
    ],
    "{sensor_pn}": [
        "DS18B20", "DHT11", "BMP280", "MPU6050", "QMC5883L",
        "SHT30", "MAX30102", "VL53L0X", "AS5600", "W25Q64",
        "AT24C02", "DS1302", "PCF8563", "TM1637", "CH455",
    ],
    "{driver_pn}": [
        "ULN2003", "DRV8825", "A4988", "TB6612", "L298N",
        "TC4427", "IR2104", "EG2132", "WS2812B", "SK6812",
    ],

    # ── 电容 ──
    "{mlcc_val}": [
        "100nF", "0.1μF", "22pF", "47pF", "1nF", "10nF", "220nF",
        "1μF", "2.2μF", "4.7μF", "0.01μF", "33pF", "15pF", "100pF",
    ],
    "{mlcc_pkg}": [
        "0402", "0603", "0805", "1206", "1210",
    ],
    "{elec_val}": [
        "10μF", "22μF", "47μF", "100μF", "220μF", "330μF", "470μF",
        "1000μF", "2200μF", "4.7μF", "680μF", "1500μF",
    ],
    "{elec_pkg}": [
        "SMD-Φ4", "SMD-Φ5", "SMD-Φ6.3", "SMD-Φ8", "SMD-Φ10",
        "DIP-Φ5", "DIP-Φ6.3", "DIP-Φ8", "DIP-Φ10",
        "CASE-B", "CASE-C", "CASE-D", "1411", "2917",
    ],

    # ── 电阻 ──
    "{res_val}": [
        "10kΩ", "1kΩ", "100Ω", "4.7kΩ", "22Ω", "47kΩ", "100kΩ",
        "220Ω", "330Ω", "1MΩ", "2.2kΩ", "470Ω", "10Ω", "0Ω",
        "5.1kΩ", "20kΩ", "510Ω", "750Ω", "3.3kΩ", "1.5kΩ",
    ],
    "{res_pkg}": [
        "0402", "0603", "0805", "1206", "2512", "2010",
    ],

    # ── 电感/磁珠 ──
    "{ind_val}": [
        "10μH", "4.7μH", "2.2μH", "1μH", "22μH", "47μH", "100μH",
        "220Ω@100MHz", "600Ω@100MHz", "120Ω@100MHz", "1kΩ@100MHz",
        "30Ω@100MHz", "470Ω@100MHz",
    ],

    # ── 二极管/LED ──
    "{diode_pn}": [
        "1N4148", "1N4007", "SS14", "BAT54S", "B5819", "SMAJ5.0A",
        "SMBJ12A", "P6KE6.8A", "SR360", "1N5819", "MMBD4148",
        "ESD5Z5.0T1G", "BZV55-C3V3", "MMSZ5231B", "SD12C",
    ],
    "{led_pn}": [
        "LED-Red", "LED-Green", "LED-Blue", "LED-White", "LED-Yellow",
        "19-217/R6C-AL1M2VY/3T", "LTST-C191KRKT", "APA102",
        "WS2812B-V5", "SK6812-MINI",
    ],

    # ── 晶体管 ──
    "{transistor_pn}": [
        "S8050", "S8550", "2N2222", "2N3904", "2N3906", "BC547",
        "BC557", "MMBT3904", "MMBT3906", "SS8050",
    ],
    "{mosfet_pn}": [
        "AO3400", "AO3401", "AO4404", "IRFZ44N", "IRLML2502",
        "SI2301", "SI2302", "IRF540N", "2N7002", "BSS138",
        "IRLZ44N", "CSD18534KCS", "FDN337N",
    ],

    # ── 晶振 ──
    "{crystal_val}": [
        "8MHz", "12MHz", "16MHz", "25MHz", "32.768kHz",
        "24MHz", "4MHz", "20MHz", "48MHz", "26MHz",
    ],
    "{crystal_pkg}": [
        "5032-2P", "5032-4P", "3225-4P", "2520-4P",
        "HC-49S", "2012-2P", "3225-2P", "圆柱2×6",
    ],

    # ── 连接器 ──
    "{conn_pn}": [
        "排针 4P", "排母 8P", "PH2.0 4P", "XH2.54 2P", "VH3.96 2P",
        "USB-Micro 5P", "USB-C 16P", "DC-005 5.5×2.1", "FPC 0.5mm 24P",
        "TF卡座 翻盖", "SIM卡座 6P", "RJ45 带变压器", "DB9 母座",
        "KF128 2P", "XT30PW", "XT60H",
    ],

    # ── 通用封装 ──
    "{ic_pkg}": [
        "LQFP-48", "LQFP-64", "LQFP-100", "QFN-32", "QFN-48",
        "SOP-8", "SOP-16", "SSOP-20", "TSSOP-14", "MSOP-8",
        "SOT-23-5", "SOT-223", "TO-252", "DFN-10", "BGA-256",
        "TQFP-44", "VQFN-24",
    ],
    "{sot_pkg}": [
        "SOT-23", "SOT-323", "SOT-523", "SOT-89", "SOT-223",
    ],
    "{do_pkg}": [
        "SOD-323", "SOD-523", "SOD-123", "DO-214AC", "DO-214AA",
    ],
}


# ── 模板定义 ──

_RAW_TEMPLATES: dict[str, list[str]] = {
    "ic_mcu": [
        # 单片机 / 处理器 / FPGA
        "ref:U pn:{mcu_pn} pkg:{ic_pkg} desc:ARM Cortex-M 微控制器",
        "ref:U pn:{mcu_pn} pkg:{ic_pkg} desc:{mcu_pn} 主控芯片",
        "ref:U pn:{mcu_pn} pkg:{ic_pkg} desc:32位微控制器 72MHz",
        "ref:U pn:{mcu_pn} pkg:{ic_pkg} desc:低功耗 MCU 64KB Flash",
        "ref:IC pn:{mcu_pn} pkg:{ic_pkg} desc:单片机 {mcu_pn}",
        "ref:U pn:{mcu_pn} pkg:{ic_pkg} desc:WiFi BLE 双模 SoC",
        "ref:U pn:{mcu_pn} pkg:{ic_pkg} desc:ARM Cortex-M4 DSP FPU",
        "ref:U pn:{mcu_pn} pkg:{ic_pkg} desc:RISC-V 微控制器",
        "ref:U pn:{mcu_pn} pkg:{ic_pkg} desc:Cortex-M0+ 超低功耗",
        "ref:U pn:{mcu_pn} pkg:{ic_pkg} desc:汽车级 MCU CAN FD",
        # FPGA/CPLD
        "ref:U pn:{fpga_pn} pkg:{ic_pkg} desc:FPGA 可编程逻辑器件",
        "ref:U pn:{fpga_pn} pkg:{ic_pkg} desc:CPLD 复杂可编程逻辑",
        "ref:U pn:{fpga_pn} pkg:{ic_pkg} desc:FPGA 六千逻辑单元",
        "ref:IC pn:{fpga_pn} pkg:{ic_pkg} desc:非易失 FPGA",
        # DSP
        "ref:U pn:TMS320F28335 pkg:{ic_pkg} desc:DSP 数字信号处理器",
        "ref:U pn:TMS320F28035 pkg:{ic_pkg} desc:C2000 实时控制 MCU",
        # 无描述（真实场景常见）
        "ref:U pn:{mcu_pn} pkg:{ic_pkg} desc:",
        "ref:U pn:{mcu_pn} pkg:{ic_pkg} desc:{mcu_pn}",
        "ref:U pn:{mcu_pn} pkg:{ic_pkg} desc:IC",
    ],
    "ic_power": [
        "ref:U pn:{ldo_pn} pkg:SOT-223 desc:线性稳压器 3.3V 1A",
        "ref:U pn:{ldo_pn} pkg:SOT-89 desc:LDO 稳压 5V输出",
        "ref:U pn:{ldo_pn} pkg:SOT-23-5 desc:低压差线性稳压器",
        "ref:U pn:{ldo_pn} pkg:SOT-223 desc:电源管理 稳压器",
        "ref:U pn:{dcdc_pn} pkg:SOP-8 desc:DC-DC 降压转换器",
        "ref:U pn:{dcdc_pn} pkg:SOT-23-6 desc:同步整流降压",
        "ref:U pn:{dcdc_pn} pkg:SOP-8 desc:开关电源控制器",
        "ref:U pn:{dcdc_pn} pkg:TO-252 desc:DC-DC 大电流降压",
        "ref:U pn:{dcdc_pn} pkg:SOT-23-5 desc:升压 DC-DC 转换器",
        "ref:IC pn:{ldo_pn} pkg:SOT-223 desc:低压差 LDO",
        "ref:U pn:TPS2553 pkg:SOT-23-6 desc:USB 电源开关",
        "ref:U pn:TP4056 pkg:SOP-8 desc:锂电池充电管理",
        "ref:U pn:TL431 pkg:SOT-23 desc:可调精密电压基准",
        "ref:U pn:IP5306 pkg:SOP-8 desc:移动电源 SoC 充放电管理",
        "ref:U pn:{ldo_pn} pkg:SOT-223 desc:",
        "ref:U pn:{dcdc_pn} pkg:SOP-8 desc:",
    ],
    "ic_analog": [
        "ref:U pn:{opamp_pn} pkg:SOP-8 desc:运算放大器",
        "ref:U pn:{opamp_pn} pkg:TSSOP-14 desc:四运放",
        "ref:U pn:{opamp_pn} pkg:MSOP-8 desc:低噪声精密运放",
        "ref:U pn:{opamp_pn} pkg:SOP-8 desc:音频运算放大器",
        "ref:U pn:{opamp_pn} pkg:SOP-8 desc:仪表放大器 差分",
        "ref:U pn:{opamp_pn} pkg:SOP-8 desc:",
        "ref:U pn:LM393 pkg:SOP-8 desc:双路电压比较器",
        "ref:U pn:LM339 pkg:TSSOP-14 desc:四路差动比较器",
        "ref:U pn:ADS1115 pkg:MSOP-10 desc:16位 ADC 模数转换器",
        "ref:U pn:MCP4725 pkg:SOT-23-6 desc:12位 DAC 数模转换器",
        "ref:U pn:{interface_pn} pkg:SOP-16 desc:USB转串口芯片",
        "ref:U pn:{interface_pn} pkg:QFN-28 desc:USB-UART 桥接器",
        "ref:U pn:{interface_pn} pkg:SOP-16 desc:RS232 收发器",
        "ref:U pn:{interface_pn} pkg:SOP-8 desc:RS485 收发器",
        "ref:U pn:{interface_pn} pkg:SOP-8 desc:CAN 总线收发器",
        "ref:U pn:{interface_pn} pkg:TSSOP-14 desc:电平转换器",
        "ref:U pn:{interface_pn} pkg:MSOP-10 desc:I2C 电平转换",
        "ref:U pn:{interface_pn} pkg:QFN-32 desc:USB HUB 控制器",
        "ref:U pn:{interface_pn} pkg:SOT-23-6 desc:ESD 保护",
        "ref:U pn:{interface_pn} pkg:SOP-16 desc:",
    ],
    "ic_other": [
        "ref:U pn:{driver_pn} pkg:SOP-16 desc:达林顿驱动阵列",
        "ref:U pn:{driver_pn} pkg:TSSOP-28 desc:步进电机驱动",
        "ref:U pn:{driver_pn} pkg:QFN-36 desc:LED 恒流驱动",
        "ref:U pn:{driver_pn} pkg:SOP-16 desc:电机驱动 全桥",
        "ref:U pn:{driver_pn} pkg:SOP-8 desc:MOSFET 栅极驱动",
        "ref:U pn:{driver_pn} pkg:SOP-8 desc:",
        "ref:U pn:{sensor_pn} pkg:SOT-23 desc:温度传感器",
        "ref:U pn:{sensor_pn} pkg:LGA-12 desc:温湿度传感器",
        "ref:U pn:{sensor_pn} pkg:LGA-8 desc:气压传感器",
        "ref:U pn:{sensor_pn} pkg:QFN-24 desc:6轴 IMU 惯性测量",
        "ref:U pn:{sensor_pn} pkg:SOP-8 desc:EEPROM 64Kbit",
        "ref:U pn:{sensor_pn} pkg:SOP-8 desc:RTC 实时时钟",
        "ref:U pn:{sensor_pn} pkg:SOP-16 desc:LED 数码管驱动",
        "ref:U pn:{sensor_pn} pkg:TO-92 desc:数字温度传感器",
        "ref:U pn:74HC595 pkg:SOP-16 desc:8位移位寄存器",
        "ref:U pn:74HC14 pkg:TSSOP-14 desc:六路施密特反相器",
        "ref:U pn:74LVC1G125 pkg:SOT-23-5 desc:三态缓冲器",
        "ref:U pn:CD4051 pkg:SOP-16 desc:8选1模拟开关",
        "ref:U pn:SN74LVC1T45 pkg:SOT-23-6 desc:电平转换",
        "ref:U pn:{sensor_pn} pkg:SOP-8 desc:",
        "ref:IC pn:{driver_pn} pkg:SOP-16 desc:驱动",
        "ref:U pn:PC817 pkg:DIP-4 desc:光电耦合器",
        "ref:U pn:EL357N pkg:SOP-4 desc:高速光耦",
    ],
    "cap_mlcc": [
        "ref:C pn:CL10B104KB8NNNC pkg:{mlcc_pkg} desc:贴片电容 {mlcc_val} X7R",
        "ref:C pn:CC0603KRX7R9BB104 pkg:{mlcc_pkg} desc:MLCC {mlcc_val} 50V",
        "ref:C pn:GRM188R71H104KA93D pkg:{mlcc_pkg} desc:陶瓷电容 {mlcc_val}",
        "ref:C pn:CL05C220JB5NNNC pkg:{mlcc_pkg} desc:贴片电容 {mlcc_val} C0G",
        "ref:C pn:C1608X7R1H104K pkg:{mlcc_pkg} desc:MLCC {mlcc_val} 50V X7R",
        "ref:C pn:CC0805KKX7R7BB105 pkg:{mlcc_pkg} desc:陶瓷电容 {mlcc_val}",
        "ref:C pn:GRM155R71C104KA88D pkg:{mlcc_pkg} desc:贴片电容 {mlcc_val}",
        "ref:C pn:CL21B104KBCNNNC pkg:{mlcc_pkg} desc:多层陶瓷电容 {mlcc_val}",
        "ref:C pn: pkg:{mlcc_pkg} desc:电容 {mlcc_val}",
        "ref:C pn: pkg:{mlcc_pkg} desc:贴片电容 {mlcc_val}",
        "ref:C pn: pkg:{mlcc_pkg} desc:{mlcc_val}",
        "ref:C pn: pkg:{mlcc_pkg} desc:",
    ],
    "cap_elec": [
        "ref:C pn:EEEFK1V101P pkg:{elec_pkg} desc:贴片铝电解 {elec_val} 35V",
        "ref:C pn:EEEFK1A471SP pkg:{elec_pkg} desc:铝电解电容 {elec_val}",
        "ref:C pn:UCD1E101MCL1GS pkg:{elec_pkg} desc:铝电解 {elec_val}",
        "ref:C pn:TAJA106K010RNJ pkg:{elec_pkg} desc:钽电容 {elec_val} 10V",
        "ref:C pn:T491A106K010AT pkg:{elec_pkg} desc:贴片钽电容 {elec_val}",
        "ref:C pn:16SEPC270M pkg:{elec_pkg} desc:固态电容 {elec_val}",
        "ref:C pn:EEEFK1E102SQ pkg:{elec_pkg} desc:贴片电解电容 {elec_val} 25V",
        "ref:C pn: pkg:{elec_pkg} desc:电解电容 {elec_val}",
        "ref:C pn: pkg:{elec_pkg} desc:铝电解 {elec_val}",
        "ref:C pn: pkg:{elec_pkg} desc:钽电容 {elec_val}",
        "ref:C pn: pkg:{elec_pkg} desc:{elec_val}",
    ],
    "resistor": [
        "ref:R pn:RC0603FR-0710KL pkg:{res_pkg} desc:贴片电阻 {res_val} ±1%",
        "ref:R pn:RC0805JR-0710RL pkg:{res_pkg} desc:厚膜电阻 {res_val}",
        "ref:R pn:ERA6AEB103V pkg:{res_pkg} desc:精密薄膜电阻 {res_val}",
        "ref:R pn:CRCW060310K0FKEA pkg:{res_pkg} desc:贴片电阻 {res_val}",
        "ref:R pn:RC0402FR-0710KL pkg:{res_pkg} desc:贴片电阻 {res_val} ±1%",
        "ref:R pn:WR06X103JTL pkg:{res_pkg} desc:厚膜电阻 {res_val}",
        "ref:R pn: pkg:{res_pkg} desc:贴片电阻 {res_val}",
        "ref:R pn: pkg:{res_pkg} desc:电阻 {res_val} ±5%",
        "ref:R pn: pkg:{res_pkg} desc:{res_val}",
        "ref:R pn: pkg:{res_pkg} desc:",
        # 排阻
        "ref:RN pn:YC164-JR-0710KL pkg:{res_pkg} desc:排阻 {res_val} 4合1",
        "ref:RN pn:EXB38V103JV pkg:{res_pkg} desc:贴片排阻 {res_val}",
        # 功率电阻 / 电位器
        "ref:R pn: pkg:2512 desc:功率电阻 {res_val} 1W",
        "ref:R pn: pkg:AXIAL-0.4 desc:直插电阻 {res_val} 1/4W",
        "ref:VR pn:3296W-103 pkg:DIP-3 desc:精密电位器 {res_val}",
    ],
    "inductor": [
        "ref:L pn:CML1608U100MT pkg:{res_pkg} desc:贴片电感 {ind_val}",
        "ref:L pn:NR6045-100M pkg:SMD-6×6 desc:功率电感 {ind_val}",
        "ref:L pn:CDRH127-100MC pkg:SMD-12×12 desc:贴片功率电感 {ind_val}",
        "ref:L pn:SWPA6045S100MT pkg:SMD-6×6 desc:绕线功率电感 {ind_val}",
        "ref:L pn:MLZ1608M100WT pkg:{res_pkg} desc:贴片电感 {ind_val}",
        "ref:L pn: pkg:{res_pkg} desc:电感 {ind_val}",
        "ref:L pn: pkg:SMD-6×6 desc:功率电感 {ind_val}",
        "ref:L pn: pkg:{res_pkg} desc:{ind_val}",
        # 磁珠
        "ref:FB pn:BLM18PG121SN1D pkg:{res_pkg} desc:贴片磁珠 {ind_val}",
        "ref:FB pn:MMZ1608S121AT pkg:{res_pkg} desc:铁氧体磁珠 {ind_val}",
        "ref:FB pn:MPZ1608S121A pkg:{res_pkg} desc:磁珠 {ind_val}",
        "ref:FB pn: pkg:{res_pkg} desc:磁珠 {ind_val}",
        # 共模扼流圈
        "ref:L pn:DLW21SN900SQ2L pkg:0805 desc:共模扼流圈 90Ω@100MHz",
        "ref:L pn: pkg:{res_pkg} desc:共模电感 {ind_val}",
    ],
    "diode_led": [
        "ref:D pn:{diode_pn} pkg:{do_pkg} desc:开关二极管",
        "ref:D pn:{diode_pn} pkg:{do_pkg} desc:肖特基二极管",
        "ref:D pn:{diode_pn} pkg:{do_pkg} desc:整流二极管 1A",
        "ref:D pn:{diode_pn} pkg:{do_pkg} desc:快恢复二极管",
        "ref:D pn:{diode_pn} pkg:{do_pkg} desc:TVS 瞬态抑制",
        "ref:D pn:{diode_pn} pkg:{do_pkg} desc:ESD 静电保护",
        "ref:D pn:{diode_pn} pkg:{do_pkg} desc:稳压二极管 3.3V",
        "ref:D pn:{diode_pn} pkg:{do_pkg} desc:齐纳二极管",
        "ref:D pn:{diode_pn} pkg:{do_pkg} desc:",
        "ref:D pn:{diode_pn} pkg:SOD-323 desc:小信号二极管",
        # ESD 保护器件（容易被 ML 看到 USB/HDMI 等字眼误判为 IC）
        "ref:D pn:USBLC6-2SC6 pkg:SOT-23-6 desc:USB ESD 保护",
        "ref:D pn:USBLC6-4SC6 pkg:SOT-23-6 desc:USB 4路 ESD 保护",
        "ref:D pn:ESD5Z5.0T1G pkg:SOD-523 desc:ESD 保护二极管",
        "ref:D pn:ESD9X5.0ST5G pkg:SOD-923 desc:ESD 保护",
        "ref:D pn:SRV05-4 pkg:SOT-23-6 desc:TVS 二极管阵列",
        "ref:D pn:RCLAMP0502B pkg:SC-75 desc:ESD 保护 2路",
        "ref:D pn:TPD4S012 pkg:DSON-6 desc:USB ESD 保护",
        "ref:D pn:IP4220CZ6 pkg:SOT-886 desc:USB ESD 保护",
        "ref:D pn:CM1213A-04SO pkg:SOT-23-6 desc:ESD 保护阵列",
        "ref:D pn: pkg:SOT-23-6 desc:ESD 静电保护器件",
        # LED
        "ref:D pn:{led_pn} pkg:{res_pkg} desc:发光二极管 红色",
        "ref:D pn:{led_pn} pkg:{res_pkg} desc:LED 绿色 0603",
        "ref:D pn:{led_pn} pkg:{res_pkg} desc:高亮蓝色LED",
        "ref:D pn:{led_pn} pkg:{res_pkg} desc:贴片LED 白色",
        "ref:LED pn:{led_pn} pkg:{res_pkg} desc:LED指示灯",
        "ref:LED pn:{led_pn} pkg:{res_pkg} desc:",
    ],
    "transistor": [
        "ref:Q pn:{transistor_pn} pkg:{sot_pkg} desc:NPN 三极管",
        "ref:Q pn:{transistor_pn} pkg:{sot_pkg} desc:PNP 三极管",
        "ref:Q pn:{transistor_pn} pkg:TO-92 desc:通用 NPN 晶体管",
        "ref:Q pn:{mosfet_pn} pkg:{sot_pkg} desc:N沟道 MOSFET",
        "ref:Q pn:{mosfet_pn} pkg:{sot_pkg} desc:P沟道 MOSFET",
        "ref:Q pn:{mosfet_pn} pkg:SOP-8 desc:双 N沟道 MOSFET",
        "ref:Q pn:{mosfet_pn} pkg:TO-252 desc:功率 MOSFET N沟道",
        "ref:Q pn:{mosfet_pn} pkg:DFN-5×6 desc:大电流 MOSFET",
        "ref:Q pn:{transistor_pn} pkg:{sot_pkg} desc:",
        "ref:Q pn:{mosfet_pn} pkg:{sot_pkg} desc:",
        # 三极管 (T 前缀)
        "ref:T pn:{transistor_pn} pkg:TO-92 desc:NPN 三极管",
        "ref:T pn:{mosfet_pn} pkg:{sot_pkg} desc:N沟道 MOSFET",
        # IGBT / JFET
        "ref:Q pn:IRG4BC30UD pkg:TO-220 desc:IGBT 600V",
        "ref:Q pn:J201 pkg:TO-92 desc:JFET N沟道",
    ],
    "crystal": [
        "ref:X pn:X50328MSB2GI pkg:{crystal_pkg} desc:石英晶振 {crystal_val}",
        "ref:X pn:ABS25-32.768KHZ-6-T pkg:{crystal_pkg} desc:晶振 {crystal_val}",
        "ref:Y pn:XC2016B pkg:{crystal_pkg} desc:无源晶振 {crystal_val} 20pF",
        "ref:Y pn: pkg:{crystal_pkg} desc:晶振 {crystal_val}",
        "ref:X pn: pkg:{crystal_pkg} desc:石英晶体 {crystal_val}",
        "ref:OSC pn:OT322524MJBA4SL pkg:3225-4P desc:有源晶振 {crystal_val}",
        "ref:Y pn:SIT8008BI-33-33E pkg:3225-4P desc:可编程振荡器 {crystal_val}",
        "ref:XTAL pn: pkg:{crystal_pkg} desc:晶振 {crystal_val}",
        "ref:X pn: pkg:{crystal_pkg} desc:{crystal_val}",
        "ref:X pn: pkg:{crystal_pkg} desc:",
        "ref:Y pn: pkg:{crystal_pkg} desc:",
        "ref:Y pn: pkg:3225-4P desc:陶瓷谐振器 8MHz",
    ],
    "connector": [
        # 排针/排母
        "ref:J pn:排针4P pkg:2.54mm-4P desc:排针 4P 2.54mm 直插",
        "ref:J pn:排母8P pkg:2.54mm-8P desc:排母 8P 2.54mm 直插",
        # USB / DC
        "ref:J pn:USB-C-16P pkg:USB-C-16P desc:USB Type-C 母座 16P",
        "ref:J pn:USB-Micro-5P pkg:Micro-USB-5P desc:Micro USB 母座",
        "ref:J pn:DC-005 pkg:DC-005 desc:DC 电源插座 5.5×2.1mm",
        # FPC / TF / RJ45
        "ref:J pn:FPC-24P pkg:FPC-0.5mm-24P desc:FPC 连接器 0.5mm 24P",
        "ref:J pn:TF-翻盖 pkg:TF-SMD desc:TF卡座 翻盖式",
        "ref:J pn:RJ45 pkg:RJ45-13P desc:RJ45 网口 带变压器",
        # 接线端子
        "ref:J pn:KF128-2P pkg:P=5.0mm desc:接线端子 2P 5.0mm",
        "ref:CN pn:XH2.54-2P pkg:XH-2P desc:XH2.54 接插件 2P",
        "ref:CN pn:PH2.0-4P pkg:PH-4P desc:PH2.0 连接器 4P",
        "ref:CON pn:VH3.96-2P pkg:VH-2P desc:VH3.96 电源端子 2P",
        "ref:HDR pn:排针2P pkg:2.54mm-2P desc:排针 2P",
        "ref:P pn:XT30PW pkg:XT30 desc:XT30 电源接头",
        # 开关
        "ref:SW pn:TS-1187A pkg:SMD-4×3 desc:轻触开关 4×3mm",
        "ref:K pn:SK12D07VG3 pkg:DIP-3 desc:拨动开关 SPDT",
        "ref:SW pn: pkg:DIP-6×6 desc:轻触开关 6×6mm",
        "ref:S pn: pkg:DIP-4 desc:自锁开关",
        # 继电器
        "ref:RL pn:SRD-05VDC-SL-C pkg:DIP-5 desc:继电器 5V 单刀双掷",
        "ref:K pn:G5V-1-5VDC pkg:DIP-6 desc:信号继电器 5V",
        # 保险丝
        "ref:F pn:SMD1206P050TF pkg:1206 desc:自恢复保险丝 0.5A",
        "ref:FU pn: pkg:AXIAL-0.3 desc:保险管 2A 250V",
        # 测试点/跳线
        "ref:TP pn: pkg:SMD-1 desc:测试点",
        "ref:MP pn: pkg:SMD-1 desc:测试环",
        # 无描述
        "ref:J pn:{conn_pn} pkg:2.54mm desc:",
        "ref:CN pn: pkg:XH-4P desc:接插件 4P",
        "ref:J pn: pkg:2.54mm-6P desc:排针 6P",
    ],
}


def _fill_template(template: str) -> str:
    """用随机术语填充模板中的占位符"""
    result = template
    # 按 key 长度降序替换（避免 {mcu_pn} 被 {mcu} 部分匹配）
    for key in sorted(_TERMS.keys(), key=len, reverse=True):
        if key in result:
            result = result.replace(key, random.choice(_TERMS[key]), 1)
    return result


def _expand_templates(raw_templates: dict[str, list[str]], count_per_class: int) -> list[dict]:
    """展开模板为训练样本"""
    samples: list[dict] = []

    for comp_type, templates in raw_templates.items():
        if len(templates) >= count_per_class:
            chosen = random.sample(templates, count_per_class)
            for t in chosen:
                samples.append({"text": _fill_template(t), "type": comp_type})
        else:
            for i in range(count_per_class):
                t = random.choice(templates)
                samples.append({"text": _fill_template(t), "type": comp_type})

    return samples


def generate_data(
    count_per_class: int = 60,
    output_path: str = "data/component_train.json",
    val_split: float = 0.15,
    seed: int = 42,
) -> None:
    """生成训练/验证数据

    Args:
        count_per_class: 每个类别训练样本数
        output_path: 输出路径
        val_split: 验证集比例
        seed: 随机种子
    """
    random.seed(seed)

    # 生成全量样本（保证每个类别都有足够训练样本）
    total_per_class = int(count_per_class / (1 - val_split))
    all_samples = _expand_templates(_RAW_TEMPLATES, total_per_class)

    # 按类别分层分割
    by_class: dict[str, list] = defaultdict(list)
    for s in all_samples:
        by_class[s["type"]].append(s)

    train_samples = []
    val_samples = []
    for intent, items in by_class.items():
        split_idx = int(len(items) * (1 - val_split))
        train_samples.extend(items[:split_idx])
        val_samples.extend(items[split_idx:])

    random.shuffle(train_samples)
    random.shuffle(val_samples)

    # 确保输出目录存在
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # 写入文件
    base = Path(output_path).stem
    ext = Path(output_path).suffix
    train_path = output_dir / f"{base}_train{ext}"
    val_path = output_dir / f"{base}_val{ext}"

    for path, data in [(train_path, train_samples), (val_path, val_samples)]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # 统计
    print(f"元件分类训练数据生成完成:")
    print(f"  训练集: {len(train_samples)} 条 → {train_path}")
    print(f"  验证集: {len(val_samples)} 条 → {val_path}")
    print(f"  类别分布:")
    for comp_type in sorted(by_class.keys()):
        train_cnt = sum(1 for s in train_samples if s["type"] == comp_type)
        val_cnt = sum(1 for s in val_samples if s["type"] == comp_type)
        print(f"    {comp_type:20s}  训练 {train_cnt:3d}  验证 {val_cnt:3d}")


def main():
    parser = argparse.ArgumentParser(
        description="生成 BOM 元件分类训练数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--count", type=int, default=60,
        help="每个类别的训练样本数 (default: 60, 总计约 720 条)",
    )
    parser.add_argument(
        "--output", type=str, default="data/component_train.json",
        help="输出路径 (default: data/component_train.json)",
    )
    parser.add_argument(
        "--val-split", type=float, default=0.15,
        help="验证集比例 (default: 0.15)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="随机种子 (default: 42)",
    )
    args = parser.parse_args()

    generate_data(
        count_per_class=args.count,
        output_path=args.output,
        val_split=args.val_split,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
