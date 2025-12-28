from kimina_client import KiminaClient

client = KiminaClient(api_url="http://localhost:9000")

lean_code = """
import Mathlib

theorem my_favorite_theorem {B h V : ℝ}
    (hB : B = 30) (hh : h = 6.5)
    (hV : V = B * h / 3) :
    V = 65 := by
  -- 用已知等式替换
  rw [hV, hB, hh]
  -- 计算实数算术
  norm_num
"""

response = client.check(lean_code)

print(response)
