"""DecayDeck v4 netlist spec: the source of truth for the schematic and the board checks.

Each part: ref -> (lcsc or device key, value note, schematic block, in_bom).
Each net:  name -> list of (ref, pin), where pin is a pad number ("3") or "@NAME" (every pin with that name).
build_sch.py places the parts and draws the wires from this; verify_pcb.py checks the board against it.
"""

# Library devices that are not plain LCSC lookups.
SYSLIB = "0819f05c4eef4c71ace90d822a990e87"
DEVICES = {
    "PAD_TH": {"libraryUuid": SYSLIB, "uuid": "9aab8841b4094696bd50549098ab28ca"},  # 3.2 mm pad, 1.6 mm hole (wire pad)
}

# ref: (part, value, block, in_bom)
PARTS = {
    # --- MCU ---
    "U1": ("C2913205", "ESP32-S3-WROOM-1-N16R2", "mcu", True),
    "R22": ("C25804", "10k", "mcu", True),          # EN pull-up
    "C13": ("C15849", "1uF", "mcu", True),          # EN delay
    "C14": ("C45783", "22uF", "mcu", True),         # 3V3 bulk at module
    "C15": ("C14663", "100nF", "mcu", True),        # 3V3 HF at module
    "SW2": ("C110293", "BOOT / A", "mcu", True),    # GPIO0 user button (BOOT)
    "R23": ("C25804", "10k", "mcu", True),
    "C16": ("C14663", "100nF", "mcu", True),        # BTN_A debounce
    "SW3": ("C110293", "B", "mcu", True),
    "R24": ("C25804", "10k", "mcu", True),
    "C17": ("C14663", "100nF", "mcu", True),        # BTN_B debounce

    # --- USB-C input ---
    "J1": ("C165948", "USB-C", "usb", True),
    "R1": ("C23186", "5.1k", "usb", True),          # CC1 Rd
    "R2": ("C23186", "5.1k", "usb", True),          # CC2 Rd
    "R3": ("C25803", "100k", "usb", True),          # CC1 sense tap
    "R4": ("C25803", "100k", "usb", True),          # CC2 sense tap
    "C1": ("C1588", "1nF", "usb", True),
    "C2": ("C1588", "1nF", "usb", True),
    "U12": ("C7519", "USBLC6-2SC6", "usb", True),
    "C3": ("C1779", "4.7uF 25V", "usb", True),      # VBUS bulk at charger IN
    "C4": ("C14663", "100nF", "usb", True),

    # --- Charger + battery ---
    "U2": ("C15464", "BQ24075RGTR", "chg", True),
    "R5": ("C22764", "1.1k", "chg", True),          # ISET: 890/1100 = 0.81 A charge
    "R6": ("C22767", "1.3k", "chg", True),          # ILIM: 1610/1300 = 1.24 A input
    "R7": ("C23206", "56k", "chg", True),           # TMR: 7.5 h fast-charge timer
    "NTC1": ("C13564", "10k NTC", "chg", True),     # TS: board temp over the cell
    "C5": ("C15850", "10uF", "chg", True),          # OUT (VSYS)
    "C6": ("C15850", "10uF", "chg", True),          # BAT
    "R8": ("C4190", "2.2k", "chg", True),           # charge LED
    "LED2": ("C2286", "red", "chg", True),
    "D3": ("C124205", "BAT54WS", "chg", True),      # CHG sense isolation
    "R9": ("C25804", "10k", "chg", True),           # CHG_SNS pull-up
    "R10": ("C21190", "1k", "chg", True),           # EN2 series
    "R11": ("C25803", "100k", "chg", True),         # CHG_FAST pull-down
    "Q8": ("C8545", "2N7002", "chg", True),         # EN1 = NOT CHG_FAST
    "R12": ("C25803", "100k", "chg", True),         # EN1 pull-up to VSYS
    "Q1": ("C15127", "AO3401A", "chg", True),       # battery reverse-polarity P-FET
    "R13": ("C25804", "10k", "chg", True),          # Q1 gate to GND
    "J2": ("C295747", "BATTERY", "chg", True),
    "U4": ("C2682616", "MAX17048G+T10", "chg", True),
    "C7": ("C14663", "100nF", "chg", True),

    # --- Soft power + 3V3 buck-boost ---
    "Q2": ("C15127", "AO3401A", "pwr", True),       # VSYS -> EN when button or USB
    "R14": ("C22935", "1M", "pwr", True),           # PWR_NG pull-up
    "R15": ("C22935", "1M", "pwr", True),           # PWR_BTN_N pull-up
    "D1": ("C37704", "BAT54C", "pwr", True),        # button -> PWR_NG, button -> sense
    "SW1": ("C110293", "POWER", "pwr", True),
    "R16": ("C25803", "100k", "pwr", True),         # PWR_BTN_SNS pull-up to 3V3
    "D2": ("C37704", "BAT54C", "pwr", True),        # PWR_HOLD / Q2 -> EN
    "R17": ("C25803", "100k", "pwr", True),         # EN pull-down
    "R18": ("C25803", "100k", "pwr", True),         # PWR_HOLD pull-down
    "U3": ("C2845237", "TPS63802DLAR", "pwr", True),
    "L1": ("C18221164", "0.47uH", "pwr", True),
    "C8": ("C15850", "10uF", "pwr", True),          # buck-boost VIN
    "C9": ("C14663", "100nF", "pwr", True),
    "C10": ("C45783", "22uF", "pwr", True),         # buck-boost VOUT
    "C11": ("C45783", "22uF", "pwr", True),
    "C12": ("C14663", "100nF", "pwr", True),
    "R19": ("C23194", "511k", "pwr", True),         # FB top
    "R20": ("C23258", "88.7k", "pwr", True),        # FB bottom: 0.5 V * (1 + 511/88.7) = 3.38 V (WS2812B-2020 min 3.3 V)

    # --- HV supply: boost + doubler, comparator-gated ---
    "R21": ("C137219", "10R 1206 0.5W", "hv", True),  # 3V3 -> HV_VIN; 0.5 W so a shorted Q3 (200 mA) is survivable
    "C18": ("C96123", "47uF", "hv", True),
    "C19": ("C14663", "100nF", "hv", True),
    "L2": ("C2997659", "1mH", "hv", True),
    "Q3": ("C116737", "FMMT458TA", "hv", True),
    "R25": ("C23138", "330R", "hv", True),          # base drive
    "C20": ("C1588", "1nF", "hv", True),            # speed-up across R25
    "R26": ("C25804", "10k", "hv", True),           # base pull-down
    "U10": ("C7666", "SN74LVC1G08", "hv", True),    # HV_DRV = HV_PWM AND HV_COMP
    "C21": ("C14663", "100nF", "hv", True),
    "R27": ("C25803", "100k", "hv", True),          # HV_PWM pull-down
    "U9": ("C702117", "TLV7011", "hv", True),       # HV_COMP = HV_REF > HV_FB
    "C22": ("C14663", "100nF", "hv", True),
    "R28": ("C25803", "100k", "hv", True),          # HV_REF_PWM -> HV_REF
    "R29": ("C23242", "75k", "hv", True),           # HV_REF -> GND: ceiling 3.38*75/175*301 = 436 V (< tube max)
    "C23": ("C15849", "1uF", "hv", True),
    "D4": ("C81191", "US1M", "hv", True),           # SW -> V1
    "D5": ("C81191", "US1M", "hv", True),           # V1 -> M
    "D6": ("C81191", "US1M", "hv", True),           # M -> HV_OUT
    "C24": ("C9194", "10nF 1kV", "hv", True),       # V1 reservoir
    "C25": ("C9194", "10nF 1kV", "hv", True),       # pump cap SW -> M
    "C26": ("C426626", "10nF 2kV 1812", "hv", True),  # HV_OUT; 1812 so the 400 V pad gap is ~3 mm
    "C27": ("C426626", "10nF 2kV 1812", "hv", True),  # HV_OUT
    "D7": ("C194785", "SMAJ440A", "hv", True),      # HV clamp ~490-540 V
    "R30": ("C59781", "100M 1206", "hv", True),     # feedback divider 3x100M / 1M = 301:1
    "R31": ("C59781", "100M 1206", "hv", True),
    "R32": ("C59781", "100M 1206", "hv", True),
    "R33": ("C22935", "1M", "hv", True),
    "C28": ("C1604", "2.2nF", "hv", True),
    "R34": ("C21190", "1k", "hv", True),            # HV_FB -> ADC
    "R58": ("C163361", "47M 1206", "hv", True),     # bleeder 3x47M: HV_OUT decays in ~2 s after power-off
    "R59": ("C163361", "47M 1206", "hv", True),     # (the 301M divider alone gave tau ~ 6000 s)
    "R60": ("C163361", "47M 1206", "hv", True),

    # --- GM tubes ---
    "R35": ("C37800", "4.7M 1206", "gm", True),     # STS-5 anode 9.4 M
    "R36": ("C37800", "4.7M 1206", "gm", True),
    "J5": ("PAD_TH", "STS-5 ANODE", "gm", False),
    "J6": ("PAD_TH", "STS-5 CATHODE", "gm", False),
    "R37": ("C22961", "220k", "gm", True),          # STS-5 cathode load
    "R38": ("C21190", "1k", "gm", True),
    "C29": ("C14858", "100pF", "gm", True),         # RF filter at base
    "Q4": ("C8664", "BC847C", "gm", True),
    "R39": ("C25804", "10k", "gm", True),
    "R40": ("C26121", "2.2M 1206", "gm", True),     # SI-3BG anode 4.4 M
    "R41": ("C26121", "2.2M 1206", "gm", True),
    "J7": ("PAD_TH", "SI-3BG ANODE", "gm", False),
    "J8": ("PAD_TH", "SI-3BG CATHODE", "gm", False),
    "R42": ("C22961", "220k", "gm", True),
    "R43": ("C21190", "1k", "gm", True),
    "C30": ("C14858", "100pF", "gm", True),
    "Q5": ("C8664", "BC847C", "gm", True),
    "R44": ("C25804", "10k", "gm", True),
    "U11": ("C19829576", "74LVC2G17", "gm", True),
    "C31": ("C14663", "100nF", "gm", True),

    # --- Display (Adafruit 2090) ---
    "J3": ("C2905423", "TFT JP1 (support)", "disp", True),   # 2090 JP1: GND 1/12, Vin 2; rest = unused parallel bus
    "J4": ("C2905423", "TFT JP2 (signals)", "disp", True),
    "R45": ("C23140", "33R", "disp", True),         # SPI_SCK series
    "R46": ("C23140", "33R", "disp", True),         # SPI_MOSI series
    "R47": ("C25804", "10k", "disp", True),         # TOUCH_INT pull-up
    "R48": ("C25804", "10k", "disp", True),         # SD_CD pull-up
    "C32": ("C15850", "10uF", "disp", True),        # display supply at J4
    "C33": ("C14663", "100nF", "disp", True),

    # --- Sensors (I2C) ---
    "R49": ("C23162", "4.7k", "sens", True),        # SDA pull-up
    "R50": ("C23162", "4.7k", "sens", True),        # SCL pull-up
    "U5": ("C92489", "BME280", "sens", True),
    "C34": ("C14663", "100nF", "sens", True),
    "U6": ("C5366550", "RV-3032-C7", "sens", True),
    "C35": ("C14663", "100nF", "sens", True),
    "R51": ("C21190", "1k", "sens", True),          # VBACKUP from VBAT_P
    "C36": ("C14663", "100nF", "sens", True),
    "R52": ("C25804", "10k", "sens", True),         # RTC_INT pull-up
    "U7": ("C110926", "LIS2DH12TR", "sens", True),
    "C37": ("C14663", "100nF", "sens", True),
    "C38": ("C15850", "10uF", "sens", True),
    "U8": ("C90462", "OPT3001DNPR", "sens", True),
    "C39": ("C14663", "100nF", "sens", True),

    # --- Outputs ---
    "BZ1": ("C95298", "MLT-8540H", "out", True),   # pin 1 = +, pin 2 = -, 3/4 dummy (datasheet + symbol agree)
    "D8": ("C2128", "1N4148WS", "out", True),
    "Q6": ("C20917", "AO3400A", "out", True),
    "R53": ("C22775", "100R", "out", True),
    "R54": ("C25803", "100k", "out", True),
    "C40": ("C15850", "10uF", "out", True),
    "J9": ("PAD_TH", "MOTOR +", "out", False),
    "J10": ("PAD_TH", "MOTOR -", "out", False),
    "D9": ("C2128", "1N4148WS", "out", True),
    "Q7": ("C20917", "AO3400A", "out", True),
    "R55": ("C22775", "100R", "out", True),
    "R56": ("C25803", "100k", "out", True),
    "LED1": ("C52917434", "WS2812B-2020", "out", True),
    "R57": ("C23140", "33R", "out", True),
    "C41": ("C14663", "100nF", "out", True),
}

