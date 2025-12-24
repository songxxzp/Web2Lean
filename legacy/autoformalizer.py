from vllm import LLM, SamplingParams
from transformers import AutoTokenizer

model_name = "/root/Kimina-Autoformalizer-7B"
model = LLM(model_name)

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

problem = "The volume of a cone is given by the formula $V = \frac{1}{3}Bh$, where $B$ is the area of the base and $h$ is the height. The area of the base of a cone is 30 square units, and its height is 6.5 units. What is the number of cubic units in its volume? The answer is 65."

prompt = "Please autoformalize the following problem in Lean 4 with a header. Use the following theorem names: my_favorite_theorem.\n\n"
prompt += problem

messages = [
    {"role": "system", "content": "You are an expert in mathematics and Lean 4."},
    {"role": "user", "content": prompt}
]

text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True
)

sampling_params = SamplingParams(temperature=0.6, top_p=0.95, max_tokens=2048)
output = model.generate(text, sampling_params=sampling_params)
output_text = output[0].outputs[0].text
print(output_text)
