"""
calibrate.py
HX711 캘리브레이션 도구 — Raspberry Pi 에서만 실행

사용법:
    python calibrate.py

절차:
    1. 아무것도 올리지 않은 상태에서 Enter → tare(영점) 측정
    2. 알고 있는 무게(kg)를 입력하고 Enter
    3. 해당 무게를 로드셀에 올리고 Enter → scale_factor 계산
    4. calibration.json 저장
"""

import json
import time


LEFT_DOUT  = 5;  LEFT_SCK  = 6
RIGHT_DOUT = 13; RIGHT_SCK = 19
SAMPLES    = 20
OUTPUT     = "calibration.json"


def measure_mean(hx, n=SAMPLES):
    vals = []
    for _ in range(n):
        v = hx.get_raw_data_mean(times=1)
        if v is not False:
            vals.append(v)
        time.sleep(0.02)
    return sum(vals) / len(vals) if vals else 0.0


def calibrate_one(name, dout, sck):
    from hx711 import HX711

    print(f"\n{'='*40}")
    print(f"  {name} 캘리브레이션")
    print(f"{'='*40}")

    hx = HX711(dout_pin=dout, pd_sck_pin=sck)
    hx.set_reading_format("MSB", "MSB")
    hx.set_reference_unit(1)
    hx.reset()

    input(f"[{name}] 로드셀을 비워두고 Enter를 누르세요...")
    tare_offset = measure_mean(hx)
    print(f"  → tare_offset = {tare_offset:.0f}")

    known_kg = float(input(f"[{name}] 올릴 무게(kg)를 입력하세요 (예: 2.0): "))
    input(f"[{name}] {known_kg} kg 을 올리고 Enter를 누르세요...")
    loaded_val = measure_mean(hx)
    print(f"  → loaded_val  = {loaded_val:.0f}")

    scale_factor = (loaded_val - tare_offset) / known_kg
    print(f"  → scale_factor = {scale_factor:.2f}")

    return {"scale_factor": round(scale_factor, 4),
            "tare_offset":  round(tare_offset,  0)}


def main():
    try:
        from hx711 import HX711
    except ImportError:
        print("[ERROR] hx711 라이브러리 없음. pip install hx711")
        return

    result = {}
    result["left"]  = calibrate_one("왼손",  LEFT_DOUT,  LEFT_SCK)
    result["right"] = calibrate_one("오른손", RIGHT_DOUT, RIGHT_SCK)

    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✓ {OUTPUT} 저장 완료")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
