# gpt-tf2
TensorFlow 2 implementation of GTP2, with examples for fine tuning


### Setup

```
virtualenv -p /usr/bin/python3.6 venv
. venv/bin/activate

pip install -r requirements.txt
```



### Example

```
python finetune.py \
--model=355M \
--model_ckpt=/models/335M/model.ckpt \
--json_hparams=models/355M/hparams.json \
--json_encoder=models/355M/encoder.json \
--vocab_bpe=models/355M/vocab.bpe \
--dataset_path=dataset/killbill.txt \
--data_loader=text
```