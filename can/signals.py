# =============================================================================
# Simulated CAN DBC Signal Definitions
# =============================================================================
# A .dbc (Database CAN) file defines what messages and signals travel on the
# CAN bus. In a real car, every ECU broadcasts data on CAN — the AEB ECU
# sends brake commands, the radar sends object distance, etc.
#
# In real HIL testing, you'd open this in CANoe (Vector) or
# CANdb++ and it maps raw CAN bytes to human-readable signal values.
#
# This Python dict SIMULATES what a parsed .dbc file gives you.
# =============================================================================

CAN_SIGNALS = {

    # -------------------------------------------------------------------------
    # Message ID 0x200 — Radar Object Data (sent by Front Radar ECU)
    # This is what the ADAS ECU "sees" from the radar sensor
    # -------------------------------------------------------------------------
    "RADAR_OBJ_DISTANCE": {
        "msg_id": 0x200,
        "start_bit": 0,
        "length_bits": 12,
        "factor": 0.1,          # Raw value * 0.1 = distance in metres
        "offset": 0,
        "min": 0.0,
        "max": 200.0,
        "unit": "m",
        "description": "Distance to nearest radar target object"
    },

    "RADAR_OBJ_VELOCITY": {
        "msg_id": 0x200,
        "start_bit": 12,
        "length_bits": 12,
        "factor": 0.1,
        "offset": -100.0,       # Negative = approaching, Positive = moving away
        "min": -100.0,
        "max": 100.0,
        "unit": "m/s",
        "description": "Relative velocity of radar object"
    },

    # -------------------------------------------------------------------------
    # Message ID 0x300 — Vehicle Speed (sent by ABS/Wheel Speed ECU)
    # -------------------------------------------------------------------------
    "VEHICLE_SPEED": {
        "msg_id": 0x300,
        "start_bit": 0,
        "length_bits": 16,
        "factor": 0.01,
        "offset": 0,
        "min": 0.0,
        "max": 250.0,
        "unit": "kph",
        "description": "Current vehicle speed"
    },

    # -------------------------------------------------------------------------
    # Message ID 0x400 — AEB ECU Commands (sent by ADAS ECU)
    # This is what we're TESTING — the output of the ADAS ECU
    # -------------------------------------------------------------------------
    "AEB_BRAKE_DEMAND": {
        "msg_id": 0x400,
        "start_bit": 0,
        "length_bits": 8,
        "factor": 0.5,          # 0-100% brake demand
        "offset": 0,
        "min": 0.0,
        "max": 100.0,
        "unit": "%",
        "description": "AEB brake pressure demand to brake ECU"
    },

    "AEB_SYSTEM_STATE": {
        "msg_id": 0x400,
        "start_bit": 8,
        "length_bits": 4,
        "factor": 1,
        "offset": 0,
        "states": {
            0: "INACTIVE",
            1: "STANDBY",
            2: "WARNING",
            3: "BRAKE_PREFILL",  # Pre-charges brakes ready to fire
            4: "BRAKING",
            5: "FAULT"
        },
        "unit": "enum",
        "description": "Current AEB system state machine state"
    },

    # -------------------------------------------------------------------------
    # Message ID 0x500 — ACC ECU Commands
    # -------------------------------------------------------------------------
    "ACC_TARGET_SPEED": {
        "msg_id": 0x500,
        "start_bit": 0,
        "length_bits": 12,
        "factor": 0.1,
        "offset": 0,
        "min": 0.0,
        "max": 250.0,
        "unit": "kph",
        "description": "ACC demanded vehicle speed"
    },

    "ACC_FOLLOW_GAP": {
        "msg_id": 0x500,
        "start_bit": 12,
        "length_bits": 10,
        "factor": 0.1,
        "offset": 0,
        "min": 0.0,
        "max": 100.0,
        "unit": "m",
        "description": "ACC demanded following gap to target"
    },

    "ACC_SYSTEM_STATE": {
        "msg_id": 0x500,
        "start_bit": 22,
        "length_bits": 4,
        "factor": 1,
        "offset": 0,
        "states": {
            0: "OFF",
            1: "STANDBY",
            2: "ACTIVE",
            3: "OVERRIDE",
            4: "FAULT"
        },
        "unit": "enum",
        "description": "Current ACC system state"
    },
}
