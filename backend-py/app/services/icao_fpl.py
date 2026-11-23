"""ICAO 飞行计划报文（VATSIM 风格 raw FPL）解析与生成。

报文形状（与 VATSIM my.vatsim.net 飞行计划工具一致）：

    (FPL-CPA1025-IX
    -A359/H-S/C
    -VHHH0815
    -N0492F410 V12 EPDOS L642 CN L644 MABLI N892
    -WSSS0342 WMKK
    -DOF/261128 REG/A-BCD RMK/TEST TRIP FUEL 15624 CONT 781 ALTN 1957 FINRES 1775 TAXI 357 BLOCK 20494)

字段对应：
    1  (FPL-<callsign>-<规则><飞行种类>     规则 I/V/Y/Z，种类 S/N/G/M/X
    2  -<机型>/<尾流>-<设备>[/<应答机>]
    3  -<起飞机场><起飞时刻 HHMM>
    4  -<速度><高度> <航路>                 N0492 / M082 / K0450 ；F410 / A0450 / S1130
    5  -<目的机场><预计航时 HHMM> <备降机场>
    6  -<其他情报>                          DOF/ REG/ RMK/ 等
"""
from __future__ import annotations

import re
from typing import Any

LINE_SPLIT = re.compile(r"\r?\n")
_HEAD = re.compile(
    r"^\(?\s*FPL[-/]\s*(?P<callsign>[A-Za-z0-9]{2,7})\s*-\s*(?P<rules>[IVYZX])\s*(?P<fkind>[SNGMX])\s*$",
    re.I,
)
_SPEED_LEVEL = re.compile(r"^(?P<speed>[NMK]\d{3,4})(?P<level>[FA]\d{2,4}|VFR|S\d{4})$", re.I)
_AIRPORT_TIME = re.compile(r"^(?P<apt>[A-Za-z]{4})(?P<time>\d{4})$")


# --------------------------------------------------------------------------- #
# 生成
# --------------------------------------------------------------------------- #
def _norm_speed(plan: dict[str, Any]) -> str:
    """cruiseSpeed(数字 TAS 或已是 N/M/K 前缀) → N0492 形式。"""
    raw = str(plan.get("cruiseSpeed") or "").strip().upper()
    if not raw:
        return "N0000"
    if re.fullmatch(r"[NMK]\d{3,4}", raw):
        return raw
    if raw.isdigit():
        return f"N{int(raw):04d}"
    return "N0000"


def _norm_level(plan: dict[str, Any]) -> str:
    """cruiseAlt(英尺，如 41000 / 35000 / F410) → F410 形式。"""
    raw = str(plan.get("cruiseAlt") or "").strip().upper()
    if not raw:
        return "F000"
    if re.fullmatch(r"[FA]\d{2,4}", raw):
        return raw
    if raw.isdigit():
        feet = int(raw)
        # 18000 以上按飞行高度层，以下按高度 A0xxx
        if feet >= 18000:
            return f"F{round(feet / 100):03d}"
        return f"A{feet:03d}"
    return "F000"


def _norm_time(value: Any, fallback: str = "0000") -> str:
    s = re.sub(r"\D", "", str(value or ""))
    return (s[-4:] if len(s) >= 4 else fallback).rjust(4, "0")[:4]


def _flight_type(plan: dict[str, Any]) -> str:
    return "V" if str(plan.get("flightType") or "").upper() == "VFR" else "I"


def _type_of_flight(plan: dict[str, Any]) -> str:
    raw = str(plan.get("typeOfFlight") or "S").strip().upper()
    return raw[0] if raw and raw[0] in "SNGMX" else "S"


def _aircraft_block(plan: dict[str, Any]) -> str:
    aircraft = str(plan.get("aircraft") or "").strip().upper().replace("/", "-")
    wake = str(plan.get("wakeCategory") or "").strip().upper()[:1] or "M"
    equipment = str(plan.get("equipment") or "").strip().upper() or "SDF"
    transponder = str(plan.get("transponder") or "").strip().upper()
    block = f"{aircraft or 'ZZZZ'}/{wake}-{equipment}"
    if transponder:
        block += f"/{transponder}"
    return block


def _other_info(plan: dict[str, Any], dof: str) -> str:
    parts: list[str] = []
    if dof:
        parts.append(f"DOF/{dof}")
    reg = str(plan.get("registration") or "").strip().upper()
    if reg:
        parts.append(f"REG/{reg}")
    remarks = re.sub(r"\s+", " ", str(plan.get("remarks") or "").strip().upper())
    if remarks:
        # 备注里已带 RMK/ 则原样拼接，避免重复关键字
        parts.append(remarks if remarks.startswith("RMK/") else f"RMK/{remarks}")
    return " ".join(parts)


