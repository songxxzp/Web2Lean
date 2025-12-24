import requests

VLLM_BASE_URL = "http://localhost:8000/v1"
MODEL_PATH = "/root/Kimina-Autoformalizer-7B"

def interactive_chat_v2():
    print("🚀 VLLM 交互式工具 (使用 /v1/chat/completions 接口)")
    
    while True:
        user_input = input("\n📝 请输入数学问题 (输入 quit 退出): ")
        if user_input.lower() in ['exit', 'quit']: break

        # 直接构造 messages 列表 (无需使用本地的 AutoTokenizer)
        messages = [
            {"role": "system", "content": "You are an expert in mathematics and Lean 4."},
            {"role": "user", "content": f"Please autoformalize the following problem in Lean 4 with a header. Use the following theorem names: my_favorite_theorem.\n\n{user_input}"}
        ]
        
        # 构造请求体
        payload = {
            "model": MODEL_PATH, 
            "messages": messages,   # <-- 直接发送消息列表
            "max_tokens": 2048,
            "temperature": 0.6
        }

        try:
            # 访问 chat/completions 路径
            response = requests.post(f"{VLLM_BASE_URL}/chat/completions", json=payload)
            response.raise_for_status() # 检查 4XX/5XX 错误
            
            res_json = response.json()
            
            # 提取 chat completions 的结果
            output_text = res_json['choices'][0]['message']['content']
            
            print("\n✨ **Lean 4 结果**:")
            print("---")
            print(output_text)
            print("---")
            
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP 错误 (请确认 Server 状态及 Model ID): {e}")
        except Exception as e:
            print(f"❌ 请求失败: {e}")

if __name__ == "__main__":
    interactive_chat_v2()