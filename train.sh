python lerobot/scripts/train.py \
  --dataset.repo_id=rais/so100_test \
  --policy.type=act \
  --output_dir=outputs/train/act_so100_test \
  --job_name=act_so100_test \
  --policy.device=mps \
  --wandb.enable=true \
  --dataset.video_backend=pyav
