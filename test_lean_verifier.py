from kimina_client import KiminaClient

client = KiminaClient(api_url="http://localhost:9000")

lean_codes = ["""
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
""",
"""import Mathlib
import Aesop
set_option maxHeartbeats 0
open BigOperators Real Nat Topology Rat
/-- The volume of a cone is given by the formula $V = \frac{1}{3}Bh$, where $B$ is the area of the base and $h$ is the height. The area of the base of a cone is 30 square units, and its height is 6.5 units. What is the number of cubic units in its volume? Show that it is 65.-/
theorem mathd_algebra_478 (b h v : ℝ) (h₀ : 0 < b ∧ 0 < h ∧ 0 < v) (h₁ : v = 1 / 3 * (b * h))
    (h₂ : b = 30) (h₃ : h = 13 / 2) : v = 65 := by"""
]

for lean_code in lean_codes:
  response = client.check(lean_code)

  print(response)

  result = response.results[0]
  resp_data = result.response
  env = resp_data.get('env', 0)
  messages_raw = resp_data.get('messages', [])

  print(f"env: {env}, messages_raw: {messages_raw}")
