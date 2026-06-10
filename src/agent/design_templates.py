"""
电路设计模板库 — 常见电路模式的识别与完整性检查

当用户导入 BOM 时，系统自动扫描元件型号，匹配已知电路模板，
主动提示缺失的关键元件和建议补充的电路模块。

使用方式:
    from src.agent.design_templates import DesignTemplateEngine
    engine = DesignTemplateEngine()
    matches = engine.match(bom_items)
    # → [{template: "STM32最小系统", confidence: 0.85, missing: [...], suggestions: [...]}, ...]

模板结构:
    - name: 模板名称
    - match_keywords: 触发匹配的核心元件关键词（型号前缀/关键词）
    - required: 必需元件（缺少则严重提醒）
    - recommended: 推荐元件（缺少则建议补充）
    - optional: 可选元件（锦上添花）
    - description: 模板描述
    - theory: 设计要点说明
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TemplateMatch:
    """单个模板匹配结果"""
    template_name: str
    confidence: float  # 0-1 匹配度
    matched_components: list[str]  # 已匹配的元件型号/描述
    missing_required: list[str]  # 缺失的必需元件
    missing_recommended: list[str]  # 缺失的推荐元件
    description: str
    theory: str


# ══════════════════════════════════════════════════════
#  电路模板库 — 15+ 常见电路模式
# ══════════════════════════════════════════════════════

DESIGN_TEMPLATES = [
    {
        "name": "STM32 最小系统",
        "match_keywords": ["STM32F", "STM32G", "STM32H", "STM32L", "STM32W"],
        "required": {
            "MCU 去耦电容(0.1μF)": {"电容", "capacitor", "100nF", "0.1uF", "104"},
            "复位电路(10kΩ+0.1μF)": {"复位", "reset", "10k", "RST"},
            "晶振负载电容(12~22pF×2)": {"晶振", "crystal", "XTAL", "8M", "32.768"},
            "BOOT0 配置电阻(10kΩ下拉)": {"BOOT0", "boot", "10k"},
        },
        "recommended": {
            "SWD 调试接口(4针排针)": {"SWD", "SWCLK", "SWDIO", "ST-LINK", "调试"},
            "3.3V LDO 稳压器": {"AMS1117", "LDO", "regulator", "XC6206", "ME6211", "TPS7"},
            "电源指示灯 LED+限流电阻": {"LED", "发光", "指示"},
            "VBAT 电池供电电路": {"VBAT", "电池", "battery", "BAT54C"},
        },
        "optional": {
            "USB转串口(CH340/CP2102)": {"CH340", "CP210", "FT232", "USB", "UART"},
            "外部 EEPROM(AT24C02)": {"AT24C", "24C02", "EEPROM"},
            "用户按键(K1~K3)": {"按键", "button", "switch", "SW"},
        },
        "description": "STM32 微控制器最小系统，包含供电、时钟、复位、调试四要素",
        "theory": "STM32 上电需 VDD/VDDA 稳定后才释放 RST。BOOT0 决定启动模式(Flash/System/Bootloader)。每个 VDD 引脚旁路 0.1μF 去耦。SWD(SWDIO+SWCLK)仅需2线调试。",
    },
    {
        "name": "ESP32 IoT 系统",
        "match_keywords": ["ESP32", "ESP32-S3", "ESP32-C3", "ESP32-C6"],
        "required": {
            "3.3V 稳压器(500mA+)": {"AMS1117", "LDO", "regulator", "3.3V", "3V3"},
            "去耦电容(0.1μF+10μF)": {"电容", "capacitor", "100nF", "0.1uF", "10uF"},
        },
        "recommended": {
            "EN 引脚上拉(10kΩ)": {"EN", "enable", "10k", "CHIP_PU"},
            "IO0 启动配置": {"IO0", "GPIO0", "boot"},
            "USB-UART 芯片(CH340C)": {"CH340", "CP210", "USB", "UART"},
            "自动下载电路(三极管)": {"S8050", "NPN", "EN", "IO0"},
        },
        "optional": {
            "外置天线/IPEX 连接器": {"天线", "antenna", "IPEX", "RF"},
            "锂电池充电(TP4056)": {"TP4056", "充电", "charger", "Li-ion"},
            "OLED 显示屏(SSD1306)": {"OLED", "SSD1306", "0.96", "I2C 显示"},
        },
        "description": "ESP32 物联网核心系统，含供电、启动配置、USB通信",
        "theory": "ESP32 启动需 IO0 低电平进入下载模式。EN 内部弱上拉但建议外部 10kΩ 确保稳定。WiFi 发射峰值电流可达 500mA，LDO 需足够裕量。自动下载电路用两个 NPN 实现 RTS/DTR 控制 EN+IO0。",
    },
    {
        "name": "Buck 降压电路",
        "match_keywords": ["MP", "TPS54", "TPS56", "XL40", "XL15", "SY8", "MT24", "LMR", "RT8",
                          "BUCK", "DC-DC", "降压", "开关电源"],
        "required": {
            "输入滤波电容(≥10μF)": {"10uF", "22uF", "47uF", "电解", "electrolytic"},
            "输出滤波电容(≥22μF)": {"22uF", "47uF", "100uF", "输出电容"},
            "功率电感": {"电感", "inductor", "μH", "uH", "功率电感"},
            "反馈分压电阻(R1+R2)": {"电阻", "resistor", "FB", "反馈"},
        },
        "recommended": {
            "输入 TVS 保护": {"TVS", "SMAJ", "SMBJ", "ESD"},
            "自举电容(0.1μF)": {"bootstrap", "BOOT", "自举"},
            "软启动电容": {"soft start", "SS", "软启动"},
            "使能分压电阻": {"EN", "enable", "使能"},
        },
        "optional": {
            "输出 LC 后级滤波": {"磁珠", "ferrite", "FB", "bead"},
            "电源良好指示(PG)": {"PG", "power good", "PGOOD"},
        },
        "description": "DC-DC 降压转换器完整外围电路",
        "theory": "Buck 开关回路(VIN→HS→SW→L→Cout→GND)面积决定 EMI。输入电容靠近 VIN/GND 引脚。电感选择: L=(Vout×(Vin-Vout))/(Vin×ΔIL×fsw)。自举电容为高侧 MOSFET 提供栅极驱动电压。",
    },
    {
        "name": "锂电池供电系统",
        "match_keywords": ["TP4056", "TP4057", "IP5306", "BQ", "电池", "battery", "Li-ion",
                          "充电", "charger", "18650", "锂电池", "锂电"],
        "required": {
            "充电管理 IC(TP4056等)": {"TP4056", "TP4057", "IP5306", "充电", "charger"},
            "电池保护 IC(DW01+8205)": {"DW01", "8205", "FS8205", "保护", "protection"},
            "电池电压分压器": {"电阻", "分压", "100k", "ADC", "电压检测"},
        },
        "recommended": {
            "升压 IC(5V输出,如MT3608)": {"MT3608", "FP6298", "B628", "boost", "升压", "5V"},
            "Type-C 充电接口": {"TYPE-C", "USB-C", "CC", "5.1k"},
            "电源开关(MOSFET)": {"AO3401", "PMOS", "MOSFET", "SI23"},
        },
        "optional": {
            "电量计/库仑计": {"电量", "fuel gauge", "MAX17048", "BQ27441"},
            "NTC 温度检测": {"NTC", "热敏", "温度检测", "10k"},
        },
        "description": "锂电池充放电管理系统",
        "theory": "DW01 监测过充(4.28V)/过放(2.4V)/过流，8205 双 N-MOSFET 执行切断。分压器将电池电压缩放到 ADC 量程。CC1/CC2 各接 5.1kΩ 下拉使 Type-C 适配器输出 5V。",
    },
    {
        "name": "RS485 通信接口",
        "match_keywords": ["MAX485", "SP3485", "SN65", "RS485", "RS-485", "485", "MODBUS"],
        "required": {
            "RS485 收发器(MAX485等)": {"MAX485", "SP3485", "SN65HVD", "RS485", "485"},
            "终端电阻(120Ω)": {"120Ω", "120R", "终端", "termination"},
            "偏置电阻(偏压)": {"偏置", "bias", "fail-safe", "上下拉"},
        },
        "recommended": {
            "TVS 保护(SMBJ6.8CA)": {"TVS", "SMBJ", "SMAJ", "保护", "ESD"},
            "共模扼流圈": {"共模", "CMC", "choke", "ACM"},
            "隔离电源(DC-DC 隔离)": {"B0505", "隔离", "isolation", "DC-DC"},
        },
        "optional": {
            "自恢复保险丝(PTC)": {"PTC", "自恢复", "fuse", "保险"},
            "光电隔离器": {"光耦", "optocoupler", "6N137", "HCPL"},
        },
        "description": "工业 RS485 通信接口完整保护电路",
        "theory": "RS485 差分信号(A/B)需终端 120Ω 匹配特性阻抗。失效保护偏置确保总线空闲时 RO=1。TVS 选型: Vrwm>5V, Vclamp<收发器 ABS Max(通常 12V)。隔离方案需隔离电源+隔离信号。",
    },
    {
        "name": "USB 转串口(UART)桥接",
        "match_keywords": ["CH340", "CP210", "FT232", "PL2303", "USB转串口", "USB-UART"],
        "required": {
            "USB-UART 桥接芯片": {"CH340", "CP210", "FT232", "PL2303", "USB-UART"},
            "VCC 去耦电容(0.1μF)": {"100nF", "0.1uF", "0.1μF", "104"},
            "USB D+/D- 匹配电阻": {"22Ω", "27Ω", "USB", "D+", "D-"},
        },
        "recommended": {
            "USB 接口 TVS/ESD 保护": {"TVS", "USBLC6", "SRV05", "ESD"},
            "TX/RX 指示灯 LED": {"LED", "TXD", "RXD", "指示", "灯"},
            "VCCIO 电平匹配": {"电平", "VCCIO", "3.3V", "1.8V"},
        },
        "optional": {
            "CTS/RTS 硬件流控": {"CTS", "RTS", "流控", "flow"},
            "自恢复保险丝(VBUS)": {"PTC", "fuse", "自恢复"},
        },
        "description": "USB 转串口通信桥接电路",
        "theory": "CH340 系列是最常用的国产 USB-UART 芯片。D+/D- 22Ω 串联匹配阻抗。V3 引脚需接 0.1μF 退耦。TX/RX LED 通过限流电阻接到信号线，有数据时闪烁。",
    },
    {
        "name": "H桥电机驱动",
        "match_keywords": ["L298", "L293", "DRV", "TB66", "A4950", "电机", "motor", "H桥", "PWM"],
        "required": {
            "电机驱动 IC": {"L298", "L293", "DRV88", "TB6612", "A4950", "motor driver"},
            "续流二极管(8个)": {"二极管", "diode", "1N400", "1N5819", "SS14", "续流"},
            "电源滤波电容(100μF+)": {"100uF", "220uF", "电解", "electrolytic"},
        },
        "recommended": {
            "电流采样电阻": {"采样", "shunt", "0.1Ω", "sense", "检流"},
            "光耦隔离输入": {"光耦", "PC817", "TLP", "隔离"},
            "过流保护电路": {"过流", "current limit", "保护"},
        },
        "optional": {
            "编码器接口": {"编码器", "encoder", "霍尔", "hall"},
            "电流检测放大器": {"INA", "current sense", "MAX40", "AD84"},
        },
        "description": "直流电机 H桥驱动完整方案",
        "theory": "H 桥用 4 个 MOSFET/晶体管实现电机正反转。续流二极管在开关瞬间提供电感能量泄放路径，防止击穿 MOSFET。PWM 频率通常选 10~50kHz(高于人耳20kHz听阈)。大电解吸收电机启动浪涌电流。",
    },
    {
        "name": "运放信号调理电路",
        "match_keywords": ["LM358", "LM324", "OPA", "TL07", "MCP6", "AD8", "运放", "op-amp",
                          "放大器", "信号调理"],
        "required": {
            "反馈电阻网络(Rf+Rg)": {"电阻", "resistor", "反馈", "1k", "10k", "100k"},
            "输入偏置电阻": {"电阻", "偏置", "bias", "100k", "分压"},
        },
        "recommended": {
            "输入 RC 低通滤波": {"100Ω", "1k", "100nF", "滤波", "RC"},
            "输出保护电阻(100Ω)": {"100Ω", "output", "保护"},
            "电源去耦(0.1μF+10μF)": {"100nF", "10uF", "去耦", "decoupling"},
        },
        "optional": {
            "基准电压源(TL431/REF)": {"TL431", "LM385", "REF", "基准", "VREF"},
            "轨到轨运放(低压系统)": {"MCP600", "TLV90", "rail-to-rail", "RRIO"},
        },
        "description": "运算放大器信号调理电路",
        "theory": "同相放大 Gain=1+Rf/Rg，反相放大 Gain=-Rf/Rin。输入偏置电流流经输入电阻产生偏置电压，需平衡同相/反相端阻抗。Rf 热噪声(4kTR·BW)贡献输出噪声，不宜过大(通常 1k~100kΩ)。",
    },
    {
        "name": "LED 照明/显示驱动",
        "match_keywords": ["WS2812", "SK6812", "APA102", "LED驱动", "LED driver", "恒流",
                          "LED矩阵", "灯带", "RGB LED"],
        "required": {
            "LED 驱动 IC/可寻址 LED": {"WS2812", "SK6812", "APA102", "RGB", "LED"},
            "去耦电容(100nF×每个IC)": {"100nF", "0.1uF", "104", "去耦"},
            "电源滤波(100μF+)": {"100uF", "220uF", "电解", "大电容"},
        },
        "recommended": {
            "3.3V→5V 电平转换": {"电平转换", "level shift", "SN74", "TXS01", "74LVC"},
            "电源前端保护(防反接)": {"肖特基", "PMOS", "防反接", "reverse"},
            "信号串联电阻(100Ω)": {"100Ω", "串联", "termination"},
        },
        "optional": {
            "亮度自动调节(光敏)": {"光敏", "LDR", "ALS", "BH1750"},
            "DMX512 接口": {"MAX485", "DMX", "RS485"},
        },
        "description": "可寻址 LED 照明/显示驱动系统",
        "theory": "WS2812 每像素静态电流 1mA，全亮 60mA。100 像素需要 6A@5V——电源走线必须粗(≥2mm)且在带两端供电。数据信号 5V 逻辑电平需 3.3V→5V 转换。首像素距控制器≤50cm。",
    },
    {
        "name": "CAN 总线接口",
        "match_keywords": ["CAN", "SN65HVD", "TJA", "MCP2551", "CAN总线", "CAN transceiver"],
        "required": {
            "CAN 收发器": {"SN65HVD", "TJA10", "MCP2551", "CAN", "transceiver"},
            "终端电阻(120Ω×2)": {"120Ω", "120R", "终端", "termination"},
        },
        "recommended": {
            "共模扼流圈": {"共模", "CMC", "choke", "ACM"},
            "TVS 保护(CANH/CANL)": {"TVS", "SMBJ", "NUP2105", "ESD"},
            "隔离电源+隔离CAN": {"隔离", "isolation", "ISO", "ADuM"},
        },
        "optional": {
            "CAN FD 高速收发器": {"CAN FD", "MCP2562", "TJA1044"},
            "终端电阻切换电路": {"switch", "终端切换", "120Ω"},
        },
        "description": "CAN 总线工业通信接口",
        "theory": "CAN 总线两端各需 120Ω 终端电阻(共模匹配)。隐性电平 CANH=CANL≈2.5V，显性电平 CANH≈3.5V/CANL≈1.5V。CAN FD 支持最高 8Mbps 数据段。共模扼流圈抑制共模噪声。",
    },
    {
        "name": "SD卡/TF卡 存储接口",
        "match_keywords": ["SD卡", "TF卡", "MicroSD", "SD card", "TF card", "SPI SD"],
        "required": {
            "SD卡座(MicroSD)": {"SD卡", "TF卡", "MicroSD", "卡座", "socket"},
            "上拉电阻(CMD/DAT 10kΩ)": {"10k", "上拉", "pullup", "电阻"},
            "VDD 去耦(0.1μF+10μF)": {"100nF", "10uF", "去耦"},
        },
        "recommended": {
            "电平转换器(3.3V↔MCU)": {"电平", "level shift", "74LVC", "TXS"},
            "卡检测开关电路": {"CD", "card detect", "检测", "switch"},
            "ESD 保护(TVS阵列)": {"TVS", "ESD", "保护"},
        },
        "optional": {
            "写保护检测": {"WP", "write protect", "写保护"},
            "eMMC 替代方案": {"eMMC", "MTFC"},
        },
        "description": "SD/TF 卡存储接口电路",
        "theory": "SD 卡默认 3.3V 供电。SPI 模式需 CS/SCK/MOSI/MISO 四线+上拉。CMD/DAT 线在空闲时需上拉防止浮空——SD 规范要求 10~100kΩ。热插拔会产生 ESD 瞬态，TVS 阵列保护是必要的。",
    },
    {
        "name": "WiFi/BLE 无线模块",
        "match_keywords": ["ESP-01", "ESP-12", "HC-05", "HC-08", "NRF24", "CC2541", "蓝牙",
                          "WiFi模块", "无线模块", "蓝牙模块", "ZigBee"],
        "required": {
            "3.3V 稳压供电": {"3.3V", "3V3", "LDO", "regulator"},
            "去耦电容(0.1μF+10μF)": {"100nF", "10uF", "去耦"},
        },
        "recommended": {
            "天线匹配网络": {"天线", "antenna", "IPEX", "π型匹配"},
            "UART 电平匹配(如有)": {"电平转换", "TXS", "level shift"},
            "EN/RST 控制引脚": {"EN", "RST", "reset", "enable"},
        },
        "optional": {
            "外置天线/IPEX 座": {"IPEX", "外置天线", "SMA"},
            "屏蔽罩/吸波材料": {"屏蔽", "shield", "吸波"},
        },
        "description": "WiFi/蓝牙无线通信模块接口",
        "theory": "无线模块对电源噪声敏感——LDO PSRR 需 >40dB@100kHz。天线净空区 ≥5mm 无铜皮。PCB 板载天线需匹配网络(π型，通常 C-L-C)。模块电源引脚 0.1μF+10μF 双电容去耦。",
    },
]

# ══════════════════════════════════════════════════════
#  匹配引擎
# ══════════════════════════════════════════════════════


class DesignTemplateEngine:
    """电路设计模板匹配引擎

    扫描 BOM 元件，匹配已知电路模板，主动建议缺失元件。
    """

    def __init__(self, templates: list[dict] = None):
        self.templates = templates or DESIGN_TEMPLATES

    def match(self, bom_items: list) -> list[TemplateMatch]:
        """扫描 BOM 并返回所有匹配的模板

        Args:
            bom_items: BOMItem 列表

        Returns:
            匹配到的模板列表（按 confidence 降序排列）
        """
        matches = []
        for tmpl in self.templates:
            result = self._match_template(tmpl, bom_items)
            if result and result.confidence >= 0.3:
                matches.append(result)

        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches

    def _match_template(self, tmpl: dict, bom_items: list) -> TemplateMatch:
        """将单个模板与 BOM 进行匹配"""
        # 收集所有 BOM 元件的型号和描述文本
        bom_texts = []
        for item in bom_items:
            pn = (getattr(item, "part_number", "") or "").upper()
            desc = (getattr(item, "description", "") or "").upper()
            val = (getattr(item, "value", "") or "").upper()
            bom_texts.append(f"{pn} {desc} {val}")

        # Step 1: 核心关键词匹配
        matched_kw = []
        for kw in tmpl["match_keywords"]:
            kw_upper = kw.upper()
            for i, text in enumerate(bom_texts):
                if kw_upper in text:
                    ref = getattr(bom_items[i], "reference", "?")
                    matched_kw.append(f"{ref}({kw})")
                    break

        if not matched_kw:
            return None

        # 置信度：match_keywords 是 OR 关系，命中任意一个即确认该模板
        kw_confidence = 1.0 if matched_kw else 0.0

        # Step 2: 检查必需元件
        missing_required = []
        for name, search_kws in tmpl["required"].items():
            if not self._has_any(bom_texts, search_kws):
                missing_required.append(name)

        # Step 3: 检查推荐元件
        missing_recommended = []
        for name, search_kws in tmpl["recommended"].items():
            if not self._has_any(bom_texts, search_kws):
                missing_recommended.append(name)

        # 计算最终置信度（必需元件满足度影响置信度）
        total_required = len(tmpl["required"])
        fulfilled = total_required - len(missing_required)
        req_ratio = fulfilled / max(total_required, 1)
        confidence = kw_confidence * 0.5 + req_ratio * 0.5

        return TemplateMatch(
            template_name=tmpl["name"],
            confidence=round(min(confidence, 1.0), 2),
            matched_components=matched_kw,
            missing_required=missing_required,
            missing_recommended=missing_recommended,
            description=tmpl["description"],
            theory=tmpl.get("theory", ""),
        )

    @staticmethod
    def _has_any(texts: list[str], keywords: set) -> bool:
        """检查 texts 中是否包含任意关键词"""
        for text in texts:
            for kw in keywords:
                if kw.upper() in text:
                    return True
        return False

    def get_suggestions_report(self, bom_items: list) -> str:
        """生成主动建议报告（Markdown 格式，前端渲染）

        在 BOM 加载后自动调用，展示设计意图识别结果。
        """
        matches = self.match(bom_items)
        if not matches:
            return ""

        lines = []
        for m in matches[:3]:  # 最多显示 3 个模板
            conf_pct = int(m.confidence * 100)
            icon = "HIGH" if conf_pct >= 70 else "MED" if conf_pct >= 45 else "LOW"

            lines.append(f"\n### [{icon}] {m.template_name} (匹配度 {conf_pct}%)")
            lines.append(f"\n*{m.description}*")

            if m.matched_components:
                lines.append(f"\n已识别: {', '.join(m.matched_components[:5])}")

            if m.missing_required:
                lines.append(f"\n**缺失必需元件:**")
                for item in m.missing_required:
                    lines.append(f"- {item}")

            if m.missing_recommended:
                lines.append(f"\n*建议补充:*")
                for item in m.missing_recommended[:5]:
                    lines.append(f"- {item}")

            if m.theory:
                lines.append(f"\n> {m.theory[:150]}")

        return "\n".join(lines)
