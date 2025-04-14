# HF_HOME
export LEROBOT_RERUN_MEMORY_LIMIT=80%
python lerobot/scripts/train.py \
  --dataset.repo_id=rais/so100_test \
  --policy.type=act \
  --output_dir=outputs/train/act_so100_test \
  --job_name=act_so100_test \
  --policy.device=mps \
  --wandb.enable=true \
  --save_checkpoint=true \
  --resume=true \
  --dataset.video_backend=pyav