def build(plan: dict[str, Any], *, dof: str = "") -> str:
    """把结构化字段拼成 ICAO 报文（多行，\\r\\n 分隔）。"""
    callsign = (str(plan.get("callsign") or "").strip().upper() or "N00000")[:7]
    rules = _flight_type(plan)
    fkind = _type_of_flight(plan)
    dep = str(plan.get("depIcao") or "").strip().upper()
    arr = str(plan.get("arrIcao") or "").strip().upper()
    alternate = str(plan.get("alternate") or "").strip().upper()
    route = re.sub(r"\s+", " ", str(plan.get("route") or "").strip().upper())

    lines = [
        f"(FPL-{callsign}-{rules}{fkind}",
        f"-{_aircraft_block(plan)}",
        f"-{dep}{_norm_time(plan.get('depTime'))}",
        f"-{_norm_speed(plan)}{_norm_level(plan)} {route}".rstrip(),
        f"-{arr}{_norm_time(plan.get('flightTime'))}" + (f" {alternate}" if alternate else ""),
        f"-{_other_info(plan, dof)})" if _other_info(plan, dof) else "-)",
    ]
    return "\r\n".join(lines)


# --------------------------------------------------------------------------- #
# 解析
# --------------------------------------------------------------------------- #
def _split_sections(text: str) -> list[str]:
    raw = text.strip().replace("\r\n", "\n").strip("()")
    if raw.upper().startswith("FPL-"):
        raw = raw[4:]
    return [seg.strip() for seg in re.split(r"\n\s*-|\n-", raw) if seg.strip()]


def parse(text: str) -> dict[str, Any]:
    """解析 ICAO 报文 → 结构化字段。无法识别时抛 ValueError。

    返回字段与 FlightPlan 表一致（callsign/flightType/aircraft/wakeCategory/
    equipment/transponder/depIcao/depTime/cruiseAlt/cruiseSpeed/arrIcao/
    alternate/flightTime/route/remarks/dof/registration）。
    """
    if not text or "FPL" not in text.upper():
        raise ValueError("缺少 FPL 报文头")

    sections = _split_sections(text)
    if len(sections) < 5:
        raise ValueError("报文行数不足，应为 6 行（含表头）")

    out: dict[str, Any] = {}

    head = sections[0]
    m = re.match(r"^(?P<cs>[A-Za-z0-9]{2,7})-(?P<rules>[IVYZX])(?P<fkind>[SNGMX])$", head, re.I)
    if not m:
        m2 = re.match(r"^(?P<cs>[A-Za-z0-9]{2,7})", head)
        if not m2:
            raise ValueError("第一行缺少呼号")
        out["callsign"] = m2.group("cs").upper()
        out["flightType"] = "IFR"
    else:
        out["callsign"] = m.group("cs").upper()
        out["flightType"] = "VFR" if m.group("rules").upper() == "V" else "IFR"
        out["typeOfFlight"] = m.group("fkind").upper()

    # 机型/尾流/设备/应答机
    ac = re.match(
        r"^(?P<type>[A-Za-z0-9]{2,5})/(?P<wake>[LMHJ])(?:-(?P<equip>[A-Za-z0-9/]*))?$",
        sections[1],
        re.I,
    )
    if ac:
        out["aircraft"] = ac.group("type").upper()
        out["wakeCategory"] = ac.group("wake").upper()
        equip_raw = (ac.group("equip") or "").upper()
        equip, _, transponder = equip_raw.partition("/")
        out["equipment"] = equip
        if transponder:
            out["transponder"] = transponder
    else:
        out["aircraft"] = sections[1].split("/")[0].upper()

    # 起飞机场 + 时刻
    dep = _AIRPORT_TIME.match(sections[2])
    if not dep:
        raise ValueError("第三行应为「起飞机场+起飞时刻」，如 VHHH0815")
    out["depIcao"] = dep.group("apt").upper()
    out["depTime"] = dep.group("time")

    # 速度/高度 + 航路
    speed_level = sections[3].split(" ", 1)
    sl = _SPEED_LEVEL.match(speed_level[0])
    if sl:
        spd = sl.group("speed").upper()
        lvl = sl.group("level").upper()
        digits = spd[1:]
        # 库里 cruiseSpeed 是 3 位：N0492 -> 492，M082 -> 082
        out["cruiseSpeed"] = f"{int(digits):03d}" if digits.isdigit() else digits
        if lvl.startswith("F"):
            out["cruiseAlt"] = str(int(lvl[1:]) * 100)
        elif lvl.startswith("A"):
            out["cruiseAlt"] = str(int(lvl[1:]))
        else:
            out["cruiseAlt"] = lvl
        out["route"] = (speed_level[1] if len(speed_level) > 1 else "").strip().upper()
    else:
        out["route"] = sections[3].upper()

    # 目的机场 + 航时 + 备降
    dest_parts = sections[4].split()
    dest = _AIRPORT_TIME.match(dest_parts[0]) if dest_parts else None
    if not dest:
        raise ValueError("第五行应为「目的机场+预计航时」，如 WSSS0342")
    out["arrIcao"] = dest.group("apt").upper()
    out["flightTime"] = dest.group("time")
    if len(dest_parts) > 1:
        alt = re.match(r"^([A-Za-z]{4})$", dest_parts[1])
        if alt:
            out["alternate"] = alt.group(1).upper()

    # 其他情报
    if len(sections) > 5:
        other = sections[5]
        dof = re.search(r"DOF/(\d{6})", other)
        if dof:
            out["dof"] = dof.group(1)
        reg = re.search(r"REG/([A-Za-z0-9-]+)", other)
        if reg:
            out["registration"] = reg.group(1).upper()
        rmk = re.search(r"RMK/(.*)$", other, re.S)
        if rmk:
            out["remarks"] = rmk.group(1).strip().upper()

    return out


__all__ = ["build", "parse"]
