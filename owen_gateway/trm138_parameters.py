from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModbusFixedPointLayout:
    dot_register_base: int
    value_register_base: int
    register_stride: int
    signed_value: bool


@dataclass(frozen=True, slots=True)
class Trm138ParameterSpec:
    code: str
    title_ru: str
    manual_format: str
    gateway_protocol_format: str
    gateway_modbus_data_type: str
    indexed_by: str
    has_time_mark: bool
    fixed_point_layout: ModbusFixedPointLayout | None = None


TRM138_PARAMETER_SPECS: dict[str, Trm138ParameterSpec] = {
    "rEAd": Trm138ParameterSpec(
        code="rEAd",
        title_ru="Izmerennoe znachenie kanala",
        manual_format="float32 + optional time suffix",
        gateway_protocol_format="float32",
        gateway_modbus_data_type="float32",
        indexed_by="channel address",
        has_time_mark=True,
    ),
    "C.SP": Trm138ParameterSpec(
        code="C.SP",
        title_ru="Ustavka",
        manual_format="STORED_DOT, SGND, EX, DEC_dot_u",
        gateway_protocol_format="stored_dot",
        gateway_modbus_data_type="float32",
        indexed_by="logic unit index 0..7",
        has_time_mark=False,
        fixed_point_layout=ModbusFixedPointLayout(
            dot_register_base=16,
            value_register_base=17,
            register_stride=4,
            signed_value=True,
        ),
    ),
    "HYSt": Trm138ParameterSpec(
        code="HYSt",
        title_ru="Gisterezis",
        manual_format="STORED_DOT, EX, DEC_dot_u",
        gateway_protocol_format="stored_dot",
        gateway_modbus_data_type="float32",
        indexed_by="logic unit index 0..7",
        has_time_mark=False,
        fixed_point_layout=ModbusFixedPointLayout(
            dot_register_base=48,
            value_register_base=49,
            register_stride=2,
            signed_value=False,
        ),
    ),
    "AL.t": Trm138ParameterSpec(
        code="AL.t",
        title_ru="Vyhodnaya harakteristika LU",
        manual_format="DEC_dot0, EX",
        gateway_protocol_format="uint16",
        gateway_modbus_data_type="uint16",
        indexed_by="logic unit index 0..7",
        has_time_mark=False,
    ),
}


def get_trm138_parameter_spec(parameter_name: str) -> Trm138ParameterSpec | None:
    return TRM138_PARAMETER_SPECS.get(parameter_name)
