import os
import argparse
import importlib


import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.callbacks import LearningRateScheduler

from src.layers import EmbeddingSim, EmbeddingRet, PositionEmbedding, LayerNormalization, _get_encoder_component, gelu, ScaledDotProductAttention, MultiHeadAttention, FeedForward
from src import encoder
from src import net
from src import utils

parser = argparse.ArgumentParser(description='Input argument parser.')

parser.add_argument('--model_dir', type=str, help='name of model')

parser.add_argument('--custom_model', type=str, help='path to custom model')

parser.add_argument('--eager', help='flag to turn on/off eager mode', action='store_true')

parser.add_argument('--dataset_path', type=str, help='path to dataset')

parser.add_argument('--num_epoch', type=int, help='number of training epochs',
                    default=4)

parser.add_argument('--base_lr', type=float, help='base learning rate',
                    default=0.001)

parser.add_argument('--decay_lr', type=float, help='learning rate decay rate',
                    default=0.1)

parser.add_argument('--decay_epochs', type=str, help='epoches to decay learning rate',
                    default='1000,10000')

parser.add_argument('--steps_per_epoch', type=int, help='number of training step for each epoch',
                    default=100)

parser.add_argument('--batch_size', type=int, help='batch size',
                    default=1)

parser.add_argument('--length', type=int, help='length of input sequence (number of tokens)',
                    default=1024)

parser.add_argument('--data_loader', type=str, help='type of dataset',
                    choices=['text', 'cnndm', 'coqa'])

parser.add_argument('--output_name', type=str, help='name of output model')

args = parser.parse_args()

#python finetune.py --model_dir=models/124M/ --output_name=touhou_124_5x10.h5 --dataset_path=dataset/touhou-nsfw.txt --data_loader=text --num_epoch=5 --decay_epochs="4,5" --steps_per_epoch=10

def main():

    if not args.model_dir:
        print('model_path must be provided')
        exit()

    if args.custom_model:
        args.model = args.custom_model
    else:
        args.model = args.model_dir + "model.ckpt"
    
    args.json_hparams = args.model_dir + "hparams.json"
    args.json_encoder = args.model_dir + "encoder.json"
    args.vocab_bpe = args.model_dir + "vocab.bpe"

    if not os.path.exists('output'):
        os.makedirs('output')

    enc = encoder.get_encoder(args.json_encoder, args.vocab_bpe)

    ds = importlib.import_module(
        "src.load_" + args.data_loader).create_dataset(
        enc, args.length, args.dataset_path, args.batch_size, args.steps_per_epoch, args.num_epoch)
        
    # Setup TensorFlow to use a distribution strategy to perform compute across multiple devices.
    strategy = tf.distribute.experimental.CentralStorageStrategy()
    with strategy.scope():
        if args.model.split('.')[-1] == 'h5':
            model = keras.models.load_model(
            args.model,
            custom_objects={'EmbeddingSim': EmbeddingSim,
                            'EmbeddingRet': EmbeddingRet,
                            'PositionEmbedding': PositionEmbedding,
                            'LayerNormalization': LayerNormalization,
                            'ScaledDotProductAttention': ScaledDotProductAttention,
                            'MultiHeadAttention': MultiHeadAttention,
                            'FeedForward': FeedForward,
                            'gelu': gelu,
                            'loss': net.loss})
        elif args.model.split('.')[-1] == 'ckpt':
            args.model_ckpt = args.model
            model = net.create_model(args)
            model = net.load_weights(model, args)
        else:
            print('Unrecognized model format')
            exit()

        model.compile(
            optimizer=keras.optimizers.Adam(),
            loss=net.loss
        )

    # fine tune
    model.fit(ds,
              epochs=args.num_epoch,
              steps_per_epoch=args.steps_per_epoch,
              callbacks=[LearningRateScheduler(net.create_schedule(args))])

    model.save(os.path.join('output', args.output_name), include_optimizer=False)

    model.evaluate(ds)

if __name__ == '__main__':
    main()
