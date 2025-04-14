echo "删除 HuggingFace 记录..."
# rm -rf /home/parallels/.cache/huggingface/lerobot/rais/*
rm -rf /Users/cuiluming/.cache/huggingface/lerobot/rais/eval_so100_test
echo "缓存已删除"

# '/Users/cuiluming/.cache/huggingface/lerobot/rais/eval_so100_test'
python lerobot/scripts/control_robot.py \
  --robot.type=so100 \
  --control.type=record \
  --control.fps=30 \
  --control.single_task="hello" \
  --control.repo_id=rais/eval_so100_test \
  --control.tags='["so100","中文","打招呼"]' \
  --control.warmup_time_s=5 \
  --control.episode_time_s=15 \
  --control.reset_time_s=5 \
  --control.num_episodes=10 \
  --control.push_to_hub=false \
  --control.policy.path=outputs/train/act_so100_test/checkpoints/last/pretrained_model
