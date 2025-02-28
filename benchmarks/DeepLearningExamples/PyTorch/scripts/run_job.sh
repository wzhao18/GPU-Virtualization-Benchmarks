#!/bin/bash

# Usage
# run.sh [resnet | gnmt] [train|infer] [comp|inst|mem|time] GPU_ID


########### Constant vars ##############
CURRENT_FOLD="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
ROOT=$CURRENT_FOLD/..
nsight=/usr/local/cuda/NsightCompute-2019.3/nv-nsight-cu-cli
nvprof=/usr/local/cuda/bin/nvprof

sec_folder="../../../../sections"
comp_sec="PertSustainedActive"
inst_sec="InstCounter"
mem_sec="Memory_Usage"


# resnet (FP32)
#--fp16 --static-loss-scale 256 
resnet_train="/opt/conda/bin/python main.py --arch resnet50 -c fanin --label-smoothing 0.1 -b 64 --training-only /dataset/imagenet --epochs 1 --profile 10 --seed 2"

#--fp16 
resnet_infer="/opt/conda/bin/python main.py --arch resnet50 --evaluate /dataset/imagenet --profile 10 --epochs 1 -b 64 --seed 2"

# gnmt (FP16)
gnmt_train="./train.py --seed 2 --train-batch-size 64 --epochs 1 --profile 10 --dataset-dir /dataset/wmt_ende"
gnmt_infer="/opt/conda/bin/python3 translate.py \
  --input /dataset/wmt_ende/newstest2014.tok.bpe.32000.en \
  --reference /dataset/wmt_ende/newstest2014.de --output /tmp/output \
  --model results/gnmt/model_best.pth --batch-size 64 \
  --beam-size 5 --math fp16 --profile 10"

########### Arg 1&2: model and task ###########
if [ $1 == "resnet" ]; then
  cd $ROOT/Classification/RN50v1.5/

  if [ $2 == "train" ]; then
    cmd=$resnet_train
  else
    cmd=$resnet_infer
  fi
else
  cd $ROOT/Translation/GNMT/

  if [ $2 == "train" ]; then
    cmd=$gnmt_train
  else
    cmd=$gnmt_infer
  fi
fi

########### Arg 3: profile metric type ###########
if [ $3 == "comp" ]; then
  section=$comp_sec
  tool="nsight"
elif [ $3 == "inst" ]; then
  section=$inst_sec
  tool="nsight"
elif [ $3 == "mem" ]; then
  section=$mem_sec
  tool="nsight"
else
  # runtime capture
  tool="nvprof"
fi

########### Arg 4: profile metric type ###########
export CUDA_VISIBLE_DEVICES=$4

########### Create profile results folder ############
# goes under profile/train or profile/infer within the model folder
mkdir -p profile
mkdir -p profile/$2

############ Kick off the run #############
if [ $tool == "nsight" ]; then
  profile="$nsight --target-processes all --section-folder $sec_folder --section $section \
    --csv -f --profile-from-start off"

  echo "Writing to profile/$2/$3.txt"
  $profile $cmd > profile/$2/$3.txt

  # sketchy way to force flush
  cat profile/$2/$3.txt > /dev/null
else
  #-o profile/$1/$2/$1-%p.nvvp
#  profile="$nvprof --profile-from-start off -f \
#     -o profile/$2/$3.nvprof"

  profile="$nvprof --profile-from-start off -f --print-gpu-trace \
    --csv --normalized-time-unit ms  --log-file profile/$2/$3.txt"


  $profile $cmd 
fi

exit