GND = "GND"
NETS = {
    # ---------------- power rails ----------------
    "VBUS": [("J1", "@VBUS"), ("U12", "5"), ("C3", "1"), ("C4", "1"), ("U2", "@IN")],
    "VSYS": [("U2", "@OUT"), ("C5", "1"), ("R8", "1"), ("R12", "1"), ("R14", "1"), ("R15", "1"),
             ("Q2", "@S"), ("U3", "@VIN"), ("C8", "1"), ("C9", "1")],
    "VBAT_P": [("U2", "@BAT"), ("C6", "1"), ("Q1", "@S"), ("U4", "@CELL"), ("U4", "@VDD"), ("C7", "1"),
               ("R51", "1")],
    "BAT_RAW": [("J2", "1"), ("Q1", "@D")],  # + on the right seen from the open side, as on Adafruit's Feathers
    "3V3": [("U3", "@VOUT"), ("C10", "1"), ("C11", "1"), ("C12", "1"), ("R19", "1"),
            ("U1", "@3V3"), ("C14", "1"), ("C15", "1"), ("R22", "1"), ("R23", "1"), ("R24", "1"),
            ("R9", "1"), ("R16", "1"),
            ("R21", "1"), ("U10", "@VCC"), ("C21", "1"), ("U9", "@VCC"), ("C22", "1"),
            ("R39", "1"), ("R44", "1"), ("U11", "@VCC"), ("C31", "1"),
            ("J3", "2"), ("J4", "2"), ("C32", "1"), ("C33", "1"), ("R47", "1"), ("R48", "1"),
            ("R49", "1"), ("R50", "1"), ("U5", "@VDD"), ("U5", "@VDDIO"), ("U5", "@CSB"), ("C34", "1"),
            ("U6", "@VDD"), ("C35", "1"), ("R52", "1"),
            ("U7", "@VDD"), ("U7", "@VDD_IO"), ("U7", "@CS"), ("U7", "@SDO/SA0"), ("C37", "1"), ("C38", "1"),
            ("U8", "@VDD"), ("C39", "1"),
            ("BZ1", "1"), ("D8", "@K"), ("C40", "1"), ("J9", "1"), ("D9", "@K"),
            ("LED1", "@VDD"), ("C41", "1")],
    GND: [("J1", "@GND"), ("J1", "@EH"), ("R1", "2"), ("R2", "2"), ("C1", "2"), ("C2", "2"), ("U12", "2"), ("C3", "2"), ("C4", "2"),
          ("U2", "@VSS"), ("U2", "@EP"), ("U2", "@#CE"), ("U2", "@SYSOFF"), ("R5", "2"), ("R6", "2"), ("R7", "2"),
          ("NTC1", "2"), ("C5", "2"), ("C6", "2"), ("R11", "2"), ("Q8", "@S"), ("R13", "2"), ("J2", "2"), ("J2", "3"), ("J2", "4"),
          ("U4", "@GND"), ("U4", "@CTG"), ("U4", "@QSTRT"), ("U4", "@EP"), ("C7", "2"),
          ("SW1", "2"), ("R17", "2"), ("R18", "2"),
          ("U3", "@GND"), ("U3", "@AGND"), ("U3", "@MODE"), ("C8", "2"), ("C9", "2"),
          ("C10", "2"), ("C11", "2"), ("C12", "2"), ("R20", "2"),
          ("U1", "@GND"), ("C13", "2"), ("C14", "2"), ("C15", "2"), ("SW2", "2"), ("C16", "2"), ("SW3", "2"),
          ("C17", "2"),
          ("C18", "2"), ("C19", "2"), ("Q3", "2"), ("R26", "2"), ("U10", "@GND"), ("C21", "2"), ("R27", "2"),
          ("U9", "@VEE"), ("C22", "2"), ("R29", "2"), ("C23", "2"), ("C24", "2"), ("C26", "2"), ("C27", "2"),
          ("D7", "@A"), ("R33", "2"), ("C28", "2"), ("R60", "2"),
          ("R37", "2"), ("C29", "2"), ("Q4", "2"), ("R42", "2"), ("C30", "2"), ("Q5", "2"),
          ("U11", "@GND"), ("C31", "2"),
          ("J3", "1"), ("J3", "12"), ("J4", "1"), ("J4", "11"), ("C32", "2"), ("C33", "2"),
          ("U5", "@GND"), ("U5", "@SDO"), ("C34", "2"), ("U6", "@VSS"), ("U6", "@EVI"), ("C35", "2"), ("C36", "2"),
          ("U7", "@GND"), ("U7", "@RES"), ("C37", "2"), ("C38", "2"), ("U8", "@GND"), ("U8", "@EP"), ("U8", "@ADDR"), ("C39", "2"),
          ("Q6", "@S"), ("R54", "2"), ("C40", "2"), ("Q7", "@S"), ("R56", "2"), ("LED1", "@GND"), ("C41", "2")],

    # ---------------- USB ----------------
    "CC1": [("J1", "@CC1"), ("R1", "1"), ("R3", "1")],
    "CC2": [("J1", "@CC2"), ("R2", "1"), ("R4", "1")],
    "CC1_SNS": [("R3", "2"), ("C1", "1"), ("U1", "@IO2")],
    "CC2_SNS": [("R4", "2"), ("C2", "1"), ("U1", "@IO3")],
    "USB_DP": [("J1", "@DP1"), ("J1", "@DP2"), ("U12", "3"), ("U12", "4"), ("U1", "@IO20")],
    "USB_DN": [("J1", "@DN1"), ("J1", "@DN2"), ("U12", "1"), ("U12", "6"), ("U1", "@IO19")],

    # ---------------- charger ----------------
    "BQ_ISET": [("U2", "@ISET"), ("R5", "1")],
    "BQ_ILIM": [("U2", "@ILIM"), ("R6", "1")],
    "BQ_TMR": [("U2", "@TMR"), ("R7", "1")],
    "BQ_TS": [("U2", "@TS"), ("NTC1", "1")],
    "CHG_N": [("U2", "@#CHG"), ("LED2", "@K"), ("D3", "1")],
    "CHG_LED_A": [("R8", "2"), ("LED2", "@A")],
    "CHG_SNS": [("D3", "2"), ("R9", "2"), ("U1", "@IO35")],
    "CHG_FAST": [("U1", "@IO18"), ("R10", "1"), ("R11", "1"), ("Q8", "@G")],
    "BQ_EN2": [("R10", "2"), ("U2", "@EN2")],
    "BQ_EN1": [("U2", "@EN1"), ("Q8", "@D"), ("R12", "2")],
    "Q1_G": [("Q1", "@G"), ("R13", "1")],
    "BAT_ALRT": [("U4", "@ALRT#")],

    # ---------------- soft power ----------------
    "PWR_NG": [("U2", "@#PGOOD"), ("R14", "2"), ("Q2", "@G"), ("D1", "1")],
    "PWR_BTN_N": [("D1", "3"), ("R15", "2"), ("SW1", "3")],  # SKRT pad 1 = pad 3 inside the switch: left unwired
    "PWR_BTN_SNS": [("D1", "2"), ("R16", "2"), ("U1", "@IO16")],
    "PWR_PFET": [("Q2", "@D"), ("D2", "2")],
    "PWR_HOLD": [("U1", "@IO15"), ("D2", "1"), ("R18", "1")],
    "PWR_EN": [("D2", "3"), ("R17", "1"), ("U3", "@EN")],
    "ESP_EN": [("U3", "@PG"), ("U1", "@EN"), ("R22", "2"), ("C13", "1")],
    "BB_L1": [("U3", "@L1"), ("L1", "1")],
    "BB_L2": [("U3", "@L2"), ("L1", "2")],
    "BB_FB": [("U3", "@FB"), ("R19", "2"), ("R20", "1")],

    # ---------------- MCU I/O ----------------
    "BTN_A": [("U1", "@IO0"), ("SW2", "3"), ("R23", "2"), ("C16", "1")],
    "BTN_B": [("U1", "@IO42"), ("SW3", "3"), ("R24", "2"), ("C17", "1")],

    # ---------------- HV ----------------
    "HV_VIN": [("R21", "2"), ("C18", "1"), ("C19", "1"), ("L2", "1")],
    "HV_SW": [("L2", "2"), ("Q3", "3"), ("D4", "@A"), ("C25", "1")],
    "HV_BASE": [("Q3", "1"), ("R25", "2"), ("C20", "2"), ("R26", "1")],
    "HV_DRV": [("U10", "@Y"), ("R25", "1"), ("C20", "1")],
    "HV_PWM": [("U1", "@IO6"), ("U10", "@A"), ("R27", "1")],
    "HV_COMP": [("U9", "@OUT"), ("U10", "@B")],
    "HV_REF_PWM": [("U1", "@IO7"), ("R28", "1")],
    "HV_REF": [("R28", "2"), ("R29", "1"), ("C23", "1"), ("U9", "@IN+")],
    "HV_V1": [("D4", "@K"), ("C24", "1"), ("D5", "@A")],
    "HV_M": [("C25", "2"), ("D5", "@K"), ("D6", "@A")],
    "HV_OUT": [("D6", "@K"), ("C26", "1"), ("C27", "1"), ("D7", "@K"), ("R30", "1"), ("R35", "1"), ("R40", "1"),
               ("R58", "1")],
    "HV_B1": [("R58", "2"), ("R59", "1")],
    "HV_B2": [("R59", "2"), ("R60", "1")],
    "HV_D1": [("R30", "2"), ("R31", "1")],
    "HV_D2": [("R31", "2"), ("R32", "1")],
    "HV_FB": [("R32", "2"), ("R33", "1"), ("C28", "1"), ("U9", "@IN"), ("R34", "1")],
    "HV_FB_ADC": [("R34", "2"), ("U1", "@IO1")],

    # ---------------- GM tubes ----------------
    "GM1_AM": [("R35", "2"), ("R36", "1")],
    "GM1_ANODE": [("R36", "2"), ("J5", "1")],
    "GM1_K": [("J6", "1"), ("R37", "1"), ("R38", "1")],
    "GM1_B": [("R38", "2"), ("C29", "1"), ("Q4", "1")],
    "GM1_C": [("Q4", "3"), ("R39", "2"), ("U11", "@1A")],
    "GM1_OUT": [("U11", "@1Y"), ("U1", "@IO4")],
    "GM2_AM": [("R40", "2"), ("R41", "1")],
    "GM2_ANODE": [("R41", "2"), ("J7", "1")],
    "GM2_K": [("J8", "1"), ("R42", "1"), ("R43", "1")],
    "GM2_B": [("R43", "2"), ("C30", "1"), ("Q5", "1")],
    "GM2_C": [("Q5", "3"), ("R44", "2"), ("U11", "@2A")],
    "GM2_OUT": [("U11", "@2Y"), ("U1", "@IO5")],

    # ---------------- display ----------------
    "DISP_3VO": [("J4", "3"), ("J4", "15"), ("J4", "16"), ("J4", "17")],  # IM3/IM2/IM1 high = 4-wire SPI
    "SPI_SCK": [("U1", "@IO12"), ("R45", "1")],
    "SPI_SCK_D": [("R45", "2"), ("J4", "4")],
    "SPI_MOSI": [("U1", "@IO11"), ("R46", "1")],
    "SPI_MOSI_D": [("R46", "2"), ("J4", "6")],
    "SPI_MISO": [("U1", "@IO13"), ("J4", "5")],
    "TFT_CS": [("U1", "@IO10"), ("J4", "7")],
    "TFT_DC": [("U1", "@IO14"), ("J4", "8")],
    "TFT_RST": [("U1", "@IO41"), ("J4", "9")],
    "TFT_BL": [("U1", "@IO17"), ("J4", "10")],
    "TOUCH_INT": [("U1", "@IO38"), ("J4", "12"), ("R47", "2")],
    "SD_CS": [("U1", "@IO39"), ("J4", "19")],
    "SD_CD": [("U1", "@IO40"), ("J4", "20"), ("R48", "2")],

    # ---------------- I2C + sensors ----------------
    "I2C_SDA": [("U1", "@IO36"), ("R49", "2"), ("J4", "13"), ("U4", "@SDA"), ("U5", "@SDI"), ("U6", "@SDA"),
                ("U7", "@SDA/SDI/SDO"), ("U8", "@SDA")],
    "I2C_SCL": [("U1", "@IO37"), ("R50", "2"), ("J4", "14"), ("U4", "@SCL"), ("U5", "@SCK"), ("U6", "@SCL"),
                ("U7", "@SCL/SPC"), ("U8", "@SCL")],
    "RTC_VB": [("R51", "2"), ("U6", "@VBACKUP"), ("C36", "1")],
    "RTC_INT": [("U6", "@INT#"), ("R52", "2"), ("U1", "@IO21")],
    "IMU_INT": [("U7", "@INT1"), ("U1", "@IO48")],

    # ---------------- outputs ----------------
    "BUZZER": [("U1", "@IO8"), ("R53", "1")],
    "BZ_G": [("R53", "2"), ("R54", "1"), ("Q6", "@G")],
    "BZ_DRV": [("Q6", "@D"), ("BZ1", "2"), ("D8", "@A")],
    "VIBRATE": [("U1", "@IO9"), ("R55", "1")],
    "MOT_G": [("R55", "2"), ("R56", "1"), ("Q7", "@G")],
    "MOT_DRV": [("Q7", "@D"), ("J10", "1"), ("D9", "@A")],
    "LED_DATA": [("U1", "@IO47"), ("R57", "1")],
    "LED_DIN": [("R57", "2"), ("LED1", "@DI")],
}
