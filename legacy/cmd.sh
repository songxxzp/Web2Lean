python -m vllm.entrypoints.api_server \
    --model /root/Kimina-Autoformalizer-7B \
    --tensor-parallel-size 1 \
    --dtype auto \
    --port 8000 \
    --host 0.0.0.0

vllm serve /root/Kimina-Autoformalizer-7B --tensor-parallel-size 1 --port 8000 --host 0.0.0.0

git clone https://github.com/NVIDIA/Megatron-LM.git && cd Megatron-LM && pip install -e .

pip install --upgrade pip
pip install mbridge torch_memory_saver sglang
PYTHONPATH=/datadisk/Megatron-LM python tools/convert_hf_to_torch_dist.py     ${MODEL_ARGS[@]}     --hf-checkpoint /root/Qwen3-0.6B     --save /root/Qwen3-0.6B_torch_dist
