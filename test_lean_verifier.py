from kimina_client import KiminaClient

client = KiminaClient(api_url="http://localhost:9000")

lean_code = """
import Mathlib

theorem my_favorite_theorem {B h V : ℝ}
    (hB : B = 30) (hh : h = 6.5)
    (hV : V = B * h / 3) :
    V = 65 := by
  calc
    V = B * h / 3     := by rw [hV]
    _ = 30 * h / 3    := by rw [hB]
    _ = 30 * 6.5 / 3  := by rw [hh]
    _ = 65            := by norm_num
"""

response = client.check(lean_code)

print(response)
